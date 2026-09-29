"""Regression tests for code-review findings (dockets, deadlines, playbook, renderers)."""

import contextlib
import io
import json
import shutil
import tempfile
import unittest
import urllib.parse
from datetime import date
from pathlib import Path

from gigi import brief, courtlistener as cl, dashboard, docket as dk, playbook as pbk
from gigi.casefile import case_deadlines, init_case, load_case
from gigi.cli import main
from gigi.deadlines import compute, submission_day
from gigi.ics import _escape

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "sample-case"


def run(*argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(list(argv))
    return code, buf.getvalue()


def entry(n, d, text):
    return dk.Entry(number=n, date=d, text=text)


class HolidayPassThroughTests(unittest.TestCase):
    def test_state_holidays_count_forward_only(self):
        fri = date(2026, 11, 27)  # day after Thanksgiving; a Texas state holiday
        self.assertEqual(submission_day(date(2026, 11, 6))[0], fri)
        self.assertEqual(submission_day(date(2026, 11, 6), state=[fri])[0], date(2026, 11, 30))
        # Backward periods ignore state holidays (FRCP 6(a)(6)(C)).
        self.assertEqual(compute(date(2027, 3, 9), 7, backward=True, state=[date(2027, 3, 2)])[0], date(2027, 3, 2))
        # Court-declared closures still apply both ways.
        self.assertEqual(compute(date(2027, 3, 9), 7, backward=True, extra=[date(2027, 3, 2)])[0], date(2027, 3, 1))

    def test_case_extra_holidays_reach_submission_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = Path(tmp) / "c"
            shutil.copytree(SAMPLE, case)
            cfg = json.loads((case / "case.json").read_text())
            cfg["extra_holidays"] = ["2026-04-02"]
            # A motion with no clerk-listed date: its LR 7.3 day (4/2) must roll off the closure.
            cfg["entry_overrides"] = {"14": {"date": "2026-03-12", "text": "MOTION to Strike by Jane Doe"}}
            (case / "case.json").write_text(json.dumps(cfg))
            dls = case_deadlines(load_case(case), date(2026, 3, 25))
        subs = {d.source: d.due for d in dls if d.kind == "submission"}
        self.assertEqual(subs["ECF 14"], date(2026, 4, 3))
        self.assertEqual(subs["ECF 9"], date(2026, 4, 2))  # the clerk's listed date is authoritative

    def test_cli_holiday_flag(self):
        code, out = run("submission", "--filed", "2026-09-23", "--holiday", "2026-10-14")
        self.assertIn("2026-10-15", out)
        code, out = run("post-judgment", "--entered", "2026-09-14", "--holiday", "2026-10-14")
        self.assertIn("Notice of appeal [FRAP 4(a)(1)(A)]: 2026-10-15", out)


class HearingStatusTests(unittest.TestCase):
    def test_reset_supersedes_and_cancel_cancels(self):
        d = dk.Docket(entries=[
            entry(2, date(2026, 1, 6), "ORDER ... Initial Conference set for 3/2/2026 at 10:00 AM in Courtroom 9B before Judge Jane Roe."),
            entry(4, date(2026, 2, 1), "NOTICE of Resetting. Initial Conference reset for 3/9/2026 at 10:00 AM in Courtroom 9B before Judge Jane Roe."),
            entry(6, date(2026, 2, 5), "NOTICE OF SETTING. Motion Hearing set for 3/20/2026 at 02:00 PM in by telephone before Judge Jane Roe."),
            entry(8, date(2026, 3, 1), "ORDER Cancelling Motion Hearing set for March 20, 2026. (Signed by Magistrate Judge Pat Doe)"),
            entry(None, date(2026, 3, 9), "Minute Entry for proceedings held before Judge Jane Roe. INITIAL CONFERENCE held on 3/9/2026."),
        ])
        got = [(h["date"], h["what"], h["status"]) for h in d.hearing_settings()]
        self.assertEqual(got, [
            (date(2026, 3, 2), "Initial Conference", "superseded"),
            (date(2026, 3, 9), "Initial Conference", "held"),
            (date(2026, 3, 20), "Motion Hearing", "cancelled"),
        ])

    def test_past_hearing_not_superseded_by_later_setting(self):
        d = dk.Docket(entries=[
            entry(38, date(2025, 11, 10), "ORDER ... Motion Hearing set for 11/17/2025 at 10:30 AM in by telephone before Judge X"),
            entry(48, date(2025, 11, 24), "NOTICE of Setting ... Initial Conference and Motion Hearing reset for 12/8/2025 at 10:30 AM in by telephone before Judge X"),
        ])
        self.assertEqual([h["status"] for h in d.hearing_settings()], ["scheduled", "scheduled"])

    def test_only_scheduled_hearings_reach_the_calendar(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = Path(tmp) / "c"
            shutil.copytree(SAMPLE, case)
            raw = json.loads((case / "docket.json").read_text())
            raw["documents"].append({"id": "x", "title": "ORDER Cancelling Evidentiary Hearing set for April 1, 2026. (Signed by Judge Jane Roe)",
                                     "filing_date": "2026-03-24", "restricted": False, "primary_docket_sheet_number": 13, "downloaded": 0})
            (case / "docket.json").write_text(json.dumps(raw))
            labels = [d.label for d in case_deadlines(load_case(case), date(2026, 3, 25))]
        self.assertFalse(any("Evidentiary Hearing" in l for l in labels))


class ClassificationTests(unittest.TestCase):
    def test_filings_that_mention_a_motion_are_not_motions(self):
        for text, kind in {
            "MEMORANDUM in Opposition to [5] MOTION to Dismiss": "response",
            "MEMORANDUM in Support re: [5] MOTION to Dismiss": "support",
            "SURREPLY to [5] MOTION to Dismiss": "reply",
            "SUR-REPLY in Opposition to [5] MOTION to Dismiss": "reply",
            "OBJECTIONS to [5] MOTION to Dismiss": "other",
            "Joint STATUS REPORT re: [5] MOTION to Stay": "other",
            "Joint MOTION to Amend Scheduling Order": "motion",
            "Renewed MOTION for Sanctions": "motion",
            "Amended Motion AND Leave to File Document": "motion",
        }.items():
            with self.subTest(text=text):
                self.assertEqual(dk.classify(text), kind)

    def test_orders_signed_by_magistrates_and_uppercase_orders(self):
        self.assertEqual(dk.classify("SCHEDULING ORDER. ETT: 2 days. (Signed by Magistrate Judge Pat Doe)"), "order")
        self.assertEqual(dk.classify("Report re: discovery ( Signed by Judge Jane Roe )"), "order")
        self.assertEqual(dk.classify("MEMORANDUM AND RECOMMENDATIONS re [5] MOTION to Dismiss"), "order")
        self.assertEqual(dk.classify("PROPOSED ORDER granting motion"), "support")


class DispositionTests(unittest.TestCase):
    def test_no_false_rulings_from_dates_or_other_relief(self):
        d = dk.Docket(entries=[
            entry(4, date(2026, 1, 2), "MOTION to Compel by Jane Doe"),
            entry(9, date(2026, 1, 3), "MOTION for Protective Order by Acme"),
            entry(10, date(2026, 1, 9), "ORDER granting extension of time to respond re: [9] MOTION for Protective Order."),
            entry(None, date(2026, 1, 10), "Minute Entry. Court granting continuance re: 4/1/2026 Evidentiary Hearing."),
            entry(11, date(2026, 1, 11), "ORDER denying request for oral argument re: 4 May 2026 hearing"),
        ])
        self.assertEqual([r["entry"].number for r in d.pending_motions(date(2026, 1, 20))], [4, 9])

    def test_qualified_and_multiword_rulings(self):
        d = dk.Docket(entries=[
            entry(30, date(2026, 2, 1), "ORDER denying without prejudice [5] Motion to Dismiss; granting in part [6] Motion to Compel; "
                                        "granting 19 Joint MOTION to Amend Scheduling Order; denying 25 Renewed MOTION for Sanctions; "
                                        "denying 26 Cross MOTION for Summary Judgment"),
        ])
        self.assertEqual(sorted(d.dispositions()), [5, 6, 19, 25, 26])

    def test_rulings_after_as_of_do_not_count(self):
        d = dk.load(SAMPLE / "docket.json")
        self.assertEqual([r["entry"].number for r in d.pending_motions(date(2026, 3, 1))], [5])

    def test_undated_motions_are_listed_not_dropped(self):
        d = dk.load(SAMPLE / "docket.json")
        dk.apply_overrides(d, {"14": {"text": "MOTION for Entry of Final Judgment Under Rule 54(b)"}})
        rows = d.pending_motions(date(2026, 3, 25))
        self.assertEqual([r["entry"].number for r in rows], [9, 14])
        self.assertIsNone(rows[-1]["submission_day"])
        self.assertIs(d.entries[-1].number, 14)  # undated entries sort last


class CourtListenerDateParamTests(unittest.TestCase):
    def test_rd_filters_on_entry_date(self):
        seen = []

        class Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def opener(req, timeout=30):
            seen.append(req)
            return Resp(json.dumps({"results": [{"caseName": "A v. B", "dateFiled": "2019-01-01",
                                                 "entry_date_filed": "2024-05-01"}], "next": None}).encode())

        hits = cl.CourtListener(opener=opener, pause=0).search("order", kind="rd", filed_after="2024-01-01")
        params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(seen[0].full_url).query))
        self.assertEqual(params.get("entry_date_filed_after"), "2024-01-01")
        self.assertNotIn("filed_after", params)
        self.assertEqual(hits[0]["date"], "2024-05-01")


