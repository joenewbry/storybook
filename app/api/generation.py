"""Image and video generation endpoints."""

import asyncio
from fastapi import APIRouter, HTTPException
from app.database import get_session, SessionLocal
from app.models import Story, Scene, Shot, WorldBible
from app.services.prompt_builder import build_image_prompt, build_video_prompt
from app.services.grok_video import image_to_base64_data_uri
from app.services.queue import generation_queue
from app.config import GENERATED_DIR

router = APIRouter(tags=["generation"])


def _load_world_bible_dict(session, story_id: int) -> dict | None:
    """Load world bible as dict for prompt injection."""
    wb = session.query(WorldBible).filter_by(story_id=story_id).first()
    if not wb:
        return None
    return wb.to_full_dict()


@router.post("/api/stories/{story_id}/build-prompts")
def build_prompts(story_id: int):
    """Build image prompts for all shots in a story."""
    session = get_session()
    try:
        story = session.query(Story).get(story_id)
        if not story:
            raise HTTPException(404, "Story not found")

        story_data = {
            "visual_style": story.visual_style,
            "music_style": story.music_style,
            "color_script": story.color_script,
        }

        # Load world bible for consistency injection
        world_bible = _load_world_bible_dict(session, story_id)

        all_shots = []
        scene_index_map = {}  # shot_id -> scene_index
        scene_idx = 0
        for ch in story.chapters:
            for sc in ch.scenes:
                for sh in sc.shots:
                    all_shots.append(sh)
                    scene_index_map[sh.id] = scene_idx
                scene_idx += 1

        for i, shot in enumerate(all_shots):
            prev_data = all_shots[i - 1].to_dict() if i > 0 else None
            next_data = all_shots[i + 1].to_dict() if i < len(all_shots) - 1 else None
            prompt = build_image_prompt(
                shot.to_dict(), story_data, prev_data, next_data,
                world_bible=world_bible,
                scene_index=scene_index_map.get(shot.id),
            )
            shot.image_prompt = prompt
            shot.generation_status = "prompt_ready"

        session.commit()
        return {"ok": True, "prompts_built": len(all_shots)}
    finally:
        session.close()


@router.post("/api/shots/{shot_id}/generate")
async def generate_shot(shot_id: int):
    """Generate image for a single shot."""
    session = get_session()
    try:
        shot = session.query(Shot).get(shot_id)
        if not shot:
            raise HTTPException(404, "Shot not found")

        prompt = shot.image_prompt
        if not prompt:
            scene = shot.scene
            chapter = scene.chapter
            story = chapter.story
            story_data = {
                "visual_style": story.visual_style,
                "music_style": story.music_style,
            }
            world_bible = _load_world_bible_dict(session, story.id)
            prompt = build_image_prompt(shot.to_dict(), story_data, world_bible=world_bible)
            shot.image_prompt = prompt

        shot.generation_status = "generating"
        session.commit()
    finally:
        session.close()

    # Fire and forget — runs in the event loop background
    asyncio.create_task(
        generation_queue.generate_shot(shot_id, prompt, SessionLocal)
    )
    return {"ok": True, "shot_id": shot_id}


@router.post("/api/stories/{story_id}/generate-all")
async def generate_all(story_id: int):
    """Generate images for all shots that have prompts."""
    session = get_session()
    try:
        story = session.query(Story).get(story_id)
        if not story:
            raise HTTPException(404, "Story not found")

        shots_to_generate = []
        story_data = {
            "visual_style": story.visual_style,
            "music_style": story.music_style,
        }
        world_bible = _load_world_bible_dict(session, story_id)

        all_shots = []
        scene_index_map = {}
        scene_idx = 0
        for ch in story.chapters:
            for sc in ch.scenes:
                for sh in sc.shots:
                    all_shots.append(sh)
                    scene_index_map[sh.id] = scene_idx
                scene_idx += 1

        for i, shot in enumerate(all_shots):
            if shot.generation_status == "complete":
                continue
            prompt = shot.image_prompt
            if not prompt:
                prev_data = all_shots[i - 1].to_dict() if i > 0 else None
                next_data = all_shots[i + 1].to_dict() if i < len(all_shots) - 1 else None
                prompt = build_image_prompt(
                    shot.to_dict(), story_data, prev_data, next_data,
                    world_bible=world_bible,
                    scene_index=scene_index_map.get(shot.id),
                )
                shot.image_prompt = prompt

            shot.generation_status = "generating"
            shots_to_generate.append({"shot_id": shot.id, "prompt": prompt})

        story.status = "generating"
        session.commit()
    finally:
        session.close()

    if shots_to_generate:
        async def _run():
            await generation_queue.generate_batch(shots_to_generate, SessionLocal)
            s = SessionLocal()
            try:
                st = s.query(Story).get(story_id)
                if st:
                    st.status = "complete"
                    s.commit()
            finally:
                s.close()

        asyncio.create_task(_run())

    return {"ok": True, "generating": len(shots_to_generate)}


