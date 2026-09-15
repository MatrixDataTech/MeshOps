"""Transport-independent operational message and alert logic."""

from datetime import datetime, timedelta

from meshops.models.air_quality import AirQuality
from meshops.models.alert import Alert
from meshops.models.node import Node
from meshops.models.sun import SunTimes
from meshops.models.weather import Weather
from meshops.services.status import SubsystemStatus


class BotService:
    """Build concise operational responses without sending them anywhere."""

    HIGH_TEMPERATURE = 95
    HIGH_WIND = 25
    POOR_AQI = 151
    STALE_AFTER = timedelta(minutes=30)
    MAX_RF_MESSAGE_BYTES = 220
    MAX_RF_MESSAGE_LENGTH = MAX_RF_MESSAGE_BYTES
    STATUS_ICONS = {
        "mesh": "📡",
        "gps": "📍",
        "weather": "🌤",
        "aqi": "🌫",
        "internet": "🌐",
        "maps": "🗺",
        "refresh": "🔄",
    }

    def __init__(self):
        self._active_alert_keys: set[str] = set()

    def handle_command(self, command: str, **context) -> str:
        """Dispatch a supported command using supplied application data."""

        command = command.strip().lower()

        if command == "weather":
            return self.format_weather(context.get("weather"), context.get("aqi"))
        if command == "aqi":
            return self.format_aqi(context.get("aqi"))
        if command == "status":
            return self.format_status(context.get("statuses", []))
        if command == "team":
            return self.format_team(context.get("team", []))
        if command == "sun":
            return self.format_sun(context.get("sun"))
        if command in {"burns", "events"}:
            return self.format_events(context.get("events", []))
        if command == "help":
            return "Commands: weather, aqi, status, team, sun, burns."

        return "Unknown command. Try: weather, aqi, status, team, sun, burns."

    def format_weather(
        self,
        weather: Weather | None,
        aqi: AirQuality | None = None,
    ) -> str:
        """Return a compact weather response suitable for an RF channel."""

        if weather is None:
            return "🌤 Weather unavailable."

        lines = [
            "🌤 Camp Weather",
            f"{weather.temperature:.0f}°F (feels {weather.feels_like:.0f}°F)",
            f"Humidity {weather.humidity}%",
            f"Wind {weather.wind_speed:.0f} mph",
        ]

        if aqi is not None:
            lines.append(f"🌫 AQI {aqi.value} ({aqi.category})")

        lines.append(f"Updated {self._age_text(weather.updated)}")
        return self._truncate_rf_message("\n".join(lines))

    def format_sun(self, sun: SunTimes | None) -> str:
        """Return concise local sunrise and sunset information."""

        if sun is None:
            return "Sun times unavailable."

        return (
            f"Sunrise {sun.sunrise.strftime('%-I:%M %p')}. "
            f"Sunset {sun.sunset.strftime('%-I:%M %p')}. "
            f"Daylight {sun.day_length_text}."
        )

    def format_events(self, events: list[str]) -> str:
        """Return the operational event list in a compact RF-friendly form."""

        items = [event.strip() for event in events if event.strip()]
        if not items:
            return "No scheduled burns or operational events."

        return self._truncate_rf_message("Burns\n" + "\n".join(items))

    def format_aqi(self, aqi: AirQuality | None) -> str:
        """Return a compact AQI response."""

        if aqi is None:
            return "🌫 AQI unavailable."

        return (
            f"🌫 AQI {aqi.value}: {aqi.category}. "
            f"Updated {self._age_text(aqi.updated)}."
        )

    def format_status(self, statuses: list[SubsystemStatus]) -> str:
        """Return a compact system summary from structured status data."""

        if not statuses:
            return "System status unavailable."

        return self._truncate_rf_message("\n".join(
            f"{self.STATUS_ICONS.get(status.key, '•')} "
            f"{status.label}: {status.summary}"
            for status in statuses
        ))

    def format_team(self, nodes: list[Node]) -> str:
        """Return configured team-node freshness and battery."""

        if not nodes:
            return "No team nodes."

        return "\n".join(
            f"{node.name}: {node.last_heard_text}, {node.battery_text}"
            for node in nodes
        )

    def check_alerts(
        self,
        *,
        weather: Weather | None,
        aqi: AirQuality | None,
        statuses: list[SubsystemStatus],
        camp_node: Node | None = None,
        repeated_node_failures: int = 0,
        rain_expected: bool = False,
    ) -> list[Alert]:
        """Return newly active alerts and suppress repeated identical alerts."""

        candidates = self._alert_candidates(
            weather=weather,
            aqi=aqi,
            statuses=statuses,
            camp_node=camp_node,
            repeated_node_failures=repeated_node_failures,
            rain_expected=rain_expected,
        )
        candidate_keys = {alert.key for alert in candidates}
        new_alerts = [
            alert for alert in candidates if alert.key not in self._active_alert_keys
        ]

        self._active_alert_keys = candidate_keys
        return new_alerts

    def current_alerts(
        self,
        *,
        weather: Weather | None,
        aqi: AirQuality | None,
        statuses: list[SubsystemStatus],
        camp_node: Node | None = None,
    ) -> list[Alert]:
        """Return current alerts without changing duplicate-suppression state."""

        return self._alert_candidates(
            weather=weather,
            aqi=aqi,
            statuses=statuses,
            camp_node=camp_node,
            repeated_node_failures=0,
            rain_expected=False,
        )

    def build_morning_report(
        self,
        *,
        weather: Weather | None,
        aqi: AirQuality | None,
        sun: SunTimes | None = None,
        events: list[str] | None = None,
        node_count: int,
        team_count: int = 0,
        camp_status: str,
        statuses: list[SubsystemStatus] | None = None,
        alerts: list[Alert],
    ) -> str:
        """Return a compact operational report suitable for radio transmission."""

        event_items = [item.strip() for item in (events or []) if item.strip()]
        event_text = "; ".join(event_items) or "None"
        sun_text = "Unavailable"

        if sun is not None:
            sun_text = (
                f"{sun.sunrise.strftime('%-I:%M %p')} / "
                f"{sun.sunset.strftime('%-I:%M %p')}"
            )

        weather_text = "unavailable"
        if weather is not None:
            weather_text = (
                f"{weather.temperature:.0f}F feels {weather.feels_like:.0f}F, "
                f"RH {weather.humidity}%, wind {weather.wind_speed:.0f}mph"
            )
            if self._is_stale(weather.updated):
                weather_text += " (stale)"

        aqi_text = "unavailable"
        if aqi is not None:
            aqi_text = f"{aqi.value} {aqi.category}"
            if self._is_stale(aqi.updated):
                aqi_text += " (stale)"

        lines = [
            "Good Morning",
            f"Weather: {weather_text}",
            f"AQI: {aqi_text}",
            f"Mesh: {node_count} active; camp {camp_status}; team {team_count}",
            f"Sun: {sun_text}",
            f"Events: {event_text}",
        ]

        return self._truncate_rf_message("\n".join(lines))

    def _truncate_rf_message(self, message: str) -> str:
        if len(message.encode("utf-8")) <= self.MAX_RF_MESSAGE_BYTES:
            return message

        marker = "..."
        truncated = message
        while len(f"{truncated}{marker}".encode("utf-8")) > self.MAX_RF_MESSAGE_BYTES:
            truncated = truncated[:-1]

        return f"{truncated.rstrip()}{marker}"

    def _alert_candidates(
        self,
        *,
        weather: Weather | None,
        aqi: AirQuality | None,
        statuses: list[SubsystemStatus],
        camp_node: Node | None,
        repeated_node_failures: int,
        rain_expected: bool,
    ) -> list[Alert]:
        alerts = []

        if rain_expected:
            alerts.append(Alert("rain-expected", "warning", "Rain expected."))

        if weather is not None:
            if weather.temperature >= self.HIGH_TEMPERATURE:
                alerts.append(Alert("high-temperature", "warning", "High temperature."))
            if weather.wind_speed >= self.HIGH_WIND:
                alerts.append(Alert("high-wind", "warning", "High wind."))
            if self._is_stale(weather.updated):
                alerts.append(Alert("weather-stale", "warning", "Weather is stale."))

        if aqi is not None:
            if aqi.value >= self.POOR_AQI:
                alerts.append(Alert("poor-aqi", "warning", "Poor AQI."))
            if self._is_stale(aqi.updated):
                alerts.append(Alert("aqi-stale", "warning", "AQI is stale."))

        status_by_key = {status.key: status for status in statuses}
        mesh_status = status_by_key.get("mesh")
        internet_status = status_by_key.get("internet")

        if mesh_status is not None and mesh_status.state in {"degraded", "unavailable"}:
            alerts.append(Alert("mesh-unavailable", "critical", "Mesh disconnected."))

        if internet_status is not None and internet_status.state == "unavailable":
            alerts.append(Alert("internet-unavailable", "warning", "Internet unavailable."))

        if camp_node is not None and self._camp_node_is_stale(camp_node):
            alerts.append(Alert("camp-node-offline", "critical", "Camp node offline."))

        if repeated_node_failures > 1:
            alerts.append(Alert("repeated-node-failures", "warning", "Repeated node failures."))

        return alerts

    def _is_stale(self, updated: datetime) -> bool:
        return datetime.now() - updated > self.STALE_AFTER

    @staticmethod
    def _camp_node_is_stale(node: Node) -> bool:
        if node.last_heard is None:
            return True

        return datetime.now().timestamp() - node.last_heard > 300

    @staticmethod
    def _age_text(updated: datetime) -> str:
        seconds = max(0, int((datetime.now() - updated).total_seconds()))

        if seconds < 60:
            return "just now"
        if seconds < 3600:
            return f"{seconds // 60}m ago"
        return f"{seconds // 3600}h ago"
