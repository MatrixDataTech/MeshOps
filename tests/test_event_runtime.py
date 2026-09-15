import unittest
from unittest.mock import Mock

from meshops.services.event_runtime import EventRuntime, RadioConnectionLost


class EventRuntimeTests(unittest.TestCase):
    def test_start_refreshes_and_attaches_one_radio_owner(self):
        mesh = Mock()
        adapter = Mock()
        runtime = EventRuntime(mesh, adapter, refresh_seconds=30, clock=lambda: 10)
        interface = Mock()

        runtime.start(interface)

        mesh.refresh_from_interface.assert_called_once_with(interface)
        adapter.attach.assert_called_once_with(interface)

    def test_tick_refreshes_only_when_due(self):
        mesh = Mock()
        adapter = Mock()
        clock = Mock(side_effect=[10, 39, 40, 40])
        runtime = EventRuntime(mesh, adapter, refresh_seconds=30, clock=clock)
        interface = Mock()
        runtime.start(interface)

        runtime.tick(interface)
        runtime.tick(interface)

        self.assertEqual(mesh.refresh_from_interface.call_count, 2)

    def test_tick_sends_a_due_morning_update(self):
        mesh = Mock()
        adapter = Mock()
        morning_update = Mock()
        morning_update.due_report.return_value = "Good Morning"
        context_provider = Mock(return_value={"node_count": 24})
        runtime = EventRuntime(
            mesh,
            adapter,
            refresh_seconds=30,
            clock=lambda: 10,
            morning_update=morning_update,
            context_provider=context_provider,
        )
        interface = Mock()
        runtime.start(interface)

        runtime.tick(interface)

        morning_update.due_report.assert_called_once_with(context_provider)
        adapter.send_channel_message.assert_called_once_with("Good Morning", interface)
        morning_update.mark_sent.assert_called_once_with()

    def test_tick_holds_messages_when_the_bot_channel_is_unavailable(self):
        mesh = Mock()
        adapter = Mock()
        adapter.channel_available = False
        morning_update = Mock()
        outbound_messages = Mock()
        runtime = EventRuntime(
            mesh,
            adapter,
            refresh_seconds=30,
            clock=lambda: 10,
            morning_update=morning_update,
            context_provider=Mock(),
            outbound_messages=outbound_messages,
        )
        interface = Mock()
        runtime.start(interface)

        runtime.tick(interface)

        morning_update.due_report.assert_not_called()
        outbound_messages.next_message.assert_not_called()

    def test_tick_sends_a_queued_dashboard_message(self):
        mesh = Mock()
        adapter = Mock()
        outbound_messages = Mock()
        outbound_messages.next_message.return_value = "Radio check"
        runtime = EventRuntime(
            mesh,
            adapter,
            refresh_seconds=30,
            clock=lambda: 10,
            outbound_messages=outbound_messages,
        )
        interface = Mock()
        runtime.start(interface)

        runtime.tick(interface)

        adapter.send_channel_message.assert_called_once_with("Radio check", interface)
        outbound_messages.mark_sent.assert_called_once_with()

    def test_tick_restarts_runtime_after_radio_connection_timeout(self):
        mesh = Mock()
        adapter = Mock()
        adapter.send_channel_message.side_effect = RuntimeError(
            "Timed out waiting for connection completion"
        )
        outbound_messages = Mock()
        outbound_messages.next_message.return_value = "Radio check"
        runtime = EventRuntime(
            mesh,
            adapter,
            refresh_seconds=30,
            clock=lambda: 10,
            outbound_messages=outbound_messages,
        )
        interface = Mock()
        runtime.start(interface)

        with self.assertRaises(RadioConnectionLost):
            runtime.tick(interface)

        outbound_messages.mark_failed.assert_called_once_with()

    def test_tick_keeps_running_after_an_ordinary_send_failure(self):
        mesh = Mock()
        adapter = Mock()
        adapter.send_channel_message.side_effect = RuntimeError("radio rejected message")
        outbound_messages = Mock()
        outbound_messages.next_message.return_value = "Radio check"
        runtime = EventRuntime(
            mesh,
            adapter,
            refresh_seconds=30,
            clock=lambda: 10,
            outbound_messages=outbound_messages,
        )
        interface = Mock()
        runtime.start(interface)

        runtime.tick(interface)

        outbound_messages.mark_failed.assert_called_once_with()

    def test_stop_detaches_before_interface_closes(self):
        runtime = EventRuntime(Mock(), Mock(), refresh_seconds=30)

        runtime.stop()

        runtime.bot_adapter.detach.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