# ===== Video Generation Endpoints =====

def _get_shot_image_data_uri(shot) -> str | None:
    """Get the current reference image as a base64 data URI for the video API."""
    if not shot.assets:
        return None
    for a in shot.assets:
        if a.is_current and a.asset_type == "image" and a.file_path:
            full_path = GENERATED_DIR / a.file_path
            return image_to_base64_data_uri(full_path)
    return None


@router.post("/api/shots/{shot_id}/generate-video")
async def generate_shot_video(shot_id: int):
    """Generate video for a single shot (image-to-video with reference image)."""
    session = get_session()
    try:
        shot = session.query(Shot).get(shot_id)
        if not shot:
            raise HTTPException(404, "Shot not found")

        scene = shot.scene
        chapter = scene.chapter
        story = chapter.story
        story_data = {"visual_style": story.visual_style, "music_style": story.music_style}
        world_bible = _load_world_bible_dict(session, story.id)

        # Build video prompt
        prompt = build_video_prompt(shot.to_dict(), story_data, world_bible=world_bible)
        shot.video_prompt = prompt
        shot.video_generation_status = "generating"

        # Get reference image as data URI
        image_url = _get_shot_image_data_uri(shot)
        duration = int(shot.duration) if shot.duration else 5

        session.commit()
    finally:
        session.close()

    asyncio.create_task(
        generation_queue.generate_video_for_shot(
            shot_id, prompt, image_url, duration, SessionLocal
        )
    )
    return {"ok": True, "shot_id": shot_id}


@router.post("/api/scenes/{scene_id}/generate-video-sequence")
async def generate_scene_video_sequence(scene_id: int):
    """Generate videos for all shots in a scene sequentially (continuous camera)."""
    session = get_session()
    try:
        scene = session.query(Scene).get(scene_id)
        if not scene:
            raise HTTPException(404, "Scene not found")

        story = scene.chapter.story
        story_data = {"visual_style": story.visual_style, "music_style": story.music_style}
        world_bible = _load_world_bible_dict(session, story.id)

        scene_shots = []
        sorted_shots = sorted(scene.shots, key=lambda s: s.order_index)
        for i, shot in enumerate(sorted_shots):
            is_continuation = i > 0
            prompt = build_video_prompt(
                shot.to_dict(), story_data,
                is_continuation=is_continuation,
                world_bible=world_bible,
            )
            shot.video_prompt = prompt
            shot.video_generation_status = "generating"

            image_url = _get_shot_image_data_uri(shot)
            scene_shots.append({
                "shot_id": shot.id,
                "prompt": prompt,
                "image_url": image_url,
                "duration": int(shot.duration) if shot.duration else 5,
                "order_index": shot.order_index,
            })

        session.commit()
    finally:
        session.close()

    if scene_shots:
        asyncio.create_task(
            generation_queue.generate_scene_video_sequence(scene_shots, SessionLocal)
        )

    return {"ok": True, "scene_id": scene_id, "shots": len(scene_shots)}


@router.post("/api/stories/{story_id}/generate-all-videos")
async def generate_all_videos(story_id: int):
    """Generate videos for all shots in a story.

    Scenes run in parallel; shots within each scene run sequentially for continuous camera.
    """
    session = get_session()
    try:
        story = session.query(Story).get(story_id)
        if not story:
            raise HTTPException(404, "Story not found")

        story_data = {"visual_style": story.visual_style, "music_style": story.music_style}
        world_bible = _load_world_bible_dict(session, story_id)

        all_scene_shots = []  # list of lists
        for ch in story.chapters:
            for scene in ch.scenes:
                sorted_shots = sorted(scene.shots, key=lambda s: s.order_index)
                scene_shots = []
                for i, shot in enumerate(sorted_shots):
                    # Skip shots without reference images
                    image_url = _get_shot_image_data_uri(shot)
                    if not image_url and i == 0:
                        continue  # First shot needs a reference image

                    is_continuation = i > 0
                    prompt = build_video_prompt(
                        shot.to_dict(), story_data,
                        is_continuation=is_continuation,
                        world_bible=world_bible,
                    )
                    shot.video_prompt = prompt
                    shot.video_generation_status = "generating"

                    scene_shots.append({
                        "shot_id": shot.id,
                        "prompt": prompt,
                        "image_url": image_url,
                        "duration": int(shot.duration) if shot.duration else 5,
                        "order_index": shot.order_index,
                    })

                if scene_shots:
                    all_scene_shots.append(scene_shots)

        session.commit()
    finally:
        session.close()

    total = sum(len(s) for s in all_scene_shots)
    if all_scene_shots:
        async def _run():
            tasks = [
                generation_queue.generate_scene_video_sequence(scene_shots, SessionLocal)
                for scene_shots in all_scene_shots
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
            from app.web.ws import ws_manager
            await ws_manager.broadcast({"type": "video_generation_complete"})

        asyncio.create_task(_run())

    return {"ok": True, "scenes": len(all_scene_shots), "total_shots": total}
