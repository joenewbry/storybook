"""Rate-limited async queue for image generation."""

import asyncio
from app.services.grok_image import generate_image
from app.web.ws import ws_manager

MAX_CONCURRENT = 3
INTERVAL = 0.25  # seconds between requests


class GenerationQueue:
    def __init__(self):
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT)

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

            result = await generate_image(prompt, shot_id)

            if result:
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
                            file_path=result,
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
                    })
                finally:
                    session.close()

            return result

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


generation_queue = GenerationQueue()
