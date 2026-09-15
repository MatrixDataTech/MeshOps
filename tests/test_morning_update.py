from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock
from zoneinfo import ZoneInfo

from meshops.services.bot import BotService
from meshops.services.morning_update import MorningUpdateService


class MorningUpdateServiceTests(unittest.TestCase):
    def settings(self, state_file: Path) -> dict:
        return {
            "enabled": True,
            "time": "08:00",
            "grace_minutes": 120,
            "state_file": str(state_file),
            "events": ["Temple Burn: 8:00 PM"],
        }

    def test_builds_report_once_and_persists_successful_send(self):
        with TemporaryDirectory() as directory:
            state_file = Path(directory) / "morning-update.json"
            bot = Mock()
            bot.check_alerts.return_value = []
            bot.build_morning_report.return_value = "Good Morning"
            now = datetime(2026, 8, 31, 8, 5, tzinfo=ZoneInfo("America/Los_Angeles"))
            service = MorningUpdateService(
                bot,
                self.settings(state_file),
                "America/Los_Angeles",
                now_provider=lambda: now,
                time_is_trusted=lambda: True,
            )
            context = {"weather": None, "aqi": None, "statuses": [], "home_node": None, "node_count": 24, "team": []}

            self.assertEqual(service.due_report(context), "Good Morning")
            service.mark_sent()

            restarted = MorningUpdateService(
                bot,
                self.settings(state_file),
                "America/Los_Angeles",
                now_provider=lambda: now,
                time_is_trusted=lambda: True,
            )
            self.assertIsNone(restarted.due_report(context))

    def test_does_not_send_outside_the_scheduled_window(self):
        with TemporaryDirectory() as directory:
            bot = Mock()
            now = datetime(2026, 8, 31, 10, 1, tzinfo=ZoneInfo("America/Los_Angeles"))
            service = MorningUpdateService(
                bot,
                self.settings(Path(directory) / "state.json"),
                "America/Los_Angeles",
                now_provider=lambda: now,
                time_is_trusted=lambda: True,
            )

            self.assertIsNone(service.due_report({}))
            bot.build_morning_report.assert_not_called()

    def test_normal_execution_at_scheduled_time_with_valid_clock(self):
        with TemporaryDirectory() as directory:
            bot = Mock()
            bot.check_alerts.return_value = []
            bot.build_morning_report.return_value = "Good Morning"
            service = MorningUpdateService(
                bot,
                self.settings(Path(directory) / "state.json"),
                "America/Los_Angeles",
                now_provider=lambda: datetime(
                    2026, 8, 31, 8, 0, tzinfo=ZoneInfo("America/Los_Angeles")
                ),
                time_is_trusted=lambda: True,
            )

            self.assertEqual(service.due_report({}), "Good Morning")

    def test_offline_data_still_builds_report_with_valid_clock(self):
        with TemporaryDirectory() as directory:
            service = MorningUpdateService(
                BotService(),
                self.settings(Path(directory) / "state.json"),
                "America/Los_Angeles",
                now_provider=lambda: datetime(
                    2026, 8, 31, 8, 0, tzinfo=ZoneInfo("America/Los_Angeles")
                ),
                time_is_trusted=lambda: True,
            )
            context = {
                "weather": None,
                "aqi": None,
                "statuses": [],
                "home_node": None,
                "node_count": 147,
                "team": [],
            }

            report = service.due_report(context)

            self.assertIn("Weather: unavailable", report)
            self.assertIn("AQI: unavailable", report)
            self.assertIn("Mesh: 147 active; camp Unavailable", report)

    def test_untrusted_clock_suppresses_report_without_collecting_context(self):
        with TemporaryDirectory() as directory:
            context_provider = Mock()
            service = MorningUpdateService(
                Mock(),
                self.settings(Path(directory) / "state.json"),
                "America/Los_Angeles",
                now_provider=lambda: datetime(
                    2026, 8, 31, 8, 0, tzinfo=ZoneInfo("America/Los_Angeles")
                ),
                time_is_trusted=lambda: False,
            )

            self.assertIsNone(service.due_report(context_provider))
            context_provider.assert_not_called()

    def test_clock_becomes_trusted_at_0835_and_sends_once(self):
        with TemporaryDirectory() as directory:
            bot = Mock()
            bot.check_alerts.return_value = []
            bot.build_morning_report.return_value = "Good Morning"
            trusted = False
            service = MorningUpdateService(
                bot,
                self.settings(Path(directory) / "state.json"),
                "America/Los_Angeles",
                now_provider=lambda: datetime(
                    2026, 8, 31, 8, 35, tzinfo=ZoneInfo("America/Los_Angeles")
                ),
                time_is_trusted=lambda: trusted,
            )

            self.assertIsNone(service.due_report({}))
            trusted = True
            self.assertEqual(service.due_report({}), "Good Morning")
            service.mark_sent()
            self.assertIsNone(service.due_report({}))

    def test_clock_becomes_trusted_at_1120_and_skips_report(self):
        with TemporaryDirectory() as directory:
            bot = Mock()
            service = MorningUpdateService(
                bot,
                self.settings(Path(directory) / "state.json"),
                "America/Los_Angeles",
                now_provider=lambda: datetime(
                    2026, 8, 31, 11, 20, tzinfo=ZoneInfo("America/Los_Angeles")
                ),
                time_is_trusted=lambda: True,
            )

            self.assertIsNone(service.due_report({}))
            bot.build_morning_report.assert_not_called()

    def test_clock_correction_does_not_duplicate_a_calendar_day(self):
        with TemporaryDirectory() as directory:
            state_file = Path(directory) / "state.json"
            bot = Mock()
            bot.check_alerts.return_value = []
            bot.build_morning_report.return_value = "Good Morning"
            now = datetime(2026, 8, 31, 8, 5, tzinfo=ZoneInfo("America/Los_Angeles"))
            service = MorningUpdateService(
                bot,
                self.settings(state_file),
                "America/Los_Angeles",
                now_provider=lambda: now,
                time_is_trusted=lambda: True,
            )

            self.assertEqual(service.due_report({}), "Good Morning")
            service.mark_sent()
            now = datetime(2026, 9, 1, 8, 5, tzinfo=ZoneInfo("America/Los_Angeles"))
            self.assertEqual(service.due_report({}), "Good Morning")
            service.mark_sent()
            now = datetime(2026, 8, 31, 8, 10, tzinfo=ZoneInfo("America/Los_Angeles"))
            self.assertIsNone(service.due_report({}))

    def test_context_failure_does_not_prevent_scheduled_report(self):
        with TemporaryDirectory() as directory:
            bot = Mock()
            bot.check_alerts.return_value = []
            bot.build_morning_report.return_value = "Good Morning fallback"
            context_provider = Mock(side_effect=RuntimeError("weather and AQI offline"))
            service = MorningUpdateService(
                bot,
                self.settings(Path(directory) / "state.json"),
                "America/Los_Angeles",
                now_provider=lambda: datetime(
                    2026, 8, 31, 8, 0, tzinfo=ZoneInfo("America/Los_Angeles")
                ),
                time_is_trusted=lambda: True,
            )

            self.assertEqual(
                service.due_report(context_provider), "Good Morning fallback"
            )


if __name__ == "__main__":
    unittest.main()
