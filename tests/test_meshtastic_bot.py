from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from meshops.services.meshtastic_bot import MeshtasticBotAdapter


class MeshtasticBotAdapterTests(unittest.TestCase):
    def setUp(self):
        self.bot = Mock()
        self.bot.handle_command.return_value = "AQI 42: Good."
        self.context = {"weather": None, "aqi": None, "statuses": [], "team": []}
        self.adapter = MeshtasticBotAdapter(self.bot, lambda: self.context)
        self.adapter._channel_index = 2
        self.interface = Mock()
        self.interface.myInfo = SimpleNamespace(my_node_num=42)

    def test_replies_privately_to_mdtcamp_command(self):
        handled = self.adapter.handle_packet(
            {
                "from": 99,
                "fromId": "!sender",
                "to": 0,
                "channel": 2,
                "id": 123,
                "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "!mesh aqi"},
            },
            self.interface,
        )

        self.assertTrue(handled)
        self.bot.handle_command.assert_called_once_with("aqi", **self.context)
        self.interface.sendText.assert_called_once_with(
            "AQI 42: Good.",
            destinationId="!sender",
            channelIndex=2,
            replyId=123,
        )

    def test_observes_received_packets_before_command_handling(self):
        observer = Mock()
        adapter = MeshtasticBotAdapter(
            self.bot,
            lambda: self.context,
            packet_observer=observer,
        )
        packet = {"fromId": "!sender", "decoded": {"text": "ordinary message"}}

        adapter._on_receive(packet, self.interface)

        observer.assert_called_once_with(packet)

    def test_replies_to_direct_command_from_any_channel(self):
        handled = self.adapter.handle_packet(
            {
                "from": 99,
                "fromId": "!sender",
                "to": 42,
                "channel": 5,
                "id": 124,
                "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "!mesh status"},
            },
            self.interface,
        )

        self.assertTrue(handled)
        self.interface.sendText.assert_called_once_with(
            "AQI 42: Good.",
            destinationId="!sender",
            channelIndex=5,
            replyId=124,
        )

    def test_sends_operational_update_to_mdtcamp(self):
        self.adapter.send_channel_message("Good Morning", self.interface)

        self.interface.sendText.assert_called_once_with(
            "Good Morning",
            channelIndex=2,
        )

    def test_attach_disables_commands_without_a_configured_channel(self):
        adapter = MeshtasticBotAdapter(self.bot, lambda: self.context)

        self.assertFalse(adapter.attach(self.interface))
        self.assertFalse(adapter.channel_available)

    def test_attach_disables_commands_when_channel_is_missing(self):
        adapter = MeshtasticBotAdapter(self.bot, lambda: self.context, "MDTCamp")
        self.interface.localNode.getChannelByName.return_value = None

        self.assertFalse(adapter.attach(self.interface))
        self.assertFalse(adapter.channel_available)

    def test_ignores_unprefixed_or_other_channel_messages(self):
        unprefixed = {
            "from": 99,
            "fromId": "!sender",
            "to": 0,
            "channel": 2,
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "weather"},
        }
        other_channel = {
            "from": 99,
            "fromId": "!sender",
            "to": 0,
            "channel": 3,
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "!mesh weather"},
        }

        self.assertFalse(self.adapter.handle_packet(unprefixed, self.interface))
        self.assertFalse(self.adapter.handle_packet(other_channel, self.interface))
        self.interface.sendText.assert_not_called()

    def test_rate_limits_repeat_commands_from_one_sender(self):
        packet = {
            "from": 99,
            "fromId": "!sender",
            "to": 42,
            "channel": 0,
            "id": 125,
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "!mesh status"},
        }

        self.assertTrue(self.adapter.handle_packet(packet, self.interface))
        self.assertFalse(self.adapter.handle_packet(packet, self.interface))
        self.interface.sendText.assert_called_once()


if __name__ == "__main__":
    unittest.main()
