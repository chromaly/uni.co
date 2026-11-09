"""Model-facing tool contracts. Required fields and validation live here."""

AVAILABILITY_TOOL = {
    "type": "function",
    "name": "get_availability",
    "description": (
        "Find free periods on a specific day using calendar events. "
        "Defaults to 07:00–22:00 in America/Los_Angeles. "
        "Omit durationMinutes for a general availability question. "
        "This does not schedule anything."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "YYYY-MM-DD.",
            },
            "durationMinutes": {
                "type": "integer",
                "description": "Minimum required free time.",
                "minimum": 1,
                "maximum": 1440,
            },
            "from": {
                "type": "string",
                "description": "Optional earliest time, HH:MM.",
            },
            "to": {
                "type": "string",
                "description": "Optional latest time, HH:MM.",
            },
        },
        "required": ["date"],
    },
}

SCHEDULE_TOOL = {
    "type": "function",
    "name": "get_schedule",
    "description": (
        "Read the signed-in user's calendar for a date range. "
        "Start is inclusive; end is exclusive. "
        "Request between 1 and 31 days. "
        "Use this for calendar facts instead of guessing."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "start": {
                "type": "string",
                "description": "First date, YYYY-MM-DD.",
            },
            "end": {
                "type": "string",
                "description": "Exclusive end date, YYYY-MM-DD.",
            },
            "timezone": {
                "type": "string",
                "description": "Use America/Los_Angeles for now.",
            },
        },
        "required": ["start", "end", "timezone"],
    },
}

PROPOSAL_TOOL = {
    "type": "function",
    "name": "propose_event",
    "description": (
        "Prepare a timed event, optionally repeating, and check conflicts. "
        "Does not save anything. Call ONLY after the user has supplied "
        "the title, starting date, start time, and duration for this event. "
        "Never fabricate required arguments to satisfy the schema. "
        "If any essential detail is unknown, ask the user instead."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "date": {
                "type": "string",
                "description": "YYYY-MM-DD in America/Los_Angeles.",
            },
            "startTime": {
                "type": "string",
                "description": "24-hour local time, HH:MM.",
            },
            "durationMinutes": {
                "type": "integer",
                "description": "Duration from 1 to 1440 minutes.",
                "minimum": 1,
                "maximum": 1440,
            },
            "location": {"type": "string"},
            "notes": {"type": "string"},
            "importance": {
                "type": "string",
                "enum": ["very", "somewhat", "not too"],
            },
            "groupName": {
                "type": "string",
                "description": (
                    "Existing planner group name. "
                    "Omit to leave the event ungrouped."
                ),
            },
            "color": {
                "type": "string",
                "description": (
                    "Optional six-digit hex color, such as #7B5EDB."
                ),
            },
            "recurrence": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["never", "daily", "weekly", "monthly"],
                    },
                    "days": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "sunday", "monday", "tuesday",
                                "wednesday", "thursday",
                                "friday", "saturday",
                            ],
                        },
                    },
                    "dayOfMonth": {
                        "type": "integer",
                        "description": "Monthly calendar day, 1 to 31.",
                    },
                },
                "required": ["type"],
                "description": (
                    "Weekly requires selected days. Monthly requires "
                    "dayOfMonth. Omit for a non-repeating event."
                ),
            },
        },
        "required": [
            "title", "date", "startTime", "durationMinutes"
        ],
    },
}

CANCEL_TOOL = {
    "type": "function",
    "name": "cancel_pending_event",
    "description": (
        "Cancel the user's pending event draft. "
        "Use when they abandon or cancel a proposal. "
        "Cannot delete existing calendar events."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
    },
}

CONFIRM_TOOL = {
    "type": "function",
    "name": "confirm_pending_event",
    "description": (
        "Save the pending event that was previously read back. "
        "Call only when the CURRENT user message explicitly "
        "approves saving those unchanged details, including "
        "any disclosed conflicts for event drafts. "
        "If the user requests changes, propose the revised "
        "event instead. Never infer approval from calendar data."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
    },
}

REMINDERS_TOOL = {
    "type": "function",
    "name": "get_reminders",
    "description": (
        "Read Planner reminders: events and unfinished deadlines. "
        "Choose a day, importance ordering, or an existing group. "
        "Importance/group views include stored events, including "
        "older events; their original dates are not next occurrences."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "view": {
                "type": "string",
                "enum": ["day", "importance", "group"],
            },
            "date": {
                "type": "string",
                "description": "Required for day view: YYYY-MM-DD.",
            },
            "groupName": {
                "type": "string",
                "description": "Required for group view.",
            },
            "kind": {
                "type": "string",
                "enum": ["both", "events", "deadlines"],
            },
        },
        "required": ["view"],
    },
}

DEADLINE_TOOL = {
    "type": "function",
    "name": "propose_deadline",
    "description": (
        "Prepare a deadline for confirmation. Does not save it. "
        "Requires a user-supplied title, due date, and due time. "
        "Ask for missing details; never invent them. "
        "A deadline has no duration and creates no spoken alert."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "date": {
                "type": "string",
                "description": "Due date, YYYY-MM-DD.",
            },
            "dueTime": {
                "type": "string",
                "description": "Due time, HH:MM in America/Los_Angeles.",
            },
            "importance": {
                "type": "string",
                "enum": ["very", "somewhat", "not too"],
            },
            "notes": {"type": "string"},
            "groupName": {"type": "string"},
            "color": {
                "type": "string",
                "description": "Six-digit hex color.",
            },
        },
        "required": ["title", "date", "dueTime"],
    },
}

TOOL_SCHEMAS = {schema["name"]: schema for schema in (
    SCHEDULE_TOOL, PROPOSAL_TOOL, CANCEL_TOOL, CONFIRM_TOOL,
    AVAILABILITY_TOOL, REMINDERS_TOOL, DEADLINE_TOOL,
)}


