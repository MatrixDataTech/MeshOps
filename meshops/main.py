import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from meshops.app import meshops
from meshops.core.runtime import is_event_mode
from meshops.routes.dashboard import router as dashboard_router
from meshops.routes.nodes import router as nodes_router
from meshops.routes.map import router as map_router


async def refresh_loop():
    while True:
        try:
            meshops.mesh.refresh()
        except Exception as exc:
            print(f"Refresh failed: {exc}")

        await asyncio.sleep(meshops.config["mesh"]["refresh_seconds"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None

    if not is_event_mode():
        meshops.startup()
        task = asyncio.create_task(refresh_loop())

    yield

    if task is not None:
        task.cancel()
        meshops.shutdown()


app = FastAPI(
    title="MeshOps",
    lifespan=lifespan,
)

app.mount(
    "/static",
    StaticFiles(directory="meshops/ui/static"),
    name="static",
)

app.include_router(dashboard_router)
app.include_router(map_router)

app.include_router(nodes_router)
