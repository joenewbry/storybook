"""Deterministic prompt composition from shot metadata + story style."""


def build_image_prompt(shot: dict, story: dict, prev_shot: dict | None = None, next_shot: dict | None = None) -> str:
    """Build a Grok Imagine prompt from shot metadata.

    Considers visual continuity with adjacent shots.
    """
    parts = []

    # Style prefix from story
    style = story.get("visual_style", "")
    if style:
        parts.append(style.rstrip(".") + ".")

    # Shot description (the core visual)
    desc = shot.get("description", "")
    if desc:
        parts.append(desc)

    # Shot type / camera angle
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

    # Lighting
    lighting = shot.get("lighting", "")
    if lighting:
        parts.append(f"Lighting: {lighting}.")

    # Color mood
    color_mood = shot.get("color_mood", "")
    if color_mood:
        parts.append(f"Color palette: {color_mood}.")

    # Color palette hex → descriptive
    palette = shot.get("color_palette", [])
    if palette and len(palette) >= 2:
        parts.append(f"Dominant colors: {', '.join(palette[:4])}.")

    # Camera movement hint (for implied motion in still image)
    camera = shot.get("camera_movement", "")
    camera_detail = shot.get("camera_movement_detail", "")
    if camera and camera != "static":
        motion_hint = camera_detail or camera
        parts.append(f"Implied camera motion: {motion_hint}.")

    # Continuity with adjacent shots
    if prev_shot and prev_shot.get("description"):
        parts.append(f"Continuation from: {prev_shot['description'][:80]}.")

    # Mandatory suffix: no text
    parts.append("No text, no words, no letters, no typography, no UI elements.")

    # Aspect ratio hint
    parts.append("Vertical 9:16 portrait composition for mobile viewing.")

    return " ".join(parts)


def build_all_prompts(story_data: dict) -> list[dict]:
    """Build prompts for all shots in a story.

    Returns: list of {"shot_id": int, "prompt": str}
    """
    results = []
    all_shots = []

    # Flatten all shots with ordering
    for ch in story_data.get("chapters", []):
        for sc in ch.get("scenes", []):
            for sh in sc.get("shots", []):
                all_shots.append(sh)

    for i, shot in enumerate(all_shots):
        prev_shot = all_shots[i - 1] if i > 0 else None
        next_shot = all_shots[i + 1] if i < len(all_shots) - 1 else None
        prompt = build_image_prompt(shot, story_data, prev_shot, next_shot)
        results.append({"shot_id": shot["id"], "prompt": prompt})

    return results
