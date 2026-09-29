"""iCalendar (RFC 5545) export so deadlines land in Outlook/Google/Apple Calendar."""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from gigi.deadlines import Deadline


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
        .replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Fold content lines longer than 75 octets (RFC 5545 §3.1)."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, current = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        limit = 75 if not parts else 74  # continuation lines start with a space
        if len(current) + len(b) > limit:
            parts.append(current.decode("utf-8"))
            current = b
        else:
            current += b
    parts.append(current.decode("utf-8"))
    return "\r\n ".join(parts)


def to_ics(
    deadlines: Iterable[Deadline],
    calendar_name: str = "Case deadlines",
    alarms_days: Iterable[int] = (7, 1),
    now: Optional[datetime] = None,
) -> str:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//gigi//sdtx deadlines//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{_escape(calendar_name)}",
    ]
    for dl in deadlines:
        uid = hashlib.sha1(f"{dl.label}|{dl.due.isoformat()}|{dl.source}".encode("utf-8")).hexdigest()
        desc = "\n".join(filter(None, [f"Rule: {dl.rule}" if dl.rule else "", f"Source: {dl.source}" if dl.source else ""] + dl.notes))
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}@gigi",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{dl.due.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{(dl.due + timedelta(days=1)).strftime('%Y%m%d')}",
            f"SUMMARY:{_escape(dl.label)}",
            f"DESCRIPTION:{_escape(desc)}",
            "TRANSP:TRANSPARENT",
        ]
        for days in alarms_days:
            lines += [
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"TRIGGER:-P{int(days)}D",
                f"DESCRIPTION:{_escape(dl.label)} in {int(days)} day(s)",
                "END:VALARM",
            ]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
