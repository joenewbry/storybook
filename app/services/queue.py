"""Rate-limited async queue for image and video generation."""

import asyncio
from pathlib import Path
from app.services.grok_image import generate_image
from app.services.grok_video import generate_video, extract_last_frame, image_to_base64_data_uri
from app.config import GENERATED_DIR, VIDEOS_DIR
from app.web.ws import ws_manager

MAX_CONCURRENT = 3
VIDEO_MAX_CONCURRENT = 1
INTERVAL = 0.25  # seconds between requests


class GenerationQueue:
    def __init__(self):
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        self._video_semaphore = asyncio.Semaphore(VIDEO_MAX_CONCURRENT)

    async def generate_shot(self, shot_id: int, prompt: str, session_factory) -> str | None:
        """Generate image for a single shot with rate limiting."""
        async with self._semaphore:
            await asyncio.sleep(INTERVAL)

            # Notify start
            await ws_manager.broadcast({
                "type": "shot_progress",
                "shot_id": shot_id,
                "status": "generating",
            })

            path, error = await generate_image(prompt, shot_id)

            if path:
                # Update DB
                from app.models import Shot, Asset
                session = session_factory()
                try:
                    shot = session.query(Shot).get(shot_id)
                    if shot:
                        shot.generation_status = "complete"
                        # Mark old assets as not current
                        for a in shot.assets:
                            if a.asset_type == "image":
                                a.is_current = False
                        asset = Asset(
                            shot_id=shot_id,
                            asset_type="image",
                            file_path=path,
                            generation_params={"prompt": prompt},
                            is_current=True,
                        )
                        session.add(asset)
                        session.commit()

                        await ws_manager.broadcast({
                            "type": "shot_progress",
                            "shot_id": shot_id,
                            "status": "complete",
                            "image": asset.to_dict(),
                        })
                finally:
                    session.close()
            else:
                # Mark as error
                from app.models import Shot
                session = session_factory()
                try:
                    shot = session.query(Shot).get(shot_id)
                    if shot:
                        shot.generation_status = "error"
                        session.commit()
                    await ws_manager.broadcast({
                        "type": "shot_progress",
                        "shot_id": shot_id,
                        "status": "error",
                        "error_message": error or "Unknown error",
                    })
                finally:
                    session.close()

            return path

    async def generate_batch(self, shots: list[dict], session_factory):
        """Generate images for multiple shots concurrently.

        shots: list of {"shot_id": int, "prompt": str}
        """
        tasks = [
            self.generate_shot(s["shot_id"], s["prompt"], session_factory)
            for s in shots
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        await ws_manager.broadcast({"type": "generation_complete"})
        return results


    async def generate_video_for_shot(
        self, shot_id: int, prompt: str, image_url: str | None,
        duration: int, session_factory,
    ) -> str | None:
        """Generate video for a single shot with rate limiting."""
        async with self._video_semaphore:
            await asyncio.sleep(INTERVAL)

            await ws_manager.broadcast({
                "type": "video_progress",
                "shot_id": shot_id,
                "status": "generating",
            })

            path, error = await generate_video(prompt, shot_id, image_url=image_url, duration=duration)

            if path:
                from app.models import Shot, Asset
                session = session_factory()
                try:
                    shot = session.query(Shot).get(shot_id)
                    if shot:
                        shot.video_generation_status = "complete"
                        # Mark old video assets as not current
                        for a in shot.assets:
                            if a.asset_type == "video":
                                a.is_current = False
                        asset = Asset(
                            shot_id=shot_id,
                            asset_type="video",
                            file_path=path,
                            generation_params={"prompt": prompt, "image_url": image_url[:100] if image_url else None},
                            is_current=True,
                        )
                        session.add(asset)
                        session.commit()

                        await ws_manager.broadcast({
                            "type": "video_progress",
                            "shot_id": shot_id,
                            "status": "complete",
                            "video": asset.to_dict(),
                        })
                finally:
                    session.close()
            else:
                from app.models import Shot
                session = session_factory()
                try:
                    shot = session.query(Shot).get(shot_id)
                    if shot:
                        shot.video_generation_status = "error"
                        session.commit()
                    await ws_manager.broadcast({
                        "type": "video_progress",
                        "shot_id": shot_id,
                        "status": "error",
                        "error_message": error or "Unknown error",
                    })
                finally:
                    session.close()

            return path

    async def generate_scene_video_sequence(
        self, scene_shots: list[dict], session_factory,
    ):
        """Generate videos for shots in a scene sequentially (continuous camera).

        scene_shots: list of {"shot_id": int, "prompt": str, "image_url": str|None, "duration": int, "order_index": int}
        Shot 1 uses its reference image. Shot 2+ uses the last frame of the previous video.
        """
        sorted_shots = sorted(scene_shots, key=lambda s: s.get("order_index", 0))
        prev_video_path = None

        for i, shot_info in enumerate(sorted_shots):
            shot_id = shot_info["shot_id"]
            prompt = shot_info["prompt"]
            duration = shot_info.get("duration", 5)
            image_url = shot_info.get("image_url")

            # For shot 2+: extract last frame from previous video
            if i > 0 and prev_video_path:
                frame_path = VIDEOS_DIR / f"shot_{shot_id}_prev_frame.png"
                if extract_last_frame(prev_video_path, frame_path):
                    image_url = image_to_base64_data_uri(frame_path)
                # If extraction fails, fall back to the shot's own reference image

            result = await self.generate_video_for_shot(
                shot_id, prompt, image_url, duration, session_factory
            )

            if result:
                prev_video_path = GENERATED_DIR / result
            else:
                # Chain broken — next shot falls back to its own reference image
                prev_video_path = None

        await ws_manager.broadcast({
            "type": "video_generation_scene_complete",
            "scene_shot_ids": [s["shot_id"] for s in sorted_shots],
        })

    async def generate_shot_map(self, scene_id: int, prompt: str, session_factory):
        """Generate a shot map image for a scene."""
        async with self._semaphore:
            await asyncio.sleep(INTERVAL)

            await ws_manager.broadcast({
                "type": "shot_map_progress",
                "scene_id": scene_id,
                "status": "generating",
            })

            from app.services.shot_map import generate_shot_map_image
            path, error = await generate_shot_map_image(prompt, scene_id)

            if path:
                from app.models import SceneAsset
                session = session_factory()
                try:
                    # Mark old shot maps as not current
                    old_maps = session.query(SceneAsset).filter_by(
                        scene_id=scene_id, asset_type="shot_map"
                    ).all()
                    for m in old_maps:
                        m.is_current = False

                    asset = SceneAsset(
                        scene_id=scene_id,
                        asset_type="shot_map",
                        file_path=path,
                        generation_params={"prompt": prompt},
                        is_current=True,
                    )
                    session.add(asset)
                    session.commit()

                    await ws_manager.broadcast({
                        "type": "shot_map_progress",
                        "scene_id": scene_id,
                        "status": "complete",
                        "shot_map": asset.to_dict(),
                    })
                finally:
                    session.close()
            else:
                await ws_manager.broadcast({
                    "type": "shot_map_progress",
                    "scene_id": scene_id,
                    "status": "error",
                    "error_message": error or "Unknown error",
                })


generation_queue = GenerationQueue()
