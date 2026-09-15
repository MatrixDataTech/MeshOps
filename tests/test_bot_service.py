from datetime import datetime, timedelta
import unittest

from meshops.models.air_quality import AirQuality
from meshops.models.node import Node
from meshops.models.weather import Weather
from meshops.services.bot import BotService
from meshops.services.status import SubsystemStatus


class BotServiceTests(unittest.TestCase):
    def setUp(self):
        self.bot = BotService()
        self.weather = Weather(
            temperature=82,
            feels_like=84,
            humidity=22,
            wind_speed=8,
            weather_code=0,
            updated=datetime.now(),
        )
        self.aqi = AirQuality(42, "Good", "🟢", datetime.now())

    def test_handles_weather_and_aqi_commands(self):
        weather = self.bot.handle_command(
            "weather",
            weather=self.weather,
            aqi=self.aqi,
        )

        self.assertIn("🌤 Camp Weather", weather)
        self.assertIn("82°F (feels 84°F)", weather)
        self.assertIn("🌫 AQI 42 (Good)", weather)
        self.assertIn("🌫 AQI 42: Good", self.bot.handle_command("aqi", aqi=self.aqi))

    def test_returns_events_for_burns_and_events_commands(self):
        events = ["Man Burn: Saturday 9:00 PM", "Temple Burn: Sunday 8:00 PM"]

        burns = self.bot.handle_command("burns", events=events)
        alias = self.bot.handle_command("events", events=events)

        self.assertIn("Burns", burns)
        self.assertIn("Man Burn", burns)
        self.assertEqual(alias, burns)
        self.assertIn("burns", self.bot.handle_command("help"))

    def test_team_response_formats_the_selected_team_nodes(self):
        nodes = [
            Node("1", "TEAM-FLX", "FLX", "RAK4631", battery=82),
        ]

        response = self.bot.format_team(nodes)

        self.assertIn("TEAM-FLX", response)

    def test_team_response_reports_an_empty_team(self):
        self.assertEqual(self.bot.format_team([]), "No team nodes.")

    def test_alerts_are_deduplicated_until_condition_clears(self):
        hot_weather = Weather(
            temperature=100,
            feels_like=100,
            humidity=10,
            wind_speed=5,
            weather_code=0,
            updated=datetime.now(),
        )

        first = self.bot.check_alerts(
            weather=hot_weather,
            aqi=None,
            statuses=[],
        )
        repeated = self.bot.check_alerts(
            weather=hot_weather,
            aqi=None,
            statuses=[],
        )
        self.bot.check_alerts(weather=None, aqi=None, statuses=[])
        resumed = self.bot.check_alerts(
            weather=hot_weather,
            aqi=None,
            statuses=[],
        )

        self.assertEqual([alert.key for alert in first], ["high-temperature"])
        self.assertEqual(repeated, [])
        self.assertEqual([alert.key for alert in resumed], ["high-temperature"])

    def test_returns_rain_alert_when_forecast_input_requires_it(self):
        alerts = self.bot.check_alerts(
            weather=None,
            aqi=None,
            statuses=[],
            rain_expected=True,
        )

        self.assertEqual([alert.key for alert in alerts], ["rain-expected"])

    def test_current_alerts_does_not_consume_duplicate_alert_state(self):
        hot_weather = Weather(
            temperature=100,
            feels_like=100,
            humidity=10,
            wind_speed=5,
            weather_code=0,
            updated=datetime.now(),
        )

        preview_alerts = self.bot.current_alerts(
            weather=hot_weather,
            aqi=None,
            statuses=[],
        )
        scheduled_alerts = self.bot.check_alerts(
            weather=hot_weather,
            aqi=None,
            statuses=[],
        )

        self.assertEqual([alert.key for alert in preview_alerts], ["high-temperature"])
        self.assertEqual([alert.key for alert in scheduled_alerts], ["high-temperature"])

    def test_builds_compact_morning_report(self):
        report = self.bot.build_morning_report(
            weather=self.weather,
            aqi=self.aqi,
            node_count=24,
            camp_status="Online",
            alerts=[],
        )

        self.assertIn("Good Morning", report)
        self.assertIn("Weather: 82F", report)
        self.assertIn("Sun: Unavailable", report)
        self.assertIn("Events: None", report)
        self.assertIn("AQI: 42 Good", report)
        self.assertIn("Mesh: 24 active; camp Online", report)
        self.assertNotIn("Alerts:", report)

    def test_morning_report_omits_alerts_for_human_follow_up(self):
        alerts = self.bot.check_alerts(
            weather=Weather(
                temperature=100,
                feels_like=100,
                humidity=10,
                wind_speed=5,
                weather_code=0,
                updated=datetime.now(),
            ),
            aqi=None,
            statuses=[],
        )

        report = self.bot.build_morning_report(
            weather=self.weather,
            aqi=self.aqi,
            node_count=24,
            camp_status="Online",
            alerts=alerts,
        )

        self.assertNotIn("Alerts:", report)

    def test_morning_report_stays_within_rf_message_limit(self):
        report = self.bot.build_morning_report(
            weather=self.weather,
            aqi=self.aqi,
            node_count=24,
            camp_status="Online",
            events=["Temple Burn: " + "important " * 50],
            alerts=[],
        )

        self.assertLessEqual(len(report.encode("utf-8")), self.bot.MAX_RF_MESSAGE_BYTES)
        self.assertTrue(report.endswith("..."))

    def test_byte_limit_preserves_valid_unicode(self):
        report = self.bot._truncate_rf_message("🌤 " * 100)

        self.assertLessEqual(len(report.encode("utf-8")), self.bot.MAX_RF_MESSAGE_BYTES)
        self.assertTrue(report.endswith("..."))

    def test_status_response_uses_structured_statuses(self):
        status = SubsystemStatus(
            "mesh", "Mesh", "healthy", "24 nodes", "Connected",
        )

        self.assertEqual(self.bot.format_status([status]), "📡 Mesh: 24 nodes")


if __name__ == "__main__":
    unittest.main()
