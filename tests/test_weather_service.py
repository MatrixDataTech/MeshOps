from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import requests

from meshops.services.status import StatusService
from meshops.services.weather import WeatherService


class WeatherServiceTests(unittest.TestCase):
    def response(self):
        response = Mock()
        response.json.return_value = {
            "current": {
                "temperature_2m": 82,
                "relative_humidity_2m": 22,
                "apparent_temperature": 84,
                "weather_code": 0,
                "wind_speed_10m": 8,
            }
        }
        return response

    @patch("meshops.services.weather.requests.get")
    def test_returns_cached_observation_after_failed_refresh(self, get):
        get.side_effect = [
            self.response(),
            requests.ConnectionError("offline"),
            requests.ConnectionError("nws offline"),
        ]
        now = datetime(2026, 8, 3, 8, 0)
        with TemporaryDirectory() as directory:
            service = WeatherService(
                cache_minutes=15,
                state_path=Path(directory) / "weather.json",
                now_provider=lambda: now,
            )
            first = service.current(40.786, -119.205)
            service.now_provider = lambda: now + timedelta(minutes=16)
            fallback = service.current(40.786, -119.205)

        self.assertEqual(fallback, first)
        self.assertIn("Open-Meteo: offline", service.last_error)
        self.assertEqual(get.call_count, 3)

        weather_status = next(
            status for status in StatusService().snapshot(
                mesh=Mock(is_connected=True, nodes=[], last_refresh_at=now, last_refresh_error=None),
                home_node=None,
                weather=service,
                maps=Mock(discover=lambda: []),
                refresh_seconds=30,
            ) if status.key == "weather"
        )
        self.assertEqual(weather_status.state, "degraded")
        self.assertEqual(weather_status.summary, "Stale")

    @patch("meshops.services.weather.requests.get")
    def test_uses_nws_when_open_meteo_is_rate_limited(self, get):
        points = Mock()
        points.json.return_value = {
            "properties": {"observationStations": "https://api.weather.gov/gridpoints/STO/1,1/stations"}
        }
        stations = Mock()
        stations.json.return_value = {
            "features": [{"id": "https://api.weather.gov/stations/KSMF"}]
        }
        observation = Mock()
        observation.json.return_value = {
            "properties": {
                "temperature": {"value": 20},
                "relativeHumidity": {"value": 40},
                "windSpeed": {"value": 16},
                "heatIndex": {"value": None},
                "windChill": {"value": None},
            }
        }
        get.side_effect = [requests.HTTPError("429"), points, stations, observation]
        now = datetime(2026, 8, 3, 8, 0)
        with TemporaryDirectory() as directory:
            service = WeatherService(
                state_path=Path(directory) / "weather.json",
                now_provider=lambda: now,
            )
            weather = service.current(38.5734656, -121.4285824)

        self.assertEqual(weather.source, "NWS")
        self.assertEqual(weather.temperature, 68)
        self.assertEqual(weather.feels_like, 68)
        self.assertEqual(weather.humidity, 40)
        self.assertAlmostEqual(weather.wind_speed, 9.94, places=2)
        self.assertIsNone(service.last_error)
        self.assertEqual(get.call_count, 4)

        status = next(
            item for item in StatusService().snapshot(
                mesh=Mock(is_connected=True, nodes=[], last_refresh_at=now, last_refresh_error=None),
                home_node=None,
                weather=service,
                maps=Mock(discover=lambda: []),
                refresh_seconds=30,
            ) if item.key == "weather"
        )
        self.assertEqual(status.summary, "NWS fallback")

    @patch("meshops.services.weather.requests.get")
    def test_daily_open_meteo_limit_uses_nws_until_the_next_day(self, get):
        daily_limit = Mock()
        daily_limit.status_code = 429
        daily_limit.json.return_value = {
            "reason": "Daily API request limit exceeded. Please try again tomorrow."
        }
        points = Mock()
        points.json.return_value = {
            "properties": {"observationStations": "https://api.weather.gov/stations"}
        }
        stations = Mock()
        stations.json.return_value = {
            "features": [{"id": "https://api.weather.gov/stations/KSMF"}]
        }
        observation = Mock()
        observation.json.return_value = {
            "properties": {
                "temperature": {"value": 20},
                "relativeHumidity": {"value": 40},
                "windSpeed": {"value": 16},
                "heatIndex": {"value": None},
                "windChill": {"value": None},
            }
        }
        now = datetime(2026, 8, 3, 8, 0)
        with TemporaryDirectory() as directory:
            state_path = Path(directory) / "weather.json"
            get.side_effect = [
                daily_limit,
                points,
                stations,
                observation,
                observation,
                points,
                stations,
                observation,
            ]
            service = WeatherService(state_path=state_path, now_provider=lambda: now)
            first = service.current(38.5734656, -121.4285824)

            service.now_provider = lambda: now + timedelta(minutes=16)
            second = service.current(38.5734656, -121.4285824)

            restarted = WeatherService(
                state_path=state_path,
                now_provider=lambda: now + timedelta(minutes=32),
            )
            third = restarted.current(38.5734656, -121.4285824)

        self.assertEqual(first.source, "NWS")
        self.assertEqual(second.source, "NWS")
        self.assertEqual(third.source, "NWS")
        self.assertEqual(service.open_meteo_blocked_until, datetime(2026, 8, 4))
        self.assertEqual(restarted.open_meteo_blocked_until, datetime(2026, 8, 4))
        self.assertEqual(get.call_count, 8)
        self.assertTrue(all("open-meteo.com" not in call.args[0] for call in get.call_args_list[4:]))

    @patch("meshops.services.weather.requests.get")
    def test_nws_failure_during_daily_limit_cooldown_is_delayed(self, get):
        points = Mock()
        points.json.return_value = {
            "properties": {"observationStations": "https://api.weather.gov/stations"}
        }
        stations = Mock()
        stations.json.return_value = {
            "features": [{"id": "https://api.weather.gov/stations/KSAC"}]
        }
        incomplete_observation = Mock()
        incomplete_observation.json.return_value = {
            "properties": {
                "temperature": {"value": 40},
                "relativeHumidity": {"value": None},
                "windSpeed": {"value": 0},
                "heatIndex": {"value": None},
                "windChill": {"value": None},
            }
        }
        get.side_effect = [points, stations, incomplete_observation]
        now = datetime(2026, 8, 3, 16, 0)
        with TemporaryDirectory() as directory:
            service = WeatherService(
                state_path=Path(directory) / "weather.json",
                now_provider=lambda: now,
            )
            service.open_meteo_blocked_until = datetime(2026, 8, 4)
            first = service.current(38.5734656, -121.4285824)
            service.now_provider = lambda: now + timedelta(minutes=1)
            second = service.current(38.5734656, -121.4285824)

        self.assertIsNone(first)
        self.assertIsNone(second)
        self.assertEqual(get.call_count, 3)
        self.assertIn("daily-limit cooldown active", service.last_error)

    @patch("meshops.services.weather.requests.get")
    def test_persists_cache_across_restart_and_delays_failed_retries(self, get):
        now = datetime(2026, 8, 3, 8, 0)
        with TemporaryDirectory() as directory:
            state_path = Path(directory) / "weather.json"
            get.return_value = self.response()
            first_service = WeatherService(
                state_path=state_path,
                now_provider=lambda: now,
            )
            first = first_service.current(40.786, -119.205)

            get.side_effect = requests.ConnectionError("rate limited")
            restarted_service = WeatherService(
                state_path=state_path,
                now_provider=lambda: now + timedelta(minutes=16),
            )
            fallback = restarted_service.current(40.786, -119.205)
            second = restarted_service.current(40.786, -119.205)

        self.assertEqual(fallback, first)
        self.assertEqual(second, first)
        self.assertEqual(get.call_count, 3)
        self.assertIn("rate limited", restarted_service.last_error)

    @patch("meshops.services.weather.requests.get")
    def test_reuses_fresh_cache_without_another_request(self, get):
        get.return_value = self.response()
        now = datetime(2026, 8, 3, 8, 0)
        with TemporaryDirectory() as directory:
            service = WeatherService(
                cache_minutes=15,
                state_path=Path(directory) / "weather.json",
                now_provider=lambda: now,
            )
            first = service.current(40.786, -119.205)
            service.now_provider = lambda: now + timedelta(minutes=5)
            second = service.current(40.786, -119.205)

        self.assertEqual(second, first)
        get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
