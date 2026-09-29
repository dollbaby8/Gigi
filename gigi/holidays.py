"""Federal legal holidays for FRCP 6(a)(6) time computation.

FRCP 6(a)(6)(A) defines "legal holiday" to include "the day set aside by
statute for observing" the holidays listed in 5 U.S.C. § 6103(a). When a
fixed-date holiday falls on a Saturday the observed day is the preceding
Friday; when it falls on a Sunday, the following Monday (5 U.S.C. § 6103(b)).
Both the calendar date and the observed date are treated as legal holidays.

Days declared a holiday by the President or Congress (FRCP 6(a)(6)(B)) and
unplanned clerk's-office closures (FRCP 6(a)(3)) cannot be computed; pass
them in as ``extra`` dates.
"""

from datetime import date, timedelta
from typing import Dict, Iterable, Optional

MONDAY, THURSDAY, SATURDAY, SUNDAY = 0, 3, 5, 6


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    nxt = date(year + (month // 12), month % 12 + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(d: date) -> date:
    if d.weekday() == SATURDAY:
        return d - timedelta(days=1)
    if d.weekday() == SUNDAY:
        return d + timedelta(days=1)
    return d


def _fixed(year: int):
    days = [(date(year, 1, 1), "New Year's Day")]
    if year >= 2021:
        days.append((date(year, 6, 19), "Juneteenth National Independence Day"))
    days += [
        (date(year, 7, 4), "Independence Day"),
        (date(year, 11, 11), "Veterans Day"),
        (date(year, 12, 25), "Christmas Day"),
    ]
    return days


def federal_holidays(year: int) -> Dict[date, str]:
    """Return {date: name} for every legal holiday that falls in ``year``."""
    out: Dict[date, str] = {}
    # Scan neighbouring years too: New Year's Day on a Saturday is observed
    # on December 31 of the prior year.
    for y in (year - 1, year, year + 1):
        for d, name in _fixed(y):
            out[d] = name
            obs = _observed(d)
            if obs != d:
                out[obs] = f"{name} (observed)"
        if y >= 1986:
            out[_nth_weekday(y, 1, MONDAY, 3)] = "Birthday of Martin Luther King, Jr."
        out[_nth_weekday(y, 2, MONDAY, 3)] = "Washington's Birthday"
        out[_last_weekday(y, 5, MONDAY)] = "Memorial Day"
        out[_nth_weekday(y, 9, MONDAY, 1)] = "Labor Day"
        out[_nth_weekday(y, 10, MONDAY, 2)] = "Columbus Day"
        out[_nth_weekday(y, 11, THURSDAY, 4)] = "Thanksgiving Day"
    return {d: n for d, n in sorted(out.items()) if d.year == year}


def holiday_name(d: date, extra: Iterable[date] = ()) -> Optional[str]:
    """Name of the legal holiday on ``d``, or None."""
    if d in set(extra):
        return "Court-declared holiday / clerk's office inaccessible"
    return federal_holidays(d.year).get(d)


def is_business_day(d: date, extra: Iterable[date] = ()) -> bool:
    """True unless ``d`` is a Saturday, Sunday, or legal holiday."""
    return d.weekday() < SATURDAY and holiday_name(d, extra) is None
