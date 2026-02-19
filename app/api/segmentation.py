"""LLM segmentation and shot breakdown endpoints."""

from fastapi import APIRouter, HTTPException
from app.database import get_session
from app.models import Story, Chapter, Scene, Shot
from app.services.llm import segment_story, breakdown_scene

router = APIRouter(tags=["segmentation"])


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


@router.post("/api/scenes/{scene_id}/breakdown")
def breakdown(scene_id: int):
    """Break a scene into shots with visual direction."""
    session = get_session()
    try:
        scene = session.query(Scene).get(scene_id)
        if not scene:
            raise HTTPException(404, "Scene not found")

        chapter = scene.chapter
        story = chapter.story

        # Clear existing shots if re-breaking
        for sh in list(scene.shots):
            session.delete(sh)
        session.flush()

        scene_data = scene.to_dict()
        story_context = {
            "visual_style": story.visual_style,
            "music_style": story.music_style,
            "color_script": story.color_script,
        }

        shots_data = breakdown_scene(scene_data, story_context)

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
        return {"ok": True, "shots": len(shots_data)}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(500, f"Breakdown failed: {str(e)}")
    finally:
        session.close()


@router.post("/api/stories/{story_id}/breakdown-all")
def breakdown_all(story_id: int):
    """Break down all scenes in a story into shots."""
    session = get_session()
    try:
        story = session.query(Story).get(story_id)
        if not story:
            raise HTTPException(404, "Story not found")

        total_shots = 0
        story_context = {
            "visual_style": story.visual_style,
            "music_style": story.music_style,
            "color_script": story.color_script,
        }

        for chapter in story.chapters:
            for scene in chapter.scenes:
                # Skip if already has shots
                if scene.shots:
                    total_shots += len(scene.shots)
                    continue

                scene_data = scene.to_dict()
                shots_data = breakdown_scene(scene_data, story_context)

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
                    total_shots += 1

        story.status = "broken_down"
        session.commit()
        return {"ok": True, "total_shots": total_shots}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(500, f"Breakdown failed: {str(e)}")
    finally:
        session.close()
