"""World Bible API endpoints — extraction, CRUD, reference generation."""

import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import get_session, SessionLocal
from app.models import (
    Story, WorldBible, Character, CharacterReference,
    Location, LocationReference, Prop, PropReference, CameraBible,
)
from app.services.world_builder import extract_world_elements, refine_prompt_descriptions
from app.services.reference_generator import (
    generate_character_reference, generate_location_reference, generate_prop_reference,
    CHARACTER_REF_TYPES, LOCATION_REF_TYPES, PROP_REF_TYPES,
)
from app.web.ws import ws_manager

router = APIRouter(tags=["world_bible"])


# ===== Extraction =====

@router.post("/api/stories/{story_id}/world-bible/extract")
async def extract_world_bible(story_id: int):
    """Extract world bible from story text (async with WebSocket progress)."""
    session = get_session()
    try:
        story = session.query(Story).get(story_id)
        if not story:
            raise HTTPException(404, "Story not found")

        # Remove existing world bible if re-extracting
        existing = session.query(WorldBible).filter_by(story_id=story_id).first()
        if existing:
            session.delete(existing)
            session.flush()

        raw_text = story.raw_text
        visual_style = story.visual_style
        sid = story.id
    finally:
        session.close()

    async def _run():
        try:
            await ws_manager.broadcast({
                "type": "extraction_progress",
                "story_id": sid,
                "status": "extracting",
                "step": "Analyzing story for characters, locations, props...",
            })

            loop = asyncio.get_event_loop()

            # Step 1: Extract world elements
            world_data = await loop.run_in_executor(
                None, extract_world_elements, raw_text, visual_style
            )

            await ws_manager.broadcast({
                "type": "extraction_progress",
                "story_id": sid,
                "status": "refining",
                "step": "Refining prompt descriptions for image generation...",
            })

            # Step 2: Refine prompt descriptions
            refined = await loop.run_in_executor(
                None, refine_prompt_descriptions, world_data, visual_style
            )

            # Merge refined descriptions back
            refined_chars = {c["name"]: c["prompt_description"] for c in refined.get("characters", [])}
            refined_locs = {l["name"]: l["prompt_description"] for l in refined.get("locations", [])}
            refined_props = {p["name"]: p["prompt_description"] for p in refined.get("props", [])}

            # Step 3: Save to DB
            s = SessionLocal()
            try:
                wb = WorldBible(
                    story_id=sid,
                    status="extracted",
                    global_style_prompt=world_data.get("global_style_prompt", ""),
                    design_language=world_data.get("design_language", ""),
                    color_palette=world_data.get("color_palette", []),
                    era_setting=world_data.get("era_setting", ""),
                    atmosphere=world_data.get("atmosphere", ""),
                )
                s.add(wb)
                s.flush()

                # Characters
                for c_data in world_data.get("characters", []):
                    char = Character(
                        world_bible_id=wb.id,
                        name=c_data.get("name", "Unknown"),
                        role=c_data.get("role", ""),
                        age_appearance=c_data.get("age_appearance", ""),
                        gender_presentation=c_data.get("gender_presentation", ""),
                        body_type=c_data.get("body_type", ""),
                        face_description=c_data.get("face_description", ""),
                        hair=c_data.get("hair", ""),
                        skin=c_data.get("skin", ""),
                        clothing_default=c_data.get("clothing_default", ""),
                        distinctive_features=c_data.get("distinctive_features", ""),
                        demeanor=c_data.get("demeanor", ""),
                        prompt_description=refined_chars.get(c_data.get("name", ""), ""),
                        scene_appearances=c_data.get("scene_appearances", []),
                    )
                    s.add(char)

                # Locations
                for l_data in world_data.get("locations", []):
                    loc = Location(
                        world_bible_id=wb.id,
                        name=l_data.get("name", "Unknown"),
                        location_type=l_data.get("location_type", ""),
                        description=l_data.get("description", ""),
                        architectural_style=l_data.get("architectural_style", ""),
                        lighting_default=l_data.get("lighting_default", ""),
                        color_palette=l_data.get("color_palette", []),
                        atmosphere=l_data.get("atmosphere", ""),
                        time_of_day=l_data.get("time_of_day", ""),
                        key_objects=l_data.get("key_objects", ""),
                        prompt_description=refined_locs.get(l_data.get("name", ""), ""),
                        scene_appearances=l_data.get("scene_appearances", []),
                    )
                    s.add(loc)

                # Props
                for p_data in world_data.get("props", []):
                    prop = Prop(
                        world_bible_id=wb.id,
                        name=p_data.get("name", "Unknown"),
                        category=p_data.get("category", ""),
                        description=p_data.get("description", ""),
                        visual_details=p_data.get("visual_details", ""),
                        scale=p_data.get("scale", ""),
                        material_notes=p_data.get("material_notes", ""),
                        prompt_description=refined_props.get(p_data.get("name", ""), ""),
                        scene_appearances=p_data.get("scene_appearances", []),
                    )
                    s.add(prop)

                # Camera Bible
                cam_data = world_data.get("camera_bible", {})
                camera = CameraBible(
                    world_bible_id=wb.id,
                    lens_style=cam_data.get("lens_style", ""),
                    film_stock=cam_data.get("film_stock", ""),
                    color_grading=cam_data.get("color_grading", ""),
                    lighting_philosophy=cam_data.get("lighting_philosophy", ""),
                    movement_philosophy=cam_data.get("movement_philosophy", ""),
                    reference_films=cam_data.get("reference_films", ""),
                    prompt_prefix=refined.get("camera_prompt_prefix", ""),
                )
                s.add(camera)

                # Update story status
                story = s.query(Story).get(sid)
                if story:
                    story.status = "world_extracted"

                s.commit()

                await ws_manager.broadcast({
                    "type": "extraction_progress",
                    "story_id": sid,
                    "status": "complete",
                    "world_bible": wb.to_full_dict(),
                })
            except Exception as e:
                s.rollback()
                raise e
            finally:
                s.close()

        except Exception as e:
            await ws_manager.broadcast({
                "type": "extraction_progress",
                "story_id": sid,
                "status": "error",
                "error": str(e),
            })

    asyncio.create_task(_run())
    return {"ok": True, "message": "World bible extraction started"}


