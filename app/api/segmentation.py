"""LLM segmentation and shot breakdown endpoints."""

import asyncio
from fastapi import APIRouter, HTTPException
from app.database import get_session, SessionLocal
from app.models import Story, Chapter, Scene, Shot, WorldBible
from app.services.llm import segment_story, breakdown_scene
from app.web.ws import ws_manager

router = APIRouter(tags=["segmentation"])

# Track active breakdowns to prevent double-processing
_active_breakdowns: set[int] = set()


@router.post("/api/stories/{story_id}/segment")
def segment(story_id: int):
    """Segment a story into chapters and scenes using Claude."""
    session = get_session()
    try:
        story = session.query(Story).get(story_id)
        if not story:
            raise HTTPException(404, "Story not found")

        # Clear existing chapters/scenes if re-segmenting
        for ch in list(story.chapters):
            session.delete(ch)
        session.flush()

        result = segment_story(story.raw_text, story.title)

        for ch_idx, ch_data in enumerate(result.get("chapters", [])):
            chapter = Chapter(
                story_id=story.id,
                title=ch_data.get("title", f"Chapter {ch_idx + 1}"),
                summary=ch_data.get("summary", ""),
                order_index=ch_idx,
                source_text=ch_data.get("source_text", ""),
            )
            session.add(chapter)
            session.flush()

            for sc_idx, sc_data in enumerate(ch_data.get("scenes", [])):
                scene = Scene(
                    chapter_id=chapter.id,
                    order_index=sc_idx,
                    scene_type=sc_data.get("scene_type", "scene"),
                    source_text=sc_data.get("source_text", ""),
                    goal=sc_data.get("goal", ""),
                    conflict=sc_data.get("conflict", ""),
                    outcome=sc_data.get("outcome", ""),
                    emotion=sc_data.get("emotion", ""),
                    logic=sc_data.get("logic", ""),
                    decision=sc_data.get("decision", ""),
                    opening_emotion=sc_data.get("opening_emotion", ""),
                    closing_emotion=sc_data.get("closing_emotion", ""),
                    intensity=sc_data.get("intensity", 0.5),
                    target_duration=sc_data.get("target_duration", 30),
                )
                session.add(scene)

        story.status = "segmented"
        session.commit()
        return {"ok": True, "chapters": len(result.get("chapters", []))}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(500, f"Segmentation failed: {str(e)}")
    finally:
        session.close()


def _get_world_bible_context(session, story_id: int) -> dict | None:
    """Load world bible as a dict for injection into breakdown/prompts."""
    wb = session.query(WorldBible).filter_by(story_id=story_id).first()
    if not wb:
        return None
    return wb.to_full_dict()


def _do_breakdown_scene(scene_id: int, story_context: dict, world_bible: dict | None) -> tuple[int, list]:
    """Run breakdown synchronously in a thread (Claude call is blocking)."""
    session = SessionLocal()
    try:
        scene = session.query(Scene).get(scene_id)
        if not scene:
            return scene_id, []

        # Clear existing shots if re-breaking
        for sh in list(scene.shots):
            session.delete(sh)
        session.flush()

        scene_data = scene.to_dict()
        shots_data = breakdown_scene(scene_data, story_context, world_bible)

        for sh_idx, sh_data in enumerate(shots_data):
            shot = Shot(
                scene_id=scene.id,
                order_index=sh_idx,
                description=sh_data.get("description", ""),
                dialogue=sh_data.get("dialogue", ""),
                shot_type=sh_data.get("shot_type", "medium"),
                camera_movement=sh_data.get("camera_movement", "static"),
                camera_movement_detail=sh_data.get("camera_movement_detail", ""),
                color_palette=sh_data.get("color_palette", []),
                color_mood=sh_data.get("color_mood", ""),
                lighting=sh_data.get("lighting", ""),
                music_tempo=sh_data.get("music_tempo", ""),
                music_mood=sh_data.get("music_mood", ""),
                music_instruments=sh_data.get("music_instruments", ""),
                music_note=sh_data.get("music_note", ""),
                duration=sh_data.get("duration", 4.0),
                transition_type=sh_data.get("transition_type", "cut"),
                transition_duration=sh_data.get("transition_duration", 0.5),
                generation_status="pending",
            )
            session.add(shot)

        session.commit()

        # Auto-apply intelligent transitions
        try:
            from app.services.transitions import suggest_transitions
            scene = session.query(Scene).get(scene_id)
            if scene and scene.shots and len(scene.shots) >= 2:
                sorted_shots = sorted(scene.shots, key=lambda s: s.order_index)
                shots_dicts = [s.to_dict() for s in sorted_shots]
                scene_dict = scene.to_dict()
                suggestions = suggest_transitions(shots_dicts, scene_dict)
                for sug in suggestions:
                    shot = session.query(Shot).get(sug["from_shot_id"])
                    if shot:
                        shot.transition_type = sug["suggested_type"]
                        shot.transition_duration = sug["suggested_duration"]
                session.commit()
        except Exception:
            pass  # Don't fail breakdown if transitions fail

        return scene_id, shots_data
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


