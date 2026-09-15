from dataclasses import dataclass
from datetime import datetime


@dataclass
class Node:
    id: str
    name: str
    short_name: str
    hardware: str

    battery: int | None = None
    voltage: float | None = None

    latitude: float | None = None
    longitude: float | None = None
    altitude: int | None = None
    position_updated_at: int | None = None

    snr: float | None = None
    hops: int | None = None

    last_heard: int | None = None

    @property
    def has_position(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def hardware_name(self) -> str:
        """Return a human-friendly hardware name."""

        names = {
            "HELTEC_MESH_NODE_T114": "Heltec T114",
            "SEEED_SOLAR_NODE": "Seeed Solar Node",
            "TRACKER_T1000_E": "Seeed T1000-E",
            "T_DECK": "LilyGO T-Deck",
            "HELTEC_V3": "Heltec V3",
            "RAK4631": "RAK4631",
            "TBEAM": "LilyGO T-Beam",
            "SEEED_WIO_TRACKER_L1": "Seeed Wio Tracker L1",
            "SEEED_XIAO_S3": "Seeed XIAO S3",
            "STATION_G2": "Station G2",
        }

        return names.get(self.hardware, self.hardware)

    @property
    def battery_text(self) -> str:
        """Return a human-friendly battery string."""

        if self.battery is None:
            return "Unknown"

        if self.battery >= 101:
            return "USB Powered"

        return f"{self.battery}%"

    @property
    def voltage_text(self) -> str:
        """Return a formatted battery voltage."""

        if self.voltage is None:
            return "Unknown"

        return f"{self.voltage:.2f} V"

    @property
    def hops_text(self) -> str:
        if self.hops is None:
            return "-"

        if self.hops == 0:
            return "Local"

        if self.hops == 1:
            return "1 hop"

        return f"{self.hops} hops"

    @property
    def gps_text(self) -> str:
        return "Yes" if self.has_position else "No"

    @property
    def position_age_text(self) -> str:
        if not self.has_position:
            return "No position"
        if self.position_updated_at is None:
            return "Age unknown"

        return self._age_text(self.position_updated_at)

    @property
    def last_heard_text(self) -> str:
        if self.last_heard is None:
            return "-"

        return self._age_text(self.last_heard)

    @staticmethod
    def _age_text(timestamp: int) -> str:
        seconds = max(0, int(datetime.now().timestamp()) - timestamp)

        if seconds < 60:
            return "Just now"

        if seconds < 3600:
            return f"{seconds // 60} min ago"

        if seconds < 86_400:
            return f"{seconds // 3600} hr ago"

        return f"{seconds // 86_400} day ago" if seconds < 172_800 else f"{seconds // 86_400} days ago"