# ===== Read =====

@router.get("/api/stories/{story_id}/world-bible")
def get_world_bible(story_id: int):
    """Get the world bible for a story."""
    session = get_session()
    try:
        wb = session.query(WorldBible).filter_by(story_id=story_id).first()
        if not wb:
            raise HTTPException(404, "No world bible found for this story")
        return wb.to_full_dict()
    finally:
        session.close()


# ===== Character CRUD =====

class CharacterUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    age_appearance: str | None = None
    gender_presentation: str | None = None
    body_type: str | None = None
    face_description: str | None = None
    hair: str | None = None
    skin: str | None = None
    clothing_default: str | None = None
    distinctive_features: str | None = None
    demeanor: str | None = None
    prompt_description: str | None = None


@router.patch("/api/characters/{char_id}")
def update_character(char_id: int, data: CharacterUpdate):
    session = get_session()
    try:
        char = session.query(Character).get(char_id)
        if not char:
            raise HTTPException(404, "Character not found")
        for field, val in data.model_dump(exclude_none=True).items():
            setattr(char, field, val)
        session.commit()
        return char.to_dict()
    finally:
        session.close()


@router.delete("/api/characters/{char_id}")
def delete_character(char_id: int):
    session = get_session()
    try:
        char = session.query(Character).get(char_id)
        if not char:
            raise HTTPException(404, "Character not found")
        session.delete(char)
        session.commit()
        return {"ok": True}
    finally:
        session.close()


# ===== Location CRUD =====

class LocationUpdate(BaseModel):
    name: str | None = None
    location_type: str | None = None
    description: str | None = None
    architectural_style: str | None = None
    lighting_default: str | None = None
    atmosphere: str | None = None
    time_of_day: str | None = None
    key_objects: str | None = None
    prompt_description: str | None = None


