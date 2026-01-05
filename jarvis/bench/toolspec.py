"""Build tool specifications for provider tool-calling."""

from __future__ import annotations

import inspect
from typing import Any, Callable, Optional, get_origin


def _json_type(annotation: Any) -> str:
    if annotation is inspect._empty:
        return "string"
    origin = get_origin(annotation)
    if origin is list:
        return "array"
    if annotation in (int,):
        return "integer"
    if annotation in (float,):
        return "number"
    if annotation in (bool,):
        return "boolean"
    if annotation in (dict,):
        return "object"
    return "string"


def tool_to_openai_spec(tool: Callable[..., Any]) -> dict[str, Any]:
    sig = inspect.signature(tool)
    props: dict[str, Any] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        if name == "self":
            continue
        props[name] = {
            "type": _json_type(param.annotation),
            "description": "",
        }
        if param.default is inspect._empty:
            required.append(name)

    return {
        "type": "function",
        "function": {
            "name": tool.__name__,
            "description": (tool.__doc__ or "").strip(),
            "parameters": {
                "type": "object",
                "properties": props,
                "required": required,
                "additionalProperties": True,
            },
        },
    }


def tool_to_anthropic_spec(tool: Callable[..., Any]) -> dict[str, Any]:
    # Anthropic tools use {name, description, input_schema}
    sig = inspect.signature(tool)
    props: dict[str, Any] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        if name == "self":
            continue
        props[name] = {"type": _json_type(param.annotation)}
        if param.default is inspect._empty:
            required.append(name)

    return {
        "name": tool.__name__,
        "description": (tool.__doc__ or "").strip(),
        "input_schema": {
            "type": "object",
            "properties": props,
            "required": required,
            "additionalProperties": True,
        },
    }

