"""Determine whether wall-clock time is safe for calendar scheduling."""

from datetime import datetime, timezone
from pathlib import Path


class SystemTimeTrust:
    """Accept systemd-synchronized time or a plausible matching hardware RTC."""

    MINIMUM_TRUSTED_EPOCH = int(
        datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()
    )

    def __init__(
        self,
        synchronized_path: Path = Path("/run/systemd/timesync/synchronized"),
        rtc_epoch_path: Path = Path("/sys/class/rtc/rtc0/since_epoch"),
        now_provider=lambda: datetime.now(timezone.utc),
        rtc_tolerance_seconds: int = 300,
    ):
        self.synchronized_path = synchronized_path
        self.rtc_epoch_path = rtc_epoch_path
        self.now_provider = now_provider
        self.rtc_tolerance_seconds = rtc_tolerance_seconds

    def is_trusted(self) -> bool:
        """Return true only for a clock confirmed by time sync or a valid RTC."""

        if self.synchronized_path.exists():
            return True

        try:
            rtc_epoch = int(self.rtc_epoch_path.read_text(encoding="utf-8").strip())
        except (FileNotFoundError, OSError, TypeError, ValueError):
            return False

        system_epoch = int(self.now_provider().timestamp())
        return (
            rtc_epoch >= self.MINIMUM_TRUSTED_EPOCH
            and system_epoch >= self.MINIMUM_TRUSTED_EPOCH
            and abs(system_epoch - rtc_epoch) <= self.rtc_tolerance_seconds
        )