def auth(**over):
    a = {"id": "x", "kind": "fifth_cir", "case_name": "Doe v. Acme", "citation": "", "holding": "h", "use": "u",
         "targets": ["ECF 9"], "verified": True, "verification": "read"}
    a.update(over)
    return a


class MergeTests(unittest.TestCase):
    def test_blank_citations_do_not_collapse(self):
        pb = pbk.empty()
        counts = pbk.merge(pb, {"authorities": [auth(id="doe-ecf50", holding="one"), auth(id="doe-ecf80", holding="two")]})
        self.assertEqual(counts["added"], 2)

    def test_ids_unique_across_sections_and_kept_on_upgrade(self):
        pb = pbk.empty()
        pb["targets"] = {"ECF 9": {}}
        pbk.merge(pb, {"authorities": [auth(id="smith", citation="1 F.4th 1", verified=False, verification="")]})
        pbk.merge(pb, {"adverse": [auth(id="smith", citation="2 F.4th 2")]})
        pbk.merge(pb, {"authorities": [auth(id="gamma", citation="1 F.4th 1")]})  # verified upgrade
        self.assertEqual(pb["authorities"][0]["id"], "smith")
        self.assertTrue(pb["authorities"][0]["verified"])
        self.assertEqual(pbk.validate(pb), [])

    def test_leads_are_deduplicated(self):
        pb = pbk.empty()
        lead = {"unverified_leads": [{"case_name": "L", "why": "w"}]}
        pbk.merge(pb, lead)
        self.assertEqual(pbk.merge(pb, lead)["leads"], 0)


class RobustnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name) / "c"
        shutil.copytree(SAMPLE, self.case)

    def tearDown(self):
        self.tmp.cleanup()

    def _cfg(self, **changes):
        cfg = json.loads((self.case / "case.json").read_text())
        cfg.update(changes)
        (self.case / "case.json").write_text(json.dumps(cfg))

    def test_init_merges_instead_of_wiping(self):
        init_case(self.case, judge="Jane Q. Roe")
        cfg = json.loads((self.case / "case.json").read_text())
        self.assertEqual(cfg["judge"], "Jane Q. Roe")
        self.assertEqual(len(cfg["scheduling_order"]["deadlines"]), 4)
        self.assertEqual(cfg["caption"], "Doe v. Acme Widgets, LLC")

    def test_manual_disposition_shapes(self):
        self._cfg(manual_dispositions={"9": "granted by bare ORDER"})
        code, out = run("docket", str(self.case), "motions")
        self.assertEqual(code, 0)
        self.assertIn("granted by bare ORDER", out)

    def test_undated_and_malformed_config_dates(self):
        self._cfg(custom_deadlines=[{"label": "Joint pretrial order"}])
        self.assertEqual(run("deadlines", str(self.case), "--as-of", "2026-03-25")[0], 0)
        self._cfg(judgment_entered="2026-13-01")
        with self.assertRaises(ValueError):
            load_case(self.case)

    def test_dashboard_tolerates_nulls_and_blocks_script_urls(self):
        pb = json.loads((self.case / "playbook.json").read_text())
        pb["in_case_orders"][0].update(date=None, ecf=12)
        pb["targets"]["ECF 9"]["title"] = None
        pb["authorities"][0]["source_url"] = "javascript:alert(1)"
        (self.case / "playbook.json").write_text(json.dumps(pb))
        self._cfg(alerts=["plain string alert"])
        html = dashboard.render(load_case(self.case), date(2026, 3, 25))
        self.assertIn("plain string alert", html)
        self.assertNotIn("javascript:", html)

    def test_brief_tolerates_missing_citation(self):
        pb = json.loads((self.case / "playbook.json").read_text())
        pb["authorities"].append({"id": "lead1", "kind": "judge", "case_name": "Doe v. Acme (order)",
                                  "targets": ["ECF 9"], "verified": False})
        text = brief.render_insert(pb, "ECF 9", include_unverified=True, as_of=date(2026, 3, 25))
        self.assertIn("Doe v. Acme (order)", text)

    def test_merge_accepts_research_hits_as_leads(self):
        hits = Path(self.tmp.name) / "hits.json"
        hits.write_text(json.dumps([{"case_name": "Alpha v. Beta", "url": "https://example.test"}]))
        code, out = run("merge", str(self.case), str(hits))
        self.assertEqual(code, 0)
        self.assertIn("unverified_leads", out)
        self.assertEqual(json.loads((self.case / "playbook.json").read_text())["unverified_leads"][0]["case_name"], "Alpha v. Beta")


class IcsEscapeTests(unittest.TestCase):
    def test_bare_carriage_return_is_escaped(self):
        self.assertEqual(_escape("a\rb"), "a\\nb")


if __name__ == "__main__":
    unittest.main()
