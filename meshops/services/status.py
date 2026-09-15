"""Build structured, presentation-independent subsystem health status."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from meshops.models.node import Node
from meshops.services.aqi import AQIService
from meshops.services.maps import MapService
from meshops.services.meshtastic import MeshtasticService
from meshops.services.weather import WeatherService


StatusState = Literal["healthy", "degraded", "unavailable", "unknown"]


@dataclass(frozen=True)
class SubsystemStatus:
    """A status-bar-ready description of one MeshOps subsystem."""

    key: str
    label: str
    state: StatusState
    summary: str
    detail: str


class StatusService:
    """Expose the operational health of MeshOps subsystems as structured data."""

    def snapshot(
        self,
        *,
        mesh: MeshtasticService,
        home_node: Node | None,
        weather: WeatherService,
        maps: MapService,
        refresh_seconds: int,
        aqi: AQIService | None = None,
        active_node_count: int | None = None,
    ) -> list[SubsystemStatus]:
        """Return statuses in the order intended for the shared status bar."""

        return [
            self._mesh_status(mesh, active_node_count),
            self._gps_status(home_node),
            self._internet_status(weather),
            self._weather_status(weather),
            self._aqi_status(aqi),
            self._maps_status(maps, home_node),
            self._refresh_status(mesh, refresh_seconds),
        ]

    @staticmethod
    def _mesh_status(
        mesh: MeshtasticService,
        active_node_count: int | None,
    ) -> SubsystemStatus:
        if not mesh.is_connected:
            return SubsystemStatus(
                "mesh", "Mesh", "unavailable", "Disconnected",
                "The local Meshtastic connection is not active.",
            )

        if mesh.last_refresh_error:
            return SubsystemStatus(
                "mesh", "Mesh", "degraded", "Refresh error",
                mesh.last_refresh_error,
            )

        summary = f"{len(mesh.nodes)} known nodes"
        if active_node_count is not None:
            summary = f"{active_node_count} active / {len(mesh.nodes)} known"

        return SubsystemStatus(
            "mesh", "Mesh", "healthy", summary,
            "The local Meshtastic connection is active.",
        )

    @staticmethod
    def _gps_status(home_node: Node | None) -> SubsystemStatus:
        if home_node is None:
            return SubsystemStatus(
                "gps", "GPS", "unavailable", "No position",
                "No configured Home Node or other mesh node has a usable position.",
            )

        return SubsystemStatus(
            "gps", "GPS", "healthy", home_node.name,
            "The Home Node has a usable GPS position.",
        )

    @staticmethod
    def _internet_status(weather: WeatherService) -> SubsystemStatus:
        if weather.last_error:
            return SubsystemStatus(
                "internet", "Internet", "degraded", "Weather retrying",
                f"The most recent weather request failed: {weather.last_error}",
            )

        if weather.last_success is not None:
            return SubsystemStatus(
                "internet", "Internet", "healthy", "Reachable",
                "Confirmed by the most recent successful weather request.",
            )

        if weather.last_error:
            return SubsystemStatus(
                "internet", "Internet", "unknown", "Not confirmed",
                "The most recent weather request failed; this alone cannot identify the cause.",
            )

        return SubsystemStatus(
            "internet", "Internet", "unknown", "Not checked",
            "No external request has completed during this application run.",
        )

    @staticmethod
    def _weather_status(weather: WeatherService) -> SubsystemStatus:
        if weather.last_success is not None and weather.last_error:
            return SubsystemStatus(
                "weather", "Weather", "degraded", "Stale",
                f"Last good update: {weather.last_success:%H:%M:%S}. Latest error: {weather.last_error}",
            )

        if (
            weather.last_success is not None
            and getattr(weather, "last_observation", None) is not None
            and weather.last_observation.source == "NWS"
        ):
            return SubsystemStatus(
                "weather", "Weather", "degraded", "NWS fallback",
                "Open-Meteo is unavailable; current weather came from NWS.",
            )

        if weather.last_success is not None:
            return SubsystemStatus(
                "weather", "Weather", "healthy", "Current",
                f"Last successful update: {weather.last_success:%H:%M:%S}.",
            )

        if weather.last_error:
            return SubsystemStatus(
                "weather", "Weather", "degraded", "Unavailable",
                weather.last_error,
            )

        return SubsystemStatus(
            "weather", "Weather", "unknown", "Not requested",
            "Weather needs a Home Node position before it can be requested.",
        )

    @staticmethod
    def _aqi_status(aqi: AQIService | None) -> SubsystemStatus:
        if aqi is None:
            return SubsystemStatus(
                "aqi", "AQI", "unavailable", "Not configured",
                "An AQI provider has not been configured yet.",
            )

        if aqi.last_success is not None:
            return SubsystemStatus(
                "aqi", "AQI", "healthy", "Current",
                f"Last successful update: {aqi.last_success:%H:%M:%S}.",
            )

        if aqi.last_error:
            return SubsystemStatus(
                "aqi", "AQI", "degraded", "Unavailable", aqi.last_error,
            )

        return SubsystemStatus(
            "aqi", "AQI", "unknown", "Not requested",
            "AQI needs a Home Node position before it can be requested.",
        )

    @staticmethod
    def _maps_status(
        maps: MapService,
        home_node: Node | None,
    ) -> SubsystemStatus:
        installed_maps = maps.discover()

        if not installed_maps:
            return SubsystemStatus(
                "maps", "Maps", "unavailable", "Online fallback",
                "No offline MBTiles packages are installed.",
            )

        if home_node is None:
            return SubsystemStatus(
                "maps", "Maps", "unknown", "Map available",
                "Offline maps are installed, but no Home Node position is available.",
            )

        offline_map = maps.map_for_coordinate(
            home_node.latitude,
            home_node.longitude,
        )

        if offline_map is None:
            return SubsystemStatus(
                "maps", "Maps", "degraded", "No local coverage",
                "Offline maps are installed but none cover the Home Node position.",
            )

        return SubsystemStatus(
            "maps", "Maps", "healthy", offline_map.name,
            "The Home Node is covered by an installed offline map.",
        )

    @staticmethod
    def _refresh_status(
        mesh: MeshtasticService,
        refresh_seconds: int,
    ) -> SubsystemStatus:
        if mesh.last_refresh_at is None:
            return SubsystemStatus(
                "refresh", "Refresh", "unavailable", "No refresh",
                "The mesh node cache has not completed a refresh.",
            )

        if mesh.last_refresh_error:
            return SubsystemStatus(
                "refresh", "Refresh", "degraded", "Failed",
                mesh.last_refresh_error,
            )

        age = datetime.now() - mesh.last_refresh_at
        stale_after = timedelta(seconds=refresh_seconds * 2)

        if age > stale_after:
            return SubsystemStatus(
                "refresh", "Refresh", "degraded", "Stale",
                f"Last completed refresh was {int(age.total_seconds())} seconds ago.",
            )

        return SubsystemStatus(
            "refresh", "Refresh", "healthy", "Current",
            f"Last completed refresh was {int(age.total_seconds())} seconds ago.",
        )
