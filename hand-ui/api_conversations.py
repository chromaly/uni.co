from contextlib import contextmanager
import time
from urllib.parse import quote
from uuid import uuid4

from firebase_admin import firestore


class ConversationBusy(Exception):
    pass


@contextmanager
def conversation_turn(uid):
    db = firestore.client()
    ref = db.collection("_assistantConversations").document(
        quote(uid, safe="")
    )
    lease_id = str(uuid4())

    @firestore.transactional
    def acquire(transaction):
        snapshot = ref.get(transaction=transaction)
        stored = snapshot.to_dict() or {}
        now = time.time()

        if stored.get("lease_until", 0) > now:
            raise ConversationBusy(
                "Another message is still being processed."
            )

        # Bound history growth and expire inactive conversations.
        expired = (
            now - stored.get("updated_at", 0) >= 3600
            or stored.get("turns", 0) >= 20
        )

        previous = (
            None if expired
            else stored.get("interaction_id")
        )

        transaction.set(
            ref,
            {
                "lease_id": lease_id,
                "lease_until": now + 300,
            },
            merge=True,
        )

        return {
            "previous_interaction_id": previous,
            "turns": 0 if expired else stored.get("turns", 0),
            "reset": bool(
                expired and stored.get("interaction_id")
            ),
            "completed": False,
            "pending_proposal": (
                None if expired
                else stored.get("pending_proposal")
            ),
        }

    state = acquire(db.transaction())

    @firestore.transactional
    def finish(transaction):
        snapshot = ref.get(transaction=transaction)
        stored = snapshot.to_dict() or {}

        if stored.get("lease_id") != lease_id:
            raise ConversationBusy(
                "Conversation ownership changed. Please retry."
            )

        changes = {
            "lease_id": None,
            "lease_until": 0,
        }

        if state["completed"]:
            changes.update({
                "interaction_id": state["previous_interaction_id"],
                "turns": state["turns"] + 1,
                "updated_at": time.time(),
                "pending_proposal": state["pending_proposal"],
            })

        transaction.update(ref, changes)

    try:
        yield state
    finally:
        finish(db.transaction())