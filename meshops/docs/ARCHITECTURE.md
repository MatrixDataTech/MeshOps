# Architecture

## Layers

Browser

↓

FastAPI Routes

↓

MeshOps Application

↓

Services

↓

Models

↓

Meshtastic Radio

## Philosophy

Routes never talk directly to hardware.

Hardware access lives in services.

Business logic belongs in MeshOps.

Presentation belongs in Jinja templates.
