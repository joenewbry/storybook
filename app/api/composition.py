"""FFmpeg composition endpoints."""

import asyncio
from fastapi import APIRouter, HTTPException
from app.database import get_session, SessionLocal
from app.models import Scene, Asset
from app.services.composer import compose_scene
from app.web.ws import ws_manager

router = APIRouter(tags=["composition"])


@router.post("/api/scenes/{scene_id}/compose")
async def compose(scene_id: int):
    """Compose a scene's shots into a video with Ken Burns + transitions."""
    session = get_session()
    try:
        scene = session.query(Scene).get(scene_id)
        if not scene:
            raise HTTPException(404, "Scene not found")

        shots_data = [sh.to_dict() for sh in scene.shots]
        if not shots_data:
            raise HTTPException(400, "Scene has no shots")

        has_images = any(sh.get("current_image") for sh in shots_data)
        if not has_images:
            raise HTTPException(400, "No images generated yet for this scene's shots")
    finally:
        session.close()

    async def _compose():
        result = await compose_scene(shots_data, scene_id)
        if result:
            s = SessionLocal()
            try:
                sc = s.query(Scene).get(scene_id)
                if sc and sc.shots:
                    asset = Asset(
                        shot_id=sc.shots[0].id,
                        asset_type="composed",
                        file_path=result,
                        generation_params={"scene_id": scene_id, "shot_count": len(shots_data)},
                        is_current=True,
                    )
                    s.add(asset)
                    s.commit()
                await ws_manager.broadcast({
                    "type": "composition_complete",
                    "scene_id": scene_id,
                    "video_path": result,
                })
            finally:
                s.close()

    asyncio.create_task(_compose())
    return {"ok": True, "scene_id": scene_id}
