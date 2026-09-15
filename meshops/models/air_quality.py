from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AirQuality:
    """A current U.S. Air Quality Index observation."""

    value: int
    category: str
    indicator: str
    updated: datetime
