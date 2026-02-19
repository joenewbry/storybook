"""SQLAlchemy models: Story → Chapter → Scene → Shot → Asset."""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime,
    ForeignKey, JSON,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _utcnow():
    return datetime.now(timezone.utc)


class Story(Base):
    __tablename__ = "stories"

    id = Column(Integer, primary_key=True)
    title = Column(String(300), nullable=False)
    raw_text = Column(Text, nullable=False)
    visual_style = Column(Text, default="")
    color_script = Column(JSON, default=dict)  # emotion → palette map
    music_style = Column(Text, default="")
    status = Column(String(50), default="draft")  # draft, segmented, broken_down, generating, complete
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    chapters = relationship("Chapter", back_populates="story", cascade="all, delete-orphan",
                            order_by="Chapter.order_index")

    def to_dict(self):
        return {
            "id": self.id, "title": self.title, "raw_text": self.raw_text,
            "visual_style": self.visual_style, "color_script": self.color_script,
            "music_style": self.music_style, "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "chapter_count": len(self.chapters) if self.chapters else 0,
            "scene_count": sum(len(ch.scenes) for ch in self.chapters) if self.chapters else 0,
            "shot_count": sum(
                len(sc.shots) for ch in self.chapters for sc in ch.scenes
            ) if self.chapters else 0,
        }


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False)
    title = Column(String(300), default="")
    summary = Column(Text, default="")
    order_index = Column(Integer, default=0)
    source_text = Column(Text, default="")

    story = relationship("Story", back_populates="chapters")
    scenes = relationship("Scene", back_populates="chapter", cascade="all, delete-orphan",
                          order_by="Scene.order_index")

    def to_dict(self):
        return {
            "id": self.id, "story_id": self.story_id, "title": self.title,
            "summary": self.summary, "order_index": self.order_index,
            "source_text": self.source_text,
            "scene_count": len(self.scenes) if self.scenes else 0,
        }


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(Integer, primary_key=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    order_index = Column(Integer, default=0)
    scene_type = Column(String(20), default="scene")  # scene or sequel
    source_text = Column(Text, default="")
    goal = Column(Text, default="")
    conflict = Column(Text, default="")
    outcome = Column(Text, default="")
    # For sequels: emotion, logic, decision
    emotion = Column(Text, default="")
    logic = Column(Text, default="")
    decision = Column(Text, default="")
    opening_emotion = Column(String(100), default="")
    closing_emotion = Column(String(100), default="")
    intensity = Column(Float, default=0.5)  # 0-1
    target_duration = Column(Integer, default=30)  # seconds, 15-60

    chapter = relationship("Chapter", back_populates="scenes")
    shots = relationship("Shot", back_populates="scene", cascade="all, delete-orphan",
                         order_by="Shot.order_index")

    def to_dict(self):
        return {
            "id": self.id, "chapter_id": self.chapter_id,
            "order_index": self.order_index, "scene_type": self.scene_type,
            "source_text": self.source_text,
            "goal": self.goal, "conflict": self.conflict, "outcome": self.outcome,
            "emotion": self.emotion, "logic": self.logic, "decision": self.decision,
            "opening_emotion": self.opening_emotion, "closing_emotion": self.closing_emotion,
            "intensity": self.intensity, "target_duration": self.target_duration,
            "shot_count": len(self.shots) if self.shots else 0,
        }


class Shot(Base):
    __tablename__ = "shots"

    id = Column(Integer, primary_key=True)
    scene_id = Column(Integer, ForeignKey("scenes.id"), nullable=False)
    order_index = Column(Integer, default=0)
    description = Column(Text, default="")
    dialogue = Column(Text, default="")
    shot_type = Column(String(50), default="")  # wide, medium, close-up, extreme-close-up, etc.
    camera_movement = Column(String(50), default="")  # static, pan, tilt, zoom, dolly, crane, etc.
    camera_movement_detail = Column(Text, default="")
    color_palette = Column(JSON, default=list)  # list of hex colors
    color_mood = Column(String(100), default="")
    lighting = Column(String(200), default="")
    music_tempo = Column(String(50), default="")
    music_mood = Column(String(100), default="")
    music_instruments = Column(String(200), default="")
    music_note = Column(Text, default="")
    duration = Column(Float, default=4.0)  # seconds, 2-8
    transition_type = Column(String(50), default="cut")  # cut, dissolve, fade, wipe
    transition_duration = Column(Float, default=0.5)
    image_prompt = Column(Text, default="")
    generation_status = Column(String(50), default="pending")  # pending, prompt_ready, generating, complete, error

    scene = relationship("Scene", back_populates="shots")
    assets = relationship("Asset", back_populates="shot", cascade="all, delete-orphan")

    def to_dict(self):
        current_asset = None
        if self.assets:
            for a in self.assets:
                if a.is_current and a.asset_type == "image":
                    current_asset = a.to_dict()
                    break
        return {
            "id": self.id, "scene_id": self.scene_id,
            "order_index": self.order_index, "description": self.description,
            "dialogue": self.dialogue, "shot_type": self.shot_type,
            "camera_movement": self.camera_movement,
            "camera_movement_detail": self.camera_movement_detail,
            "color_palette": self.color_palette, "color_mood": self.color_mood,
            "lighting": self.lighting,
            "music_tempo": self.music_tempo, "music_mood": self.music_mood,
            "music_instruments": self.music_instruments, "music_note": self.music_note,
            "duration": self.duration,
            "transition_type": self.transition_type,
            "transition_duration": self.transition_duration,
            "image_prompt": self.image_prompt,
            "generation_status": self.generation_status,
            "current_image": current_asset,
        }


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True)
    shot_id = Column(Integer, ForeignKey("shots.id"), nullable=False)
    asset_type = Column(String(20), default="image")  # image, video, composed
    file_path = Column(String(500), default="")
    generation_params = Column(JSON, default=dict)
    is_current = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    shot = relationship("Shot", back_populates="assets")

    def to_dict(self):
        return {
            "id": self.id, "shot_id": self.shot_id,
            "asset_type": self.asset_type, "file_path": self.file_path,
            "generation_params": self.generation_params,
            "is_current": self.is_current,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
