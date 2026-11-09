"""Bind tool schemas to handlers and validate requests from the model."""
import json
from dataclasses import dataclass
from typing import Callable

from .tool_schemas import TOOL_SCHEMAS


def validate(value, schema, path="arguments"):
    kind = schema.get("type")
    checks = {
        "object": lambda: isinstance(value, dict),
        "array": lambda: isinstance(value, list),
        "string": lambda: isinstance(value, str),
        "integer": lambda: type(value) is int,
        "number": lambda: type(value) in (int, float),
        "boolean": lambda: type(value) is bool,
    }
    if kind in checks and not checks[kind]():
        raise ValueError(f"{path} must be {kind}.")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path} is not an allowed value.")
    if kind == "object":
        properties = schema.get("properties", {})
        if not set(schema.get("required", [])).issubset(value):
            raise ValueError(f"{path} is missing required fields.")
        if not set(value).issubset(properties):
            raise ValueError(f"{path} has unexpected fields.")
        for key, item in value.items():
            validate(item, properties[key], f"{path}.{key}")
    elif kind == "array":
        for index, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{index}]")
    if kind in ("integer", "number"):
        if "minimum" in schema and value < schema["minimum"]:
            raise ValueError(f"{path} is too small.")
        if "maximum" in schema and value > schema["maximum"]:
            raise ValueError(f"{path} is too large.")


@dataclass(frozen=True)
class BoundTool:
    schema: dict
    handler: Callable


class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, name, handler):
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = BoundTool(TOOL_SCHEMAS[name], handler)

    @property
    def schemas(self):
        return [tool.schema for tool in self._tools.values()]

    def __contains__(self, name):
        return name in self._tools

    def execute(self, name, arguments):
        tool = self._tools[name]
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        if arguments is None and not tool.schema["parameters"].get("properties"):
            arguments = {}
        validate(arguments, tool.schema["parameters"])
        print("Assistant tool:", name, flush=True)
        return tool.handler(**arguments)


# Compatibility for existing callers while new integrations use ToolRegistry.
CALLBACK_TO_TOOL = {
    "schedule_lookup": "get_schedule",
    "event_proposer": "propose_event",
    "event_canceller": "cancel_pending_event",
    "event_confirmer": "confirm_pending_event",
    "availability_lookup": "get_availability",
    "reminders_lookup": "get_reminders",
    "deadline_proposer": "propose_deadline",
}


def registry_from_callbacks(callbacks):
    registry = ToolRegistry()
    for key, handler in callbacks.items():
        if key not in CALLBACK_TO_TOOL:
            raise TypeError(f"Unknown tool callback: {key}")
        if handler is not None:
            registry.register(CALLBACK_TO_TOOL[key], handler)
    return registry
