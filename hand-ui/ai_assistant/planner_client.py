"""Authenticated planner transport shared by desktop workers and assistant tools."""
import os

import requests


class PlannerAPIError(RuntimeError):
    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__(f"Planner API returned HTTP {status_code}")


class PlannerClient:
    def __init__(self, token, base_url=None, transport=None):
        self._token = token
        self.base_url = (base_url or os.environ.get(
            "PLANNER_API_URL", "http://127.0.0.1:8787"
        )).rstrip("/")
        self._transport = transport

    def _request(self, method, path, *, params=None, body=None,
                 timeout=30, allow_missing=False):
        request = self._transport or requests.request
        kwargs = {
            "headers": {"Authorization": f"Bearer {self._token}"},
            "timeout": (3, timeout), "allow_redirects": False,
        }
        if params is not None:
            kwargs["params"] = params
        if body is not None:
            kwargs["json"] = body
        response = request(method, self.base_url + path, **kwargs)
        if allow_missing and response.status_code == 404:
            return None
        if response.status_code != 200:
            raise PlannerAPIError(response.status_code)
        result = response.json()
        if not isinstance(result, dict):
            raise RuntimeError("Planner returned an invalid response.")
        return result

    @staticmethod
    def _status(result, allowed):
        if result.get("status") not in allowed:
            raise RuntimeError("Planner returned an invalid operation status.")
        return result

    def get_schedule(self, start, end, timezone):
        result = self._request("GET", "/schedule", params={
            "start": start, "end": end, "timezone": timezone})
        if not isinstance(result.get("events"), list):
            raise RuntimeError("Planner returned an invalid schedule.")
        return result

    def propose_event(self, title, date, startTime, durationMinutes,
                      location="", notes="", importance="somewhat",
                      groupName=None, color=None, recurrence=None):
        result = self._request("POST", "/event-proposals", body={
            "title": title, "date": date, "startTime": startTime,
            "durationMinutes": durationMinutes, "location": location,
            "notes": notes, "importance": importance, "groupName": groupName,
            "color": color, "recurrence": recurrence if recurrence is not None else {"type": "never"},
        })
        return self._status(result, {"needs_details", "needs_confirmation"})

    def propose_deadline(self, title, date, dueTime, importance="somewhat",
                         notes="", groupName=None, color=None):
        result = self._request("POST", "/deadline-proposals", body={
            "title": title, "date": date, "dueTime": dueTime,
            "importance": importance, "notes": notes,
            "groupName": groupName, "color": color,
        })
        return self._status(result, {"needs_details", "needs_confirmation"})

    def confirm_proposal(self, proposal_id):
        result = self._request("POST", "/event-proposals/confirm",
                               body={"proposalId": proposal_id}, timeout=45)
        return self._status(result, {"saved", "needs_confirmation", "draft_unavailable"})

    def cancel_proposal(self, proposal_id):
        result = self._request("POST", "/event-proposals/cancel",
                               body={"proposalId": proposal_id}, timeout=15,
                               allow_missing=True)
        if result is None:
            return False
        if result.get("cancelled") is not True:
            raise RuntimeError("Cancellation was not confirmed.")
        return True

    def get_availability(self, date, durationMinutes=1,
                         timezone="America/Los_Angeles", **options):
        if not set(options).issubset({"from", "to"}):
            raise ValueError("Invalid availability options.")
        result = self._request("GET", "/availability", params={
            "date": date, "durationMinutes": durationMinutes,
            "timezone": timezone, **options,
        })
        if not isinstance(result.get("slots"), list):
            raise RuntimeError("Invalid availability response.")
        return result

    def get_reminders(self, view, date=None, groupName=None, kind="both"):
        params = {"view": view, "kind": kind}
        if date is not None:
            params["date"] = date
        if groupName is not None:
            params["groupName"] = groupName
        return self._status(self._request("GET", "/reminders", params=params, timeout=45),
                            {"ok", "needs_details"})

    def save_note(self, content, request_id, date=None):
        body = {"content": content, "requestId": request_id}
        if date is not None:
            body["date"] = date
        return self._status(self._request("POST", "/notes", body=body), {"saved"})

    def search_notes(self, query="", date=None, limit=5):
        params = {"query": query, "limit": limit}
        if date is not None:
            params["date"] = date
        return self._status(self._request("GET", "/notes/search", params=params), {"ok"})

    def get_note(self, date, entryId):
        return self._status(self._request("GET", "/notes/entry", params={
            "date": date, "entryId": entryId,
        }), {"ok", "not_found"})

    def remember(self, content, type, request_id, source_text):
        return self._status(self._request("POST", "/memory", body={
            "content": content, "type": type, "requestId": request_id,
            "sourceText": source_text,
        }), {"saved"})

    def search_memory(self, query="", limit=5):
        return self._status(self._request("GET", "/memory/search", params={
            "query": query, "limit": limit,
        }), {"ok"})

    def update_memory(self, memoryId, content, source_text, type=None):
        body = {"memoryId": memoryId, "content": content, "sourceText": source_text}
        if type is not None:
            body["type"] = type
        return self._status(self._request("POST", "/memory/update", body=body), {"saved", "not_found"})

    def forget_memory(self, memoryId):
        return self._status(self._request("POST", "/memory/forget", body={
            "memoryId": memoryId,
        }), {"forgotten"})


# Backward-compatible functions for the manual reader and existing scripts.
def get_schedule(token, *args, **kwargs):
    return PlannerClient(token).get_schedule(*args, **kwargs)


def propose_event(token, *args, **kwargs):
    return PlannerClient(token).propose_event(*args, **kwargs)


def propose_deadline(token, *args, **kwargs):
    return PlannerClient(token).propose_deadline(*args, **kwargs)


def confirm_event_proposal(token, proposal_id):
    return PlannerClient(token).confirm_proposal(proposal_id)


def cancel_event_proposal(token, proposal_id):
    return PlannerClient(token).cancel_proposal(proposal_id)


def get_availability(token, *args, **kwargs):
    return PlannerClient(token).get_availability(*args, **kwargs)


def get_reminders(token, *args, **kwargs):
    return PlannerClient(token).get_reminders(*args, **kwargs)
