import io
import json
import unittest
import urllib.parse
from datetime import date, datetime, timezone

from gigi import courtlistener as cl
from gigi.deadlines import Deadline
from gigi.ics import _fold, to_ics


class IcsTests(unittest.TestCase):
    def test_calendar_structure(self):
        dl = Deadline("Response due; ECF 9, protective order", date(2026, 4, 2), rule="LR 7.3", source="ECF 9",
                      notes=["line one", "line two"])
        text = to_ics([dl], "Doe deadlines", now=datetime(2026, 3, 25, tzinfo=timezone.utc))
        self.assertTrue(text.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertTrue(text.endswith("END:VCALENDAR\r\n"))
        self.assertIn("DTSTART;VALUE=DATE:20260402", text)
        self.assertIn("DTEND;VALUE=DATE:20260403", text)
        self.assertIn("SUMMARY:Response due\\; ECF 9\\, protective order", text)
        self.assertEqual(text.count("BEGIN:VALARM"), 2)
        self.assertIn("TRIGGER:-P7D", text)

    def test_folding(self):
        folded = _fold("DESCRIPTION:" + "x" * 200)
        for line in folded.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75)
        self.assertEqual(folded.replace("\r\n ", ""), "DESCRIPTION:" + "x" * 200)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class CourtListenerTests(unittest.TestCase):
    def test_search_builds_query_and_normalizes(self):
        seen = []
        pages = [
            {"next": "https://www.courtlistener.com/api/rest/v4/search/?cursor=abc&type=o", "results": [
                {"caseName": "Alpha v. Beta", "dateFiled": "2019-05-01", "docketNumber": "4:18-cv-1",
                 "court_citation_string": "S.D. Tex.", "judge": "Keith P. Ellison", "citation": [],
                 "absolute_url": "/opinion/1/alpha-v-beta/", "opinions": [{"snippet": "a <mark>lesser sanction</mark>"}]}]},
            {"next": None, "results": [{"caseName": "Gamma v. Delta", "absolute_url": "/opinion/2/g/"}]},
        ]

        def opener(req, timeout=30):
            seen.append(req)
            return FakeResponse(json.dumps(pages[len(seen) - 1]).encode())

        client = cl.CourtListener(token="t0k", opener=opener, pause=0)
        hits = client.search('"41(b)"', judge="Keith P. Ellison", limit=5)
        first = urllib.parse.urlparse(seen[0].full_url)
        params = dict(urllib.parse.parse_qsl(first.query))
        self.assertEqual(params["judge"], "Keith P. Ellison")
        self.assertEqual(params["court"], "txsd")
        self.assertEqual(params["type"], "o")
        self.assertEqual(seen[0].get_header("Authorization"), "Token t0k")
        self.assertIn("cursor=abc", seen[1].full_url)
        self.assertEqual(len(hits), 2)
        self.assertEqual(hits[0]["snippet"], "a **lesser sanction**")
        self.assertEqual(hits[0]["url"], "https://www.courtlistener.com/opinion/1/alpha-v-beta/")

    def test_recap_search_uses_assigned_to(self):
        seen = []

        def opener(req, timeout=30):
            seen.append(req)
            return FakeResponse(json.dumps({"results": [], "next": None}).encode())

        cl.CourtListener(token="", opener=opener, pause=0).search("order", kind="rd", judge="Ellison")
        params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(seen[0].full_url).query))
        self.assertEqual(params["assigned_to"], "Ellison")
        self.assertNotIn("judge", params)
        self.assertIsNone(seen[0].get_header("Authorization"))

    def test_errors_are_wrapped(self):
        def opener(req, timeout=30):
            raise OSError("blocked")

        with self.assertRaises(cl.CourtListenerError):
            cl.CourtListener(opener=opener, pause=0).search("x")

    def test_markdown(self):
        md = cl.to_markdown([cl.normalize_hit({"caseName": "Alpha v. Beta", "absolute_url": "/o/1/"})], "Title")
        self.assertIn("**Alpha v. Beta**", md)
        self.assertIn("verify every quotation", md)

    def test_issue_presets_have_queries(self):
        for key, spec in cl.ISSUES.items():
            with self.subTest(key=key):
                self.assertTrue(spec["q"] and spec["title"])


if __name__ == "__main__":
    unittest.main()
