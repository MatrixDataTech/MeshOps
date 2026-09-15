import time
import unittest

from meshops.services.meshtastic import MeshtasticService


class MeshtasticServiceTests(unittest.TestCase):
    def test_received_packet_activity_overrides_stale_library_timestamp(self):
        service = MeshtasticService()
        service.record_packet({"fromId": "!ec03f100"}, received_at=1_800_000_000)

        node = service._node_from_data(
            {
                "user": {"id": "!ec03f100", "longName": "MDT-JRN"},
                "lastHeard": 1_700_000_000,
            }
        )

        self.assertEqual(node.last_heard, 1_800_000_000)

    def test_received_packet_updates_the_current_node_cache(self):
        service = MeshtasticService()
        node = service._node_from_data({"user": {"id": "!ec03f100", "longName": "MDT-JRN"}})
        service._nodes = [node]

        service.record_packet({"from": 0xEC03F100}, received_at=1_800_000_000)

        self.assertEqual(node.last_heard, 1_800_000_000)

    def test_position_packet_updates_position_and_its_freshness_separately(self):
        service = MeshtasticService()
        node = service._node_from_data(
            {
                "user": {"id": "!sparkle", "longName": "SparkleCOC MDTf261"},
                "position": {
                    "latitude": 40.7904,
                    "longitude": -119.2165,
                    "time": 1_700_000_000,
                },
            }
        )
        service._nodes = [node]

        service.record_packet(
            {
                "fromId": "!sparkle",
                "decoded": {
                    "portnum": "POSITION_APP",
                    "position": {
                        "latitude": 40.775,
                        "longitude": -119.195,
                        "altitude": 1190,
                    },
                },
            },
            received_at=1_800_000_000,
        )

        self.assertEqual(node.last_heard, 1_800_000_000)
        self.assertEqual(node.position_updated_at, 1_800_000_000)
        self.assertEqual((node.latitude, node.longitude), (40.775, -119.195))

        refreshed = service._node_from_data(
            {
                "user": {"id": "!sparkle", "longName": "SparkleCOC MDTf261"},
                "position": {"latitude": 40.775, "longitude": -119.195},
            }
        )
        self.assertEqual(refreshed.position_updated_at, 1_800_000_000)

    def test_active_node_count_uses_the_requested_time_window(self):
        service = MeshtasticService()
        current_time = int(time.time())
        service._nodes = [
            service._node_from_data(
                {"user": {"id": "!recent", "longName": "Recent"}, "lastHeard": current_time - 60}
            ),
            service._node_from_data(
                {"user": {"id": "!old", "longName": "Old"}, "lastHeard": current_time - 18_000}
            ),
        ]

        self.assertEqual(service.active_node_count(hours=4), 1)

    def test_recent_position_nodes_excludes_stale_or_unpositioned_nodes(self):
        service = MeshtasticService()
        current_time = int(time.time())
        fresh_position = service._node_from_data(
            {
                "user": {"id": "!fresh", "longName": "Fresh"},
                "position": {
                    "latitude": 40.786,
                    "longitude": -119.205,
                    "time": current_time - 60,
                },
                "lastHeard": current_time - 60,
            }
        )
        stale_position = service._node_from_data(
            {
                "user": {"id": "!stale", "longName": "Stale"},
                "position": {
                    "latitude": 40.786,
                    "longitude": -119.205,
                    "time": current_time - 32_400,
                },
                "lastHeard": current_time - 60,
            }
        )
        fresh_without_position = service._node_from_data(
            {
                "user": {"id": "!no-position", "longName": "No Position"},
                "lastHeard": current_time - 60,
            }
        )
        unknown_position_age = service._node_from_data(
            {
                "user": {"id": "!unknown-age", "longName": "Unknown Age"},
                "position": {"latitude": 40.786, "longitude": -119.205},
                "lastHeard": current_time - 60,
            }
        )
        service._nodes = [
            fresh_position,
            stale_position,
            fresh_without_position,
            unknown_position_age,
        ]

        self.assertEqual(service.recent_position_nodes(hours=8), [fresh_position])

    def test_recent_position_nodes_keep_distinct_node_ids_with_the_same_name(self):
        service = MeshtasticService()
        current_time = int(time.time())
        earlier = service._node_from_data(
            {
                "user": {"id": "!old-jrn", "longName": "MDT-JRN"},
                "position": {
                    "latitude": 40.786,
                    "longitude": -119.205,
                    "time": current_time - 120,
                },
            }
        )
        later = service._node_from_data(
            {
                "user": {"id": "!new-jrn", "longName": "MDT-JRN"},
                "position": {
                    "latitude": 40.787,
                    "longitude": -119.206,
                    "time": current_time - 60,
                },
            }
        )
        service._nodes = [earlier, later]
        self.assertEqual(service.recent_position_nodes(hours=8), [earlier, later])


if __name__ == "__main__":
    unittest.main()
