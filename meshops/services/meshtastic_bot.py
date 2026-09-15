"""Manual Meshtastic transport adapter for BotService commands."""

from datetime import datetime, timedelta
import logging
import time
from typing import Callable

from pubsub import pub

from meshops.services.bot import BotService


log = logging.getLogger(__name__)


class MeshtasticBotAdapter:
    """Receive prefixed commands and send private responses on an approved channel."""

    COMMAND_PREFIX = "!mesh"
    COMMAND_COOLDOWN = timedelta(seconds=15)

    def __init__(
        self,
        bot: BotService,
        context_provider: Callable[[], dict],
        channel_name: str | None = None,
        packet_observer: Callable[[dict], None] | None = None,
    ):
        self.bot = bot
        self.context_provider = context_provider
        self.channel_name = channel_name
        self.packet_observer = packet_observer
        self._channel_index: int | None = None
        self._last_command_at: dict[str, datetime] = {}
        self._attached = False

    @property
    def channel_available(self) -> bool:
        """Whether this adapter is attached to its configured channel."""

        return self._attached and self._channel_index is not None

    def attach(self, interface) -> bool:
        """Subscribe to commands while the caller owns the radio interface."""

        if self._attached:
            raise RuntimeError("Bot adapter is already attached.")

        if not self.channel_name:
            log.info("Bot channel is not configured; command handling is disabled.")
            return False

        channel = interface.localNode.getChannelByName(self.channel_name)

        if channel is None:
            log.warning(
                "Bot channel %s is not present on the attached radio; "
                "command handling is disabled.",
                self.channel_name,
            )
            return False

        self._channel_index = channel.index
        pub.subscribe(self._on_receive, "meshtastic.receive")
        self._attached = True
        log.info("Listening for %s commands on %s.", self.COMMAND_PREFIX, self.channel_name)
        return True

    def detach(self) -> None:
        """Stop receiving commands before the caller closes the interface."""

        if not self._attached:
            return

        pub.unsubscribe(self._on_receive, "meshtastic.receive")
        self._channel_index = None
        self._attached = False

    def listen(self, interface) -> None:
        """Run until interrupted while intentionally holding the radio interface."""

        self.attach(interface)

        try:
            while True:
                time.sleep(1)
        finally:
            self.detach()

    def handle_packet(self, packet: dict, interface) -> bool:
        """Handle one packet and return whether it produced a private reply."""

        command = self._command_from_packet(packet, interface)

        if command is None:
            return False

        sender = packet.get("fromId")

        if not sender or self._is_rate_limited(sender):
            return False

        context = self.context_provider()
        response = self.bot.handle_command(command, **context)
        interface.sendText(
            response,
            destinationId=sender,
            channelIndex=packet.get("channel", 0),
            replyId=packet.get("id"),
        )
        self._last_command_at[sender] = datetime.now()
        log.info("Replied to %s command from %s.", command, sender)
        return True

    def send_channel_message(self, message: str, interface) -> None:
        """Send an operational announcement to the configured camp channel."""

        if self._channel_index is None:
            raise RuntimeError("Bot adapter is not attached to a channel.")

        interface.sendText(message, channelIndex=self._channel_index)
        log.info("Sent operational update on %s.", self.channel_name)

    def _on_receive(self, packet: dict, interface) -> None:
        if self.packet_observer is not None:
            try:
                self.packet_observer(packet)
            except Exception:
                log.exception("Unable to record received mesh packet activity.")

        decoded = packet.get("decoded", {})
        text = decoded.get("text")
        is_command = isinstance(text, str) and text.lower().startswith(self.COMMAND_PREFIX)

        if is_command:
            log.info(
                "Received %s packet from %s on channel %s (port %s).",
                self.COMMAND_PREFIX,
                packet.get("fromId") or packet.get("from"),
                packet.get("channel"),
                decoded.get("portnum"),
            )

        try:
            replied = self.handle_packet(packet, interface)
        except Exception:
            log.exception("Unable to process bot command packet.")
        else:
            if is_command and not replied:
                log.info("Ignored %s packet after validation.", self.COMMAND_PREFIX)

    def _command_from_packet(self, packet: dict, interface) -> str | None:
        decoded = packet.get("decoded", {})
        text = decoded.get("text")

        if not isinstance(text, str) or not text.lower().startswith(self.COMMAND_PREFIX):
            return None

        if not self._is_text_message(decoded):
            return None

        if packet.get("from") == interface.myInfo.my_node_num:
            return None

        if not self._is_direct_message(packet, interface) and not self._is_camp_channel(packet):
            return None

        command = text[len(self.COMMAND_PREFIX):].strip()
        return command or "help"

    @staticmethod
    def _is_text_message(decoded: dict) -> bool:
        portnum = decoded.get("portnum")
        return portnum in {"TEXT_MESSAGE_APP", 1}

    @staticmethod
    def _is_direct_message(packet: dict, interface) -> bool:
        return packet.get("to") == interface.myInfo.my_node_num

    def _is_camp_channel(self, packet: dict) -> bool:
        return self._channel_index is not None and packet.get("channel") == self._channel_index

    def _is_rate_limited(self, sender: str) -> bool:
        last_command = self._last_command_at.get(sender)

        return (
            last_command is not None
            and datetime.now() - last_command < self.COMMAND_COOLDOWN
        )
