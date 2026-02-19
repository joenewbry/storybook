"""Shot CRUD + reordering endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import get_session
from app.models import Shot

router = APIRouter(prefix="/api/shots", tags=["shots"])


class ShotUpdate(BaseModel):
    description: str | None = None
    dialogue: str | None = None
    shot_type: str | None = None
    camera_movement: str | None = None
    camera_movement_detail: str | None = None
    color_palette: list[str] | None = None
    color_mood: str | None = None
    lighting: str | None = None
    music_tempo: str | None = None
    music_mood: str | None = None
    music_instruments: str | None = None
    music_note: str | None = None
    duration: float | None = None
    transition_type: str | None = None
    transition_duration: float | None = None
    image_prompt: str | None = None


@router.get("/{shot_id}")
def get_shot(shot_id: int):
    session = get_session()
    try:
        shot = session.query(Shot).get(shot_id)
        if not shot:
            raise HTTPException(404, "Shot not found")
        return shot.to_dict()
    finally:
        session.close()


@router.patch("/{shot_id}")
def update_shot(shot_id: int, body: ShotUpdate):
    session = get_session()
    try:
        shot = session.query(Shot).get(shot_id)
        if not shot:
            raise HTTPException(404, "Shot not found")
        for field, val in body.model_dump(exclude_unset=True).items():
            setattr(shot, field, val)
        session.commit()
        session.refresh(shot)
        return shot.to_dict()
    finally:
        session.close()


class ReorderBody(BaseModel):
    shot_ids: list[int]


@router.post("/reorder")
def reorder_shots(body: ReorderBody):
    """Reorder shots by providing shot IDs in desired order."""
    session = get_session()
    try:
        for idx, shot_id in enumerate(body.shot_ids):
            shot = session.query(Shot).get(shot_id)
            if shot:
                shot.order_index = idx
        session.commit()
        return {"ok": True}
    finally:
        session.close()
