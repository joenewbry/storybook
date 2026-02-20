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
    scene_assets = relationship("SceneAsset", back_populates="scene", cascade="all, delete-orphan")

    def to_dict(self):
        shot_map = None
        if self.scene_assets:
            for sa in self.scene_assets:
                if sa.asset_type == "shot_map" and sa.is_current:
                    shot_map = sa.to_dict()
                    break
        return {
            "id": self.id, "chapter_id": self.chapter_id,
            "order_index": self.order_index, "scene_type": self.scene_type,
            "source_text": self.source_text,
            "goal": self.goal, "conflict": self.conflict, "outcome": self.outcome,
            "emotion": self.emotion, "logic": self.logic, "decision": self.decision,
            "opening_emotion": self.opening_emotion, "closing_emotion": self.closing_emotion,
            "intensity": self.intensity, "target_duration": self.target_duration,
            "shot_count": len(self.shots) if self.shots else 0,
            "shot_map": shot_map,
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
    video_prompt = Column(Text, default="")
    video_generation_status = Column(String(50), default="pending")  # pending, generating, complete, error

    scene = relationship("Scene", back_populates="shots")
    assets = relationship("Asset", back_populates="shot", cascade="all, delete-orphan")

    def to_dict(self):
        current_image = None
        current_video = None
        if self.assets:
            for a in self.assets:
                if a.is_current and a.asset_type == "image" and not current_image:
                    current_image = a.to_dict()
                if a.is_current and a.asset_type == "video" and not current_video:
                    current_video = a.to_dict()
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
            "video_prompt": self.video_prompt,
            "video_generation_status": self.video_generation_status,
            "current_image": current_image,
            "current_video": current_video,
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


class SceneAsset(Base):
    __tablename__ = "scene_assets"

    id = Column(Integer, primary_key=True)
    scene_id = Column(Integer, ForeignKey("scenes.id"), nullable=False)
    asset_type = Column(String(50), default="shot_map")  # shot_map
    file_path = Column(String(500), default="")
    generation_params = Column(JSON, default=dict)
    is_current = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    scene = relationship("Scene", back_populates="scene_assets")

    def to_dict(self):
        return {
            "id": self.id, "scene_id": self.scene_id,
            "asset_type": self.asset_type, "file_path": self.file_path,
            "generation_params": self.generation_params,
            "is_current": self.is_current,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ===== World Bible Models =====

class WorldBible(Base):
    __tablename__ = "world_bibles"

    id = Column(Integer, primary_key=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False, unique=True)
    status = Column(String(50), default="extracting")  # extracting, extracted, complete
    global_style_prompt = Column(Text, default="")
    design_language = Column(Text, default="")  # shape language rules, stylization level
    color_palette = Column(JSON, default=list)  # master palette
    era_setting = Column(Text, default="")
    atmosphere = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    story = relationship("Story", backref="world_bible", uselist=False)
    characters = relationship("Character", back_populates="world_bible", cascade="all, delete-orphan")
    locations = relationship("Location", back_populates="world_bible", cascade="all, delete-orphan")
    props = relationship("Prop", back_populates="world_bible", cascade="all, delete-orphan")
    camera_bible = relationship("CameraBible", back_populates="world_bible", uselist=False, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id, "story_id": self.story_id, "status": self.status,
            "global_style_prompt": self.global_style_prompt,
            "design_language": self.design_language,
            "color_palette": self.color_palette,
            "era_setting": self.era_setting, "atmosphere": self.atmosphere,
            "character_count": len(self.characters) if self.characters else 0,
            "location_count": len(self.locations) if self.locations else 0,
            "prop_count": len(self.props) if self.props else 0,
            "has_camera_bible": self.camera_bible is not None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_full_dict(self):
        d = self.to_dict()
        d["characters"] = [c.to_dict() for c in (self.characters or [])]
        d["locations"] = [l.to_dict() for l in (self.locations or [])]
        d["props"] = [p.to_dict() for p in (self.props or [])]
        d["camera_bible"] = self.camera_bible.to_dict() if self.camera_bible else None
        return d


class Character(Base):
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True)
    world_bible_id = Column(Integer, ForeignKey("world_bibles.id"), nullable=False)
    name = Column(String(200), nullable=False)
    role = Column(String(100), default="")  # protagonist, antagonist, supporting, etc.
    age_appearance = Column(String(100), default="")
    gender_presentation = Column(String(100), default="")
    body_type = Column(String(200), default="")
    face_description = Column(Text, default="")
    hair = Column(String(200), default="")
    skin = Column(String(200), default="")
    clothing_default = Column(Text, default="")
    distinctive_features = Column(Text, default="")
    demeanor = Column(Text, default="")
    prompt_description = Column(Text, default="")  # compiled injection block
    scene_appearances = Column(JSON, default=list)  # scene IDs where this character appears

    world_bible = relationship("WorldBible", back_populates="characters")
    references = relationship("CharacterReference", back_populates="character", cascade="all, delete-orphan")

    def to_dict(self):
        approved_refs = [r.to_dict() for r in (self.references or []) if r.is_approved]
        all_refs = [r.to_dict() for r in (self.references or [])]
        return {
            "id": self.id, "world_bible_id": self.world_bible_id,
            "name": self.name, "role": self.role,
            "age_appearance": self.age_appearance,
            "gender_presentation": self.gender_presentation,
            "body_type": self.body_type, "face_description": self.face_description,
            "hair": self.hair, "skin": self.skin,
            "clothing_default": self.clothing_default,
            "distinctive_features": self.distinctive_features,
            "demeanor": self.demeanor,
            "prompt_description": self.prompt_description,
            "scene_appearances": self.scene_appearances,
            "references": all_refs,
            "approved_ref": approved_refs[0] if approved_refs else None,
        }


class CharacterReference(Base):
    __tablename__ = "character_references"

    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    ref_type = Column(String(50), default="portrait")  # portrait, full_body, three_quarter
    file_path = Column(String(500), default="")
    prompt_used = Column(Text, default="")
    is_approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)

    character = relationship("Character", back_populates="references")

    def to_dict(self):
        return {
            "id": self.id, "character_id": self.character_id,
            "ref_type": self.ref_type, "file_path": self.file_path,
            "prompt_used": self.prompt_used, "is_approved": self.is_approved,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True)
    world_bible_id = Column(Integer, ForeignKey("world_bibles.id"), nullable=False)
    name = Column(String(200), nullable=False)
    location_type = Column(String(50), default="")  # interior, exterior
    description = Column(Text, default="")
    architectural_style = Column(Text, default="")
    lighting_default = Column(Text, default="")
    color_palette = Column(JSON, default=list)
    atmosphere = Column(Text, default="")
    time_of_day = Column(String(100), default="")
    key_objects = Column(Text, default="")
    prompt_description = Column(Text, default="")
    scene_appearances = Column(JSON, default=list)

    world_bible = relationship("WorldBible", back_populates="locations")
    references = relationship("LocationReference", back_populates="location", cascade="all, delete-orphan")

    def to_dict(self):
        approved_refs = [r.to_dict() for r in (self.references or []) if r.is_approved]
        all_refs = [r.to_dict() for r in (self.references or [])]
        return {
            "id": self.id, "world_bible_id": self.world_bible_id,
            "name": self.name, "location_type": self.location_type,
            "description": self.description,
            "architectural_style": self.architectural_style,
            "lighting_default": self.lighting_default,
            "color_palette": self.color_palette,
            "atmosphere": self.atmosphere, "time_of_day": self.time_of_day,
            "key_objects": self.key_objects,
            "prompt_description": self.prompt_description,
            "scene_appearances": self.scene_appearances,
            "references": all_refs,
            "approved_ref": approved_refs[0] if approved_refs else None,
        }


class LocationReference(Base):
    __tablename__ = "location_references"

    id = Column(Integer, primary_key=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    ref_type = Column(String(50), default="establishing")  # establishing, detail, mood
    file_path = Column(String(500), default="")
    prompt_used = Column(Text, default="")
    is_approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)

    location = relationship("Location", back_populates="references")

    def to_dict(self):
        return {
            "id": self.id, "location_id": self.location_id,
            "ref_type": self.ref_type, "file_path": self.file_path,
            "prompt_used": self.prompt_used, "is_approved": self.is_approved,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Prop(Base):
    __tablename__ = "props"

    id = Column(Integer, primary_key=True)
    world_bible_id = Column(Integer, ForeignKey("world_bibles.id"), nullable=False)
    name = Column(String(200), nullable=False)
    category = Column(String(100), default="")  # technology, weapon, vehicle, personal_item
    description = Column(Text, default="")
    visual_details = Column(Text, default="")
    scale = Column(String(200), default="")
    material_notes = Column(Text, default="")
    prompt_description = Column(Text, default="")
    scene_appearances = Column(JSON, default=list)

    world_bible = relationship("WorldBible", back_populates="props")
    references = relationship("PropReference", back_populates="prop", cascade="all, delete-orphan")

    def to_dict(self):
        approved_refs = [r.to_dict() for r in (self.references or []) if r.is_approved]
        all_refs = [r.to_dict() for r in (self.references or [])]
        return {
            "id": self.id, "world_bible_id": self.world_bible_id,
            "name": self.name, "category": self.category,
            "description": self.description, "visual_details": self.visual_details,
            "scale": self.scale, "material_notes": self.material_notes,
            "prompt_description": self.prompt_description,
            "scene_appearances": self.scene_appearances,
            "references": all_refs,
            "approved_ref": approved_refs[0] if approved_refs else None,
        }


class PropReference(Base):
    __tablename__ = "prop_references"

    id = Column(Integer, primary_key=True)
    prop_id = Column(Integer, ForeignKey("props.id"), nullable=False)
    ref_type = Column(String(50), default="detail")  # detail, in_use, scale_reference
    file_path = Column(String(500), default="")
    prompt_used = Column(Text, default="")
    is_approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)

    prop = relationship("Prop", back_populates="references")

    def to_dict(self):
        return {
            "id": self.id, "prop_id": self.prop_id,
            "ref_type": self.ref_type, "file_path": self.file_path,
            "prompt_used": self.prompt_used, "is_approved": self.is_approved,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CameraBible(Base):
    __tablename__ = "camera_bibles"

    id = Column(Integer, primary_key=True)
    world_bible_id = Column(Integer, ForeignKey("world_bibles.id"), nullable=False, unique=True)
    lens_style = Column(Text, default="")  # e.g. "anamorphic, shallow DOF"
    film_stock = Column(Text, default="")  # e.g. "Kodak Vision3 500T, heavy grain"
    color_grading = Column(Text, default="")  # e.g. "teal and orange push, crushed blacks"
    lighting_philosophy = Column(Text, default="")  # e.g. "motivated lighting only"
    movement_philosophy = Column(Text, default="")  # e.g. "handheld for tension, locked off for power"
    reference_films = Column(Text, default="")
    prompt_prefix = Column(Text, default="")  # compiled text that starts every image prompt

    world_bible = relationship("WorldBible", back_populates="camera_bible")

    def to_dict(self):
        return {
            "id": self.id, "world_bible_id": self.world_bible_id,
            "lens_style": self.lens_style, "film_stock": self.film_stock,
            "color_grading": self.color_grading,
            "lighting_philosophy": self.lighting_philosophy,
            "movement_philosophy": self.movement_philosophy,
            "reference_films": self.reference_films,
            "prompt_prefix": self.prompt_prefix,
        }
