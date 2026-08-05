# runtime_context.py

from dataclasses import dataclass
from functools import lru_cache

from email_agent.services.calendar import CalendarService
from email_agent.services.macos_calendar import get_default_macos_calendar_service


@dataclass(frozen=True)
class AgentContext:
    calendar: CalendarService


@lru_cache(maxsize=1)
def create_default_agent_context() -> AgentContext:
    """创建当前进程默认使用的 AgentContext。"""

    return AgentContext(calendar=get_default_macos_calendar_service())
