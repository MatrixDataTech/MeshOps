"""Manually run the configured MeshOps command listener.

Stop the web development server before starting this process. It intentionally
owns the Meshtastic serial interface until interrupted with Ctrl-C.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from meshtastic.serial_interface import SerialInterface

from meshops.app import meshops
from meshops.services.meshtastic_bot import MeshtasticBotAdapter


def main():
    """Run the manually invoked listener until interrupted."""

    if not meshops.bot_channel:
        raise SystemExit("Set meshtastic.bot_channel before starting the command listener.")

    adapter = MeshtasticBotAdapter(
        meshops.bot,
        meshops.bot_context,
        channel_name=meshops.bot_channel,
    )

    meshops.startup()

    try:
        with SerialInterface() as interface:
            adapter.listen(interface)
    finally:
        meshops.shutdown()


if __name__ == "__main__":
    main()
