import copy
import unittest
from datetime import date
from pathlib import Path

from gigi import brief, playbook as pbk

SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "sample-case" / "playbook.json"


def authority(**over):
    a = {
        "id": "x", "kind": "fifth_cir", "case_name": "Alpha v. Beta", "citation": "1 F.4th 1 (5th Cir. 2021)",
        "holding": "h", "use": "u", "targets": ["ECF 9"], "verified": True, "verification": "read full text",
        "quote": "q", "pin": "at 2", "source_url": "https://example.test/alpha",
    }
    a.update(over)
    return a


class PlaybookTests(unittest.TestCase):
    def setUp(self):
        self.pb = pbk.load(SAMPLE)

    def test_sample_is_valid(self):
        self.assertEqual(pbk.validate(self.pb), [])

    def test_validation_catches_problems(self):
        pb = copy.deepcopy(self.pb)
        pb["authorities"] += [
            authority(id="frcp-26c1"),  # duplicate id
            authority(id="y", verified=False, verification=""),  # unverified quote
            authority(id="z", kind="blog", targets=["ECF 999"]),
            authority(id="w", verification=""),  # verified without a note
        ]
        problems = "\n".join(pbk.validate(pb))
        self.assertIn("duplicate id", problems)
        self.assertIn("quotation is unverified", problems)
        self.assertIn("unknown kind 'blog'", problems)
        self.assertIn("target 'ECF 999' is not defined", problems)
        self.assertIn("verified without a verification note", problems)

    def test_select_orders_by_kind_and_filters_unverified(self):
        pb = copy.deepcopy(self.pb)
        pb["authorities"] += [
            authority(id="f"),
            authority(id="j", kind="judge", case_name="Judge v. Own"),
            authority(id="u", verified=False),
        ]
        kinds = [a["kind"] for a in pbk.select(pb, target="ECF 9")]
        self.assertEqual(kinds, ["judge", "fifth_cir", "rule"])
        self.assertEqual(len(pbk.select(pb, target="ECF 9", verified_only=False)), 4)

    def test_merge_dedupes_and_upgrades(self):
        pb = copy.deepcopy(self.pb)
        first = {"authorities": [authority(id="a", verified=False, verification="")], "unverified_leads": [{"case_name": "L", "why": "w"}]}
        self.assertEqual(pbk.merge(pb, first, issue="rule41b"), {"added": 1, "upgraded": 0, "skipped": 0, "leads": 1})
        second = {"authorities": [authority(id="a", kind="ellison", targets=["ECF 200"])]}
        self.assertEqual(pbk.merge(pb, second)["upgraded"], 1)
        merged = [a for a in pb["authorities"] if a["case_name"] == "Alpha v. Beta"]
        self.assertEqual(len(merged), 1)
        self.assertTrue(merged[0]["verified"])
        self.assertEqual(merged[0]["kind"], "judge")
        self.assertEqual(merged[0]["targets"], ["ECF 200", "ECF 9"])


class BriefTests(unittest.TestCase):
    def setUp(self):
        self.pb = pbk.load(SAMPLE)
        self.pb["authorities"].append(authority(id="u", verified=False, case_name="Unchecked v. Case"))

    def test_render_excludes_unverified_by_default(self):
        text = brief.render_insert(self.pb, "ECF 9", as_of=date(2026, 3, 25))
        self.assertIn("ATTORNEY WORK PRODUCT", text)
        self.assertIn("The Court's own orders in this case", text)
        self.assertIn("Fed. R. Civ. P. 26(c)(1)", text)
        self.assertIn("Cite-check table", text)
        self.assertIn("Excluded — unverified", text)
        self.assertNotIn("Unchecked v. Case**", text)

    def test_render_can_include_unverified_with_warning(self):
        text = brief.render_insert(self.pb, "ECF 9", include_unverified=True, as_of=date(2026, 3, 25))
        self.assertIn("**Unchecked v. Case**", text)
        self.assertIn("UNVERIFIED", text)

    def test_unknown_target(self):
        text = brief.render_insert(self.pb, "ECF 404", as_of=date(2026, 3, 25))
        self.assertIn("No verified material", text)


if __name__ == "__main__":
    unittest.main()
