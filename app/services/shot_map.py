"""Shot map generation — bird's-eye camera path visualization via Grok Imagine."""

import httpx
from app.config import XAI_API_KEY, SHOT_MAPS_DIR
from app.services.transitions import TRANSITION_TYPES

API_URL = "https://api.x.ai/v1/images/generations"


def build_shot_map_prompt(scene: dict, shots: list[dict]) -> str:
    """Build a Grok Imagine prompt for a bird's-eye camera path diagram.

    Args:
        scene: Scene dict (from Scene.to_dict()).
        shots: List of shot dicts ordered by order_index.

    Returns:
        Prompt string for Grok image generation.
    """
    lines = [
        "Technical overhead camera map, blueprint style, dark navy background, bright colored lines.",
        "Bird's-eye view diagram showing camera positions and movement paths through a scene.",
        f"Scene: {scene.get('goal', 'Unknown scene')}",
        "",
        "Camera positions (numbered circles):",
    ]

    for i, shot in enumerate(shots, 1):
        shot_type = shot.get("shot_type", "medium")
        movement = shot.get("camera_movement", "static")
        detail = shot.get("camera_movement_detail", "")
        desc = (shot.get("description") or "")[:80]
        lines.append(f"  {i}. {shot_type.upper()} — {movement} — {desc}")
        if detail:
            lines.append(f"     Movement: {detail}")

    if len(shots) >= 2:
        lines.append("")
        lines.append("Transitions between positions (dashed arrows):")
        for i in range(len(shots) - 1):
            cur = shots[i]
            nxt = shots[i + 1]
            trans = cur.get("transition_type", "cut")
            icon = TRANSITION_TYPES.get(trans, {}).get("icon", "/")
            lines.append(f"  {i+1} [{icon}] {i+2}: {trans}")

    lines.extend([
        "",
        "Style: Numbered bright cyan circles for camera positions, dashed magenta arrows for movement paths,",
        "small white silhouettes for character positions, grid overlay, neon glow on lines.",
        "Vertical 9:16 aspect ratio, no text labels.",
    ])

    return "\n".join(lines)


async def generate_shot_map_image(prompt: str, scene_id: int, api_key: str = "") -> tuple[str | None, str | None]:
    """Generate a shot map image via Grok Imagine API.

    Returns (file_path, error_message). file_path is relative from generated/.
    """
    key = api_key or XAI_API_KEY
    if not key:
        return None, "No XAI_API_KEY set. Add XAI_API_KEY=xai-... to your .env file"

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

            filename = f"scene_{scene_id}_shot_map.png"
            filepath = SHOT_MAPS_DIR / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(img_response.content)

            return f"shot_maps/{filename}", None

    except (httpx.HTTPError, KeyError, IndexError) as e:
        print(f"Shot map generation failed for scene {scene_id}: {e}")
        return None, f"Grok API error: {e}"
