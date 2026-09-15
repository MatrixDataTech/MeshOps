import logging
from datetime import datetime, timedelta

from meshtastic.serial_interface import SerialInterface

from meshops.models.node import Node


log = logging.getLogger(__name__)


class MeshtasticService:
    """Interface to the local Meshtastic node."""

    def __init__(self):
        self.connected = False
        self.last_refresh_at: datetime | None = None
        self.last_refresh_error: str | None = None
        self._packet_received_at_by_node_id: dict[str, int] = {}
        self._position_received_at_by_node_id: dict[str, int] = {}
        self._nodes: list[Node] = []
        self._local_node: Node | None = None

    def connect(self):
        self.connected = True
        self.refresh()

    def disconnect(self):
        self._packet_received_at_by_node_id = {}
        self._position_received_at_by_node_id = {}
        self._nodes = []
        self._local_node = None
        self.connected = False

    @property
    def is_connected(self):
        return self.connected

    def _node_from_data(self, data: dict) -> Node:
        """Convert Meshtastic node data into a Node object."""

        user = data.get("user", {})
        metrics = data.get("deviceMetrics", {})
        position = data.get("position", {})

        node_id = user.get("id", "")
        last_heard = data.get("lastHeard")
        observed_at = self._packet_received_at_by_node_id.get(node_id)
        position_updated_at = max(
            self._position_timestamp(position) or 0,
            self._position_received_at_by_node_id.get(node_id, 0),
        ) or None

        if observed_at is not None and (last_heard is None or observed_at > last_heard):
            last_heard = observed_at

        return Node(
            id=node_id,
            name=user.get("longName", "Unknown"),
            short_name=user.get("shortName", ""),
            hardware=user.get("hwModel", ""),
            battery=metrics.get("batteryLevel"),
            voltage=metrics.get("voltage"),
            latitude=position.get("latitude"),
            longitude=position.get("longitude"),
            altitude=position.get("altitude"),
            position_updated_at=position_updated_at,
            snr=data.get("snr"),
            hops=data.get("hopsAway"),
            last_heard=last_heard,
        )

    def record_packet(self, packet: dict, received_at: int | None = None) -> None:
        """Record fresh activity from a packet received by the local radio."""

        node_id = packet.get("fromId")

        if not isinstance(node_id, str) or not node_id:
            node_num = packet.get("from")
            node_id = f"!{node_num:08x}" if isinstance(node_num, int) else None

        if node_id is None:
            return

        timestamp = received_at if received_at is not None else int(datetime.now().timestamp())
        self._packet_received_at_by_node_id[node_id] = timestamp
        packet_position = self._packet_position(packet)
        if packet_position is not None:
            self._position_received_at_by_node_id[node_id] = timestamp

        for node in self._nodes:
            if node.id == node_id:
                node.last_heard = timestamp
                if packet_position is not None:
                    self._record_position_packet(node, packet_position, timestamp)
                break

    @staticmethod
    def _position_timestamp(position: dict) -> int | None:
        timestamp = position.get("time") or position.get("timestamp")
        return timestamp if isinstance(timestamp, int) and timestamp > 0 else None

    @staticmethod
    def _packet_position(packet: dict) -> dict | None:
        decoded = packet.get("decoded", {})
        position = decoded.get("position")
        if not isinstance(position, dict):
            return None

        latitude = position.get("latitude")
        longitude = position.get("longitude")
        if latitude is None or longitude is None:
            return None

        return position

    def _record_position_packet(
        self,
        node: Node,
        position: dict,
        received_at: int,
    ) -> None:
        node.latitude = position["latitude"]
        node.longitude = position["longitude"]
        node.altitude = position.get("altitude")
        node.position_updated_at = self._position_timestamp(position) or received_at

    def refresh(self):
        """Refresh the node cache with a short-lived serial session."""

        try:
            with SerialInterface() as interface:
                self.refresh_from_interface(interface)
        except Exception as exc:
            self._record_refresh_error(exc)

    def refresh_from_interface(self, interface) -> None:
        """Refresh from an interface owned by an EventRuntime process."""

        try:
            my_id = interface.getMyUser()["id"]
            nodes = []
            local = None

            for data in interface.nodes.values():
                node = self._node_from_data(data)
                nodes.append(node)

                if node.id == my_id:
                    local = node

            self._nodes = sorted(nodes, key=lambda node: node.name.lower())
            self._local_node = local
            self.connected = True
            self.last_refresh_at = datetime.now()
            self.last_refresh_error = None
            log.info("Refreshed %d mesh nodes.", len(nodes))
        except Exception as exc:
            self._record_refresh_error(exc)

    def _record_refresh_error(self, exc: Exception) -> None:
        self.last_refresh_error = str(exc)
        log.exception("Unable to refresh node cache: %s", exc)

    @property
    def nodes(self) -> list[Node]:
        return self._nodes

    @property
    def local_node(self) -> Node | None:
        return self._local_node

    def active_node_count(self, hours: int) -> int:
        """Return nodes heard by this radio within the operational time window."""

        cutoff = int((datetime.now() - timedelta(hours=hours)).timestamp())
        return sum(
            node.last_heard is not None and node.last_heard >= cutoff
            for node in self._nodes
        )

    def recent_position_nodes(self, hours: int) -> list[Node]:
        """Return freshest positioned nodes with actual recent radio activity."""

        cutoff = int((datetime.now() - timedelta(hours=hours)).timestamp())
        recent = []

        for node in self._nodes:
            if (
                not node.has_position
                or node.position_updated_at is None
                or node.position_updated_at < cutoff
            ):
                continue
            recent.append(node)

        return sorted(recent, key=lambda node: node.name.lower())
