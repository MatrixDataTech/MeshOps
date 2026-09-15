from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from meshops.app import MeshOps
from meshops.models.node import Node


class MeshOpsTeamNodesTests(unittest.TestCase):
    def test_team_nodes_uses_the_freshest_record_for_each_configured_name(self):
        app = MeshOps.__new__(MeshOps)
        old_flx = Node("!oldflx", "TEAM-FLX", "FLX", "SEEED_SOLAR_NODE", last_heard=100)
        fresh_flx = Node("!newflx", "TEAM-FLX", "FLX", "SEEED_SOLAR_NODE", last_heard=200)
        jrn = Node("!jrn", "TEAM-JRN", "JRN", "TRACKER_T1000_E", last_heard=150)
        public_node = Node("!public", "Other Node", "OTH", "HELTEC_V3", last_heard=300)
        app.mesh = SimpleNamespace(nodes=[old_flx, fresh_flx, jrn, public_node])
        app.config = {"team": {"name_prefix": "TEAM-"}}

        team = app.team_nodes()

        self.assertEqual([node.name for node in team], ["TEAM-FLX", "TEAM-JRN"])
        self.assertEqual(team[0].id, "!newflx")

    def test_team_nodes_returns_no_nodes_without_a_prefix(self):
        app = MeshOps.__new__(MeshOps)
        app.mesh = SimpleNamespace(nodes=[Node("!one", "TEAM-FLX", "FLX", "RAK4631")])
        app.config = {"team": {"name_prefix": ""}}

        self.assertEqual(app.team_nodes(), [])

    def test_bot_context_disables_external_refresh(self):
        app = MeshOps.__new__(MeshOps)
        app.context = Mock(return_value={"weather": "cached"})

        context = app.bot_context()

        self.assertEqual(context, {"weather": "cached"})
        app.context.assert_called_once_with(refresh_external=False)


if __name__ == "__main__":
    unittest.main()
