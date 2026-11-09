"""Bounded Gemini conversation loop; independent of Qt and planner HTTP."""
import json
import os

from google import genai
from google.genai import types

from .tool_registry import registry_from_callbacks
# Preserve the existing imports used by scripts and older integrations.
from .tool_schemas import (
    AVAILABILITY_TOOL, SCHEDULE_TOOL, PROPOSAL_TOOL, CANCEL_TOOL,
    CONFIRM_TOOL, REMINDERS_TOOL, DEADLINE_TOOL,
)


class AssistantCore:
    def __init__(self, client=None):
        if client is None:
            key = os.environ.get("GEMINI_API_KEY")
            if not key:
                raise RuntimeError("Set GEMINI_API_KEY in your terminal first.")
            client = genai.Client(
                api_key=key,
                http_options=types.HttpOptions(
                    timeout=30_000,
                    retry_options=types.HttpRetryOptions(attempts=0),
                ),
            )
        self.client = client
        self.previous_interaction_id = None

    def reply(self, message, tools=None, **callbacks):
        if tools is not None and callbacks:
            raise TypeError("Supply a tool registry or callbacks, not both.")
        registry = tools if tools is not None else registry_from_callbacks(callbacks)
        interaction_id = self.previous_interaction_id
        next_input = message
        tool_calls_used = 0

        for _ in range(4):
            response = self.client.interactions.create(
                model="gemini-3.5-flash-lite",
                input=next_input,
                previous_interaction_id=interaction_id,
                tools=registry.schemas,
            )
            interaction_id = response.id
            calls = [step for step in response.steps if step.type == "function_call"]

            if not calls:
                answer = (response.output_text or "").strip()
                if not answer:
                    raise RuntimeError("Gemini returned no text.")
                self.previous_interaction_id = interaction_id
                return answer

            results = []
            for call in calls:
                tool_calls_used += 1
                if tool_calls_used > 3:
                    raise RuntimeError("Assistant reached its calendar-tool limit.")
                if call.name not in registry:
                    raise RuntimeError("Assistant requested an unavailable tool.")
                try:
                    result = registry.execute(call.name, call.arguments)
                except (ValueError, TypeError):
                    result = {"error": "Invalid tool arguments. Check the requested fields."}
                except Exception as error:
                    # Never print credentials, request bodies, or raw SDK errors.
                    status = getattr(error, "status_code", None)
                    detail = f", HTTP {status}" if isinstance(status, int) else ""
                    print(f"Assistant tool failed: {call.name} ({type(error).__name__}{detail})", flush=True)
                    result = {"error": (
                        "Could not verify the operation's outcome. "
                        "Do not claim it succeeded or failed. "
                        "For a save, retry the same pending proposal "
                        "rather than creating another."
                    )}
                results.append({
                    "type": "function_result", "name": call.name,
                    "call_id": call.id,
                    "result": [{"type": "text", "text": json.dumps(result)}],
                })
            next_input = results

        raise RuntimeError("Assistant could not finish within the tool-step limit.")