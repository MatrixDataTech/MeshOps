import base64
import unittest

from meshops.services.channel_share import ChannelShareService


class FakeNode:
    def getChannelByName(self, name):
        return object() if name == "CampOps" else None

    def getURL(self, includeAll=True):
        if not includeAll:
            raise AssertionError("Expected all channels in share link")
        return "https://meshtastic.org/e/#channel-data"


class FakeInterface:
    localNode = FakeNode()


class ChannelShareServiceTests(unittest.TestCase):
    def test_builds_add_only_svg_qr_for_existing_channel(self):
        service = ChannelShareService("CampOps")

        service.refresh_from_interface(FakeInterface())

        self.assertTrue(service.available)
        self.assertIsNone(service.error)
        encoded = service.qr_data_uri.split(",", 1)[1]
        self.assertIn(b"<svg", base64.b64decode(encoded))

    def test_is_unavailable_when_channel_is_missing(self):
        service = ChannelShareService("Other")

        service.refresh_from_interface(FakeInterface())

        self.assertFalse(service.available)
        self.assertEqual(service.error, "Channel not found: Other")
