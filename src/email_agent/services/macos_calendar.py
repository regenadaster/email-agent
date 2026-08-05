"""macOS Calendar adapter implemented with AppleScript via ``osascript``.

The adapter keeps AppleScript details outside the provider-neutral calendar
contract.  Input datetimes are converted to the Mac's local timezone before
being passed as numeric components, avoiding locale-dependent date parsing.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from datetime import datetime
from functools import lru_cache

from email_agent.services.calendar import (
    CalendarConflict,
    CalendarNotFoundError,
    CalendarOperationError,
    CalendarPermissionError,
    CalendarService,
    CalendarUnavailableError,
    CalendarValidationError,
    normalize_optional_text,
    normalize_required_text,
    validate_time_range,
)

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]

_FIELD_SEPARATOR = "\x1f"
_RECORD_SEPARATOR = "\x1e"
_EXPECTED_CONFLICT_FIELD_COUNT = 17

_CREATE_EVENT_APPLESCRIPT = r"""
on buildDate(y, m, d, h, minuteValue, secondValue)
    set resultDate to current date
    set day of resultDate to 1
    set year of resultDate to (y as integer)
    set month of resultDate to (m as integer)
    set day of resultDate to (d as integer)
    set time of resultDate to ((h as integer) * hours + (minuteValue as integer) * minutes + (secondValue as integer))
    return resultDate
end buildDate

on run argv
    set eventTitle to item 1 of argv
    set startDate to my buildDate(item 2 of argv, item 3 of argv, item 4 of argv, item 5 of argv, item 6 of argv, item 7 of argv)
    set endDate to my buildDate(item 8 of argv, item 9 of argv, item 10 of argv, item 11 of argv, item 12 of argv, item 13 of argv)
    set eventLocation to item 14 of argv
    set eventNotes to item 15 of argv
    set requestedCalendar to item 16 of argv

    tell application "Calendar"
        if requestedCalendar is not "" then
            if not (exists calendar requestedCalendar) then
                error "CALENDAR_NOT_FOUND:" & requestedCalendar
            end if
            set targetCalendar to calendar requestedCalendar
            if writable of targetCalendar is false then
                error "CALENDAR_NOT_WRITABLE:" & requestedCalendar
            end if
        else
            set availableCalendars to every calendar whose writable is true
            if (count of availableCalendars) is 0 then
                error "NO_WRITABLE_CALENDAR"
            end if
            set targetCalendar to item 1 of availableCalendars
        end if

        tell targetCalendar
            set createdEvent to make new event with properties {summary:eventTitle, start date:startDate, end date:endDate, location:eventLocation, description:eventNotes}
        end tell

        set createdUID to uid of createdEvent as text
        if createdUID is "" then
            error "EMPTY_EVENT_UID"
        end if
        return createdUID
    end tell
end run
"""

_FIND_CONFLICTS_APPLESCRIPT = r"""
on buildDate(y, m, d, h, minuteValue, secondValue)
    set resultDate to current date
    set day of resultDate to 1
    set year of resultDate to (y as integer)
    set month of resultDate to (m as integer)
    set day of resultDate to (d as integer)
    set time of resultDate to ((h as integer) * hours + (minuteValue as integer) * minutes + (secondValue as integer))
    return resultDate
end buildDate

on replaceText(findText, replacementText, sourceText)
    set oldDelimiters to AppleScript's text item delimiters
    set AppleScript's text item delimiters to findText
    set sourceItems to text items of sourceText
    set AppleScript's text item delimiters to replacementText
    set resultText to sourceItems as text
    set AppleScript's text item delimiters to oldDelimiters
    return resultText
end replaceText

on sanitizeField(sourceValue)
    set fieldSeparator to ASCII character 31
    set recordSeparator to ASCII character 30
    set cleanedText to sourceValue as text
    set cleanedText to my replaceText(fieldSeparator, " ", cleanedText)
    set cleanedText to my replaceText(recordSeparator, " ", cleanedText)
    set cleanedText to my replaceText(ASCII character 13, " ", cleanedText)
    set cleanedText to my replaceText(ASCII character 10, " ", cleanedText)
    set cleanedText to my replaceText(ASCII character 9, " ", cleanedText)
    return cleanedText
end sanitizeField

on joinText(textItems, delimiterText)
    set oldDelimiters to AppleScript's text item delimiters
    set AppleScript's text item delimiters to delimiterText
    set joinedText to textItems as text
    set AppleScript's text item delimiters to oldDelimiters
    return joinedText
end joinText