@router.patch("/api/locations/{loc_id}")
def update_location(loc_id: int, data: LocationUpdate):
    session = get_session()
    try:
        loc = session.query(Location).get(loc_id)
        if not loc:
            raise HTTPException(404, "Location not found")
        for field, val in data.model_dump(exclude_none=True).items():
            setattr(loc, field, val)
        session.commit()
        return loc.to_dict()
    finally:
        session.close()


@router.delete("/api/locations/{loc_id}")
def delete_location(loc_id: int):
    session = get_session()
    try:
        loc = session.query(Location).get(loc_id)
        if not loc:
            raise HTTPException(404, "Location not found")
        session.delete(loc)
        session.commit()
        return {"ok": True}
    finally:
        session.close()


# ===== Prop CRUD =====

class PropUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    description: str | None = None
    visual_details: str | None = None
    scale: str | None = None
    material_notes: str | None = None
    prompt_description: str | None = None


@router.patch("/api/props/{prop_id}")
def update_prop(prop_id: int, data: PropUpdate):
    session = get_session()
    try:
        prop = session.query(Prop).get(prop_id)
        if not prop:
            raise HTTPException(404, "Prop not found")
        for field, val in data.model_dump(exclude_none=True).items():
            setattr(prop, field, val)
        session.commit()
        return prop.to_dict()
    finally:
        session.close()


@router.delete("/api/props/{prop_id}")
def delete_prop(prop_id: int):
    session = get_session()
    try:
        prop = session.query(Prop).get(prop_id)
        if not prop:
            raise HTTPException(404, "Prop not found")
        session.delete(prop)
        session.commit()
        return {"ok": True}
    finally:
        session.close()


# ===== Camera Bible =====

class CameraBibleUpdate(BaseModel):
    lens_style: str | None = None
    film_stock: str | None = None
    color_grading: str | None = None
    lighting_philosophy: str | None = None
    movement_philosophy: str | None = None
    reference_films: str | None = None
    prompt_prefix: str | None = None


@router.patch("/api/camera-bible/{cb_id}")
def update_camera_bible(cb_id: int, data: CameraBibleUpdate):
    session = get_session()
    try:
        cb = session.query(CameraBible).get(cb_id)
        if not cb:
            raise HTTPException(404, "Camera bible not found")
        for field, val in data.model_dump(exclude_none=True).items():
            setattr(cb, field, val)
        session.commit()
        return cb.to_dict()
    finally:
        session.close()


# ===== Reference Generation =====

@router.post("/api/characters/{char_id}/generate-references")
async def generate_char_references(char_id: int):
    """Generate reference images for a character (portrait, full_body, three_quarter)."""
    session = get_session()
    try:
        char = session.query(Character).get(char_id)
        if not char:
            raise HTTPException(404, "Character not found")
        prompt_desc = char.prompt_description
        char_name = char.name
        wb = char.world_bible
        camera_prefix = wb.camera_bible.prompt_prefix if wb and wb.camera_bible else ""
    finally:
        session.close()

    if not prompt_desc:
        raise HTTPException(400, "Character has no prompt_description. Edit it first.")

    async def _run():
        for ref_type in CHARACTER_REF_TYPES:
            await ws_manager.broadcast({
                "type": "reference_progress",
                "entity_type": "character",
                "entity_id": char_id,
                "ref_type": ref_type,
                "status": "generating",
            })

            file_path, prompt_used = await generate_character_reference(
                char_id, ref_type, prompt_desc, camera_prefix
            )

            s = SessionLocal()
            try:
                ref = CharacterReference(
                    character_id=char_id,
                    ref_type=ref_type,
                    file_path=file_path or "",
                    prompt_used=prompt_used,
                    is_approved=False,
                )
                s.add(ref)
                s.commit()
                ref_dict = ref.to_dict()
            finally:
                s.close()

            await ws_manager.broadcast({
                "type": "reference_progress",
                "entity_type": "character",
                "entity_id": char_id,
                "ref_type": ref_type,
                "status": "complete" if file_path else "error",
                "reference": ref_dict,
            })

    asyncio.create_task(_run())
    return {"ok": True, "message": f"Generating references for {char_name}"}


