import asyncio
import os
import unittest
from unittest.mock import patch

from meshops.app import meshops
from meshops.core.runtime import EVENT_MODE_VARIABLE, is_event_mode
from meshops.main import app, lifespan


class RuntimeModeTests(unittest.TestCase):
    def test_event_mode_requires_explicit_value(self):
        with patch.dict(os.environ, {EVENT_MODE_VARIABLE: "1"}):
            self.assertTrue(is_event_mode())

        with patch.dict(os.environ, {EVENT_MODE_VARIABLE: "true"}):
            self.assertFalse(is_event_mode())

    def test_event_mode_lifespan_does_not_open_a_second_radio_connection(self):
        async def run_lifespan():
            with (
                patch("meshops.main.is_event_mode", return_value=True),
                patch.object(meshops, "startup") as startup,
                patch.object(meshops, "shutdown") as shutdown,
            ):
                async with lifespan(app):
                    pass

                startup.assert_not_called()
                shutdown.assert_not_called()

        asyncio.run(run_lifespan())


if __name__ == "__main__":
    unittest.main()
