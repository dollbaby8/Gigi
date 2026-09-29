"""Deadline computation under FRCP 6, FRAP 26, and S.D. Tex. Local Rules.

Every computed date carries human-readable notes explaining each step, so a
reviewing attorney can check the arithmetic instead of trusting it. Always
confirm a deadline against the rule text and any case-specific order before
relying on it.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable, List, Optional, Tuple

from gigi.holidays import holiday_name, is_business_day

# S.D. Tex. LR 7.3: opposed motions are submitted to the judge 21 days from
# filing; LR 7.4 requires responses by the submission day.
SDTX_SUBMISSION_DAYS = 21
SDTX_REPLY_DAYS = 7  # LR 7.4(E): movant's reply, "unless otherwise directed by the presiding judge"
MAIL_DAYS = 3  # FRCP 6(d)


@dataclass
class Deadline:
    label: str
    due: date
    rule: str = ""
    trigger: Optional[date] = None
    source: str = ""
    kind: str = "deadline"  # deadline | submission | hearing | trial | info
    notes: List[str] = field(default_factory=list)

    def days_from(self, as_of: date) -> int:
        return (self.due - as_of).days

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "due": self.due.isoformat(),
            "rule": self.rule,
            "trigger": self.trigger.isoformat() if self.trigger else None,
            "source": self.source,
            "kind": self.kind,
            "notes": list(self.notes),
        }


def _describe(d: date, extra: Iterable[date]) -> str:
    return holiday_name(d, extra) or d.strftime("%A")


def roll(d: date, direction: int = 1, extra: Iterable[date] = ()) -> Tuple[date, List[str]]:
    """Move ``d`` off weekends and legal holidays (FRCP 6(a)(1)(C), 6(a)(5)).

    ``direction`` is +1 for periods measured forward from an event and -1 for
    periods measured backward from one.
    """
    extra = tuple(extra)
    start = d
    while not is_business_day(d, extra):
        d += timedelta(days=direction)
    if d == start:
        return d, []
    word = "next" if direction > 0 else "previous"
    return d, [
        f"Period ended {start.isoformat()} ({_describe(start, extra)}); "
        f"FRCP 6(a)(1)(C) moves it to the {word} business day, {d.isoformat()} ({d.strftime('%A')})."
    ]


def compute(
    trigger: date,
    days: int,
    *,
    mail_service: bool = False,
    backward: bool = False,
    extra: Iterable[date] = (),
) -> Tuple[date, List[str]]:
    """Compute a deadline ``days`` after (or before) ``trigger``.

    FRCP 6(a)(1): exclude the trigger day, count every day, include the last
    day, and roll off weekends/holidays. FRCP 6(d): when service was by mail
    (or another 6(d) method), add 3 days after the 6(a) period ends, then roll
    again.
    """
    if days < 0:
        raise ValueError("days must be non-negative; use backward=True")
    if backward and mail_service:
        raise ValueError("FRCP 6(d) applies only to periods measured after service")
    extra = tuple(extra)
    direction = -1 if backward else 1
    raw = trigger + timedelta(days=direction * days)
    notes = [
        f"{days} days {'before' if backward else 'after'} {trigger.isoformat()} = {raw.isoformat()} "
        f"({raw.strftime('%A')}) [FRCP 6(a)(1)(A)-(B)]."
    ]
    due, rolled = roll(raw, direction, extra)
    notes += rolled
    if mail_service:
        plus = due + timedelta(days=MAIL_DAYS)
        notes.append(
            f"FRCP 6(d): served by mail (or other 6(d) method), so 3 days are added after "
            f"the period ends: {plus.isoformat()} ({plus.strftime('%A')})."
        )
        due, rolled = roll(plus, 1, extra)
        notes += rolled
    return due, notes


def submission_day(filed: date, extra: Iterable[date] = ()) -> Tuple[date, List[str]]:
    """S.D. Tex. LR 7.3 submission day (also the LR 7.4 response deadline)."""
    due, notes = compute(filed, SDTX_SUBMISSION_DAYS, extra=extra)
    notes.append(
        "S.D. Tex. LR 7.3/7.4: the opposed motion is submitted on this day and any response is due by it. "
        "Check the judge's procedures and any order setting a different schedule."
    )
    return due, notes


def reply_day(response_filed: date, extra: Iterable[date] = ()) -> Tuple[date, List[str]]:
    """S.D. Tex. LR 7.4(E): the movant may reply within 7 days after the response is filed."""
    due, notes = compute(response_filed, SDTX_REPLY_DAYS, extra=extra)
    notes.append(
        "S.D. Tex. LR 7.4(E) (7 days from the response, unless otherwise directed by the presiding judge). "
        "Confirm against the current Local Rules and the judge's procedures."
    )
    return due, notes


def post_judgment(entered: date, *, us_party: bool = False, extra: Iterable[date] = ()) -> List[Deadline]:
    """Deadlines triggered by entry of a final judgment (or Rule 54(b) judgment).

    These run from *entry*, not service, so FRCP 6(d) never adds days.
    """
    extra = tuple(extra)
    out: List[Deadline] = []

    def add(label: str, days: int, rule: str, *notes: str) -> Deadline:
        due, steps = compute(entered, days, extra=extra)
        dl = Deadline(label, due, rule, entered, kind="deadline", notes=steps + list(notes))
        out.append(dl)
        return dl

    add(
        "Motion for attorney's fees",
        14,
        "FRCP 54(d)(2)(B)(i)",
        "Unless a statute or court order provides otherwise.",
    )
    add(
        "Rule 59(e) motion to alter or amend / Rule 59(b) new trial / Rule 52(b) amended findings",
        28,
        "FRCP 59(b), 59(e), 52(b)",
        "Cannot be extended: FRCP 6(b)(2).",
        "A timely motion tolls the appeal deadline: FRAP 4(a)(4)(A).",
    )
    appeal_days = 60 if us_party else 30
    appeal = add(
        "Notice of appeal",
        appeal_days,
        "FRAP 4(a)(1)(B)" if us_party else "FRAP 4(a)(1)(A)",
        "Jurisdictional. Restarts from the order disposing of a timely FRAP 4(a)(4)(A) motion.",
    )
    ext, steps = compute(appeal.due, 30, extra=extra)
    out.append(
        Deadline(
            "Last day to move to extend appeal time (excusable neglect or good cause)",
            ext,
            "FRAP 4(a)(5)(A)",
            entered,
            notes=steps + ["Motion must be filed no later than 30 days after the FRAP 4(a) time expires."],
        )
    )
    try:
        anniversary = entered.replace(year=entered.year + 1)
    except ValueError:  # entered on Feb 29
        anniversary = entered.replace(year=entered.year + 1, day=28)
    due, steps = roll(anniversary, 1, extra)
    out.append(
        Deadline(
            "Outside limit for Rule 60(b)(1)-(3) motions",
            due,
            "FRCP 60(c)(1)",
            entered,
            notes=[f"One year after entry = {anniversary.isoformat()}."]
            + steps
            + ["All Rule 60(b) motions must also be made within a reasonable time."],
        )
    )
    return out
