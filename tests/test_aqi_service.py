import unittest
from unittest.mock import Mock, patch

from meshops.services.aqi import AQIService


class AQIServiceTests(unittest.TestCase):
    @patch("meshops.services.aqi.requests.get")
    def test_returns_structured_observation_and_reuses_cache(self, get):
        response = Mock()
        response.json.return_value = {"current": {"us_aqi": 42}}
        get.return_value = response
        service = AQIService(cache_minutes=15)

        first = service.current(40.786, -119.205)
        second = service.current(40.786, -119.205)

        self.assertEqual(first.value, 42)
        self.assertEqual(first.category, "Good")
        self.assertEqual(first.indicator, "🟢")
        self.assertEqual(second, first)
        get.assert_called_once_with(
            service.URL,
            params={
                "latitude": 40.786,
                "longitude": -119.205,
                "current": "us_aqi",
            },
            timeout=10,
        )

    def test_uses_us_aqi_categories(self):
        self.assertEqual(AQIService.category_for(50), "Good")
        self.assertEqual(AQIService.category_for(51), "Moderate")
        self.assertEqual(
            AQIService.category_for(101),
            "Unhealthy for Sensitive Groups",
        )
        self.assertEqual(AQIService.category_for(301), "Hazardous")


if __name__ == "__main__":
    unittest.main()