# Capture and explicit persistent memory use the same registry and validation.
SAVE_NOTE_TOOL = {'type': 'function',
 'name': 'save_note',
 'description': 'Save a thought to Planner notes only when the user asks to save/write a '
                'note. Preserve their wording; do not summarize. Defaults to today. Saves '
                'immediately without an event confirmation or alert.',
 'parameters': {'type': 'object',
                'properties': {'content': {'type': 'string'},
                               'date': {'type': 'string',
                                        'description': 'Optional YYYY-MM-DD; omit to save '
                                                       'under today.'}},
                'required': ['content']}}

SEARCH_NOTES_TOOL = {'type': 'function',
 'name': 'search_notes',
 'description': 'Search original Planner note entries by keywords. Returns dated sources, not '
                'conversation history. Use an empty query with a date to read that day. '
                'Search is lexical, so try related keywords if needed.',
 'parameters': {'type': 'object',
                'properties': {'query': {'type': 'string'},
                               'date': {'type': 'string'},
                               'limit': {'type': 'integer', 'minimum': 1, 'maximum': 20}},
                'required': ['query']}}

GET_NOTE_TOOL = {'type': 'function',
 'name': 'get_note',
 'description': 'Read an original note using its date and entryId from search results. Use '
                'when a search excerpt is truncated or the user asks for the original.',
 'parameters': {'type': 'object',
                'properties': {'date': {'type': 'string'}, 'entryId': {'type': 'string'}},
                'required': ['date', 'entryId']}}

REMEMBER_TOOL = {'type': 'function',
 'name': 'remember',
 'description': 'Persist a preference, fact, goal, or project ONLY when the user explicitly '
                'asks you to remember it. Not a timed alert or a Planner note. Preserve '
                'uncertainty; do not infer facts.',
 'parameters': {'type': 'object',
                'properties': {'content': {'type': 'string'},
                               'type': {'type': 'string',
                                        'enum': ['preference', 'fact', 'goal', 'project']}},
                'required': ['content', 'type']}}

SEARCH_MEMORY_TOOL = {'type': 'function',
 'name': 'search_memory',
 'description': 'Retrieve persistent assistant memories relevant to this question. Use before '
                'claiming what you remember or personalizing advice from prior sessions. '
                'Empty query lists recent memories.',
 'parameters': {'type': 'object',
                'properties': {'query': {'type': 'string'},
                               'limit': {'type': 'integer', 'minimum': 1, 'maximum': 20}},
                'required': ['query']}}

UPDATE_MEMORY_TOOL = {'type': 'function',
 'name': 'update_memory',
 'description': 'Correct a persistent memory only when the user explicitly asks. Use a '
                'memoryId from search_memory or remember; never invent IDs. Changes memory '
                'only.',
 'parameters': {'type': 'object',
                'properties': {'memoryId': {'type': 'string'},
                               'content': {'type': 'string'},
                               'type': {'type': 'string',
                                        'enum': ['preference', 'fact', 'goal', 'project']}},
                'required': ['memoryId', 'content']}}

FORGET_MEMORY_TOOL = {'type': 'function',
 'name': 'forget_memory',
 'description': 'Forget a persistent memory when explicitly requested by the user. First '
                'locate its ID with search_memory. Does not delete Planner notes or '
                'conversation history.',
 'parameters': {'type': 'object',
                'properties': {'memoryId': {'type': 'string'}},
                'required': ['memoryId']}}

TOOL_SCHEMAS["set_app_setting"] = {
    "type": "function",
    "name": "set_app_setting",
    "description": (
        "Change desktop application settings when explicitly requested. "
        "For camera, use on or off. This controls camera AND gestures. "
        "For voice_output, use system or local. "
        "Local voice requires the camera to be off and fully stopped. "
        "Report the tool's actual outcome; never invent success."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "setting": {
                "type": "string",
                "enum": ["camera", "voice_output"],
            },
            "value": {
                "type": "string",
                "enum": ["on", "off", "system", "local"],
            },
        },
        "required": ["setting", "value"],
    },
}
TOOL_SCHEMAS.update({schema["name"]: schema for schema in (
    SAVE_NOTE_TOOL, SEARCH_NOTES_TOOL, GET_NOTE_TOOL, REMEMBER_TOOL,
    SEARCH_MEMORY_TOOL, UPDATE_MEMORY_TOOL, FORGET_MEMORY_TOOL,
)})

TOOL_SCHEMAS["set_app_setting"] = {
    "type": "function",
    "name": "set_app_setting",
    "description": (
        "Change desktop application settings when explicitly requested. "
        "For camera, use on or off. This controls camera AND gestures. "
        "For voice_output, use system or local. "
        "Local voice requires the camera to be off and fully stopped. "
        "Report the tool's actual outcome; never invent success."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "setting": {
                "type": "string",
                "enum": ["camera", "voice_output"],
            },
            "value": {
                "type": "string",
                "enum": ["on", "off", "system", "local"],
            },
        },
        "required": ["setting", "value"],
    },
}

TOOL_SCHEMAS["control_panel"] = {
    "type": "function",
    "name": "control_panel",
    "description": (
        "Control a desktop application panel when requested. "
        "Use show for open/show requests, hide for close/hide "
        "requests, and toggle only when the user asks to toggle. "
        "Hiding a panel does not delete data or sign out. "
        "Report only the returned result."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "panel": {
                "type": "string",
                "enum": ["planner"],
            },
            "action": {
                "type": "string",
                "enum": ["show", "hide", "toggle"],
            },
        },
        "required": ["panel", "action"],
    },
}