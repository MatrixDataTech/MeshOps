"""Run MeshOps web and bot features with one owner of the radio interface."""

import logging
import os
from pathlib import Path
import signal
import sys
from threading import Event, Thread
from time import sleep

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["MESHOPS_EVENT_MODE"] = "1"

from meshtastic.serial_interface import SerialInterface
import uvicorn

from meshops.app import meshops
from meshops.main import app
from meshops.services.event_runtime import EventRuntime
from meshops.services.meshtastic_bot import MeshtasticBotAdapter


log = logging.getLogger(__name__)


def main():
    """Run until interrupted, with one process owning both radio and web state."""

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stop_event = Event()

    def observe_packet(packet):
        meshops.mesh.record_packet(packet)

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=meshops.config["server"]["host"],
            port=meshops.config["server"]["port"],
            log_level="info",
        )
    )
    adapter = MeshtasticBotAdapter(
        meshops.bot,
        meshops.bot_context,
        meshops.bot_channel,
        packet_observer=observe_packet,
    )
    runtime = EventRuntime(
        meshops.mesh,
        adapter,
        meshops.config["mesh"]["refresh_seconds"],
        morning_update=meshops.morning_update,
        context_provider=meshops.context,
        channel_share=meshops.channel_share,
        outbound_messages=meshops.outbound_messages,
    )

    def request_stop(signum, frame):
        log.info("Stopping Event Runtime after signal %s.", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    with SerialInterface() as interface:
        runtime.start(interface)
        web_thread = Thread(target=server.run, name="meshops-web", daemon=True)
        web_thread.start()

        try:
            while not stop_event.is_set():
                runtime.tick(interface)
                sleep(1)
        finally:
            runtime.stop()
            server.should_exit = True
            web_thread.join(timeout=15)
if __name__ == "__main__":
    main()
