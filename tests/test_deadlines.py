import unittest
from datetime import date

from gigi.deadlines import compute, post_judgment, reply_day, roll, submission_day


class SubmissionDayTests(unittest.TestCase):
    """LR 7.3 dates checked against S.D. Tex. clerk-generated 'Motion Docket Date' entries."""

    CLERK_PAIRS = [
        (date(2025, 9, 22), date(2025, 10, 14)),  # day 21 is Columbus Day
        (date(2025, 9, 23), date(2025, 10, 14)),
        (date(2025, 9, 26), date(2025, 10, 17)),
        (date(2026, 8, 29), date(2026, 9, 21)),  # day 21 is a Saturday
        (date(2026, 9, 23), date(2026, 10, 14)),
        (date(2026, 9, 26), date(2026, 10, 19)),
        (date(2026, 9, 28), date(2026, 10, 19)),
    ]

    def test_matches_clerk_dates(self):
        for filed, expected in self.CLERK_PAIRS:
            with self.subTest(filed=filed):
                self.assertEqual(submission_day(filed)[0], expected)


class ReplyDayTests(unittest.TestCase):
    def test_seven_days_and_rolls(self):
        self.assertEqual(reply_day(date(2026, 10, 14))[0], date(2026, 10, 21))
        # 11/4/2026 + 7 = 11/11/2026, Veterans Day -> 11/12.
        self.assertEqual(reply_day(date(2026, 11, 4))[0], date(2026, 11, 12))


class ComputeTests(unittest.TestCase):
    def test_plain_period(self):
        due, notes = compute(date(2026, 10, 2), 14)
        self.assertEqual(due, date(2026, 10, 16))
        self.assertEqual(len(notes), 1)

    def test_mail_service_adds_three_days_then_rolls(self):
        # 14 days from Fri 10/2 = Fri 10/16; +3 = Mon 10/19.
        self.assertEqual(compute(date(2026, 10, 2), 14, mail_service=True)[0], date(2026, 10, 19))
        # Period ends Fri 10/9; +3 = Mon 10/12 (Columbus Day) -> Tue 10/13.
        self.assertEqual(compute(date(2026, 9, 25), 14, mail_service=True)[0], date(2026, 10, 13))

    def test_backward_rolls_earlier(self):
        # 3 days before Mon 7/6/2026 is Fri 7/3 (Independence Day observed) -> Thu 7/2.
        self.assertEqual(compute(date(2026, 7, 6), 3, backward=True)[0], date(2026, 7, 2))

    def test_roll_explains_itself(self):
        due, notes = roll(date(2026, 10, 17))
        self.assertEqual(due, date(2026, 10, 19))
        self.assertIn("Saturday", notes[0])

    def test_rejects_invalid_combinations(self):
        with self.assertRaises(ValueError):
            compute(date(2026, 1, 1), -1)
        with self.assertRaises(ValueError):
            compute(date(2026, 1, 1), 3, mail_service=True, backward=True)


class PostJudgmentTests(unittest.TestCase):
    def test_standard_deadlines(self):
        got = {d.rule: d.due for d in post_judgment(date(2026, 10, 5))}
        self.assertEqual(got["FRCP 54(d)(2)(B)(i)"], date(2026, 10, 19))
        self.assertEqual(got["FRCP 59(b), 59(e), 52(b)"], date(2026, 11, 2))
        self.assertEqual(got["FRAP 4(a)(1)(A)"], date(2026, 11, 4))
        self.assertEqual(got["FRAP 4(a)(5)(A)"], date(2026, 12, 4))
        self.assertEqual(got["FRCP 60(c)(1)"], date(2027, 10, 5))

    def test_us_party_gets_sixty_days(self):
        got = {d.rule: d.due for d in post_judgment(date(2026, 10, 5), us_party=True)}
        self.assertEqual(got["FRAP 4(a)(1)(B)"], date(2026, 12, 4))

    def test_appeal_deadline_rolls_off_holiday(self):
        # 30 days after 10/12/2026 = 11/11/2026 (Veterans Day) -> 11/12.
        got = {d.rule: d.due for d in post_judgment(date(2026, 10, 12))}
        self.assertEqual(got["FRAP 4(a)(1)(A)"], date(2026, 11, 12))


if __name__ == "__main__":
    unittest.main()
