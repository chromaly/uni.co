import logging

import firebase_admin
from firebase_admin import auth
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from ai_assistant.assistant_session import AssistantSession
from ai_assistant.tool_registry import ToolRegistry
from api_conversations import conversation_turn, ConversationBusy

firebase_app = firebase_admin.initialize_app(
    options={"projectId": "planner-io-f4953"}
)

app = FastAPI(title="Assistant API")
bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    presented_proposal_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    message: str = Field(
        min_length=1,
        max_length=4000,
    )


class ApiSession(AssistantSession):
    """Calendar reading, drafts, and confirmation of presented drafts."""

    def _tools(self):
        registry = ToolRegistry()

        registry.register("get_schedule", self.lookup_schedule)
        registry.register("get_availability", self.lookup_availability)
        registry.register("get_reminders", self.lookup_reminders)
        registry.register("propose_event", self.prepare_event)
        registry.register("cancel_pending_event", self.cancel_pending)
        
        eligible_id = self.presented_proposal_id

        if eligible_id:
            registry.register(
                "confirm_pending_event",
                lambda: self.confirm_pending(eligible_id),
            )
        return registry

def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    if credentials is None:
        raise HTTPException(401, "A Bearer token is required.")

    try:
        decoded = auth.verify_id_token(
            credentials.credentials,
            app=firebase_app,
        )
    except (auth.InvalidIdTokenError, ValueError):
        raise HTTPException(401, "Invalid or expired Firebase token.")
    except Exception:
        raise HTTPException(503, "Could not verify authentication.")

    return {
        "uid": decoded["uid"],
        "token": credentials.credentials,
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "assistant"}

@app.post("/assistant/message")
def assistant_message(
    body: MessageRequest,
    user=Depends(require_user),
):
    message = body.message.strip()

    if not message:
        raise HTTPException(400, "Message cannot be blank.")

    session = None

    try:
        with conversation_turn(user["uid"]) as conversation:
            session = ApiSession()
            session.pending_proposal = conversation["pending_proposal"]

            if body.presented_proposal_id is not None:
                pending = session.pending_proposal

                if (
                    not pending
                    or pending.get("proposalId")
                    != body.presented_proposal_id
                ):
                    raise HTTPException(
                        409,
                        "The displayed proposal is no longer current. "
                        "Review the latest draft before confirming.",
                    )

                session.mark_presented(body.presented_proposal_id)

            session.assistant.previous_interaction_id = (
                conversation["previous_interaction_id"]
            )

            reply = session.reply(message, user["token"])

            conversation["pending_proposal"] = session.pending_proposal

            conversation["previous_interaction_id"] = (
                session.assistant.previous_interaction_id
            )
            conversation["completed"] = True

            result = {
                "answer": reply.text,
                "conversation_reset": conversation["reset"],
                "pending_proposal": session.pending_proposal,
                "proposal_to_present": reply.proposal_to_present,
            }

        return result

    except ConversationBusy as error:
        raise HTTPException(409, str(error))

    except HTTPException:
        raise
    
    except Exception as error:
        safe_messages = {
            "Set GEMINI_API_KEY in your terminal first.",
            "Planner is not connected.",
            "Gemini returned no text.",
            "Assistant requested an unavailable tool.",
            "Assistant reached its calendar-tool limit.",
            "Assistant could not finish within the tool-step limit.",
        }

        detail = str(error)
        logger.error(
            "Assistant request failed: %s — %s",
            type(error).__name__,
            detail if detail in safe_messages else "Details withheld",
        )
        raise HTTPException(502, "The assistant request failed.")

    finally:
        if session is not None:
            session.assistant.client.close()