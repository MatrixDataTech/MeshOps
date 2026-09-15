from datetime import date, datetime
from zoneinfo import ZoneInfo
import unittest

from meshops.models.sun import SunTimes
from meshops.services.bot import BotService
from meshops.services.sun import SunService


class SunServiceTests(unittest.TestCase):
    def test_calculates_burning_man_sun_times_in_local_time(self):
        service = SunService("America/Los_Angeles")

        sun = service.for_location(40.7864, -119.2065, date(2026, 8, 30))

        self.assertIsNotNone(sun)
        self.assertEqual(sun.sunrise.tzinfo.key, "America/Los_Angeles")
        self.assertEqual(sun.sunrise.hour, 6)
        self.assertEqual(sun.sunset.hour, 19)
        self.assertGreater(sun.day_length.total_seconds(), 12 * 3600)
        self.assertLess(sun.day_length.total_seconds(), 14 * 3600)

    def test_returns_none_when_sun_does_not_rise_or_set(self):
        service = SunService("America/Los_Angeles")

        self.assertIsNone(service.for_location(89.0, 0.0, date(2026, 6, 21)))

    def test_bot_formats_sun_command(self):
        zone = ZoneInfo("America/Los_Angeles")
        sun = SunTimes(
            sunrise=datetime(2026, 8, 30, 6, 21, tzinfo=zone),
            sunset=datetime(2026, 8, 30, 19, 34, tzinfo=zone),
        )

        response = BotService().handle_command("sun", sun=sun)

        self.assertIn("Sunrise 6:21 AM", response)
        self.assertIn("Sunset 7:34 PM", response)
        self.assertIn("Daylight 13h 13m", response)


if __name__ == "__main__":
    unittest.main()
