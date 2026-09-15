from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class SunTimes:
    """Local sunrise, sunset, and daylight duration for one operational day."""

    sunrise: datetime
    sunset: datetime

    @property
    def day_length(self) -> timedelta:
        return self.sunset - self.sunrise

    @property
    def day_length_text(self) -> str:
        total_minutes = round(self.day_length.total_seconds() / 60)
        return f"{total_minutes // 60}h {total_minutes % 60:02d}m"
