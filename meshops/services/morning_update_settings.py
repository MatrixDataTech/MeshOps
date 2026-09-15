"""Validated persistence for editable Morning Update settings."""

from datetime import time
from pathlib import Path

import yaml

from meshops.core.config import CONFIG_FILE


class MorningUpdateSettings:
    """Update the Morning Update section without replacing the application config."""

    def __init__(self, config: dict, config_path: Path = CONFIG_FILE):
        self.config = config
        self.config_path = config_path

    def values(self) -> dict:
        """Return a copy suitable for rendering or API responses."""

        settings = self.config["morning_update"]
        return {
            "enabled": settings["enabled"],
            "time": settings["time"],
            "events": list(settings.get("events", [])),
        }

    def update(self, *, enabled: bool, scheduled_time: str, events: list[str]) -> dict:
        """Validate and persist settings with an atomic file replacement."""

        if not isinstance(enabled, bool):
            raise ValueError("Enabled must be true or false.")

        try:
            parsed_time = time.fromisoformat(scheduled_time)
        except (TypeError, ValueError) as exc:
            raise ValueError("Time must use HH:MM format.") from exc

        if parsed_time.second or parsed_time.microsecond:
            raise ValueError("Time must use HH:MM format.")

        cleaned_events = [event.strip() for event in events if event.strip()]
        if len(cleaned_events) > 20:
            raise ValueError("Use no more than 20 event lines.")
        if any(len(event) > 160 for event in cleaned_events):
            raise ValueError("Each event line must be 160 characters or fewer.")

        settings = self.config["morning_update"]
        settings["enabled"] = enabled
        settings["time"] = parsed_time.strftime("%H:%M")
        settings["events"] = cleaned_events

        temporary_path = self.config_path.with_suffix(".tmp")
        temporary_path.write_text(
            yaml.safe_dump(self.config, sort_keys=False),
            encoding="utf-8",
        )
        temporary_path.replace(self.config_path)
        return self.values()
