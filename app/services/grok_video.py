"""Async Grok Imagine Video API client — submit-then-poll pattern."""

import asyncio
import base64
import os
import subprocess
import httpx
from pathlib import Path
from app.config import XAI_API_KEY, VIDEOS_DIR

API_URL = "https://api.x.ai/v1/videos/generations"
POLL_INTERVAL = 5  # seconds
POLL_TIMEOUT = 300  # 5 minutes


async def generate_video(
    prompt: str,
    shot_id: int,
    image_url: str | None = None,
    duration: int = 5,
    api_key: str = "",
) -> str | None:
    """Generate a 9:16 video via Grok Imagine Video API.

    Returns the relative file path (from generated/) on success, None on failure.
    image_url can be a base64 data URI or a public URL for image-to-video.
    """
    key = api_key or XAI_API_KEY
    if not key:
        print(f"[grok_video] No API key for shot {shot_id}")
        return None

    try:
        payload = {
            "model": "grok-imagine-video",
            "prompt": prompt,
            "n": 1,
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "duration": duration,
        }
        if image_url:
            payload["image_url"] = image_url

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

            # If synchronous response with direct URL
            if "data" in result and result["data"]:
                video_url = result["data"][0].get("url")
                if video_url:
                    return await _download_video(video_url, shot_id, key)

            # Async pattern: poll for completion
            request_id = result.get("id") or result.get("request_id")
            if not request_id:
                print(f"[grok_video] No request_id in response for shot {shot_id}")
                return None

            video_url = await _poll_for_completion(request_id, key)
            if video_url:
                return await _download_video(video_url, shot_id, key)

            return None

    except (httpx.HTTPError, KeyError, IndexError) as e:
        print(f"[grok_video] Generation failed for shot {shot_id}: {e}")
        return None


async def _poll_for_completion(request_id: str, api_key: str) -> str | None:
    """Poll the API until the video is ready or timeout."""
    elapsed = 0
    async with httpx.AsyncClient(timeout=30) as client:
        while elapsed < POLL_TIMEOUT:
            await asyncio.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL

            try:
                resp = await client.get(
                    f"{API_URL}/{request_id}",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()

                status = data.get("status", "")
                if status == "completed" or status == "succeeded":
                    items = data.get("data", [])
                    if items:
                        return items[0].get("url")
                    return None
                elif status in ("failed", "error"):
                    print(f"[grok_video] Generation failed: {data}")
                    return None
                # else: still processing, keep polling
            except httpx.HTTPError as e:
                print(f"[grok_video] Poll error: {e}")
                # Continue polling on transient errors

    print(f"[grok_video] Timeout waiting for request {request_id}")
    return None


async def _download_video(video_url: str, shot_id: int, api_key: str) -> str | None:
    """Download completed video to local storage."""
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.get(video_url, timeout=120)
            resp.raise_for_status()

            filename = f"shot_{shot_id}.mp4"
            filepath = VIDEOS_DIR / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(resp.content)

            return f"videos/{filename}"
    except httpx.HTTPError as e:
        print(f"[grok_video] Download failed for shot {shot_id}: {e}")
        return None


def extract_last_frame(video_path: str | Path, output_path: str | Path) -> bool:
    """Extract the last frame of a video using FFmpeg.

    Returns True on success, False on failure.
    """
    video_path = str(video_path)
    output_path = str(output_path)

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-sseof", "-0.1",
                "-i", video_path,
                "-frames:v", "1",
                "-q:v", "2",
                output_path,
            ],
            capture_output=True, timeout=30,
        )
        return result.returncode == 0 and Path(output_path).exists()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"[grok_video] Frame extraction failed: {e}")
        return False


def image_to_base64_data_uri(image_path: str | Path) -> str | None:
    """Convert a local image file to a base64 data URI."""
    image_path = Path(image_path)
    if not image_path.exists():
        return None

    suffix = image_path.suffix.lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
    mime = mime_map.get(suffix, "image/png")

    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime};base64,{data}"
