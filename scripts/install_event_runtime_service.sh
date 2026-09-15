#!/usr/bin/env bash
# Install MeshOps Event Runtime as a boot-persistent systemd service.
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    exec sudo -- "$0" "$@"
fi

PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PROJECT_OWNER=${SUDO_USER:-}
UNIT_NAME=meshops-event-runtime.service
UNIT_SOURCE="$PROJECT_ROOT/systemd/$UNIT_NAME"
UNIT_DESTINATION="/etc/systemd/system/$UNIT_NAME"
BACKUP_ROOT=/etc/systemd/system/meshops-event-runtime.backups
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIRECTORY="$BACKUP_ROOT/$TIMESTAMP"
CONFIG_EXAMPLE="$PROJECT_ROOT/config/meshops.example.yaml"
CONFIG_FILE="$PROJECT_ROOT/config/meshops.yaml"

if [[ -z "$PROJECT_OWNER" ]] || ! id "$PROJECT_OWNER" >/dev/null 2>&1; then
    echo "Run this script from a regular user account with sudo." >&2
    exit 1
fi

if [[ ! -f "$UNIT_SOURCE" ]]; then
    echo "Missing unit file: $UNIT_SOURCE" >&2
    exit 1
fi
if [[ ! -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
    echo "Missing virtual environment: $PROJECT_ROOT/.venv/bin/python" >&2
    exit 1
fi
if [[ ! -f "$CONFIG_EXAMPLE" ]]; then
    echo "Missing example configuration: $CONFIG_EXAMPLE" >&2
    exit 1
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
    install -m 0600 -o "$PROJECT_OWNER" -g "$PROJECT_OWNER" "$CONFIG_EXAMPLE" "$CONFIG_FILE"
    echo "Created local configuration at $CONFIG_FILE"
fi

if [[ -e "$UNIT_DESTINATION" ]]; then
    install -d -m 0755 "$BACKUP_DIRECTORY"
    install -m 0644 "$UNIT_DESTINATION" "$BACKUP_DIRECTORY/$UNIT_NAME"
    echo "Backed up existing unit to $BACKUP_DIRECTORY/$UNIT_NAME"
fi

TEMP_UNIT=$(mktemp)
trap 'rm -f "$TEMP_UNIT"' EXIT
sed \
    -e "s|__MESHOPS_USER__|$PROJECT_OWNER|g" \
    -e "s|__MESHOPS_PROJECT_ROOT__|$PROJECT_ROOT|g" \
    "$UNIT_SOURCE" > "$TEMP_UNIT"
install -D -m 0644 "$TEMP_UNIT" "$UNIT_DESTINATION"
systemctl daemon-reload
systemctl enable "$UNIT_NAME"

if [[ ${1:-} == "--start" ]]; then
    systemctl restart "$UNIT_NAME"
fi

echo "Installed $UNIT_NAME"
echo "Rollback: restore a saved unit from $BACKUP_ROOT, then run systemctl daemon-reload."
