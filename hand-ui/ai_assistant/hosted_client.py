"""Desktop transport for the hosted assistant."""

import os

import requests


class HostedAssistantClient:
    def __init__(self):
        self.base_url = os.environ.get(
            "ASSISTANT_API_URL",
            "http://127.0.0.1:8792",
        ).rstrip("/")

    def reply(self, message, token, presented_proposal_id=None):
        if not token:
            raise RuntimeError("Sign in to Planner first.")

        body = {"message": message}

        if presented_proposal_id is not None:
            body["presented_proposal_id"] = presented_proposal_id

        try:
            response = requests.post(
                f"{self.base_url}/assistant/message",
                headers={"Authorization": f"Bearer {token}"},
                json=body,
                timeout=(5, 180),
                allow_redirects=False,
            )
        except requests.RequestException:
            raise RuntimeError(
                "Could not reach the assistant. "
                "If you were saving something, check Planner "
                "before trying again."
            ) from None

        if response.status_code == 401:
            raise RuntimeError(
                "Your sign-in expired. Reconnect to Planner."
            )

        if response.status_code == 409:
            raise RuntimeError(
                "The conversation is busy or the draft changed. "
                "Ask the assistant to review the current draft."
            )

        if response.status_code != 200:
            raise RuntimeError(
                f"Assistant returned HTTP {response.status_code}. "
                "If you were saving something, check Planner "
                "before trying again."
            )

        try:
            result = response.json()
        except ValueError:
            raise RuntimeError(
                "Assistant returned an invalid response."
            ) from None

        if (
            not isinstance(result, dict)
            or not isinstance(result.get("answer"), str)
            or not result["answer"].strip()
        ):
            raise RuntimeError(
                "Assistant returned an invalid answer."
            )

        return result