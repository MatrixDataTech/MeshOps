from datetime import datetime, timedelta
import json
import logging
from pathlib import Path

import requests

from meshops.models.weather import Weather


log = logging.getLogger(__name__)


class OpenMeteoDailyLimitError(requests.HTTPError):
    """Raised when Open-Meteo reports that its daily request allowance is exhausted."""


class WeatherService:
    """Retrieve weather with NWS fallback and persistent local caching."""

    URL = "https://api.open-meteo.com/v1/forecast"
    NWS_POINTS_URL = "https://api.weather.gov/points/{latitude},{longitude}"
    DEFAULT_STATE_FILE = Path(".meshops-state/weather.json")
    DEFAULT_NWS_USER_AGENT = "MeshOps/0.1 (https://github.com/MatrixDataTech/MeshOps)"

    def __init__(
        self,
        cache_minutes: int = 15,
        retry_minutes: int = 5,
        state_path: Path = DEFAULT_STATE_FILE,
        nws_user_agent: str = DEFAULT_NWS_USER_AGENT,
        now_provider=datetime.now,
    ):
        self.cache_duration = timedelta(minutes=cache_minutes)
        self.retry_duration = timedelta(minutes=retry_minutes)
        self.state_path = state_path
        self.nws_headers = {
            "Accept": "application/geo+json",
            "User-Agent": nws_user_agent,
        }
        self.now_provider = now_provider
        self.last_success: datetime | None = None
        self.last_attempt: datetime | None = None
        self.last_error: str | None = None
        self.last_primary_error: str | None = None
        self.last_observation: Weather | None = None
        self.open_meteo_blocked_until: datetime | None = None
        self._nws_observation_urls: dict[tuple[float, float], str] = {}
        self._load_cached_observation()

    @property
    def cached(self) -> Weather | None:
        """Return the latest observation without performing network I/O."""

        return self.last_observation

    def current(self, latitude: float, longitude: float) -> Weather | None:
        """Return weather from cache, Open-Meteo, NWS, or the last good reading."""

        now = self.now_provider()
        if self._cache_is_fresh(now) or self._retry_is_delayed(now):
            return self.last_observation

        self.last_attempt = now
        if self._open_meteo_is_blocked(now):
            return self._fallback_to_nws(latitude, longitude, now, None)

        try:
            observation = self._fetch_open_meteo(latitude, longitude, now)
        except OpenMeteoDailyLimitError as primary_error:
            self._begin_open_meteo_daily_limit_cooldown(now, primary_error)
            return self._fallback_to_nws(latitude, longitude, now, primary_error)
        except (requests.RequestException, KeyError, TypeError, ValueError) as primary_error:
            self.last_primary_error = str(primary_error)
            return self._fallback_to_nws(latitude, longitude, now, primary_error)

        self._store_observation(observation, now)
        self.last_primary_error = None
        return observation

    def _fetch_open_meteo(self, latitude: float, longitude: float, now: datetime) -> Weather:
        response = requests.get(
            self.URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": (
                    "temperature_2m,"
                    "relative_humidity_2m,"
                    "apparent_temperature,"
                    "weather_code,"
                    "wind_speed_10m"
                ),
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
            },
            timeout=10,
        )
        if response.status_code == 429:
            try:
                reason = response.json().get("reason", "")
            except (TypeError, ValueError):
                reason = ""
            if "daily api request limit exceeded" in reason.lower():
                raise OpenMeteoDailyLimitError(reason)
        response.raise_for_status()
        current = response.json()["current"]
        return Weather(
            temperature=current["temperature_2m"],
            feels_like=current["apparent_temperature"],
            humidity=current["relative_humidity_2m"],
            wind_speed=current["wind_speed_10m"],
            weather_code=current["weather_code"],
            updated=now,
            source="Open-Meteo",
        )

    def _fallback_to_nws(
        self,
        latitude: float,
        longitude: float,
        now: datetime,
        primary_error: Exception | None,
    ) -> Weather | None:
        try:
            observation = self._fetch_nws_observation(latitude, longitude, now)
        except (requests.RequestException, KeyError, TypeError, ValueError, IndexError) as nws_error:
            primary_message = (
                str(primary_error)
                if primary_error is not None
                else "daily-limit cooldown active"
            )
            self.last_error = f"Open-Meteo: {primary_message}; NWS: {nws_error}"
            log.warning("Weather refresh failed; retaining cached weather: %s", self.last_error)
            return self.last_observation

        self._store_observation(observation, now)
        if primary_error is not None:
            log.warning("Open-Meteo refresh failed; using NWS fallback: %s", primary_error)
        return observation

    def _fetch_nws_observation(self, latitude: float, longitude: float, now: datetime) -> Weather:
        key = (round(latitude, 4), round(longitude, 4))
        observation_url = self._nws_observation_urls.get(key)

        if observation_url is None:
            points = requests.get(
                self.NWS_POINTS_URL.format(latitude=key[0], longitude=key[1]),
                headers=self.nws_headers,
                timeout=10,
            )
            points.raise_for_status()
            stations_url = points.json()["properties"]["observationStations"]
            stations = requests.get(
                stations_url,
                headers=self.nws_headers,
                timeout=10,
            )
            stations.raise_for_status()
            station_url = stations.json()["features"][0]["id"]
            observation_url = f"{station_url}/observations/latest"
            self._nws_observation_urls[key] = observation_url

        response = requests.get(
            observation_url,
            headers=self.nws_headers,
            timeout=10,
        )
        response.raise_for_status()
        properties = response.json()["properties"]
        temperature = self._celsius_to_fahrenheit(properties["temperature"]["value"])
        humidity = properties["relativeHumidity"]["value"]
        wind_speed = properties.get("windSpeed", {}).get("value")
        feels_like = self._first_celsius_value(
            properties.get("heatIndex", {}).get("value"),
            properties.get("windChill", {}).get("value"),
            properties["temperature"]["value"],
        )

        if temperature is None or humidity is None:
            raise ValueError("NWS observation is missing temperature or humidity.")

        return Weather(
            temperature=temperature,
            feels_like=feels_like,
            humidity=round(humidity),
            wind_speed=(wind_speed or 0) * 0.621371,
            weather_code=0,
            updated=now,
            source="NWS",
        )

    def _store_observation(self, observation: Weather, now: datetime) -> None:
        self.last_observation = observation
        self.last_success = now
        self.last_error = None
        self._persist_cached_observation()

    @staticmethod
    def _celsius_to_fahrenheit(value: float | int | None) -> float | None:
        if value is None:
            return None
        return value * 9 / 5 + 32

    def _first_celsius_value(self, *values: float | int | None) -> float:
        for value in values:
            converted = self._celsius_to_fahrenheit(value)
            if converted is not None:
                return converted
        raise ValueError("NWS observation is missing apparent temperature.")

    def _cache_is_fresh(self, now: datetime) -> bool:
        return (
            self.last_observation is not None
            and self.last_success is not None
            and now - self.last_success < self.cache_duration
        )

    def _retry_is_delayed(self, now: datetime) -> bool:
        return (
            self.last_error is not None
            and self.last_attempt is not None
            and now - self.last_attempt < self.retry_duration
        )

    def _open_meteo_is_blocked(self, now: datetime) -> bool:
        return (
            self.open_meteo_blocked_until is not None
            and now < self.open_meteo_blocked_until
        )

    def _begin_open_meteo_daily_limit_cooldown(
        self,
        now: datetime,
        error: OpenMeteoDailyLimitError,
    ) -> None:
        tomorrow = (now + timedelta(days=1)).date()
        self.open_meteo_blocked_until = datetime.combine(tomorrow, datetime.min.time())
        self.last_primary_error = (
            f"Open-Meteo daily request limit reached; retrying after "
            f"{self.open_meteo_blocked_until.isoformat(timespec='minutes')} ({error})"
        )

    def _load_cached_observation(self) -> None:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            updated = datetime.fromisoformat(payload["updated"])
            self.last_observation = Weather(
                temperature=payload["temperature"],
                feels_like=payload["feels_like"],
                humidity=payload["humidity"],
                wind_speed=payload["wind_speed"],
                weather_code=payload["weather_code"],
                updated=updated,
                source=payload.get("source", "Open-Meteo"),
            )
            self.last_success = updated
            blocked_until = payload.get("open_meteo_blocked_until")
            if blocked_until:
                self.open_meteo_blocked_until = datetime.fromisoformat(blocked_until)
        except (FileNotFoundError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return

    def _persist_cached_observation(self) -> None:
        if self.last_observation is None:
            return

        observation = self.last_observation
        payload = {
            "temperature": observation.temperature,
            "feels_like": observation.feels_like,
            "humidity": observation.humidity,
            "wind_speed": observation.wind_speed,
            "weather_code": observation.weather_code,
            "updated": observation.updated.isoformat(),
            "source": observation.source,
            "open_meteo_blocked_until": (
                self.open_meteo_blocked_until.isoformat()
                if self.open_meteo_blocked_until is not None
                else None
            ),
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.state_path.with_suffix(".tmp")
        temporary_path.write_text(json.dumps(payload), encoding="utf-8")
        temporary_path.replace(self.state_path)
