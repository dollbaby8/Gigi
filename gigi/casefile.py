"""A case directory bundles everything Gigi knows about one lawsuit.

    cases/<slug>/
        case.json       metadata, scheduling-order deadlines, targets, overrides
        docket.json     docket snapshot (DocketBird, CourtListener, or normalized)
        playbook.json   citation-verified authority bank (see gigi.playbook)
        out/            generated briefs, calendars, dashboards

``cases/`` is git-ignored: case files are attorney work product.
"""

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Tuple

from gigi import playbook as pbk
from gigi.deadlines import Deadline, post_judgment
from gigi.docket import Docket, _parse_date, apply_overrides, load as load_docket

CASE_TEMPLATE = {
    "case_number": "",
    "court": "S.D. Tex.",
    "caption": "",
    "judge": "",
    "our_side": "",
    "service_by_mail": False,
    "extra_holidays": [],
    "judgment_entered": None,
    "us_party": False,
    "scheduling_order": {"source": "", "deadlines": []},
    "custom_deadlines": [],
    "alerts": [],
    "entry_overrides": {},
    "manual_dispositions": {},
}


@dataclass
class Case:
    root: Path
    cfg: dict
    docket: Docket
    playbook: dict

    @property
    def out_dir(self) -> Path:
        path = self.root / "out"
        path.mkdir(parents=True, exist_ok=True)
        return path


def init_case(root, **fields) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    cfg = dict(CASE_TEMPLATE, **{k: v for k, v in fields.items() if v is not None})
    (root / "case.json").write_text(json.dumps(cfg, indent=1) + "\n", encoding="utf-8")
    pb_path = root / "playbook.json"
    if not pb_path.exists():
        pbk.save(pbk.empty(cfg["case_number"], cfg["judge"]), pb_path)
    return root


def load_case(root) -> Case:
    root = Path(root)
    cfg_path = root / "case.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"{cfg_path} not found; run `gigi init {root}` first")
    cfg = dict(CASE_TEMPLATE, **json.loads(cfg_path.read_text(encoding="utf-8")))
    docket = load_docket(root / "docket.json") if (root / "docket.json").exists() else Docket()
    docket.case_number = cfg["case_number"] or docket.case_number
    docket.caption = cfg["caption"] or docket.caption
    docket.judge = cfg["judge"] or docket.judge
    docket.court = cfg["court"] or docket.court
    apply_overrides(docket, cfg.get("entry_overrides"))
    docket.manual_dispositions = {
        int(k): v if isinstance(v, list) else [v] for k, v in (cfg.get("manual_dispositions") or {}).items()
    }
    pb_path = root / "playbook.json"
    pb = pbk.load(pb_path) if pb_path.exists() else pbk.empty(cfg["case_number"], cfg["judge"])
    return Case(root, cfg, docket, pb)


def extra_holidays(cfg: dict) -> Tuple[date, ...]:
    return tuple(d for d in (_parse_date(x) for x in cfg.get("extra_holidays", [])) if d)


def _from_cfg(item: dict, default_source: str, default_rule: str = "") -> Deadline:
    return Deadline(
        label=item["label"],
        due=_parse_date(item["date"]),
        rule=item.get("rule", default_rule),
        source=item.get("source", default_source),
        kind=item.get("kind", "deadline"),
        notes=[item["note"]] if item.get("note") else [],
    )


def case_deadlines(case: Case, as_of: date, include_past: bool = False) -> List[Deadline]:
    cfg = case.cfg
    out: List[Deadline] = []
    so = cfg.get("scheduling_order") or {}
    for item in so.get("deadlines", []):
        out.append(_from_cfg(item, so.get("source", "Scheduling order"), "Scheduling order"))
    for item in cfg.get("custom_deadlines", []):
        out.append(_from_cfg(item, "case.json"))
    for row in case.docket.pending_motions(as_of):
        e = row["entry"]
        out.append(
            Deadline(
                label=f"Submission day — {e.label}: {e.short(80)}",
                due=row["submission_day"],
                rule="S.D. Tex. LR 7.3/7.4",
                trigger=e.date,
                source=e.label,
                kind="submission",
                notes=[f"Submission day from {row['submission_source']}; responses are due by this date."],
            )
        )
    for h in case.docket.hearing_settings():
        if h["date"]:
            out.append(
                Deadline(
                    label=f"{h['what']} — {h['mode']} ({h['time']})",
                    due=h["date"],
                    rule="Court setting",
                    source=h["entry"].label,
                    kind="hearing",
                    notes=[h["where"]],
                )
            )
    if cfg.get("judgment_entered"):
        for dl in post_judgment(_parse_date(cfg["judgment_entered"]), us_party=cfg.get("us_party", False),
                                extra=extra_holidays(cfg)):
            dl.source = "Judgment entered " + cfg["judgment_entered"]
            out.append(dl)
    uniq = {}
    for dl in out:
        if dl.due and (include_past or dl.due >= as_of):
            uniq.setdefault((dl.label, dl.due), dl)
    return sorted(uniq.values(), key=lambda d: (d.due, d.label))
