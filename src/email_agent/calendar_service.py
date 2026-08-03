import subprocess
from datetime import datetime

_APPLESCRIPT = r"""
on buildDate(y, m, d, h, minuteValue)
    set resultDate to current date
    set day of resultDate to 1
    set year of resultDate to (y as integer)
    set month of resultDate to (m as integer)
    set day of resultDate to (d as integer)
    set time of resultDate to ((h as integer) * hours + (minuteValue as integer) * minutes)
    return resultDate
end buildDate

on run argv
    set eventTitle to item 1 of argv

    set startDate to my buildDate(item 2 of argv, item 3 of argv, item 4 of argv, item 5 of argv, item 6 of argv)

    set endDate to my buildDate(item 7 of argv, item 8 of argv, item 9 of argv, item 10 of argv, item 11 of argv)

    set eventLocation to item 12 of argv
    set eventNotes to item 13 of argv
    set requestedCalendar to item 14 of argv

    tell application "Calendar"
        if requestedCalendar is not "" then
            if not (exists calendar requestedCalendar) then
                error "Calendar does not exist: " & requestedCalendar
            end if
            set targetCalendar to calendar requestedCalendar
        else
            set availableCalendars to every calendar whose writable is true
            if (count of availableCalendars) is 0 then
                error "No writable calendar is available"
            end if
            set targetCalendar to item 1 of availableCalendars
        end if

        tell targetCalendar
            set createdEvent to make new event with properties {summary:eventTitle, start date:startDate, end date:endDate, location:eventLocation, description:eventNotes}
        end tell

        return uid of createdEvent
    end tell
end run
"""


def book_calendar_event(
    *,
    title: str,
    start: datetime,
    end: datetime,
    location: str = "",
    notes: str = "",
    calendar_name: str = "",
) -> str:
    """在当前用户的 macOS 日历中创建事件并返回事件 UID。"""

    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start 和 end 必须包含时区")

    if end <= start:
        raise ValueError("结束时间必须晚于开始时间")

    # 转换为用户电脑的本地时区
    local_start = start.astimezone()
    local_end = end.astimezone()

    arguments = [
        title,
        str(local_start.year),
        str(local_start.month),
        str(local_start.day),
        str(local_start.hour),
        str(local_start.minute),
        str(local_end.year),
        str(local_end.month),
        str(local_end.day),
        str(local_end.hour),
        str(local_end.minute),
        location,
        notes,
        calendar_name,
    ]

    result = subprocess.run(
        ["osascript", "-", *arguments],
        input=_APPLESCRIPT,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"创建日历事件失败：{result.stderr.strip()}")

    return result.stdout.strip()