on run argv
    set queryStart to my buildDate(item 1 of argv, item 2 of argv, item 3 of argv, item 4 of argv, item 5 of argv, item 6 of argv)
    set queryEnd to my buildDate(item 7 of argv, item 8 of argv, item 9 of argv, item 10 of argv, item 11 of argv, item 12 of argv)
    set requestedCalendar to item 13 of argv
    set fieldSeparator to ASCII character 31
    set recordSeparator to ASCII character 30
    set outputText to ""

    tell application "Calendar"
        if requestedCalendar is not "" then
            if not (exists calendar requestedCalendar) then
                error "CALENDAR_NOT_FOUND:" & requestedCalendar
            end if
            set targetCalendars to {calendar requestedCalendar}
        else
            set targetCalendars to every calendar
        end if

        repeat with calendarRef in targetCalendars
            set currentCalendarName to name of calendarRef as text

            tell calendarRef
                set matchingEvents to every event where its start date is less than queryEnd and end date is greater than queryStart
            end tell

            repeat with eventRef in matchingEvents
                set eventUID to ""
                set eventTitle to "(无标题)"
                set eventLocation to ""
                set allDayFlag to false

                try
                    set eventUID to uid of eventRef as text
                end try
                try
                    set eventTitle to summary of eventRef as text
                    if eventTitle is "" then set eventTitle to "(无标题)"
                end try
                try
                    set eventLocation to location of eventRef as text
                end try
                try
                    set allDayFlag to allday event of eventRef
                end try

                set eventStart to start date of eventRef
                set eventEnd to end date of eventRef

                set startYear to (year of eventStart) as integer
                set startMonth to (month of eventStart) as integer
                set startDay to (day of eventStart) as integer
                set startHour to (hours of eventStart) as integer
                set startMinute to (minutes of eventStart) as integer
                set startSecond to (seconds of eventStart) as integer

                set endYear to (year of eventEnd) as integer
                set endMonth to (month of eventEnd) as integer
                set endDay to (day of eventEnd) as integer
                set endHour to (hours of eventEnd) as integer
                set endMinute to (minutes of eventEnd) as integer
                set endSecond to (seconds of eventEnd) as integer

                if allDayFlag then
                    set allDayText to "true"
                else
                    set allDayText to "false"
                end if

                set recordFields to {¬
                    my sanitizeField(eventUID), ¬
                    my sanitizeField(currentCalendarName), ¬
                    my sanitizeField(eventTitle), ¬
                    startYear as text, ¬
                    startMonth as text, ¬
                    startDay as text, ¬
                    startHour as text, ¬
                    startMinute as text, ¬
                    startSecond as text, ¬
                    endYear as text, ¬
                    endMonth as text, ¬
                    endDay as text, ¬
                    endHour as text, ¬
                    endMinute as text, ¬
                    endSecond as text, ¬
                    my sanitizeField(eventLocation), ¬
                    allDayText}

                set recordText to my joinText(recordFields, fieldSeparator)
                if outputText is "" then
                    set outputText to recordText
                else
                    set outputText to outputText & recordSeparator & recordText
                end if
            end repeat
        end repeat
    end tell

    return outputText
