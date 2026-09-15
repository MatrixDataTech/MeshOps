from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from meshops.app import meshops
from meshops.core.version import VERSION

router = APIRouter()

templates = Jinja2Templates(directory="meshops/ui/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    context = meshops.context()
    context["request"] = request
    context["version"] = VERSION

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=context,
    )


@router.put("/api/channel-message", response_class=JSONResponse)
async def queue_channel_message(request: Request):
    """Queue one deliberate channel message for the event runtime."""

    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("Message request must be an object.")
        meshops.outbound_messages.queue_message(payload.get("message"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JSONResponse(meshops.outbound_messages.status())


@router.get("/daily-summary", response_class=HTMLResponse)
async def daily_summary(request: Request):
    context = meshops.context()
    context["request"] = request
    context["status_by_key"] = {
        status.key: status for status in context["statuses"]
    }
    context["morning_update"] = meshops.morning_update_settings.values()
    context["morning_report"] = meshops.morning_update.build_report(context)

    return templates.TemplateResponse(
        request=request,
        name="daily_summary.html",
        context=context,
    )


@router.put("/api/morning-update", response_class=JSONResponse)
async def save_morning_update(request: Request):
    """Persist Daily Summary settings after validating browser input."""

    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("Settings must be an object.")
        events = payload.get("events", [])
        if not isinstance(events, list) or not all(isinstance(item, str) for item in events):
            raise ValueError("Events must be a list of text lines.")
        settings = meshops.morning_update_settings.update(
            enabled=payload.get("enabled"),
            scheduled_time=payload.get("time"),
            events=events,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JSONResponse({"settings": settings})
