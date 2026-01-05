"""Interactive benchmark runner."""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from jarvis.audit import append_event
from jarvis.config import config
from jarvis.llm.claude import get_system_prompt
from jarvis.tools import get_all_tools

from .providers import ModelResponse, ProviderError, get_provider
from .scenarios import Scenario, get_scenarios
from .toolspec import tool_to_anthropic_spec, tool_to_openai_spec

BENCH_SYSTEM_APPENDIX = """
You are being evaluated in a benchmark harness.

Rules:
- Prefer calling tools over asking questions.
- Assume the repository root is the current working directory, so use path='.' unless otherwise specified.
- Do not ask the user for the repo path unless explicitly required.
- If a tool supports a `confirm` parameter and you need to proceed, ask the user for confirmation first.
- If tools are provided and a tool is clearly relevant, call it with sensible defaults instead of asking clarifying questions.
- Keep responses concise and voice-friendly.
""".strip()

SCORING_RUBRIC = """
Scoring rubric (1-5):
1 = wrong/no tool use when required, unsafe, or unhelpful
2 = partially correct but missed tools or made mistakes
3 = acceptable, minor issues
4 = good, correct tool use, clear
5 = excellent: correct, fast, minimal, robust tool use
""".strip()

AUTO_JUDGE_PROMPT = """
You are an expert evaluator for a voice assistant benchmark.

## Task
Evaluate the assistant's response to a user request.

## User Request
{prompt}

## Expected Tools (if any)
{expected_tools}

## Tools Called
{tool_calls}

## Assistant's Final Response
{response}

## Latency
{latency_ms:.0f} ms

## Scoring Rubric
1 = wrong/no tool use when required, unsafe, or unhelpful
2 = partially correct but missed tools or made mistakes
3 = acceptable, minor issues
4 = good, correct tool use, clear
5 = excellent: correct, fast, minimal, robust tool use

## Instructions
- Score 1-5 based on the rubric
- Consider: Did it call the right tools? Was the response helpful? Was it voice-friendly (concise)?
- Respond with ONLY a JSON object: {{"score": <1-5>, "notes": "<brief explanation>"}}
""".strip()


@dataclass
class RunResult:
    model: str
    provider: str
    scenario_id: str
    category: str
    latency_ms_total: float
    tool_calls: list[dict[str, Any]]
    final_text: str
    expected_tools: tuple[str, ...]
    auto_pass: Optional[bool]
    human_score: Optional[int]
    human_notes: str
    auto_judge_score: Optional[int]
    auto_judge_notes: str
    auto_judge_provider: str
    auto_judge_model: str


def _results_path() -> Path:
    path = config.storage.data_dir.expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path / "bench_results.jsonl"


def _truncate(text: str, max_chars: int = 3000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... [truncated]"


def _truncate_tool_output(text: str) -> str:
    return _truncate(text, max_chars=4000)


def _tool_map() -> dict[str, Any]:
    tools = get_all_tools()
    return {t.__name__: t for t in tools}


def _coerce_value(value: Any, annotation: Any) -> Any:
    if value is None:
        return None
    if annotation is inspect._empty:
        return value
    if annotation is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "y"}:
                return True
            if lowered in {"false", "0", "no", "n"}:
                return False
        return bool(value)
    if annotation is int:
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.isdigit() or (stripped.startswith("-") and stripped[1:].isdigit()):
                return int(stripped)
        return value
    if annotation is float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                return value
    return value


def _coerce_args(tool: Any, args: dict[str, Any]) -> dict[str, Any]:
    sig = inspect.signature(tool)
    coerced: dict[str, Any] = dict(args)
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        if name in coerced:
            coerced[name] = _coerce_value(coerced[name], param.annotation)
    return coerced


async def _execute_tool(name: str, args: Any) -> str:
    tools = _tool_map()
    tool = tools.get(name)
    if not tool:
        return f"Tool not found: {name}"

    if isinstance(args, str):
        try:
            parsed = json.loads(args)
        except Exception:
            parsed = {}
        args = parsed

    if not isinstance(args, dict):
        return "Tool args must be an object."

    args = _coerce_args(tool, args)

    try:
        result = tool(**args)
        if inspect.isawaitable(result):
            result = await result
        return str(result)
    except TypeError as exc:
        return f"Tool invocation error: {exc}"
    except Exception as exc:
        return f"Tool execution error: {exc}"


def _build_tools_for_provider(provider: str, tool_names: Optional[set[str]] = None) -> list[dict[str, Any]]:
    tools = get_all_tools()
    if tool_names is not None:
        tools = [t for t in tools if t.__name__ in tool_names]
    if provider == "openai":
        return [tool_to_openai_spec(t) for t in tools]
    return [tool_to_anthropic_spec(t) for t in tools]


def _auto_grade(
    expected: tuple[str, ...],
    calls: list[dict[str, Any]],
    final_text: str,
) -> Optional[bool]:
    if not expected:
        return None
    called = {c.get("name") for c in calls}
    # Require both: expected tool(s) were called, and a user-facing response was produced.
    return all(name in called for name in expected) and bool(final_text.strip())


