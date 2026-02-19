"""Image generation endpoints."""

import asyncio
from fastapi import APIRouter, HTTPException
from app.database import get_session, SessionLocal
from app.models import Story, Shot, WorldBible
from app.services.prompt_builder import build_image_prompt
from app.services.queue import generation_queue

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
