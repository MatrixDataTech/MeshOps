"""Queue deliberate dashboard messages for the single radio owner."""

from datetime import datetime
from queue import Empty, Full, Queue
from threading import Lock


class OutboundMessageService:
    """Validate and hold one pending channel message in memory."""

    MAX_BYTES = 220

    def __init__(self, channel_name: str | None):
        self.channel_name = channel_name
        self._queue: Queue[str] = Queue(maxsize=1)
        self._lock = Lock()
        self._pending = False
        self._last_status = "No message queued."

    def queue_message(self, message: str) -> None:
        """Queue one concise message without performing radio transport."""

        if not self.channel_name:
            raise ValueError("Channel messaging is not configured.")
        if not isinstance(message, str):
            raise ValueError("Message must be text.")
        message = message.strip()
        if not message:
            raise ValueError("Enter a message first.")
        if len(message.encode("utf-8")) > self.MAX_BYTES:
            raise ValueError(f"Message must be {self.MAX_BYTES} bytes or fewer.")

        try:
            self._queue.put_nowait(message)
        except Full as exc:
            raise ValueError("A message is already waiting to send.") from exc

        with self._lock:
            self._pending = True
            self._last_status = f"Queued for {self.channel_name}."

    def next_message(self) -> str | None:
        """Return the next message for the event runtime, if one is pending."""

        try:
            message = self._queue.get_nowait()
        except Empty:
            return None

        with self._lock:
            self._pending = False
        return message

    def mark_sent(self) -> None:
        """Record that the attached radio accepted the queued message."""

        timestamp = datetime.now().strftime("%-I:%M %p")
        with self._lock:
            self._last_status = f"Handed to radio for {self.channel_name} at {timestamp}."

    def mark_failed(self) -> None:
        """Record a transport failure without retaining the message for retry."""

        with self._lock:
            self._last_status = f"Unable to send to {self.channel_name}."

    def status(self) -> dict[str, object]:
        """Return UI-ready state without exposing pending message content."""

        with self._lock:
            return {
                "channel": self.channel_name,
                "pending": self._pending,
                "message": self._last_status,
                "max_bytes": self.MAX_BYTES,
            }
