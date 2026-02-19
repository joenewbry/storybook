"""Reference image generation for world bible entities via Grok Imagine API."""

import httpx
from app.config import XAI_API_KEY, CHAR_REF_DIR, LOC_REF_DIR, PROP_REF_DIR

API_URL = "https://api.x.ai/v1/images/generations"

# Reference types per entity
CHARACTER_REF_TYPES = ["portrait", "full_body", "three_quarter"]
LOCATION_REF_TYPES = ["establishing", "detail"]
PROP_REF_TYPES = ["detail"]

# Prompt templates for different reference types
CHARACTER_PROMPTS = {
    "portrait": "Character portrait, head and shoulders, neutral expression, front-facing, studio lighting. {desc} {camera} No text, no words, no letters.",
    "full_body": "Full body character design, front view, standing pose, neutral background. {desc} {camera} No text, no words, no letters.",
    "three_quarter": "Three-quarter view character study, dynamic natural pose, environmental context. {desc} {camera} No text, no words, no letters.",
}

LOCATION_PROMPTS = {
    "establishing": "Wide establishing shot, concept art, full environment visible. {desc} {camera} No text, no words, no letters. Vertical 9:16 portrait composition.",
    "detail": "Atmospheric detail shot, mood and texture focus, close environmental study. {desc} {camera} No text, no words, no letters. Vertical 9:16 portrait composition.",
}

PROP_PROMPTS = {
    "detail": "Detailed prop design sheet, clean background, multiple angles implied, product photography style. {desc} {camera} No text, no words, no letters.",
}


async def _generate_and_save(prompt: str, filepath) -> str | None:
    """Generate an image via Grok and save to filepath."""
    key = XAI_API_KEY
    if not key:
        return None

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-2-image",
                    "prompt": prompt,
                    "n": 1,
                    "response_format": "url",
                },
            )
            response.raise_for_status()
            image_url = response.json()["data"][0]["url"]

            img_response = await client.get(image_url, timeout=30)
            img_response.raise_for_status()

            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(img_response.content)

            return str(filepath)
    except (httpx.HTTPError, KeyError, IndexError) as e:
        print(f"Reference image generation failed: {e}")
        return None


async def generate_character_reference(
    character_id: int,
    ref_type: str,
    prompt_description: str,
    camera_prefix: str = "",
) -> tuple[str | None, str]:
    """Generate a character reference image.

    Returns: (file_path or None, prompt_used)
    """
    template = CHARACTER_PROMPTS.get(ref_type, CHARACTER_PROMPTS["portrait"])
    prompt = template.format(desc=prompt_description, camera=camera_prefix)
    filename = f"char_{character_id}_{ref_type}.png"
    filepath = CHAR_REF_DIR / filename
    result = await _generate_and_save(prompt, filepath)
    rel_path = f"references/characters/{filename}" if result else None
    return rel_path, prompt


async def generate_location_reference(
    location_id: int,
    ref_type: str,
    prompt_description: str,
    camera_prefix: str = "",
) -> tuple[str | None, str]:
    """Generate a location reference image."""
    template = LOCATION_PROMPTS.get(ref_type, LOCATION_PROMPTS["establishing"])
    prompt = template.format(desc=prompt_description, camera=camera_prefix)
    filename = f"loc_{location_id}_{ref_type}.png"
    filepath = LOC_REF_DIR / filename
    result = await _generate_and_save(prompt, filepath)
    rel_path = f"references/locations/{filename}" if result else None
    return rel_path, prompt


async def generate_prop_reference(
    prop_id: int,
    ref_type: str,
    prompt_description: str,
    camera_prefix: str = "",
) -> tuple[str | None, str]:
    """Generate a prop reference image."""
    template = PROP_PROMPTS.get(ref_type, PROP_PROMPTS["detail"])
    prompt = template.format(desc=prompt_description, camera=camera_prefix)
    filename = f"prop_{prop_id}_{ref_type}.png"
    filepath = PROP_REF_DIR / filename
    result = await _generate_and_save(prompt, filepath)
    rel_path = f"references/props/{filename}" if result else None
    return rel_path, prompt
