"""Benchmark scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class Scenario:
    """A benchmark scenario."""

    id: str
    category: str  # tool_calling | simple | complex
    prompt: str
    expected_tools: tuple[str, ...] = ()
    max_turns: int = 4
    notes: str = ""


DEFAULT_SCENARIOS: list[Scenario] = [
    Scenario(
        id="tool.list_project_structure",
        category="tool_calling",
        prompt=(
            "Show me the project structure of the current repository. "
            "Assume the repo root is the current working directory (path='.')."
        ),
        expected_tools=("get_project_structure",),
        notes="Should call get_project_structure. Avoid hallucinating file names.",
    ),
    Scenario(
        id="tool.find_todos",
        category="tool_calling",
        prompt=(
            "Find TODO/FIXME/HACK comments in the current repository (path='.') "
            "and summarize the top 5 most important."
        ),
        expected_tools=("find_todos",),
        notes="Should call find_todos and then summarize.",
    ),
    Scenario(
        id="tool.daily_brief",
        category="tool_calling",
        prompt="Give me a daily brief. If you need confirmation, ask for it.",
        expected_tools=("daily_brief",),
        notes="Should call daily_brief (likely needs confirm=true depending on config).",
    ),
    Scenario(
        id="simple.style",
        category="simple",
        prompt="Reply with a concise, slightly witty greeting, 1 sentence.",
        notes="Voice-friendly concision + light humor.",
    ),
    Scenario(
        id="simple.identity",
        category="simple",
        prompt="What's your name? Who are you?",
        notes="Should identify as J.A.R.V.I.S. and explain the acronym.",
    ),
    Scenario(
        id="complex.planning",
        category="complex",
        prompt=(
            "Design a safe permission model for a voice assistant that can run commands, "
            "edit files, and access GitHub. Provide a minimal policy and escalation flow."
        ),
        notes="Assess reasoning quality, completeness, and safety.",
    ),
]


def get_scenarios() -> list[Scenario]:
    return list(DEFAULT_SCENARIOS)
