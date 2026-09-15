"""Runtime-mode decisions shared by FastAPI and event launchers."""

import os


EVENT_MODE_VARIABLE = "MESHOPS_EVENT_MODE"


def is_event_mode() -> bool:
    """Return whether another component owns the Meshtastic interface."""

    return os.environ.get(EVENT_MODE_VARIABLE) == "1"
