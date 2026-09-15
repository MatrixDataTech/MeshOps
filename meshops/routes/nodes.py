from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from meshops.app import meshops

router = APIRouter()

templates = Jinja2Templates(directory="meshops/ui/templates")


@router.get("/nodes", response_class=HTMLResponse)
async def nodes(request: Request):
    """Render the current cached mesh node inventory."""

    context = meshops.context()
    context["request"] = request
    context["title"] = "Mesh Nodes"

    return templates.TemplateResponse(
        request=request,
        name="nodes.html",
        context=context,
    )
