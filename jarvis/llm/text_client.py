"""LLM client for standalone mode with tool support."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from jarvis.config import config
from jarvis.llm.claude import get_system_prompt

logger = logging.getLogger(__name__)

# Conversation history for context
_conversation_history: list[dict] = []
MAX_HISTORY = 10  # Keep last N exchanges


def _provider_order() -> list[str]:
    mode = config.llm.auto_mode.lower()
    if mode == "latency":
        return ["openai", "claude"]
    return ["claude", "openai"]


def _parse_docstring(doc: str) -> tuple[str, dict]:
    """Parse a docstring to extract description and args."""
    if not doc:
        return "", {}

    lines = doc.strip().split("\n")
    description_lines = []
    args = {}
    current_arg = None

    in_args = False
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("args:"):
            in_args = True
            continue
        if stripped.lower().startswith(("returns:", "raises:", "example")):
            in_args = False
            continue

        if in_args:
            # Check for arg definition like "param_name: description"
            if ":" in stripped and not stripped.startswith(" "):
                parts = stripped.split(":", 1)
                current_arg = parts[0].strip()
                args[current_arg] = parts[1].strip() if len(parts) > 1 else ""
            elif current_arg and stripped:
                args[current_arg] += " " + stripped
        else:
            if stripped and not stripped.startswith("Args"):
                description_lines.append(stripped)

    return " ".join(description_lines), args


def _get_tools_for_openai() -> list[dict]:
    """Get tool definitions in OpenAI format."""
    try:
        import inspect
        from jarvis.tools import get_all_tools
        tools = get_all_tools()

        openai_tools = []
        for tool in tools:
            name = tool.__name__
            doc = tool.__doc__ or ""
            description, arg_docs = _parse_docstring(doc)

            # Get function signature
            sig = inspect.signature(tool)
            properties = {}
            required = []

            for param_name, param in sig.parameters.items():
                prop = {"type": "string"}  # Default to string

                # Try to infer type from annotation
                if param.annotation != inspect.Parameter.empty:
                    if param.annotation == int:
                        prop["type"] = "integer"
                    elif param.annotation == float:
                        prop["type"] = "number"
                    elif param.annotation == bool:
                        prop["type"] = "boolean"

                # Add description from docstring
                if param_name in arg_docs:
                    prop["description"] = arg_docs[param_name]

                properties[param_name] = prop

                # Check if required (no default value)
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)

            openai_tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": description or f"Call {name}",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                }
            })

        logger.info(f"Loaded {len(openai_tools)} tools for OpenAI")
        return openai_tools
    except Exception as e:
        logger.warning(f"Failed to load tools: {e}")
        return []


async def _execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool and return the result."""
    try:
        import asyncio
        import inspect
        from jarvis.tools import get_all_tools
        tools = get_all_tools()

        for tool in tools:
            if tool.__name__ == name:
                # Coerce argument types based on function signature
                sig = inspect.signature(tool)
                coerced_args = {}
                for param_name, param in sig.parameters.items():
                    if param_name in arguments:
                        value = arguments[param_name]
                        # Try to coerce to the expected type
                        if param.annotation != inspect.Parameter.empty:
                            try:
                                if param.annotation == int and isinstance(value, str):
                                    value = int(value)
                                elif param.annotation == float and isinstance(value, str):
                                    value = float(value)
                                elif param.annotation == bool and isinstance(value, str):
                                    value = value.lower() in ('true', '1', 'yes')
                            except (ValueError, TypeError):
                                pass
                        coerced_args[param_name] = value

                logger.info(f"Executing tool: {name}")
                if asyncio.iscoroutinefunction(tool):
                    result = await tool(**coerced_args)
                else:
                    result = tool(**coerced_args)
                logger.info(f"Tool result: {str(result)[:200]}...")
                return str(result)

        return f"Tool '{name}' not found"
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return f"Error executing tool: {e}"