@router.post("/api/locations/{loc_id}/generate-references")
async def generate_loc_references(loc_id: int):
    """Generate reference images for a location (establishing, detail)."""
    session = get_session()
    try:
        loc = session.query(Location).get(loc_id)
        if not loc:
            raise HTTPException(404, "Location not found")
        prompt_desc = loc.prompt_description
        loc_name = loc.name
        wb = loc.world_bible
        camera_prefix = wb.camera_bible.prompt_prefix if wb and wb.camera_bible else ""
    finally:
        session.close()

    if not prompt_desc:
        raise HTTPException(400, "Location has no prompt_description. Edit it first.")

    async def _run():
        for ref_type in LOCATION_REF_TYPES:
            await ws_manager.broadcast({
                "type": "reference_progress",
                "entity_type": "location",
                "entity_id": loc_id,
                "ref_type": ref_type,
                "status": "generating",
            })

            file_path, prompt_used = await generate_location_reference(
                loc_id, ref_type, prompt_desc, camera_prefix
            )

            s = SessionLocal()
            try:
                ref = LocationReference(
                    location_id=loc_id,
                    ref_type=ref_type,
                    file_path=file_path or "",
                    prompt_used=prompt_used,
                    is_approved=False,
                )
                s.add(ref)
                s.commit()
                ref_dict = ref.to_dict()
            finally:
                s.close()

            await ws_manager.broadcast({
                "type": "reference_progress",
                "entity_type": "location",
                "entity_id": loc_id,
                "ref_type": ref_type,
                "status": "complete" if file_path else "error",
                "reference": ref_dict,
            })

    asyncio.create_task(_run())
    return {"ok": True, "message": f"Generating references for {loc_name}"}


@router.post("/api/props/{prop_id}/generate-references")
async def generate_prop_references(prop_id: int):
    """Generate reference images for a prop (detail)."""
    session = get_session()
    try:
        prop = session.query(Prop).get(prop_id)
        if not prop:
            raise HTTPException(404, "Prop not found")
        prompt_desc = prop.prompt_description
        prop_name = prop.name
        wb = prop.world_bible
        camera_prefix = wb.camera_bible.prompt_prefix if wb and wb.camera_bible else ""
    finally:
        session.close()

    if not prompt_desc:
        raise HTTPException(400, "Prop has no prompt_description. Edit it first.")

    async def _run():
        for ref_type in PROP_REF_TYPES:
            await ws_manager.broadcast({
                "type": "reference_progress",
                "entity_type": "prop",
                "entity_id": prop_id,
                "ref_type": ref_type,
                "status": "generating",
            })

            file_path, prompt_used = await generate_prop_reference(
                prop_id, ref_type, prompt_desc, camera_prefix
            )

            s = SessionLocal()
            try:
                ref = PropReference(
                    prop_id=prop_id,
                    ref_type=ref_type,
                    file_path=file_path or "",
                    prompt_used=prompt_used,
                    is_approved=False,
                )
                s.add(ref)
                s.commit()
                ref_dict = ref.to_dict()
            finally:
                s.close()

            await ws_manager.broadcast({
                "type": "reference_progress",
                "entity_type": "prop",
                "entity_id": prop_id,
                "ref_type": ref_type,
                "status": "complete" if file_path else "error",
                "reference": ref_dict,
            })

    asyncio.create_task(_run())
    return {"ok": True, "message": f"Generating references for {prop_name}"}


# ===== Reference Approval =====

@router.post("/api/character-references/{ref_id}/approve")
def approve_char_reference(ref_id: int):
    session = get_session()
    try:
        ref = session.query(CharacterReference).get(ref_id)
        if not ref:
            raise HTTPException(404, "Reference not found")
        # Unapprove other refs of same type for this character
        for other in session.query(CharacterReference).filter_by(
            character_id=ref.character_id, ref_type=ref.ref_type
        ).all():
            other.is_approved = False
        ref.is_approved = True
        session.commit()
        return ref.to_dict()
    finally:
        session.close()


