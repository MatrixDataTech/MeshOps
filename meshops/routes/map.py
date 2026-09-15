from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from meshops.app import meshops


OPENSTREETMAP_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
OPENSTREETMAP_ATTRIBUTION = "&copy; OpenStreetMap contributors"

router = APIRouter()

templates = Jinja2Templates(directory="meshops/ui/templates")


@router.get("/map", response_class=HTMLResponse)
async def map_page(request: Request):
    context = meshops.context()
    home_node = context["home_node"]
    offline_map = None

    if home_node is not None:
        offline_map = meshops.maps.map_for_coordinate(
            home_node.latitude,
            home_node.longitude,
        )

    if offline_map is None:
        context.update(
            tile_url=OPENSTREETMAP_TILE_URL,
            tile_attribution=OPENSTREETMAP_ATTRIBUTION,
            map_source_label="Online OpenStreetMap",
        )
    else:
        map_identifier = quote(offline_map.identifier, safe="")
        context.update(
            tile_url=f"/tiles/{map_identifier}/{{z}}/{{x}}/{{y}}",
            tile_attribution=f"Offline MBTiles: {offline_map.name}",
            map_source_label=f"Offline map: {offline_map.name}",
        )

    context["request"] = request

    return templates.TemplateResponse(
        request=request,
        name="map.html",
        context=context,
    )


@router.get("/tiles/{map_identifier}/{zoom}/{column}/{row}", name="offline_tile")
async def offline_tile(
    map_identifier: str,
    zoom: int,
    column: int,
    row: int,
):
    tile = meshops.maps.tile(map_identifier, zoom, column, row)

    if tile is None:
        raise HTTPException(status_code=404, detail="Map tile not found")

    return Response(content=tile.data, media_type=tile.media_type)
