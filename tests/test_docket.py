import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from gigi import docket as dk

SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "sample-case" / "docket.json"


class ClassifyTests(unittest.TestCase):
    def test_kinds(self):
        cases = {
            "ORDER denying [5] Motion to Dismiss. (Signed by Judge Jane Roe)": "order",
            "MEMORANDUM AND ORDER granting in part [5] Motion to Dismiss": "order",
            "SCHEDULING/DOCKET CONTROL ORDER. Jury Trial set for 1/11/2027": "order",
            "Order on Motion for Reconsideration": "order",
            "Opposed Proposed Pretrial Order by Jane Doe": "other",
            "Mail Returned Undeliverable as to Jane Doe re: [12] Order on Motion to Compel": "mail_returned",
            "NOTICE of Setting. Initial Conference reset for 3/9/2026": "setting",
            "Minute Entry for proceedings held before Judge Jane Roe.": "minute",
            "Motion Hearing": "minute",
            "RESPONSE in Opposition to [5] MOTION to Dismiss": "response",
            "Opposed RESPONSE in Opposition to [9] MOTION": "response",
            "REPLY in Support of [14] MOTION for Entry of Order": "reply",
            "Unopposed MOTION to Compel Discovery": "motion",
            "Compel AND Sanctions": "motion",
            "Emergency AND Protective Order AND Sanctions": "motion",
            "First AMENDED COMPLAINT against Acme": "complaint",
            "NOTICE of Right to Sue": "notice",
            "TRANSCRIPT re: Motion Hearing held on March 2, 2026": "transcript",
            "BRIEF In Support re: [4] MOTION for Temporary Restraining Order": "support",
            "Second SUPPLEMENT to [11] MOTION for Contempt by Acme": "support",
            "CERTIFICATE of Conference re: [15] AMENDED MOTION": "support",
            "Supplemental EXHIBITS re: [18] MOTION for Summary Judgment": "support",
        }
        for text, kind in cases.items():
            with self.subTest(text=text):
                self.assertEqual(dk.classify(text), kind)


class SampleDocketTests(unittest.TestCase):
    def setUp(self):
        self.d = dk.load(SAMPLE)

    def test_attachments_grouped(self):
        self.assertEqual(self.d.get(5).attachments, ["Proposed Order"])
        self.assertEqual(len([e for e in self.d.entries if e.number == 9]), 1)

    def test_dispositions(self):
        disp = self.d.dispositions()
        self.assertEqual(disp[5][0]["ruling"], "denying")
        self.assertEqual(disp[10][0]["ruling"], "granting in part and denying in part")

    def test_pending_motions(self):
        rows = self.d.pending_motions(date(2026, 3, 25))
        self.assertEqual([r["entry"].number for r in rows], [9])
        self.assertEqual(rows[0]["submission_day"], date(2026, 4, 2))
        self.assertEqual(rows[0]["submission_source"], "docket text")
        self.assertFalse(rows[0]["cjra_candidate"])

    def test_motion_filed_after_as_of_is_ignored(self):
        self.assertEqual(self.d.pending_motions(date(2026, 2, 1)), [])

    def test_hearing_modes(self):
        modes = [(h["what"], h["mode"]) for h in self.d.hearing_settings()]
        self.assertEqual(modes, [("Initial Conference", "telephone"), ("Evidentiary Hearing", "in person")])

    def test_manual_dispositions_resolve_unlinked_motions(self):
        self.d.manual_dispositions = {9: [{"ruling": "granted (bare ORDER)", "order": 13}]}
        self.assertEqual(self.d.pending_motions(date(2026, 3, 25)), [])

    def test_mail_returned(self):
        self.assertEqual([e.number for e in self.d.mail_returned()], [7])

    def test_normalized_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "docket.json"
            dk.save(self.d, path)
            again = dk.load(path)
        self.assertEqual([(e.number, e.date, e.kind) for e in again.entries],
                         [(e.number, e.date, e.kind) for e in self.d.entries])

    def test_overrides_add_missing_entry(self):
        dk.apply_overrides(self.d, {"14": {"date": "2026-03-24", "text": "MOTION for Entry of Final Judgment Under Rule 54(b)"}})
        self.assertEqual(self.d.get(14).kind, "motion")
        self.assertIn(14, [r["entry"].number for r in self.d.pending_motions(date(2026, 3, 25))])


class CourtListenerFormatTests(unittest.TestCase):
    def test_loads_v4_docket_entries(self):
        rows = {"results": [{"entry_number": 3, "date_filed": "2026-01-02", "description": "",
                             "recap_documents": [{"description": "Order", "attachment_number": None, "is_available": True,
                                                  "pacer_doc_id": "1790"}]}]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cl.json"
            path.write_text(json.dumps(rows))
            d = dk.load(path)
        self.assertEqual(d.entries[0].kind, "order")
        self.assertTrue(d.entries[0].available)


class CjraTests(unittest.TestCase):
    def test_cutoffs(self):
        self.assertEqual(dk.next_cjra_cutoff(date(2026, 9, 29)), date(2026, 9, 30))
        self.assertEqual(dk.next_cjra_cutoff(date(2026, 10, 1)), date(2027, 3, 31))
        self.assertTrue(dk.is_cjra_candidate(date(2025, 12, 29), date(2026, 9, 29)))
        self.assertFalse(dk.is_cjra_candidate(date(2026, 6, 1), date(2026, 9, 29)))


if __name__ == "__main__":
    unittest.main()