@router.post("/api/location-references/{ref_id}/approve")
def approve_loc_reference(ref_id: int):
    session = get_session()
    try:
        ref = session.query(LocationReference).get(ref_id)
        if not ref:
            raise HTTPException(404, "Reference not found")
        for other in session.query(LocationReference).filter_by(
            location_id=ref.location_id, ref_type=ref.ref_type
        ).all():
            other.is_approved = False
        ref.is_approved = True
        session.commit()
        return ref.to_dict()
    finally:
        session.close()


@router.post("/api/prop-references/{ref_id}/approve")
def approve_prop_reference(ref_id: int):
    session = get_session()
    try:
        ref = session.query(PropReference).get(ref_id)
        if not ref:
            raise HTTPException(404, "Reference not found")
        for other in session.query(PropReference).filter_by(
            prop_id=ref.prop_id, ref_type=ref.ref_type
        ).all():
            other.is_approved = False
        ref.is_approved = True
        session.commit()
        return ref.to_dict()
    finally:
        session.close()


# ===== Batch Reference Generation =====

@router.post("/api/stories/{story_id}/world-bible/generate-all-references")
async def generate_all_references(story_id: int):
    """Generate references for all entities in the world bible."""
    session = get_session()
    try:
        wb = session.query(WorldBible).filter_by(story_id=story_id).first()
        if not wb:
            raise HTTPException(404, "No world bible found")

        char_ids = [(c.id, c.prompt_description) for c in wb.characters if c.prompt_description]
        loc_ids = [(l.id, l.prompt_description) for l in wb.locations if l.prompt_description]
        prop_ids = [(p.id, p.prompt_description) for p in wb.props if p.prompt_description]
        camera_prefix = wb.camera_bible.prompt_prefix if wb.camera_bible else ""
    finally:
        session.close()

    async def _run():
        for char_id, desc in char_ids:
            for ref_type in CHARACTER_REF_TYPES:
                file_path, prompt_used = await generate_character_reference(
                    char_id, ref_type, desc, camera_prefix
                )
                s = SessionLocal()
                try:
                    ref = CharacterReference(
                        character_id=char_id, ref_type=ref_type,
                        file_path=file_path or "", prompt_used=prompt_used,
                    )
                    s.add(ref)
                    s.commit()
                finally:
                    s.close()

                await ws_manager.broadcast({
                    "type": "reference_progress",
                    "entity_type": "character", "entity_id": char_id,
                    "ref_type": ref_type,
                    "status": "complete" if file_path else "error",
                })

        for loc_id, desc in loc_ids:
            for ref_type in LOCATION_REF_TYPES:
                file_path, prompt_used = await generate_location_reference(
                    loc_id, ref_type, desc, camera_prefix
                )
                s = SessionLocal()
                try:
                    ref = LocationReference(
                        location_id=loc_id, ref_type=ref_type,
                        file_path=file_path or "", prompt_used=prompt_used,
                    )
                    s.add(ref)
                    s.commit()
                finally:
                    s.close()

                await ws_manager.broadcast({
                    "type": "reference_progress",
                    "entity_type": "location", "entity_id": loc_id,
                    "ref_type": ref_type,
                    "status": "complete" if file_path else "error",
                })

        for prop_id, desc in prop_ids:
            for ref_type in PROP_REF_TYPES:
                file_path, prompt_used = await generate_prop_reference(
                    prop_id, ref_type, desc, camera_prefix
                )
                s = SessionLocal()
                try:
                    ref = PropReference(
                        prop_id=prop_id, ref_type=ref_type,
                        file_path=file_path or "", prompt_used=prompt_used,
                    )
                    s.add(ref)
                    s.commit()
                finally:
                    s.close()

                await ws_manager.broadcast({
                    "type": "reference_progress",
                    "entity_type": "prop", "entity_id": prop_id,
                    "ref_type": ref_type,
                    "status": "complete" if file_path else "error",
                })

        await ws_manager.broadcast({
            "type": "all_references_complete",
            "story_id": story_id,
        })

    asyncio.create_task(_run())
    total = len(char_ids) * 3 + len(loc_ids) * 2 + len(prop_ids) * 1
    return {"ok": True, "message": f"Generating {total} reference images", "total": total}
