from dataclasses import dataclass


@dataclass(frozen=True)
class Alert:
    """A deduplicated operational condition; it is not a transmitted message."""

    key: str
    severity: str
    message: str
