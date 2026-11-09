# Assistant structure

The desktop flow is:

`voice_worker → assistant_session → assistant_core → tool_registry → planner_client`

| Module | Responsibility |
| --- | --- |
| `voice_worker.py` | Qt signals, microphone/transcription lifecycle, playback, interruption |
| `assistant_session.py` | One conversation's tools, pending draft, and confirmation eligibility |
| `assistant_core.py` | Gemini requests and the bounded tool-result loop |
| `tool_schemas.py` | Model-facing tool names, fields, required fields, and constraints |
| `tool_registry.py` | Bind handlers and validate arguments against those schemas |
| `planner_client.py` | All authenticated planner HTTP requests and response validation |
| `planner_reader.py` | Qt adapter for the manual planner shortcut; old function imports still work |
| `prompts.py` | Conversational instructions |

Add a tool's schema in `tool_schemas.py` and bind its handler in
`AssistantSession._tools()`. Required/optional fields are read from the schema;
there is no second argument allow-list to update. Backend operations belong in
`planner_client.py`, not inside the Qt worker.

The planner backend has a corresponding division:

- `index.mjs` starts the server and connects Firebase Authentication.
- `app.mjs` authenticates requests and dispatches the route table.
- `routes.mjs` registers each endpoint once, including whether it needs JSON.
- `http.mjs` handles JSON requests and responses.
- `firestore.mjs` handles transport, pagination, encoding, and create-once writes.
- Feature modules own schedule, availability, reminders, and validation.
- `pendingProposals.mjs` owns draft expiry, ownership, cancellation, and save receipts.
- `proposalActions.mjs` implements event/deadline-specific refresh and save operations.

Existing endpoints and tool names are preserved. In particular, the legacy
`confirm_pending_event` and `cancel_pending_event` tools also handle deadline
drafts. Approval becomes available on a later turn only after playback finishes.
Revising a draft invalidates its previous approval; failed saves retain the
same draft for a safe retry.

## Development and tests

From the uni.co root:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s hand-ui/tests -v
node --test hand-ui/tests/backend.test.mjs hand-ui/tests/capture.test.mjs
```

Backend tests expect planner.io beside uni.co under the same Projects directory.
All service calls and writes are mocked; tests do not need keys, audio hardware,
or a running server.

From planner.io, the existing server startup command still works:

```sh
TZ=America/Los_Angeles node src/server/index.mjs
```

`PLANNER_API_URL` optionally changes the Python client's server address.
The Node server supports `HOST` and `PORT`; defaults remain `127.0.0.1:8787`.
These settings prepare deployment configuration, not a deployed phone service.
The proposal store remains in memory, timezone support remains limited, and
existing calendar-calculation limitations are unchanged.

The terminal voice loop and TTS experiment scripts are separate from the desktop
path and remain available. They were not converted to calendar-enabled sessions.

## Notes and explicit memory

- `save_note` appends an entry to `users/{uid}/notes/{date}`. Content is preserved,
  topic starts as null, and existing categorization remains optional.
- `search_notes` returns dated source entries. `get_note` retrieves an original
  entry when the search excerpt is truncated. Search is keyword-based, not embeddings.
- `remember`, `search_memory`, `update_memory`, and `forget_memory` use
  `users/{uid}/assistantMemories/{id}`. These records are separate from Planner notes.
- Memory capture is explicit. Automatic memory extraction, saved full conversation
  history, proactive alerts, and automatic note-panel navigation are not implemented.
- Capture request IDs are supplied by the application, not Gemini. Retries of the
  same request do not append duplicate entries. Uncertain request IDs are retained
  for the current app session; a restart loses those retry IDs.
- Notes and memories require no event approval step after an explicit capture request.
  They do not replace or approve any pending event/deadline proposal.

Restart Node and Python after these changes. The website's concurrent-edit protection
requires rebuilding and deploying Planner to GitHub Pages; it is not deployed by
the test/build commands. Until deployed, an old website tab still uses the old save
behavior. Reload it after deployment before testing simultaneous voice/browser edits.

The new memory collection must be permitted by your existing Firestore rules. See
[memory-access.md](memory-access.md) for a narrowly scoped rule example. No rules
were deployed or changed automatically, and no live account records were written
by the regression tests. Searches currently scan bounded collections, so reads
grow with the amount of stored data; use indexed search when this outgrows a prototype.

Suggested manual checks:

1. "Save this in my notes: I keep mixing up equilibrium and reaction rates."
2. "Did I write anything about chemistry?" Ask for the original if a result is truncated.
3. "Remember that I prefer studying after dinner."
4. Restart Python and ask "What study preference do you remember?"
5. "Actually, remember that I prefer mornings instead."
6. "Forget my study-time preference."

Memory must be searchable through a tool after restart; the model's old conversation
alone is not proof that the record was stored or forgotten.
