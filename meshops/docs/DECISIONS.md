B# Decisions

## 2026-08-02

### Use short-lived serial sessions

Reason

Keeping SerialInterface open overnight resulted in stale serial sessions
and prevented other applications from accessing the radio.

Decision

Open the serial interface only when data is needed and close it
immediately afterward.

Benefits

- CLI and MeshOps coexist
- Better recovery after USB reconnects
- Simpler code

## 2026-08-02

### Short-lived serial sessions

Problem

Keeping a SerialInterface open overnight eventually resulted in a stale
connection. The Meshtastic CLI could no longer acquire /dev/ttyACM0,
and telemetry stopped.

Observation

Opening a new SerialInterface for each request allowed MeshOps and the
Meshtastic CLI to coexist. The dashboard, node inventory, and CLI all
worked simultaneously.

Decision

All hardware access should use short-lived serial sessions. MeshOps
should never hold /dev/ttyACM0 longer than necessary.

Status

Implemented.