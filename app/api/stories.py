"""Story CRUD endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import get_session
from app.models import Story

router = APIRouter(prefix="/api/stories", tags=["stories"])


class StoryCreate(BaseModel):
    title: str
    raw_text: str
    visual_style: str = ""
    music_style: str = ""


class StoryUpdate(BaseModel):
    title: str | None = None
    visual_style: str | None = None
    color_script: dict | None = None
    music_style: str | None = None


@router.get("")
def list_stories():
    session = get_session()
    try:
        stories = session.query(Story).order_by(Story.created_at.desc()).all()
        return [s.to_dict() for s in stories]
    finally:
        session.close()


@router.post("")
def create_story(body: StoryCreate):
    session = get_session()
    try:
        story = Story(
            title=body.title,
            raw_text=body.raw_text,
            visual_style=body.visual_style,
            music_style=body.music_style,
        )
        session.add(story)
        session.commit()
        session.refresh(story)
        return story.to_dict()
    finally:
        session.close()


@router.get("/{story_id}")
def get_story(story_id: int):
    session = get_session()
    try:
        story = session.query(Story).get(story_id)
        if not story:
            raise HTTPException(404, "Story not found")
        return story.to_dict()
    finally:
        session.close()


@router.patch("/{story_id}")
def update_story(story_id: int, body: StoryUpdate):
    session = get_session()
    try:
        story = session.query(Story).get(story_id)
        if not story:
            raise HTTPException(404, "Story not found")
        for field, val in body.model_dump(exclude_unset=True).items():
            setattr(story, field, val)
        session.commit()
        session.refresh(story)
        return story.to_dict()
    finally:
        session.close()


@router.delete("/{story_id}")
def delete_story(story_id: int):
    session = get_session()
    try:
        story = session.query(Story).get(story_id)
        if not story:
            raise HTTPException(404, "Story not found")
        session.delete(story)
        session.commit()
        return {"ok": True}
    finally:
        session.close()


@router.get("/{story_id}/full")
def get_story_full(story_id: int):
    """Get story with all chapters, scenes, and shots."""
    session = get_session()
    try:
        story = session.query(Story).get(story_id)
        if not story:
            raise HTTPException(404, "Story not found")
        result = story.to_dict()
        result["chapters"] = []
        for ch in story.chapters:
            ch_dict = ch.to_dict()
            ch_dict["scenes"] = []
            for sc in ch.scenes:
                sc_dict = sc.to_dict()
                sc_dict["shots"] = [sh.to_dict() for sh in sc.shots]
                ch_dict["scenes"].append(sc_dict)
            result["chapters"].append(ch_dict)
        return result
    finally:
        session.close()
