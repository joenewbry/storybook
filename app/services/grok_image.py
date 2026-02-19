"""Async Grok Imagine API client for 9:16 image generation."""

import os
import httpx
from app.config import XAI_API_KEY, IMAGES_DIR

API_URL = "https://api.x.ai/v1/images/generations"


async def generate_image(prompt: str, shot_id: int, api_key: str = "") -> str | None:
    """Generate a 9:16 image via Grok Imagine API.

    Returns the relative file path (from generated/) on success, None on failure.
    """
    key = api_key or XAI_API_KEY
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

            # Download image
            img_response = await client.get(image_url, timeout=30)
            img_response.raise_for_status()

            # Save
            filename = f"shot_{shot_id}.png"
            filepath = IMAGES_DIR / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(img_response.content)

            # Return relative path from generated/
            return f"images/{filename}"

    except (httpx.HTTPError, KeyError, IndexError) as e:
        print(f"Grok image generation failed for shot {shot_id}: {e}")
        return None
