# tools/calendar_tools.py

from datetime import datetime

from langchain.tools import ToolRuntime, tool
from pydantic import BaseModel, Field

from email_agent.runtime_context import AgentContext


class CheckCalendarAvailabilityInput(BaseModel):
    start_time: datetime = Field(description="待检查时间段的开始时间，必须包含时区")
    end_time: datetime = Field(description="待检查时间段的结束时间，必须包含时区")
    calendar_name: str | None = Field(description="需要检查的日历名称，不指定时传 null")


@tool(
    "check_calendar_availability",
    args_schema=CheckCalendarAvailabilityInput,
)
def check_calendar_availability(
    start_time: datetime,
    end_time: datetime,
    calendar_name: str | None,
    runtime: ToolRuntime[AgentContext],
) -> dict:
    """检查指定时间段是否与用户已有日历事件冲突。

    仅在邮件包含明确会议或预约时间，并需要判断该时间是否可用时调用。
    本工具只读取日历，不会创建、修改或删除任何事件。
    """
    if start_time.tzinfo is None or end_time.tzinfo is None:
        return {
            "available": False,
            "error": "开始时间和结束时间必须包含时区",
            "conflicts": [],
        }

    if end_time <= start_time:
        return {
            "available": False,
            "error": "结束时间必须晚于开始时间",
            "conflicts": [],
        }

    conflicts = runtime.context.calendar.find_conflicts(
        start_time=start_time,
        end_time=end_time,
        calendar_name=calendar_name,
    )

    return {
        "available": not conflicts,
        "conflicts": [conflict.model_dump(mode="json") for conflict in conflicts],
    }
