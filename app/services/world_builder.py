"""World Bible extraction and refinement via Claude."""

import json
import anthropic
from app.config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
MODEL = "claude-sonnet-4-20250514"


def _parse_json(text: str):
    """Extract JSON from a Claude response (handles markdown code blocks)."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def extract_world_elements(raw_text: str, visual_style: str = "") -> dict:
    """Extract characters, locations, props, camera recommendations from story text.

    Returns: {
        "design_language": str,
        "global_style_prompt": str,
        "era_setting": str,
        "atmosphere": str,
        "color_palette": [hex],
        "characters": [{name, role, age_appearance, gender_presentation, body_type,
                        face_description, hair, skin, clothing_default, distinctive_features,
                        demeanor, scene_appearances}],
        "locations": [{name, location_type, description, architectural_style,
                      lighting_default, color_palette, atmosphere, time_of_day, key_objects,
                      scene_appearances}],
        "props": [{name, category, description, visual_details, scale, material_notes,
                  scene_appearances}],
        "camera_bible": {lens_style, film_stock, color_grading, lighting_philosophy,
                        movement_philosophy, reference_films},
        "color_script": [{scene_index, emotion, palette, lighting_direction}]
    }
    """
    prompt = f"""Analyze this story and extract all visual world-building elements for a Pixar-style pre-production pipeline.

STORY TEXT:
---
{raw_text}
---

VISUAL STYLE DIRECTION: {visual_style or "Cinematic, dark, dramatic"}

Extract EVERYTHING needed to maintain visual consistency across dozens of generated images.
Think like a Pixar art director building a "World Bible" — every detail matters because our
image generation model has NO memory between frames.

For each CHARACTER: be maximally specific about appearance. Don't say "attractive" — say
"sharp jawline, deep-set hazel eyes, aquiline nose, thin lips." Every visual detail you omit
will be randomly generated differently in every image.

For each LOCATION: describe architectural style, materials, lighting conditions, atmosphere.
Think "concept art direction notes."

For CAMERA BIBLE: recommend lens family, film stock look, color grading approach, and
lighting philosophy that match the story's tone. Think like a cinematographer choosing their
toolkit before production begins.

Return ONLY valid JSON:
{{
    "design_language": "Shape language rules and stylization level (e.g. 'angular, geometric shapes for antagonists; rounded, organic forms for protagonists; 70% realistic, 30% stylized')",
    "global_style_prompt": "Master visual style in one dense sentence for image generation",
    "era_setting": "Time period and world setting",
    "atmosphere": "Overall atmospheric quality",
    "color_palette": ["#hex1", "#hex2", "#hex3", "#hex4", "#hex5"],
    "characters": [
        {{
            "name": "Character Name",
            "role": "protagonist|antagonist|supporting|minor",
            "age_appearance": "appears mid-40s",
            "gender_presentation": "masculine/feminine/androgynous",
            "body_type": "tall, lean, angular build",
            "face_description": "Maximally specific: jawline, eyes (color, shape, depth), nose, mouth, expression lines, scars",
            "hair": "color, style, length, texture",
            "skin": "tone, texture, notable features",
            "clothing_default": "default outfit described in detail",
            "distinctive_features": "scars, tattoos, accessories, mannerisms",
            "demeanor": "how they carry themselves, default expression",
            "scene_appearances": [0, 1, 3]
        }}
    ],
    "locations": [
        {{
            "name": "Location Name",
            "location_type": "interior|exterior",
            "description": "Full visual description",
            "architectural_style": "Art deco, brutalist, organic, etc.",
            "lighting_default": "Default lighting condition",
            "color_palette": ["#hex1", "#hex2", "#hex3"],
            "atmosphere": "Mood and feel",
            "time_of_day": "Default time of day",
            "key_objects": "Important objects/furniture/features always present",
            "scene_appearances": [0, 2]
        }}
    ],
    "props": [
        {{
            "name": "Prop Name",
            "category": "technology|weapon|vehicle|personal_item|document|furniture",
            "description": "What it is and its narrative importance",
            "visual_details": "Specific visual appearance: color, material, condition, markings",
            "scale": "Size relative to human or known object",
            "material_notes": "Materials, finish, wear patterns",
            "scene_appearances": [1, 4]
        }}
    ],
    "camera_bible": {{
        "lens_style": "e.g. anamorphic primes, shallow DOF, slight barrel distortion",
        "film_stock": "e.g. Kodak Vision3 500T look, heavy grain, warm shadows",
        "color_grading": "e.g. teal and orange push, crushed blacks, desaturated midtones",
        "lighting_philosophy": "e.g. motivated lighting only, no flat fills, strong rim light",
        "movement_philosophy": "e.g. handheld for tension, locked tripod for power moments",
        "reference_films": "e.g. Blade Runner 2049, Sicario, Children of Men"
    }},
    "color_script": [
        {{
            "scene_index": 0,
            "emotion": "dread",
            "palette": ["#hex1", "#hex2", "#hex3"],
            "lighting_direction": "cold overhead fluorescent transitioning to warm amber"
        }}
    ]
}}"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(response.content[0].text)


def refine_prompt_descriptions(world_data: dict, visual_style: str = "") -> dict:
    """Take extracted world elements and generate Grok-optimized prompt fragments.

    Returns: {
        "characters": [{name, prompt_description}],
        "locations": [{name, prompt_description}],
        "props": [{name, prompt_description}],
        "camera_prompt_prefix": str
    }
    """
    prompt = f"""You are a prompt engineer specializing in image generation models.

Take these world-building elements and create dense, image-model-optimized text blocks.
These will be INJECTED into every image prompt where the entity appears, so they must be:
1. Self-contained (no references to other descriptions)
2. Dense with visual detail (every word paints a picture)
3. Consistent terminology (use the same words every time for the same features)
4. Focused on what's VISIBLE (not backstory or personality)

VISUAL STYLE: {visual_style or "Cinematic, dramatic"}

WORLD DATA:
{json.dumps(world_data, indent=2)}

Return ONLY valid JSON:
{{
    "characters": [
        {{
            "name": "Character Name",
            "prompt_description": "Dense visual description for image generation. Example: 'A tall, lean man in his mid-40s with a sharp angular jawline, deep-set hazel eyes under heavy brows, aquiline nose, thin lips set in a permanent half-frown. Salt-and-pepper hair cropped military-short. Weathered olive skin with a thin scar across the left cheekbone. Wearing a rumpled charcoal suit, loosened dark tie, white shirt with rolled sleeves revealing forearm tattoos.'"
        }}
    ],
    "locations": [
        {{
            "name": "Location Name",
            "prompt_description": "Dense visual description. Example: 'A vast underground server room, rows of black monolithic server racks stretching into darkness, bathed in cold blue LED strips. Concrete floor with painted yellow safety lines, exposed cable trays overhead. Single warm desk lamp in the far corner. Condensation on metal surfaces. Industrial, oppressive, claustrophobic.'"
        }}
    ],
    "props": [
        {{
            "name": "Prop Name",
            "prompt_description": "Dense visual description. Example: 'A battered stainless steel briefcase with brass latches, surface covered in scratches and dents. A faded diplomatic seal sticker on the lid. Heavy, solid, cold to the touch.'"
        }}
    ],
    "camera_prompt_prefix": "A single sentence that sets the camera/film look for ALL images. Example: 'Shot on anamorphic lenses with shallow depth of field, Kodak Vision3 500T film grain, teal and orange color grading, crushed blacks, motivated rim lighting.'"
}}"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(response.content[0].text)