@router.post("/api/scenes/{scene_id}/breakdown")
async def breakdown(scene_id: int):
    """Break a scene into shots with visual direction (async with WebSocket progress)."""
    if scene_id in _active_breakdowns:
        return {"ok": True, "message": "Already breaking down this scene"}

    # Validate scene exists and get story context
    session = get_session()
    try:
        scene = session.query(Scene).get(scene_id)
        if not scene:
            raise HTTPException(404, "Scene not found")

        chapter = scene.chapter
        story = chapter.story
        story_context = {
            "visual_style": story.visual_style,
            "music_style": story.music_style,
            "color_script": story.color_script,
        }
        story_id = story.id
    finally:
        session.close()

    # Load world bible context
    session2 = get_session()
    try:
        world_bible = _get_world_bible_context(session2, story_id)
    finally:
        session2.close()

    _active_breakdowns.add(scene_id)

    async def _run():
        try:
            await ws_manager.broadcast({
                "type": "breakdown_progress",
                "scene_id": scene_id,
                "status": "started",
            })

            loop = asyncio.get_event_loop()
            _, shots_data = await loop.run_in_executor(
                None, _do_breakdown_scene, scene_id, story_context, world_bible
            )

            await ws_manager.broadcast({
                "type": "breakdown_progress",
                "scene_id": scene_id,
                "status": "complete",
                "shot_count": len(shots_data),
            })
        except Exception as e:
            await ws_manager.broadcast({
                "type": "breakdown_progress",
                "scene_id": scene_id,
                "status": "error",
                "error": str(e),
            })
        finally:
            _active_breakdowns.discard(scene_id)

    asyncio.create_task(_run())
    return {"ok": True, "message": "Breakdown started", "scene_id": scene_id}


@router.post("/api/stories/{story_id}/breakdown-all")
async def breakdown_all(story_id: int):
    """Break down all scenes in a story into shots (async with WebSocket progress)."""
    session = get_session()
    try:
        story = session.query(Story).get(story_id)
        if not story:
            raise HTTPException(404, "Story not found")

        story_context = {
            "visual_style": story.visual_style,
            "music_style": story.music_style,
            "color_script": story.color_script,
        }

        # Collect scene IDs that need breakdown
        scenes_to_breakdown = []
        for chapter in story.chapters:
            for scene in chapter.scenes:
                if not scene.shots:
                    scenes_to_breakdown.append(scene.id)
    finally:
        session.close()

    if not scenes_to_breakdown:
        return {"ok": True, "message": "All scenes already broken down", "total_scenes": 0}

    # Load world bible
    session2 = get_session()
    try:
        world_bible = _get_world_bible_context(session2, story_id)
    finally:
        session2.close()

    async def _run():
        loop = asyncio.get_event_loop()
        total_shots = 0

        for scene_id in scenes_to_breakdown:
            if scene_id in _active_breakdowns:
                continue
            _active_breakdowns.add(scene_id)

            try:
                await ws_manager.broadcast({
                    "type": "breakdown_progress",
                    "scene_id": scene_id,
                    "status": "started",
                })

                _, shots_data = await loop.run_in_executor(
                    None, _do_breakdown_scene, scene_id, story_context, world_bible
                )
                total_shots += len(shots_data)

                await ws_manager.broadcast({
                    "type": "breakdown_progress",
                    "scene_id": scene_id,
                    "status": "complete",
                    "shot_count": len(shots_data),
                })
            except Exception as e:
                await ws_manager.broadcast({
                    "type": "breakdown_progress",
                    "scene_id": scene_id,
                    "status": "error",
                    "error": str(e),
                })
            finally:
                _active_breakdowns.discard(scene_id)

        # Update story status
        s = SessionLocal()
        try:
            st = s.query(Story).get(story_id)
            if st:
                st.status = "broken_down"
                s.commit()
        finally:
            s.close()

        await ws_manager.broadcast({
            "type": "breakdown_all_complete",
            "story_id": story_id,
            "total_shots": total_shots,
        })

    asyncio.create_task(_run())
    return {"ok": True, "message": "Breakdown started", "total_scenes": len(scenes_to_breakdown)}
