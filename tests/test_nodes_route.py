import asyncio
import unittest
from unittest.mock import patch

from starlette.requests import Request

from meshops.models.node import Node
from meshops.routes.nodes import nodes


class NodesRouteTests(unittest.TestCase):
    def test_nodes_page_renders_cached_node_inventory_and_controls(self):
        node = Node(
            id="!12345678",
            name="TEAM-FLX",
            short_name="FLX",
            hardware="HELTEC_V3",
            battery=87,
            hops=0,
            last_heard=1_700_000_000,
            latitude=40.79,
            longitude=-119.21,
            position_updated_at=1_699_999_000,
        )
        request = Request({"type": "http", "method": "GET", "path": "/nodes", "headers": []})

        async def render_page():
            with patch(
                "meshops.routes.nodes.meshops.context",
                return_value={"nodes": [node], "node_count": 1, "statuses": []},
            ):
                return await nodes(request)

        response = asyncio.run(render_page())
        body = response.body.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("Mesh Nodes", body)
        self.assertIn("Calculating current mesh activity", body)
        self.assertIn("TEAM-FLX", body)
        self.assertIn("Heltec V3", body)
        self.assertIn("87%", body)
        self.assertIn('data-sort-key="lastHeard"', body)
        self.assertIn('data-sort-key="positionUpdated"', body)
        self.assertIn("Last Packet Received", body)
        self.assertIn("Position Updated", body)
        self.assertIn("does not indicate when that node was last rebooted", body)
        self.assertIn('value="2"', body)
        self.assertIn('value="4" selected', body)
        self.assertIn('value="8"', body)
        self.assertIn('value="24"', body)
        self.assertIn('value="0"', body)
        self.assertIn('const isVisible = !hours || isRecent;', body)
        self.assertNotIn("MDT node(s) pinned", body)


if __name__ == "__main__":
    unittest.main()
