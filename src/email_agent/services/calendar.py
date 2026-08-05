"""Calendar domain models and provider-neutral service contracts.

This module deliberately contains no AppleScript, EventKit, Google Calendar,
or Microsoft Graph implementation details.  Callers such as LangChain tools
and LangGraph nodes depend on :class:`CalendarService`; provider-specific
adapters implement that protocol in separate modules.

Conventions
-----------
* Every ``datetime`` must be timezone-aware.
* Time ranges use half-open semantics: ``[start_time, end_time)``.
* Back-to-back events do not conflict.
* Provider errors are translated into the exceptions defined here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, Self, runtime_checkable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)


class CalendarServiceError(RuntimeError):
    """Base class for calendar service failures."""


class CalendarValidationError(CalendarServiceError, ValueError):
    """The caller supplied invalid calendar data."""


class CalendarNotFoundError(CalendarServiceError):
    """The requested calendar does not exist."""


class CalendarPermissionError(CalendarServiceError):
    """Calendar read/write permission was denied."""


class CalendarUnavailableError(CalendarServiceError):
    """The calendar provider or local bridge is temporarily unavailable."""


class CalendarOperationError(CalendarServiceError):
    """A provider operation failed for an otherwise valid request."""


def require_aware_datetime(value: datetime, *, field_name: str) -> datetime:
    """Return ``value`` after verifying that it has a real UTC offset."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise CalendarValidationError(f"{field_name} 必须是包含时区信息的 datetime")
    return value


def validate_time_range(
    *,
    start_time: datetime,
    end_time: datetime,
) -> tuple[datetime, datetime]:
    """Validate a timezone-aware, positive-duration time range."""
    require_aware_datetime(start_time, field_name="start_time")
    require_aware_datetime(end_time, field_name="end_time")
    if end_time <= start_time:
        raise CalendarValidationError("end_time 必须晚于 start_time")
    return start_time, end_time


def normalize_optional_text(value: str | None) -> str | None:
    """Strip optional text and turn blank strings into ``None``."""
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def normalize_required_text(value: str, *, field_name: str) -> str:
    """Strip required text and reject blank values."""
    normalized = value.strip()
    if not normalized:
        raise CalendarValidationError(f"{field_name} 不能为空")
    return normalized


class CalendarConflict(BaseModel):
    """An existing event that overlaps the requested time range."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    event_id: str = Field(min_length=1, description="Provider event UID")
    title: str = Field(min_length=1, description="Existing event title")
    start_time: datetime = Field(description="Timezone-aware event start")
    end_time: datetime = Field(description="Timezone-aware event end")
    calendar_name: str | None = Field(default=None)
    location: str | None = Field(default=None)
    is_all_day: bool = Field(default=False)

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_datetime_timezone(
        cls,
        value: datetime,
        info: ValidationInfo,
    ) -> datetime:
        return require_aware_datetime(value, field_name=info.field_name)

    @field_validator("calendar_name", "location")
    @classmethod
    def normalize_optional_fields(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @model_validator(mode="after")
    def validate_event_range(self) -> Self:
        validate_time_range(
            start_time=self.start_time,
            end_time=self.end_time,
        )
        return self


class CalendarEventCreateRequest(BaseModel):
    """Provider-neutral request for creating a calendar event."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    title: str = Field(min_length=1, max_length=500)
    start_time: datetime
    end_time: datetime
    location: str = Field(default="", max_length=1_000)
    notes: str = Field(default="", max_length=20_000)
    calendar_name: str | None = Field(default=None, max_length=500)

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_datetime_timezone(
        cls,
        value: datetime,
        info: ValidationInfo,
    ) -> datetime:
        return require_aware_datetime(value, field_name=info.field_name)

    @field_validator("calendar_name")
    @classmethod
    def normalize_calendar_name(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        validate_time_range(
            start_time=self.start_time,
            end_time=self.end_time,
        )
        normalize_required_text(self.title, field_name="title")
        return self


class CalendarAvailability(BaseModel):
    """Structured result for an availability lookup."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start_time: datetime
    end_time: datetime
    available: bool
    conflicts: list[CalendarConflict] = Field(default_factory=list)

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_datetime_timezone(
        cls,
        value: datetime,
        info: ValidationInfo,
    ) -> datetime:
        return require_aware_datetime(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        validate_time_range(
            start_time=self.start_time,
            end_time=self.end_time,
        )
        if self.available != (len(self.conflicts) == 0):
            raise CalendarValidationError(
                "available 与 conflicts 不一致：有冲突时必须为 False，无冲突时必须为 True"
            )
        return self

    @classmethod
    def from_conflicts(
        cls,
        *,
        start_time: datetime,
        end_time: datetime,
        conflicts: list[CalendarConflict],
    ) -> CalendarAvailability:
        """Build a consistent result from a provider conflict list."""
        return cls(
            start_time=start_time,
            end_time=end_time,
            available=not conflicts,
            conflicts=conflicts,
        )


@runtime_checkable
class CalendarService(Protocol):
    """Provider-neutral calendar operations used by the email agent."""

    def find_conflicts(
        self,
        *,
        start_time: datetime,
        end_time: datetime,
        calendar_name: str | None = None,
    ) -> list[CalendarConflict]:
        """Return events overlapping ``[start_time, end_time)``.

        An existing event conflicts when both conditions are true::

            existing.start_time < end_time
            existing.end_time > start_time

        Return an empty list when the interval is free.  Do not return ``None``.
        """
        ...

    def create_event(
        self,
        *,
        title: str,
        start_time: datetime,
        end_time: datetime,
        location: str = "",
        notes: str = "",
        calendar_name: str | None = None,
    ) -> str:
        """Create an event and return its non-empty provider UID.

        This method has an external side effect and should only be called by a
        deterministic execution node after validation and human approval.
        """
        ...


def check_availability(
    service: CalendarService,
    *,
    start_time: datetime,
    end_time: datetime,
    calendar_name: str | None = None,
) -> CalendarAvailability:
    """Convenience helper shared by tools and non-agent callers."""
    validate_time_range(start_time=start_time, end_time=end_time)
    conflicts = service.find_conflicts(
        start_time=start_time,
        end_time=end_time,
        calendar_name=normalize_optional_text(calendar_name),
    )
    return CalendarAvailability.from_conflicts(
        start_time=start_time,
        end_time=end_time,
        conflicts=conflicts,
    )
