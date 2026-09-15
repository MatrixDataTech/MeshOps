import os
from pathlib import Path
import yaml

CONFIG_FILE = Path("config/meshops.yaml")
EXAMPLE_CONFIG_FILE = Path("config/meshops.example.yaml")


def load_config():
    """Load local configuration, falling back to safe example defaults."""

    configured_path = os.environ.get("MESHOPS_CONFIG")
    config_file = (
        Path(configured_path).expanduser()
        if configured_path
        else CONFIG_FILE
    )
    if not config_file.exists() and not configured_path:
        config_file = EXAMPLE_CONFIG_FILE
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")

    with config_file.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
