import unittest
from datetime import date

from gigi.holidays import federal_holidays, holiday_name, is_business_day


class HolidayTests(unittest.TestCase):
    def test_2026_calendar(self):
        h = federal_holidays(2026)
        expected = {
            date(2026, 1, 1): "New Year's Day",
            date(2026, 1, 19): "Birthday of Martin Luther King, Jr.",
            date(2026, 2, 16): "Washington's Birthday",
            date(2026, 5, 25): "Memorial Day",
            date(2026, 6, 19): "Juneteenth National Independence Day",
            date(2026, 7, 3): "Independence Day (observed)",  # July 4 is a Saturday
            date(2026, 7, 4): "Independence Day",
            date(2026, 9, 7): "Labor Day",
            date(2026, 10, 12): "Columbus Day",
            date(2026, 11, 11): "Veterans Day",
            date(2026, 11, 26): "Thanksgiving Day",
            date(2026, 12, 25): "Christmas Day",
        }
        self.assertEqual(h, expected)

    def test_sunday_holiday_observed_monday(self):
        self.assertEqual(holiday_name(date(2027, 7, 5)), "Independence Day (observed)")

    def test_new_years_on_saturday_observed_prior_december(self):
        # Jan 1, 2028 is a Saturday; the observed holiday is Friday, Dec 31, 2027.
        self.assertEqual(holiday_name(date(2027, 12, 31)), "New Year's Day (observed)")

    def test_business_days(self):
        self.assertFalse(is_business_day(date(2026, 10, 17)))  # Saturday
        self.assertFalse(is_business_day(date(2025, 10, 13)))  # Columbus Day
        self.assertTrue(is_business_day(date(2026, 10, 14)))
        self.assertFalse(is_business_day(date(2026, 10, 14), extra=[date(2026, 10, 14)]))


if __name__ == "__main__":
    unittest.main()
