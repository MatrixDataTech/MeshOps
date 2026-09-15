"""Build an add-only QR join link for the managed camp channel."""

import base64
import logging
from io import BytesIO

import pyqrcode


log = logging.getLogger(__name__)


class ChannelShareService:
    """Keep the managed channel join QR in runtime memory only."""

    def __init__(self, channel_name: str | None):
        self.channel_name = channel_name
        self.qr_data_uri: str | None = None
        self.error: str | None = None

    @property
    def available(self) -> bool:
        return self.qr_data_uri is not None

    def refresh_from_interface(self, interface) -> None:
        """Generate an add-only join QR from radio-owned channel settings."""

        if not self.channel_name:
            self.qr_data_uri = None
            self.error = "No bot channel configured."
            return

        try:
            if interface.localNode.getChannelByName(self.channel_name) is None:
                raise RuntimeError(f"Channel not found: {self.channel_name}")

            share_url = interface.localNode.getURL(includeAll=True)
            add_url = share_url.replace("/e/#", "/e/?add=true#", 1)
            if add_url == share_url:
                raise RuntimeError("Unable to create an add-only channel link")

            stream = BytesIO()
            pyqrcode.create(add_url, error="M").svg(stream, scale=4, quiet_zone=2)
            svg = base64.b64encode(stream.getvalue()).decode("ascii")
            self.qr_data_uri = f"data:image/svg+xml;base64,{svg}"
            self.error = None
        except Exception as exc:
            self.qr_data_uri = None
            self.error = str(exc)
            log.warning("Unable to create %s join QR: %s", self.channel_name, exc)
