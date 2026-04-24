"""Tests for mandamus_draft."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import mandamus_draft as md  # noqa: E402


def sample_config() -> dict:
    return {
        "appeal_case_no": "24-12345",
        "case": {
            "petitioner": "ACME Corp.",
            "respondent": "Hon. Jane Doe",
            "real_party_in_interest": "John Smith",
            "district_court": "S.D. Tex.",
            "district_case_no": "4:24-cv-01",
            "district_judge": "Jane Doe",
        },
        "counsel": {
            "name": "A. Lawyer",
            "firm": "Firm LLP",
            "address": "123 Main\nHouston, TX",
            "phone": "555-0100",
            "email": "a@example.com",
            "bar_no": "TX1",
        },
        "interested_persons": ["ACME Corp.", "John Smith"],
        "oral_argument": {"requested": True, "reason": "Novel issue."},
        "issues": ["Issue one?", "Issue two?"],
        "facts": ["Fact one.", "Fact two."],
        "jurisdiction": "28 U.S.C. 1651(a).",
        "argument": {
            "no_other_adequate_means": "No adequate means.",
            "clear_and_indisputable_right": "Clear and indisputable.",
            "appropriateness": "Appropriate.",
        },
        "relief": "Vacate the order.",
        "service": ["Hon. Jane Doe"],
    }


class ValidateTests(unittest.TestCase):
    def test_complete_config_has_no_problems(self) -> None:
        self.assertEqual(md.validate(sample_config()), [])

    def test_missing_cheney_prong_reported(self) -> None:
        cfg = sample_config()
        del cfg["argument"]["appropriateness"]
        problems = md.validate(cfg)
        self.assertIn("argument.appropriateness is required (Cheney prong)", problems)

    def test_missing_counsel_field_reported(self) -> None:
        cfg = sample_config()
        del cfg["counsel"]["email"]
        self.assertIn("counsel.email is required", md.validate(cfg))

    def test_empty_facts_reported(self) -> None:
        cfg = sample_config()
        cfg["facts"] = []
        self.assertIn("facts must be a non-empty list of statements", md.validate(cfg))


class RenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = sample_config()
        self.text = md.render(self.cfg)

    def test_contains_all_required_sections(self) -> None:
        for heading in [
            "PETITION FOR WRIT OF MANDAMUS",
            "CERTIFICATE OF INTERESTED PERSONS",
            "STATEMENT REGARDING ORAL ARGUMENT",
            "TABLE OF CONTENTS",
            "TABLE OF AUTHORITIES",
            "RELIEF SOUGHT",
            "ISSUES PRESENTED",
            "JURISDICTION",
            "STATEMENT OF FACTS",
            "REASONS WHY THE WRIT SHOULD ISSUE",
            "CONCLUSION",
            "CERTIFICATE OF SERVICE",
            "CERTIFICATE OF COMPLIANCE",
        ]:
            self.assertIn(heading, self.text, f"missing section: {heading}")

    def test_cheney_prongs_present(self) -> None:
        self.assertIn("I. PETITIONER HAS NO OTHER ADEQUATE MEANS", self.text)
        self.assertIn("II. PETITIONER'S RIGHT TO ISSUANCE", self.text)
        self.assertIn("III. THE WRIT IS APPROPRIATE", self.text)

    def test_petitioner_appears_on_cover(self) -> None:
        self.assertIn("In re ACME Corp.", self.text)

    def test_case_numbers_rendered(self) -> None:
        self.assertIn("24-12345", self.text)
        self.assertIn("4:24-cv-01", self.text)

    def test_word_count_under_limit(self) -> None:
        self.assertLess(md.count_words(self.text), md.WORD_LIMIT)

    def test_oral_argument_not_requested_branch(self) -> None:
        cfg = sample_config()
        cfg["oral_argument"] = {"requested": False, "reason": "Routine."}
        text = md.render(cfg)
        self.assertIn("does not believe oral argument", text)


class WordCountTests(unittest.TestCase):
    def test_counts_words_ignoring_punctuation(self) -> None:
        self.assertEqual(md.count_words("Hello, world!  It's fine."), 5)


if __name__ == "__main__":
    unittest.main()