async def run_scenario(
    provider: str,
    model: str,
    scenario: Scenario,
    interactive: bool,
    toolset: str,
) -> RunResult:
    provider_impl = get_provider(provider)
    system = get_system_prompt() + "\n\n" + BENCH_SYSTEM_APPENDIX

    tool_names: Optional[set[str]] = None
    if toolset == "focused":
        if scenario.expected_tools:
            tool_names = set(scenario.expected_tools)
        else:
            tool_names = set()
    elif toolset == "full":
        tool_names = None
    else:
        tool_names = None

    tool_specs = _build_tools_for_provider(provider, tool_names=tool_names)

    messages: list[dict[str, Any]] = [{"role": "user", "content": scenario.prompt}]
    tool_calls: list[dict[str, Any]] = []

    start = time.monotonic()
    final_text = ""

    for turn in range(max(1, scenario.max_turns)):
        response: ModelResponse = await provider_impl.complete(
            model=model,
            system=system,
            messages=messages,
            tools=tool_specs,
        )

        if response.text:
            final_text = response.text

        if not response.tool_calls:
            if interactive and turn < scenario.max_turns - 1 and response.text.strip():
                print("\nAssistant asked:")
                print(_truncate(response.text, max_chars=800))
                reply = input("Your reply (enter to stop): ").strip()
                if reply:
                    messages.append({"role": "user", "content": reply})
                    continue
            break

        tool_calls.extend(response.tool_calls)

        # Execute tool calls and feed back tool results.
        if provider == "openai":
            for call in response.tool_calls:
                tool_name = call.get("name") or ""
                args = call.get("arguments")
                output = _truncate_tool_output(await _execute_tool(tool_name, args))

                messages.append(
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": call.get("id"),
                                "type": "function",
                                "function": {"name": tool_name, "arguments": args},
                            }
                        ],
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id"),
                        "content": output,
                    }
                )
        else:
            assistant_blocks: list[dict[str, Any]] = []
            if response.text:
                assistant_blocks.append({"type": "text", "text": response.text})

            tool_results: list[dict[str, Any]] = []
            for call in response.tool_calls:
                tool_name = call.get("name") or ""
                tool_id = call.get("id") or f"toolu_{turn}_{tool_name}"
                args = call.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                if not isinstance(args, dict):
                    args = {}

                assistant_blocks.append(
                    {"type": "tool_use", "id": tool_id, "name": tool_name, "input": args}
                )
                output = _truncate_tool_output(await _execute_tool(tool_name, args))
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": tool_id, "content": output}
                )

            # Anthropic requires tool_result blocks to correspond to a tool_use block
            messages.append({"role": "assistant", "content": assistant_blocks})
            messages.append({"role": "user", "content": tool_results})

    # If we ended with tool calls but no final text, make one more call without tools
    # to force the model to produce a summary response
    if tool_calls and not final_text.strip():
        try:
            final_response = await provider_impl.complete(
                model=model,
                system=system,
                messages=messages,
                tools=[],  # No tools - force text response
            )
            if final_response.text:
                final_text = final_response.text
        except Exception:
            pass  # Keep empty final_text if this fails

    latency_ms_total = (time.monotonic() - start) * 1000.0
    auto_pass = _auto_grade(scenario.expected_tools, tool_calls, final_text)

    return RunResult(
        model=model,
        provider=provider,
        scenario_id=scenario.id,
        category=scenario.category,
        latency_ms_total=latency_ms_total,
        tool_calls=tool_calls,
        final_text=final_text,
        expected_tools=scenario.expected_tools,
        auto_pass=auto_pass,
        human_score=None,
        human_notes="",
        auto_judge_score=None,
        auto_judge_notes="",
        auto_judge_provider="",
        auto_judge_model="",
    )


def _prompt_score() -> tuple[Optional[int], str]:
    print("\n" + SCORING_RUBRIC)
    while True:
        raw = input("Score 1-5 (enter to skip, 'help' to reprint): ").strip().lower()
        if not raw:
            return None, ""
        if raw in {"help", "?"}:
            print("\n" + SCORING_RUBRIC)
            continue
        try:
            score = int(raw)
        except ValueError:
            print("Please enter a number 1-5.")
            continue
        if 1 <= score <= 5:
            break
        print("Score must be between 1 and 5.")
    notes = input("Notes (optional): ").strip()
    return score, notes


