import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

from gigi.cli import main

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "sample-case"


def run(*argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(list(argv))
    return code, buf.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name) / "sample"
        shutil.copytree(SAMPLE, self.case)

    def tearDown(self):
        self.tmp.cleanup()

    def test_deadline_commands(self):
        code, out = run("submission", "--filed", "2025-09-22")
        self.assertEqual(code, 0)
        self.assertIn("2025-10-14", out)
        self.assertIn("Columbus Day", out)
        code, out = run("post-judgment", "--entered", "2026-10-05")
        self.assertIn("2026-11-04", out)
        code, out = run("deadline", "--from", "2026-10-02", "--days", "14", "--mail")
        self.assertIn("2026-10-19", out)

    def test_docket_views(self):
        code, out = run("docket", str(self.case), "pending", "--as-of", "2026-03-25")
        self.assertEqual(code, 0)
        self.assertIn("ECF 9", out)
        self.assertIn("1 motion(s)", out)
        code, out = run("docket", str(self.case), "hearings")
        self.assertIn("in person", out)
        code, out = run("docket", str(self.case), "motions")
        self.assertIn("denying (ECF 8)", out)

    def test_deadlines_and_ics(self):
        ics_path = self.case / "cal.ics"
        code, out = run("deadlines", str(self.case), "--as-of", "2026-03-25", "--ics", str(ics_path))
        self.assertEqual(code, 0)
        self.assertIn("Submission day — ECF 9", out)
        self.assertIn("Evidentiary Hearing", out)
        self.assertTrue(ics_path.read_text().startswith("BEGIN:VCALENDAR"))

    def test_playbook_check_and_build(self):
        code, out = run("playbook", str(self.case), "--check")
        self.assertEqual(code, 0, out)
        code, out = run("build", str(self.case), "--as-of", "2026-03-25")
        self.assertEqual(code, 0)
        outd = self.case / "out"
        self.assertTrue((outd / "brief_ecf-9.md").exists())
        self.assertTrue((outd / "deadlines.ics").exists())
        html = (outd / "dashboard.html").read_text()
        self.assertIn("Doe v. Acme Widgets, LLC", html)
        self.assertIn("prefers-color-scheme:dark", html)
        self.assertIn("1 in person", html)

    def test_init_and_import(self):
        new = Path(self.tmp.name) / "new"
        code, _ = run("init", str(new), "--case-number", "4:26-cv-2", "--judge", "Jane Roe")
        self.assertEqual(code, 0)
        code, _ = run("import-docket", str(SAMPLE / "docket.json"), str(new))
        self.assertEqual(code, 0)
        code, out = run("docket", str(new), "orders")
        self.assertIn("ECF 12", out)

    def test_research_requires_query(self):
        with contextlib.redirect_stderr(io.StringIO()):
            code, _ = run("research", "--judge", "Jane Roe")
        self.assertEqual(code, 2)


class RepoHygieneTests(unittest.TestCase):
    def test_case_data_is_ignored(self):
        ignored = (ROOT / ".gitignore").read_text().split()
        for pattern in ("cases/", "out/", "*.ics"):
            self.assertIn(pattern, ignored)


if __name__ == "__main__":
    unittest.main()
