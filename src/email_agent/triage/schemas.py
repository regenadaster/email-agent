from typing import Literal

from pydantic import BaseModel, Field


class CalendarDraft(BaseModel):
    title: str = Field(description="日历事件标题")

    start_time: str | None = Field(
        default=None,
        description="ISO 8601 开始时间，必须包含时区",
    )

    end_time: str | None = Field(
        default=None,
        description="ISO 8601 结束时间，必须包含时区",
    )

    timezone: str | None = None
    location: str | None = None
    notes: str | None = None

    missing_fields: list[str] = Field(
        default_factory=list,
    )


class TriageResult(BaseModel):
    classification: Literal[
        "ignore",
        "notify",
        "respond",
    ]

    reason: str
    confidence: float = Field(ge=0, le=1)

    calendar_action: Literal[
        "none",
        "needs_clarification",
        "propose",
    ]

    calendar_draft: CalendarDraft | None = None
