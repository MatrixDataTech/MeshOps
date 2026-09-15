from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import yaml

from meshops.services.morning_update_settings import MorningUpdateSettings


class MorningUpdateSettingsTests(unittest.TestCase):
    def test_persists_valid_settings_and_keeps_runtime_mapping_current(self):
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "meshops.yaml"
            config = {
                "morning_update": {
                    "enabled": True,
                    "time": "08:00",
                    "events": [],
                }
            }
            settings = MorningUpdateSettings(config, config_path)

            saved = settings.update(
                enabled=False,
                scheduled_time="06:30",
                events=["Temple Burn: 8:00 PM", ""],
            )

            self.assertEqual(
                saved,
                {
                    "enabled": False,
                    "time": "06:30",
                    "events": ["Temple Burn: 8:00 PM"],
                },
            )
            self.assertEqual(config["morning_update"]["time"], "06:30")
            self.assertEqual(yaml.safe_load(config_path.read_text()), config)

    def test_rejects_invalid_time_without_writing(self):
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "meshops.yaml"
            config = {
                "morning_update": {
                    "enabled": True,
                    "time": "08:00",
                    "events": [],
                }
            }
            settings = MorningUpdateSettings(config, config_path)

            with self.assertRaisesRegex(ValueError, "HH:MM"):
                settings.update(enabled=True, scheduled_time="tomorrow", events=[])

            self.assertFalse(config_path.exists())
            self.assertEqual(config["morning_update"]["time"], "08:00")


if __name__ == "__main__":
    unittest.main()
