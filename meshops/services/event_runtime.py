"""Coordinate the single radio owner used during special-event deployments."""

import logging
from time import monotonic


log = logging.getLogger(__name__)


class RadioConnectionLost(RuntimeError):
    """Signal that the single serial-radio owner must be restarted."""


class EventRuntime:
    """Refresh mesh state and receive bot commands through one radio interface."""

    def __init__(
        self,
        mesh,
        bot_adapter,
        refresh_seconds: int,
        clock=monotonic,
        morning_update=None,
        context_provider=None,
        channel_share=None,
        outbound_messages=None,
    ):
        self.mesh = mesh
        self.bot_adapter = bot_adapter
        self.refresh_seconds = refresh_seconds
        self.clock = clock
        self.morning_update = morning_update
        self.context_provider = context_provider
        self.channel_share = channel_share
        self.outbound_messages = outbound_messages
        self._next_refresh: float | None = None

    def start(self, interface) -> None:
        """Attach the bot and establish the initial shared node cache."""

        self.mesh.refresh_from_interface(interface)
        if self.channel_share is not None:
            self.channel_share.refresh_from_interface(interface)
        self.bot_adapter.attach(interface)
        self._next_refresh = self.clock() + self.refresh_seconds

    def tick(self, interface) -> None:
        """Perform a due refresh without opening another serial interface."""

        if self._next_refresh is not None and self.clock() >= self._next_refresh:
            self.mesh.refresh_from_interface(interface)
            self._next_refresh = self.clock() + self.refresh_seconds

        self._send_due_morning_update(interface)
        self._send_queued_message(interface)

    def _send_queued_message(self, interface) -> None:
        if self.outbound_messages is None or not self.bot_adapter.channel_available:
            return

        message = self.outbound_messages.next_message()
        if message is None:
            return

        try:
            self.bot_adapter.send_channel_message(message, interface)
        except Exception as exc:
            self.outbound_messages.mark_failed()
            log.exception("Unable to send queued dashboard message")
            if "Timed out waiting for connection completion" in str(exc):
                raise RadioConnectionLost("Radio connection timed out during send.") from exc
        else:
            self.outbound_messages.mark_sent()

    def _send_due_morning_update(self, interface) -> None:
        if (
            self.morning_update is None
            or self.context_provider is None
            or not self.bot_adapter.channel_available
        ):
            return

        report = self.morning_update.due_report(self.context_provider)
        if report is None:
            return

        self.bot_adapter.send_channel_message(report, interface)
        self.morning_update.mark_sent()

    def stop(self) -> None:
        """Detach message handling before the radio interface is closed."""

        self.bot_adapter.detach()
        self._next_refresh = None
