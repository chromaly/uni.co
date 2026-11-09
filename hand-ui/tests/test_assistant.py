"""Offline regression checks. Never use real model, audio, or calendar services."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_assistant.assistant_core import AssistantCore
from ai_assistant import planner_reader
from ai_assistant.assistant_session import AssistantSession
from ai_assistant.planner_client import PlannerClient, PlannerAPIError
from ai_assistant.tool_registry import ToolRegistry


def response(identifier, text="", *calls):
    return SimpleNamespace(id=identifier, output_text=text, steps=list(calls))


def call(name, arguments, identifier="call-1"):
    return SimpleNamespace(type="function_call", name=name,
                           arguments=arguments, id=identifier)


class ToolLoopTests(unittest.TestCase):
    def core(self, *responses):
        core = AssistantCore.__new__(AssistantCore)
        core.client = SimpleNamespace(interactions=SimpleNamespace(
            create=Mock(side_effect=responses)))
        core.previous_interaction_id = None
        return core

    def test_schedule_result_is_returned_with_call_id(self):
        core = self.core(response("a", "", call("get_schedule", {
            "start": "2026-11-09", "end": "2026-11-10",
            "timezone": "America/Los_Angeles"})), response("b", "Your schedule"))
        lookup = Mock(return_value={"events": []})
        self.assertEqual(core.reply("Monday?", schedule_lookup=lookup), "Your schedule")
        lookup.assert_called_once()
        continuation = core.client.interactions.create.call_args.kwargs
        self.assertEqual(continuation["previous_interaction_id"], "a")
        self.assertEqual(continuation["input"][0]["call_id"], "call-1")
        self.assertEqual(core.previous_interaction_id, "b")

    def test_unknown_fields_cannot_reach_a_tool(self):
        core = self.core(response("a", "", call("get_schedule", {
            "start": "a", "end": "b", "timezone": "c", "token": "invented"})),
            response("b", "Please clarify"))
        lookup = Mock()
        core.reply("Question", schedule_lookup=lookup)
        lookup.assert_not_called()

    def test_no_argument_cancellation(self):
        core = self.core(response("a", "", call("cancel_pending_event", None)),
                         response("b", "Cancelled"))
        cancel = Mock(return_value={"status": "cancelled"})
        core.reply("Forget it", event_canceller=cancel)
        cancel.assert_called_once_with()

    def test_unknown_tool_never_executes(self):
        core = self.core(response("a", "", call("delete_everything", {})))
        with self.assertRaises(RuntimeError):
            core.reply("Question")

    def test_deadline_metadata_is_preserved(self):
        details = {"title": "Report", "date": "2026-11-10", "dueTime": "23:59",
                   "importance": "very", "notes": "Keep this", "groupName": "Classes"}
        core = self.core(response("a", "", call("propose_deadline", details)),
                         response("b", "Shall I save it?"))
        propose = Mock(return_value={"status": "needs_confirmation"})
        core.reply("Deadline", deadline_proposer=propose)
        propose.assert_called_once_with(**details)

    def test_tool_errors_do_not_claim_save_failure(self):
        core = self.core(response("a", "", call("confirm_pending_event", {})),
                         response("b", "Could not verify"))
        core.reply("Yes", event_confirmer=Mock(side_effect=TimeoutError))
        content = core.client.interactions.create.call_args.kwargs["input"][0]
        self.assertIn("outcome", content["result"][0]["text"])

    def test_tool_loop_is_bounded(self):
        responses = [response(str(n), "", call("cancel_pending_event", {}))
                     for n in range(4)]
        core = self.core(*responses)
        cancel = Mock(return_value={"status": "no_pending_draft"})
        with self.assertRaises(RuntimeError):
            core.reply("Question", event_canceller=cancel)
        self.assertEqual(cancel.call_count, 3)


class PlannerRequestTests(unittest.TestCase):
    def test_confirmation_keeps_token_out_of_body_and_disables_redirects(self):
        fake = SimpleNamespace(status_code=200, json=lambda: {"status": "saved"})
        with patch("requests.post", return_value=fake) as post, \
             patch("requests.request", return_value=fake) as request:
            result = planner_reader.confirm_event_proposal("secret", "draft-id")
            kwargs = (request if request.called else post).call_args.kwargs
        self.assertEqual(result["status"], "saved")
        self.assertEqual(kwargs["json"], {"proposalId": "draft-id"})
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret")

    def test_cancel_missing_draft_returns_false(self):
        fake = SimpleNamespace(status_code=404)
        with patch("requests.post", return_value=fake), \
             patch("requests.request", return_value=fake):
            self.assertFalse(planner_reader.cancel_event_proposal("secret", "missing"))

    def test_configurable_base_url_and_error_status(self):
        transport = Mock(return_value=SimpleNamespace(status_code=403))
        client = PlannerClient("secret", "https://example.invalid/api/", transport)
        with self.assertRaises(PlannerAPIError) as caught:
            client.get_schedule("2026-11-09", "2026-11-10", "America/Los_Angeles")
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(transport.call_args.args[1], "https://example.invalid/api/schedule")


class RegistryTests(unittest.TestCase):
    def test_nested_recurrence_is_validated_from_the_schema(self):
        handler = Mock()
        tools = ToolRegistry()
        tools.register("propose_event", handler)
        details = {"title": "Gym", "date": "2026-11-09", "startTime": "18:00",
                   "durationMinutes": 60, "recurrence": {
                       "type": "weekly", "days": ["invented-weekday"]}}
        with self.assertRaises(ValueError):
            tools.execute("propose_event", details)
        handler.assert_not_called()

    def test_boolean_is_not_a_duration(self):
        tools = ToolRegistry()
        tools.register("get_availability", Mock())
        with self.assertRaises(ValueError):
            tools.execute("get_availability", {"date": "2026-11-09", "durationMinutes": True})


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.client.propose_event.return_value = self.draft("event", "first")
        self.client.propose_deadline.return_value = self.draft("deadline", "second")
        self.assistant = Mock()
        self.session = AssistantSession(self.assistant, lambda token: self.client)

    @staticmethod
    def draft(kind, identifier):
        return {"status": "needs_confirmation", "proposalId": identifier,
                "kind": kind, kind: {"name": "Test"}, "conflicts": []}

    def turn(self, action):
        def reply(message, *, tools):
            action(message, tools)
            return "Natural spoken answer"
        self.assistant.reply.side_effect = reply
        return self.session.reply("User request", "private-token")

    def test_confirmation_is_unavailable_until_readback_completes(self):
        def propose(message, tools):
            self.assertNotIn("private-token", message)
            self.assertNotIn("confirm_pending_event", tools)
            tools.execute("propose_event", {"title": "Test", "date": "2026-11-09",
                          "startTime": "16:00", "durationMinutes": 30})
        answer = self.turn(propose)
        self.assertEqual(answer.text, "Natural spoken answer")
        self.assertEqual(answer.proposal_to_present, "first")
        self.assertIsNone(self.session.presented_proposal_id)
        self.assertIsNone(self.session._client)
        self.session.mark_presented("first")
        self.client.confirm_proposal.return_value = {"status": "saved", "saved": True}
        self.turn(lambda message, tools: tools.execute("confirm_pending_event", {}))
        self.client.confirm_proposal.assert_called_once_with("first")
        self.assertIsNone(self.session.pending_proposal)

    def test_revised_draft_cannot_use_previous_approval(self):
        self.session.pending_proposal = self.draft("event", "first")
        self.session.mark_presented("first")
        def revise(message, tools):
            tools.execute("propose_deadline", {
                "title": "Report", "date": "2026-11-09", "dueTime": "23:59"})
            result = tools.execute("confirm_pending_event", {})
            self.assertEqual(result["status"], "confirmation_required")
        reply = self.turn(revise)
        self.assertEqual(reply.proposal_to_present, "second")
        self.client.confirm_proposal.assert_not_called()

    def test_cancellation_clears_both_states(self):
        self.session.pending_proposal = self.draft("deadline", "second")
        self.session.mark_presented("second")
        self.client.cancel_proposal.return_value = True
        self.turn(lambda message, tools: tools.execute("cancel_pending_event", {}))
        self.assertIsNone(self.session.pending_proposal)
        self.assertIsNone(self.session.presented_proposal_id)

    def test_changed_conflicts_require_readback_again(self):
        self.session.pending_proposal = self.draft("event", "first")
        self.session.mark_presented("first")
        self.client.confirm_proposal.return_value = self.draft("event", "replacement")
        reply = self.turn(lambda message, tools: tools.execute("confirm_pending_event", {}))
        self.assertEqual(reply.proposal_to_present, "replacement")
        self.assertIsNone(self.session.presented_proposal_id)

    def test_failed_save_keeps_same_draft_for_retry(self):
        self.session.pending_proposal = self.draft("event", "first")
        self.session.mark_presented("first")
        self.client.confirm_proposal.side_effect = TimeoutError
        with self.assertRaises(TimeoutError):
            self.turn(lambda message, tools: tools.execute("confirm_pending_event", {}))
        self.assertEqual(self.session.pending_proposal["proposalId"], "first")
        self.assertIsNone(self.session._client)

    def test_availability_preserves_pacific_wording(self):
        self.client.get_availability.return_value = {
            "date": "2026-11-09", "timezone": "America/Los_Angeles",
            "slots": [{"start": "2026-11-09T15:00:00Z", "end": "2026-11-09T17:30:00Z"}],
        }
        def lookup(message, tools):
            result = tools.execute("get_availability", {"date": "2026-11-09"})
            self.assertEqual(result["weekday"], "Monday")
            self.assertIn("07:00 AM", result["slots"][0]["spokenRange"])
            self.assertIn("09:30 AM", result["slots"][0]["spokenRange"])
        self.turn(lookup)

    def test_interrupted_turn_does_not_retain_token(self):
        with self.assertRaises(RuntimeError):
            self.session.reply("Question", "secret", interrupted=lambda: True)
        self.assistant.reply.assert_not_called()
        self.assertIsNone(self.session._client)

    def test_note_capture_preserves_pending_event_and_deduplicates_tool_repeats(self):
        self.session.pending_proposal = self.draft("event", "first")
        self.session.mark_presented("first")
        self.client.save_note.return_value = {"status": "saved", "entryId": "note-id"}
        def save(message, tools):
            tools.execute("save_note", {"content": "Chemistry: keep my original wording."})
            tools.execute("save_note", {"content": "Chemistry: keep my original wording."})
        self.turn(save)
        calls = self.client.save_note.call_args_list
        self.assertEqual(calls[0].kwargs["request_id"], calls[1].kwargs["request_id"])
        self.assertEqual(self.session.pending_proposal["proposalId"], "first")
        self.assertEqual(self.session.presented_proposal_id, "first")

    def test_uncertain_note_retry_reuses_request_id_on_later_turn(self):
        self.client.save_note.side_effect = [TimeoutError, {"status": "saved"}]
        def save(message, tools):
            tools.execute("save_note", {"content": "Keep this thought"})
        with self.assertRaises(TimeoutError):
            self.turn(save)
        self.turn(save)
        calls = self.client.save_note.call_args_list
        self.assertEqual(calls[0].kwargs["request_id"], calls[1].kwargs["request_id"])
        self.assertEqual(self.session._uncertain_captures, {})

    def test_memory_saves_the_source_and_requires_known_id_for_changes(self):
        self.client.remember.return_value = {"status": "saved", "memoryId": "memory-id"}
        self.client.forget_memory.return_value = {"status": "forgotten"}
        def remember(message, tools):
            result = tools.execute("update_memory", {"memoryId": "invented", "content": "Changed"})
            self.assertEqual(result["status"], "search_required")
            tools.execute("remember", {"content": "Prefers evening study", "type": "preference"})
            tools.execute("forget_memory", {"memoryId": "memory-id"})
        self.turn(remember)
        self.assertEqual(self.client.remember.call_args.kwargs["source_text"], "User request")
        self.client.update_memory.assert_not_called()
        self.client.forget_memory.assert_called_once_with(memoryId="memory-id")
        self.assertEqual(self.session._source_text, "")

    def test_memory_search_allows_a_new_session_to_correct_a_record(self):
        self.client.search_memory.return_value = {"status": "ok", "results": [{"memoryId": "old-record"}]}
        self.client.update_memory.return_value = {"status": "saved"}
        def correct(message, tools):
            tools.execute("search_memory", {"query": "study"})
            tools.execute("update_memory", {"memoryId": "old-record", "content": "Prefers mornings"})
        self.turn(correct)
        self.client.update_memory.assert_called_once_with(
            memoryId="old-record", content="Prefers mornings", type=None, source_text="User request")


if __name__ == "__main__":
    unittest.main()
