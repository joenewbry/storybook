"""FastAPI app factory with static mounts and WebSocket."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.database import init_db
from app.api.stories import router as stories_router
from app.api.shots import router as shots_router
from app.api.segmentation import router as segmentation_router
from app.api.generation import router as generation_router
from app.api.composition import router as composition_router
from app.api.world_bible import router as world_bible_router
from app.web.ws import ws_manager

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def create_app() -> FastAPI:
    app = FastAPI(title="Storybook", version="0.1.0")

    # Init DB on startup
    @app.on_event("startup")
    def startup():
        init_db()

    # API routes
    app.include_router(stories_router)
    app.include_router(shots_router)
    app.include_router(segmentation_router)
    app.include_router(generation_router)
    app.include_router(composition_router)
    app.include_router(world_bible_router)

    # Serve generated assets
    generated_dir = BASE_DIR / "data" / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/generated", StaticFiles(directory=str(generated_dir)), name="generated")

    # Serve static files
    static_dir = BASE_DIR / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # WebSocket endpoint
    @app.websocket("/ws/progress")
    async def ws_progress(ws: WebSocket):
        await ws_manager.connect(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(ws)

    # SPA fallback — serve index.html for root
    @app.get("/")
    async def index():
        return FileResponse(str(static_dir / "index.html"))

    return app