end run
"""


class MacOSCalendarService(CalendarService):
    """Calendar service backed by the current user's macOS Calendar app."""

    def __init__(
        self,
        *,
        osascript_path: str = "/usr/bin/osascript",
        timeout_seconds: float = 30.0,
        runner: CommandRunner | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise CalendarValidationError("timeout_seconds 必须大于 0")
        self._osascript_path = osascript_path
        self._timeout_seconds = timeout_seconds
        self._runner = runner or subprocess.run

    def find_conflicts(
        self,
        *,
        start_time: datetime,
        end_time: datetime,
        calendar_name: str | None = None,
    ) -> list[CalendarConflict]:
        validate_time_range(start_time=start_time, end_time=end_time)
        local_start = start_time.astimezone()
        local_end = end_time.astimezone()
        requested_calendar = normalize_optional_text(calendar_name) or ""

        output = self._run_applescript(
            script=_FIND_CONFLICTS_APPLESCRIPT,
            arguments=[
                *self._datetime_arguments(local_start),
                *self._datetime_arguments(local_end),
                requested_calendar,
            ],
            operation="查询日历冲突",
        )
        return self._parse_conflicts(output)

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
        validate_time_range(start_time=start_time, end_time=end_time)
        normalized_title = normalize_required_text(title, field_name="title")
        local_start = start_time.astimezone()
        local_end = end_time.astimezone()

        event_uid = self._run_applescript(
            script=_CREATE_EVENT_APPLESCRIPT,
            arguments=[
                normalized_title,
                *self._datetime_arguments(local_start),
                *self._datetime_arguments(local_end),
                location or "",
                notes or "",
                normalize_optional_text(calendar_name) or "",
            ],
            operation="创建日历事件",
        ).strip()

        if not event_uid:
            raise CalendarOperationError("创建日历事件失败：Calendar 未返回事件 UID")
        return event_uid

    @staticmethod
    def _datetime_arguments(value: datetime) -> list[str]:
        return [
            str(value.year),
            str(value.month),
            str(value.day),
            str(value.hour),
            str(value.minute),
            str(value.second),
        ]

    def _run_applescript(
        self,
        *,
        script: str,
        arguments: Sequence[str],
        operation: str,
    ) -> str:
        try:
            result = self._runner(
                [self._osascript_path, "-", *arguments],
                input=script,
                text=True,
                capture_output=True,
                check=False,
                timeout=self._timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise CalendarUnavailableError(
                f"{operation}失败：找不到 osascript，可确认当前程序运行在 macOS 上"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise CalendarUnavailableError(
                f"{operation}超时（{self._timeout_seconds:g} 秒）"
            ) from exc
        except OSError as exc:
            raise CalendarUnavailableError(f"{operation}失败：{exc}") from exc

        if result.returncode != 0:
            self._raise_provider_error(
                operation=operation,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        return result.stdout or ""

    @staticmethod
    def _raise_provider_error(
        *,
        operation: str,
        stdout: str | None,
        stderr: str | None,
    ) -> None:
        raw_error = (stderr or stdout or "未知错误").strip()
        normalized = raw_error.lower()

        if "calendar_not_found:" in normalized:
            requested = raw_error.split("CALENDAR_NOT_FOUND:", 1)[-1].strip()
            raise CalendarNotFoundError(f"{operation}失败：日历不存在：{requested}")

        if (
            "calendar_not_writable:" in normalized
            or "no_writable_calendar" in normalized
        ):
            raise CalendarPermissionError(
                f"{operation}失败：没有可写日历或目标日历为只读"
            )

        permission_markers = (
            "-1743",
            "not authorized to send apple events",
            "not permitted",
            "automation permission",
            "不允许发送 apple 事件",
            "没有权限",
        )
        if any(marker in normalized for marker in permission_markers):
            raise CalendarPermissionError(
                f"{operation}失败：macOS 未授权当前应用控制 Calendar。"
                "请在‘系统设置 → 隐私与安全性 → 自动化’中开启权限。"
            )

        unavailable_markers = (
            "-600",
            "application isn’t running",
            "application isn't running",
            "connection is invalid",
        )
        if any(marker in normalized for marker in unavailable_markers):
            raise CalendarUnavailableError(f"{operation}失败：{raw_error}")

        raise CalendarOperationError(f"{operation}失败：{raw_error}")

    @classmethod
    def _parse_conflicts(cls, output: str) -> list[CalendarConflict]:
        if not output.strip():
            return []

        conflicts: list[CalendarConflict] = []
        records = output.rstrip("\r\n").split(_RECORD_SEPARATOR)
        for index, record in enumerate(records, start=1):
            if not record:
                continue
            fields = record.split(_FIELD_SEPARATOR)
            if len(fields) != _EXPECTED_CONFLICT_FIELD_COUNT:
                raise CalendarOperationError(
                    "解析 Calendar 返回结果失败："
                    f"第 {index} 条记录应有 {_EXPECTED_CONFLICT_FIELD_COUNT} 个字段，"
                    f"实际为 {len(fields)} 个"
                )

            (
                event_uid,
                calendar_name,
                title,
                start_year,
                start_month,
                start_day,
                start_hour,
                start_minute,
                start_second,
                end_year,
                end_month,
                end_day,
                end_hour,
                end_minute,
                end_second,
                location,
                is_all_day,
            ) = fields

            try:
                start_time = cls._local_datetime_from_components(
                    start_year,
                    start_month,
                    start_day,
                    start_hour,
                    start_minute,
                    start_second,
                )
                end_time = cls._local_datetime_from_components(
                    end_year,
                    end_month,
                    end_day,
                    end_hour,
                    end_minute,
                    end_second,
                )
            except (TypeError, ValueError) as exc:
                raise CalendarOperationError(
                    f"解析 Calendar 返回时间失败（第 {index} 条记录）"
                ) from exc

            # Some imported/subscribed events can expose an empty UID.  The
            # model requires a stable non-empty identifier, so derive a local
            # fallback that remains deterministic for the returned record.
            stable_uid = event_uid.strip() or (
                f"macos:{calendar_name}:{start_time.isoformat()}:{title}"
            )

            conflicts.append(
                CalendarConflict(
                    event_id=stable_uid,
                    calendar_name=calendar_name or None,
                    title=title or "(无标题)",
                    start_time=start_time,
                    end_time=end_time,
                    location=location or None,
                    is_all_day=is_all_day.strip().lower() == "true",
                )
            )

        conflicts.sort(key=lambda item: (item.start_time, item.end_time, item.title))
        return conflicts

    @staticmethod
    def _local_datetime_from_components(*parts: str) -> datetime:
        year, month, day, hour, minute, second = (int(part) for part in parts)
        # ``astimezone()`` treats a naive datetime as system-local time and
        # attaches the correct offset for that date, including DST changes.
        return datetime(year, month, day, hour, minute, second).astimezone()


@lru_cache(maxsize=1)
def get_default_macos_calendar_service() -> MacOSCalendarService:
    """Return the process-wide default macOS Calendar adapter."""
    return MacOSCalendarService()


def book_calendar_event(
    *,
    title: str,
    start: datetime,
    end: datetime,
    location: str = "",
    notes: str = "",
    calendar_name: str = "",
) -> str:
    """Backward-compatible wrapper used by the repository's current graph."""
    return get_default_macos_calendar_service().create_event(
        title=title,
        start_time=start,
        end_time=end,
        location=location,
        notes=notes,
        calendar_name=calendar_name or None,
    )


__all__ = [
    "MacOSCalendarService",
    "book_calendar_event",
    "get_default_macos_calendar_service",
]
