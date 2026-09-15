# MeshOps

MeshOps is a lightweight, self-hosted operations dashboard for Meshtastic deployments. It is designed for event operations, search and rescue support, remote deployments, and other field teams that value local-first operation and simple maintenance.

It is not a replacement for a Meshtastic client. MeshOps combines cached mesh status, a Leaflet map, weather, AQI, sunrise and sunset, team awareness, and concise optional bot reports in one local web interface.

## Features

- Cached Meshtastic node inventory, team view, and map
- Weather with Open-Meteo and National Weather Service fallback
- AQI, sunrise, sunset, and subsystem health indicators
- Daily operational-summary preview and optional morning update
- Optional RF-friendly `!mesh` command responses
- Offline map support and GeoJSON overlays
- A single process owns the serial radio connection

## Requirements

- Linux host with Python 3.13 or later
- A Meshtastic radio connected by USB for live mesh features
- Internet is optional; MeshOps retains cached weather and AQI data when offline

## Quick start

```bash
git clone https://github.com/MatrixDataTech/MeshOps.git
cd MeshOps
python3.13 -m venv .venv
.venv/bin/pip install -e .
cp config/meshops.example.yaml config/meshops.yaml
```

Edit `config/meshops.yaml` for the deployment, then start the dashboard:

```bash
.venv/bin/python -m uvicorn meshops.main:app --host 127.0.0.1 --port 8000
```

For a live radio, use the event runtime instead. It intentionally owns the serial device for both refreshes and bot commands:

```bash
.venv/bin/python scripts/event_runtime.py
```

To install a boot-persistent systemd service after reviewing the configuration:

```bash
sudo scripts/install_event_runtime_service.sh --start
```

The installer creates a local `config/meshops.yaml` from the example when needed. That file and the local state directory are intentionally excluded from Git.

## Deployment notes

The example server binds to `127.0.0.1`. If remote browser access is needed, use a reverse proxy or trusted private network; do not expose the development server directly to the public Internet. MeshOps does not provide web-based radio administration.

Set `meshtastic.bot_channel` only for an approved event channel. Leaving it empty disables bot commands, scheduled channel messages, and channel-share QR output while keeping the dashboard available.

Set `team.name_prefix` to the common prefix used by your team node names (for example, `TEAM-`). Leaving it empty disables the team view and team bot response.

## License

MeshOps is licensed under the GNU General Public License, version 3. See [LICENSE](LICENSE).
