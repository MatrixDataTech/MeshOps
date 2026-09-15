from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from meshops.services.time_trust import SystemTimeTrust


class SystemTimeTrustTests(unittest.TestCase):
    def test_accepts_systemd_synchronization_signal(self):
        with TemporaryDirectory() as directory:
            synchronized = Path(directory) / "synchronized"
            synchronized.touch()
            trust = SystemTimeTrust(
                synchronized_path=synchronized,
                rtc_epoch_path=Path(directory) / "missing-rtc",
            )

            self.assertTrue(trust.is_trusted())

    def test_rejects_clock_without_sync_or_rtc(self):
        with TemporaryDirectory() as directory:
            trust = SystemTimeTrust(
                synchronized_path=Path(directory) / "missing-sync",
                rtc_epoch_path=Path(directory) / "missing-rtc",
            )

            self.assertFalse(trust.is_trusted())

    def test_accepts_plausible_rtc_that_matches_system_time(self):
        with TemporaryDirectory() as directory:
            now = datetime(2026, 8, 31, 15, 0, tzinfo=timezone.utc)
            rtc = Path(directory) / "since_epoch"
            rtc.write_text(str(int(now.timestamp()) - 10), encoding="utf-8")
            trust = SystemTimeTrust(
                synchronized_path=Path(directory) / "missing-sync",
                rtc_epoch_path=rtc,
                now_provider=lambda: now,
            )

            self.assertTrue(trust.is_trusted())

    def test_rejects_implausible_or_mismatched_rtc(self):
        with TemporaryDirectory() as directory:
            now = datetime(2026, 8, 31, 15, 0, tzinfo=timezone.utc)
            rtc = Path(directory) / "since_epoch"
            rtc.write_text("0", encoding="utf-8")
            trust = SystemTimeTrust(
                synchronized_path=Path(directory) / "missing-sync",
                rtc_epoch_path=rtc,
                now_provider=lambda: now,
            )

            self.assertFalse(trust.is_trusted())


if __name__ == "__main__":
    unittest.main()
