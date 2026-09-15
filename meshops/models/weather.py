from dataclasses import dataclass
from datetime import datetime


@dataclass
class Weather:
    temperature: float
    feels_like: float
    humidity: int
    wind_speed: float
    weather_code: int
    updated: datetime
    source: str = "Open-Meteo"
