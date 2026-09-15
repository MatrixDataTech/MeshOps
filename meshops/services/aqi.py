"""Retrieve and cache current air-quality observations."""

from datetime import datetime, timedelta

import requests

from meshops.models.air_quality import AirQuality


class AQIService:
    """Retrieve current U.S. AQI from Open-Meteo for the Home Node location."""

    URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

    def __init__(self, cache_minutes: int = 15):
        self.cache_duration = timedelta(minutes=cache_minutes)
        self.last_success: datetime | None = None
        self.last_error: str | None = None
        self._cached: AirQuality | None = None

    @property
    def cached(self) -> AirQuality | None:
        """Return the latest observation without performing network I/O."""

        return self._cached

    def current(self, latitude: float, longitude: float) -> AirQuality | None:
        """Return cached AQI when fresh, otherwise refresh it from the provider."""

        if self._cached is not None and self._cache_is_fresh():
            return self._cached

        try:
            response = requests.get(
                self.URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": "us_aqi",
                },
                timeout=10,
            )
            response.raise_for_status()
            value = round(response.json()["current"]["us_aqi"])
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            self.last_error = str(exc)
            return self._cached

        updated = datetime.now()
        self._cached = AirQuality(
            value=value,
            category=self.category_for(value),
            indicator=self.indicator_for(value),
            updated=updated,
        )
        self.last_success = updated
        self.last_error = None
        return self._cached

    def _cache_is_fresh(self) -> bool:
        return datetime.now() - self._cached.updated < self.cache_duration

    @staticmethod
    def category_for(value: int) -> str:
        if value <= 50:
            return "Good"
        if value <= 100:
            return "Moderate"
        if value <= 150:
            return "Unhealthy for Sensitive Groups"
        if value <= 200:
            return "Unhealthy"
        if value <= 300:
            return "Very Unhealthy"
        return "Hazardous"

    @staticmethod
    def indicator_for(value: int) -> str:
        if value <= 50:
            return "🟢"
        if value <= 100:
            return "🟡"
        if value <= 150:
            return "🟠"
        if value <= 200:
            return "🔴"
        if value <= 300:
            return "🟣"
        return "🟤"
