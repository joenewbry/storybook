"""Deterministic prompt composition from shot metadata + story style + world bible."""


def build_image_prompt(
    shot: dict,
    story: dict,
    prev_shot: dict | None = None,
    next_shot: dict | None = None,
    world_bible: dict | None = None,
    scene_index: int | None = None,
) -> str:
    """Build a Grok Imagine prompt from shot metadata.

    World bible injection order (Pixar pipeline):
    1. Camera bible prompt_prefix (lens, film stock, grading)
    2. Global style + design language
    3. Character prompt_descriptions (matched by name)
    4. Location prompt_description (matched by name)
    5. Prop prompt_descriptions (matched by name)
    6. Color script entry (per-scene emotion→palette)
    7. Shot-specific: type, lighting, color, camera
    8. Continuity + mandatory suffix
    """
    parts = []
    wb = world_bible or {}

    # 1. Camera bible prefix (sets the "film look" for all images)
    camera_bible = wb.get("camera_bible")
    if camera_bible and camera_bible.get("prompt_prefix"):
        parts.append(camera_bible["prompt_prefix"].rstrip(".") + ".")

    # 2. Global style
    style = story.get("visual_style", "")
    if wb.get("global_style_prompt"):
        style = wb["global_style_prompt"]
    if style:
        parts.append(style.rstrip(".") + ".")

    # Design language
    if wb.get("design_language"):
        parts.append(wb["design_language"].rstrip(".") + ".")

    # 3. Shot description (the core visual)
    desc = shot.get("description", "")
    if desc:
        parts.append(desc)

    # 4. Character injection — match character names in shot description
    desc_lower = (desc or "").lower()
    for char in wb.get("characters", []):
        if char.get("prompt_description") and char.get("name", "").lower() in desc_lower:
            parts.append(f"[{char['name']}]: {char['prompt_description']}")

    # 5. Location injection — match location names in shot description
    for loc in wb.get("locations", []):
        if loc.get("prompt_description") and loc.get("name", "").lower() in desc_lower:
            parts.append(f"[Setting: {loc['name']}]: {loc['prompt_description']}")

    # 6. Prop injection — match prop names in shot description
    for prop in wb.get("props", []):
        if prop.get("prompt_description") and prop.get("name", "").lower() in desc_lower:
            parts.append(f"[{prop['name']}]: {prop['prompt_description']}")

    # 7. Color script — per-scene palette override
    if scene_index is not None:
        color_script = wb.get("color_script") or story.get("color_script")
        if isinstance(color_script, list):
            for entry in color_script:
                if entry.get("scene_index") == scene_index:
                    if entry.get("palette"):
                        parts.append(f"Color palette: {', '.join(entry['palette'])}.")
                    if entry.get("lighting_direction"):
                        parts.append(f"Lighting: {entry['lighting_direction']}.")
                    break

    # 8. Shot type / camera angle
    shot_type = shot.get("shot_type", "")
    if shot_type:
        angle_map = {
            "wide": "Wide shot, full scene visible",
            "medium": "Medium shot, waist up",
            "close-up": "Close-up shot, face and shoulders",
            "extreme-close-up": "Extreme close-up, single detail fills frame",
            "over-the-shoulder": "Over the shoulder perspective",
            "birds-eye": "Bird's eye view, looking straight down",
            "low-angle": "Low angle shot, looking up",
            "dutch-angle": "Dutch angle, tilted frame",
            "pov": "First person point of view",
        }
        parts.append(angle_map.get(shot_type, f"{shot_type} shot") + ".")

    # Lighting (only if not already set by color script)
    lighting = shot.get("lighting", "")
    if lighting and not any("Lighting:" in p for p in parts):
        parts.append(f"Lighting: {lighting}.")

    # Color mood
    color_mood = shot.get("color_mood", "")
    if color_mood:
        parts.append(f"Color mood: {color_mood}.")

    # Color palette hex (only if not set by color script)
    palette = shot.get("color_palette", [])
    if palette and len(palette) >= 2 and not any("Color palette:" in p for p in parts):
        parts.append(f"Dominant colors: {', '.join(palette[:4])}.")

    # Camera movement hint (for implied motion in still image)
    camera = shot.get("camera_movement", "")
    camera_detail = shot.get("camera_movement_detail", "")
    if camera and camera != "static":
        motion_hint = camera_detail or camera
        parts.append(f"Implied camera motion: {motion_hint}.")

    # 9. Continuity with adjacent shots
    if prev_shot and prev_shot.get("description"):
        parts.append(f"Continuation from: {prev_shot['description'][:80]}.")

    # Mandatory suffix: no text
    parts.append("No text, no words, no letters, no typography, no UI elements.")

    # Aspect ratio hint
    parts.append("Vertical 9:16 portrait composition for mobile viewing.")

    return " ".join(parts)


def build_all_prompts(story_data: dict, world_bible: dict | None = None) -> list[dict]:
    """Build prompts for all shots in a story.

    Returns: list of {"shot_id": int, "prompt": str}
    """
    results = []
    all_shots = []
    scene_index_map = {}  # shot_id -> scene_index

    # Flatten all shots with ordering and track scene indices
    scene_idx = 0
    for ch in story_data.get("chapters", []):
        for sc in ch.get("scenes", []):
            for sh in sc.get("shots", []):
                all_shots.append(sh)
                scene_index_map[sh.get("id")] = scene_idx
            scene_idx += 1

    for i, shot in enumerate(all_shots):
        prev_shot = all_shots[i - 1] if i > 0 else None
        next_shot = all_shots[i + 1] if i < len(all_shots) - 1 else None
        prompt = build_image_prompt(
            shot, story_data, prev_shot, next_shot,
            world_bible=world_bible,
            scene_index=scene_index_map.get(shot.get("id")),
        )
        results.append({"shot_id": shot["id"], "prompt": prompt})

    return results