async def _call_openai(prompt: str) -> Optional[str]:
    global _conversation_history

    if not config.llm.openai_api_key:
        return None

    # Build messages with history
    messages = [{"role": "system", "content": get_system_prompt()}]
    messages.extend(_conversation_history[-MAX_HISTORY:])
    messages.append({"role": "user", "content": prompt})

    tools = _get_tools_for_openai()

    payload: dict[str, Any] = {
        "model": config.llm.openai_model,
        "messages": messages,
        "temperature": config.llm.temperature,
        "max_tokens": config.llm.max_tokens,
    }
    if tools:
        payload["tools"] = tools

    headers = {"Authorization": f"Bearer {config.llm.openai_api_key}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Initial request
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        msg = data["choices"][0]["message"]

        # Handle tool calls
        while msg.get("tool_calls"):
            logger.info(f"Executing {len(msg['tool_calls'])} tool(s)...")
            messages.append(msg)

            for tool_call in msg["tool_calls"]:
                func = tool_call["function"]
                name = func["name"]
                args = json.loads(func.get("arguments", "{}"))

                logger.info(f"Tool: {name}")
                result = await _execute_tool(name, args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result,
                })

            # Get next response
            payload["messages"] = messages
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            msg = data["choices"][0]["message"]

        final_response = msg.get("content", "").strip()

        # Update history
        _conversation_history.append({"role": "user", "content": prompt})
        _conversation_history.append({"role": "assistant", "content": final_response})

        return final_response


def _get_tools_for_claude() -> list[dict]:
    """Get tool definitions in Claude format."""
    try:
        import inspect
        from jarvis.tools import get_all_tools
        tools = get_all_tools()

        claude_tools = []
        for tool in tools:
            name = tool.__name__
            doc = tool.__doc__ or ""
            description, arg_docs = _parse_docstring(doc)

            sig = inspect.signature(tool)
            properties = {}
            required = []

            for param_name, param in sig.parameters.items():
                prop = {"type": "string"}
                if param.annotation != inspect.Parameter.empty:
                    if param.annotation == int:
                        prop["type"] = "integer"
                    elif param.annotation == float:
                        prop["type"] = "number"
                    elif param.annotation == bool:
                        prop["type"] = "boolean"
                if param_name in arg_docs:
                    prop["description"] = arg_docs[param_name]
                properties[param_name] = prop
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)

            claude_tools.append({
                "name": name,
                "description": description or f"Call {name}",
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            })

        logger.info(f"Loaded {len(claude_tools)} tools for Claude")
        return claude_tools
    except Exception as e:
        logger.warning(f"Failed to load tools for Claude: {e}")
        return []


async def _call_claude(prompt: str) -> Optional[str]:
    global _conversation_history

    if not config.llm.anthropic_api_key:
        return None

    # Build messages with history
    messages = list(_conversation_history[-MAX_HISTORY:])
    messages.append({"role": "user", "content": prompt})

    tools = _get_tools_for_claude()

    payload: dict[str, Any] = {
        "model": config.llm.claude_model,
        "max_tokens": config.llm.max_tokens,
        "temperature": config.llm.temperature,
        "system": get_system_prompt(),
        "messages": messages,
    }
    if tools:
        payload["tools"] = tools

    headers = {
        "x-api-key": config.llm.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

        # Handle tool use
        while data.get("stop_reason") == "tool_use":
            content = data.get("content", [])
            messages.append({"role": "assistant", "content": content})

            tool_results = []
            for block in content:
                if block.get("type") == "tool_use":
                    name = block["name"]
                    args = block.get("input", {})

                    logger.info(f"Tool: {name}")
                    result = await _execute_tool(name, args)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})

            # Get next response
            payload["messages"] = messages
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        # Extract final text
        content = data.get("content", [])
        final_response = ""
        for block in content:
            if block.get("type") == "text":
                final_response = block.get("text", "").strip()
                break

        # Update history
        _conversation_history.append({"role": "user", "content": prompt})
        _conversation_history.append({"role": "assistant", "content": final_response})

        return final_response


def clear_history():
    """Clear conversation history."""
    global _conversation_history
    _conversation_history.clear()


async def generate_reply(prompt: str) -> str:
    """Generate a reply using the configured cloud LLMs."""
    prompt = prompt.strip()
    if not prompt:
        return "I didn't catch that. Try again."

    for provider in _provider_order():
        try:
            if provider == "openai":
                response = await _call_openai(prompt)
            else:
                response = await _call_claude(prompt)
        except Exception as exc:
            logger.warning("%s call failed: %s", provider, exc)
            continue

        if response:
            return response

    return "No LLM providers available. Check your API keys."
