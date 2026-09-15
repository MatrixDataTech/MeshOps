import unittest

from meshops.services.outbound_messages import OutboundMessageService


class OutboundMessageServiceTests(unittest.TestCase):
    def test_queues_one_message_and_records_radio_handoff(self):
        service = OutboundMessageService("CampOps")

        service.queue_message("Radio check")

        self.assertTrue(service.status()["pending"])
        self.assertEqual(service.next_message(), "Radio check")
        service.mark_sent()
        self.assertFalse(service.status()["pending"])
        self.assertIn("Handed to radio", service.status()["message"])

    def test_rejects_empty_oversize_and_additional_pending_messages(self):
        service = OutboundMessageService("CampOps")

        with self.assertRaisesRegex(ValueError, "Enter a message"):
            service.queue_message("  ")
        with self.assertRaisesRegex(ValueError, "220 bytes"):
            service.queue_message("x" * 221)

        service.queue_message("First")
        with self.assertRaisesRegex(ValueError, "already waiting"):
            service.queue_message("Second")

    def test_rejects_messages_when_no_channel_is_configured(self):
        service = OutboundMessageService(None)

        with self.assertRaisesRegex(ValueError, "not configured"):
            service.queue_message("Radio check")
