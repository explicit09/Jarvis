"""Tool modules for J.A.R.V.I.S.

Tools give J.A.R.V.I.S the ability to interact with the system,
search the web, and perform various actions.
"""

from __future__ import annotations

from .alarms import get_alarm_tools, start_alarm_scheduler, stop_alarm_scheduler, set_timer_callback
from .briefing import get_briefing_tools
from .calendar import get_calendar_tools
from .code_analysis import get_code_analysis_tools
from .contacts import get_contact_tools
from .files import get_file_tools
from .github import get_github_tools
from .home_macos import get_home_macos_tools
from .macos import get_macos_tools
from .memory import get_memory_tools
from .music import get_music_tools
from .notes import get_note_tools
from .outlook_calendar import get_outlook_tools
from .routines import get_routine_tools
from .sandbox import get_sandbox_tools
from .smart_home import get_smart_home_tools
from .system import get_system_tools
from .tasks import get_task_tools
from .telephony import get_telephony_tools
from .web import get_web_tools

__all__ = [
    "get_system_tools",
    "get_web_tools",
    "get_memory_tools",
    "get_note_tools",
    "get_task_tools",
    "get_calendar_tools",
    "get_briefing_tools",
    "get_code_analysis_tools",
    "get_contact_tools",
    "get_outlook_tools",
    "get_routine_tools",
    "get_smart_home_tools",
    "get_home_macos_tools",
    "get_file_tools",
    "get_telephony_tools",
    "get_alarm_tools",
    "get_github_tools",
    "get_sandbox_tools",
    "get_macos_tools",
    "get_music_tools",
    "get_all_tools",
    "start_alarm_scheduler",
    "stop_alarm_scheduler",
    "set_timer_callback",
]


def get_all_tools() -> list:
    """Get all tools for the agent.

    Returns a list of functions decorated with @llm.function_tool
    that can be used with LiveKit's FunctionContext.
    """
    tools = []
    tools.extend(get_system_tools())
    tools.extend(get_web_tools())
    tools.extend(get_sandbox_tools())
    tools.extend(get_code_analysis_tools())
    tools.extend(get_briefing_tools())
    tools.extend(get_memory_tools())
    tools.extend(get_note_tools())
    tools.extend(get_task_tools())
    tools.extend(get_alarm_tools())  # Timers, alarms, reminders
    tools.extend(get_calendar_tools())
    tools.extend(get_outlook_tools())
    tools.extend(get_github_tools())
    tools.extend(get_contact_tools())
    tools.extend(get_routine_tools())
    tools.extend(get_smart_home_tools())
    tools.extend(get_home_macos_tools())  # macOS HomeKit/Shortcuts
    tools.extend(get_file_tools())
    tools.extend(get_telephony_tools())
    tools.extend(get_macos_tools())  # macOS utilities
    tools.extend(get_music_tools())  # Music control (Apple Music, YouTube Music)
    return tools
