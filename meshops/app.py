from meshops.core.config import load_config
from meshops.services.aqi import AQIService
from meshops.services.bot import BotService
from meshops.services.channel_share import ChannelShareService
from meshops.services.maps import MapService
from meshops.services.meshtastic import MeshtasticService
from meshops.services.morning_update import MorningUpdateService
from meshops.services.morning_update_settings import MorningUpdateSettings
from meshops.services.outbound_messages import OutboundMessageService
from meshops.services.status import StatusService
from meshops.services.sun import SunService
from meshops.services.weather import WeatherService


class MeshOps:

    def __init__(self):

        self.config = load_config()
        self.aqi = AQIService(self.config["aqi"]["refresh_minutes"])
        self.bot = BotService()
        self.bot_channel = self.config["meshtastic"].get("bot_channel")
        self.channel_share = ChannelShareService(self.bot_channel)
        self.maps = MapService()
        self.mesh = MeshtasticService()
        self.outbound_messages = OutboundMessageService(self.bot_channel)
        self.morning_update = MorningUpdateService(
            self.bot,
            self.config["morning_update"],
            self.config["site"]["timezone"],
        )
        self.morning_update_settings = MorningUpdateSettings(self.config)
        self.status = StatusService()
        self.sun = SunService(self.config["site"]["timezone"])
        self.weather = WeatherService(
            self.config["weather"]["refresh_minutes"],
            nws_user_agent=self.config["weather"].get("nws_user_agent", WeatherService.DEFAULT_NWS_USER_AGENT),
        )

    def startup(self):
        self.mesh.connect()

    def shutdown(self):
        self.mesh.disconnect()

    def home_node(self):
        """Return the preferred home node."""

        preferred = self.config["weather"]["source_node"]

        for node in self.mesh.nodes:
            if node.name == preferred and node.has_position:
                return node

        local = self.mesh.local_node

        if local and local.has_position:
            return local

        for node in self.mesh.nodes:
            if node.has_position:
                return node

        return None

    def team_nodes(self):
        """Return the freshest cached record for each configured team node name."""

        team_prefix = str(self.config.get("team", {}).get("name_prefix", "")).strip()
        if not team_prefix:
            return []

        freshest_by_name = {}

        for node in self.mesh.nodes:
            if not node.name.startswith(team_prefix):
                continue

            existing = freshest_by_name.get(node.name)
            if existing is None or (node.last_heard or 0) > (existing.last_heard or 0):
                freshest_by_name[node.name] = node

        return sorted(freshest_by_name.values(), key=lambda node: node.name)

    def bot_context(self):
        """Build radio-command context without performing network requests."""

        return self.context(refresh_external=False)

    def context(self, *, refresh_external: bool = True):
        """Build application context, optionally refreshing external data."""
        home = self.home_node()
        active_node_hours = self.config["mesh"]["active_node_hours"]
        map_node_hours = self.config["mesh"]["map_node_hours"]
        active_node_count = self.mesh.active_node_count(active_node_hours)
        aqi = None
        sun = None
        weather = None

        if home:
            if refresh_external:
                weather = self.weather.current(home.latitude, home.longitude)
                aqi = self.aqi.current(home.latitude, home.longitude)
            else:
                weather = self.weather.cached
                aqi = self.aqi.cached
            sun = self.sun.for_location(home.latitude, home.longitude)

        return {
            "site": self.config["site"]["name"],
            "location": self.config["site"]["location"],
            "connected": self.mesh.is_connected,
            "channel_share": self.channel_share,
            "outbound_message": self.outbound_messages.status(),
            "node": self.mesh.local_node,
            "node_count": active_node_count,
            "known_node_count": len(self.mesh.nodes),
            "active_node_hours": active_node_hours,
            "nodes": self.mesh.nodes,
            "map_nodes": self.mesh.recent_position_nodes(map_node_hours),
            "map_node_hours": map_node_hours,
            "team": self.team_nodes(),
            "events": list(self.config["morning_update"].get("events", [])),
            "home_node": home,
            "weather": weather,
            "weather_node": home,
            "sun": sun,
            "aqi": aqi,
            "aqi_node": home,
            "statuses": self.status.snapshot(
                mesh=self.mesh,
                home_node=home,
                weather=self.weather,
                maps=self.maps,
                refresh_seconds=self.config["mesh"]["refresh_seconds"],
                active_node_count=active_node_count,
                aqi=self.aqi,
            ),
        }


meshops = MeshOps()