def _extract_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) >= 2:
            raw = parts[1].strip()
            if raw.startswith("json"):
                raw = raw[4:].strip()

    start = raw.find("{")
    if start == -1:
        raise json.JSONDecodeError("No JSON object found", raw, 0)

    depth = 0
    end = None
    for idx in range(start, len(raw)):
        ch = raw[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = idx + 1
                break
    if end is None:
        raise json.JSONDecodeError("Unterminated JSON object", raw, start)

    return json.loads(raw[start:end])


async def _auto_judge(
    judge_provider: str,
    judge_model: str,
    scenario: Scenario,
    result: RunResult,
    retries: int,
) -> tuple[Optional[int], str]:
    """Use an LLM to automatically score the result."""
    provider_impl = get_provider(judge_provider)

    tool_names = [c.get("name") for c in result.tool_calls]
    prompt = AUTO_JUDGE_PROMPT.format(
        prompt=scenario.prompt,
        expected_tools=list(scenario.expected_tools) if scenario.expected_tools else "None specified",
        tool_calls=tool_names if tool_names else "None",
        response=_truncate(result.final_text, max_chars=2000),
        latency_ms=result.latency_ms_total,
    )

    last_error = ""
    for attempt in range(max(1, retries)):
        try:
            response = await provider_impl.complete(
                model=judge_model,
                system="Return ONLY valid JSON. No markdown.",
                messages=[{"role": "user", "content": prompt}],
                tools=[],
            )

            data = _extract_json_object(response.text)
            score = int(data.get("score", 0))
            notes = str(data.get("notes", "")).strip()
            if 1 <= score <= 5:
                return score, f"[auto-judge: {judge_provider}:{judge_model}] {notes}"
            last_error = f"Invalid score from judge: {score}"
        except Exception as exc:
            last_error = str(exc)

        prompt = (
            "Return ONLY JSON like "
            '{"score": 1, "notes": "brief"}'
            ". No extra text.\n\n"
            + prompt
        )

    return None, f"Auto-judge failed: {last_error}"


def _save_result(result: RunResult) -> None:
    record = asdict(result)
    record["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    _results_path().open("a", encoding="utf-8").write(json.dumps(record) + "\n")


async def main_async(args: argparse.Namespace) -> int:
    scenarios = get_scenarios()
    if args.scenario:
        wanted = set(args.scenario)
        scenarios = [s for s in scenarios if s.id in wanted]
        if not scenarios:
            print("No matching scenarios.")
            return 2

    models = args.model
    if not models:
        print("Provide at least one --model like openai:gpt-4o-mini or anthropic:claude-sonnet-...")
        return 2

    # Parse auto-judge model if provided
    judge_provider: Optional[str] = None
    judge_model: Optional[str] = None
    if args.auto_judge:
        if ":" not in args.auto_judge:
            print(f"Invalid auto-judge spec: {args.auto_judge} (use provider:model)")
            return 2
        judge_provider, judge_model = args.auto_judge.split(":", 1)
        print(f"Using auto-judge: {judge_provider}:{judge_model}")

    append_event({"type": "bench", "models": models, "count": len(scenarios)})

    for model_spec in models:
        if ":" not in model_spec:
            print(f"Invalid model spec: {model_spec} (use provider:model)")
            continue
        provider, model = model_spec.split(":", 1)

        print(f"\n=== {provider}:{model} ===")
        for scenario in scenarios:
            print(f"\n--- Scenario: {scenario.id} ({scenario.category}) ---")
            try:
                result = await run_scenario(
                    provider,
                    model,
                    scenario,
                    interactive=bool(args.interactive or args.judge),
                    toolset=args.toolset,
                )
            except ProviderError as exc:
                print(f"Provider error: {exc}")
                continue
            except Exception as exc:
                print(f"Run failed: {exc}")
                continue

            print(f"Latency total: {result.latency_ms_total:.0f} ms")
            if result.tool_calls:
                names = [c.get("name") for c in result.tool_calls]
                print(f"Tool calls: {names}")
            if result.auto_pass is not None:
                print(f"Auto pass: {result.auto_pass} (expected {list(result.expected_tools)})")

            print("\nOutput:\n" + _truncate(result.final_text))

            # Auto-judge with LLM
            if judge_provider and judge_model:
                print("\nAuto-judging...")
                score, notes = await _auto_judge(
                    judge_provider,
                    judge_model,
                    scenario,
                    result,
                    retries=args.auto_judge_retries,
                )
                result.auto_judge_score = score
                result.auto_judge_notes = notes
                result.auto_judge_provider = judge_provider
                result.auto_judge_model = judge_model
                if score is not None:
                    print(f"Auto-judge score: {score}/5")
                    print(f"Notes: {notes}")
                else:
                    print(f"Auto-judge failed: {notes}")
            # Manual human judge
            elif args.judge:
                score, notes = _prompt_score()
                result.human_score = score
                result.human_notes = notes

            _save_result(result)

    print(f"\nSaved results to: {_results_path()}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S benchmark runner")
    parser.add_argument(
        "--model",
        action="append",
        default=[],
        help="Model spec provider:model (e.g., openai:gpt-4o-mini, anthropic:claude-sonnet-...)",
    )
    parser.add_argument("--scenario", action="append", help="Scenario id to run (repeatable)")
    parser.add_argument("--judge", action="store_true", help="Prompt for human scoring")
    parser.add_argument(
        "--auto-judge",
        type=str,
        default=None,
        help="Use LLM as judge (e.g., anthropic:claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--auto-judge-retries",
        type=int,
        default=2,
        help="Retries for auto-judge JSON parsing/failures",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Allow human-in-the-loop replies when the model asks questions",
    )
    parser.add_argument(
        "--toolset",
        choices=["focused", "full"],
        default="focused",
        help="Toolset size: focused uses only expected tools; full includes all tools.",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))
