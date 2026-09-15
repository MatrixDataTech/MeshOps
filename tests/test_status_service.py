from datetime import datetime
from types import SimpleNamespace
import unittest

from meshops.services.status import StatusService


class StatusServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = StatusService()

    def test_snapshot_has_all_subsystems_in_display_order(self):
        mesh = SimpleNamespace(
            is_connected=True,
            nodes=[],
            last_refresh_at=datetime.now(),
            last_refresh_error=None,
        )
        weather = SimpleNamespace(last_success=None, last_error=None)
        maps = SimpleNamespace(discover=lambda: [])

        statuses = self.service.snapshot(
            mesh=mesh,
            home_node=None,
            weather=weather,
            maps=maps,
            refresh_seconds=30,
        )

        self.assertEqual(
            [status.key for status in statuses],
            ["mesh", "gps", "internet", "weather", "aqi", "maps", "refresh"],
        )
        self.assertEqual(statuses[0].state, "healthy")
        self.assertEqual(statuses[-1].state, "healthy")
        self.assertEqual(statuses[4].summary, "Not configured")

    def test_snapshot_reports_covered_offline_map(self):
        offline_map = SimpleNamespace(name="Burning Man 2026")
        maps = SimpleNamespace(
            discover=lambda: [offline_map],
            map_for_coordinate=lambda latitude, longitude: offline_map,
        )
        mesh = SimpleNamespace(
            is_connected=True,
            nodes=[],
            last_refresh_at=datetime.now(),
            last_refresh_error=None,
        )
        weather = SimpleNamespace(last_success=datetime.now(), last_error=None)
        home_node = SimpleNamespace(
            name="TEAM-FLX",
            latitude=40.786,
            longitude=-119.205,
        )

        statuses = self.service.snapshot(
            mesh=mesh,
            home_node=home_node,
            weather=weather,
            maps=maps,
            refresh_seconds=30,
        )

        maps_status = next(status for status in statuses if status.key == "maps")
        self.assertEqual(maps_status.state, "healthy")
        self.assertEqual(maps_status.summary, "Burning Man 2026")

    def test_snapshot_reports_active_and_known_mesh_counts(self):
        mesh = SimpleNamespace(
            is_connected=True,
            nodes=[object(), object(), object(), object()],
            last_refresh_at=datetime.now(),
            last_refresh_error=None,
        )
        weather = SimpleNamespace(last_success=None, last_error=None)
        maps = SimpleNamespace(discover=lambda: [])

        statuses = self.service.snapshot(
            mesh=mesh,
            home_node=None,
            weather=weather,
            maps=maps,
            refresh_seconds=30,
            active_node_count=2,
        )

        self.assertEqual(statuses[0].summary, "2 active / 4 known")


if __name__ == "__main__":
    unittest.main()
