"""FFmpeg video composition — Ken Burns effect + transitions + stitching."""

import asyncio
import os
from pathlib import Path
from app.config import IMAGES_DIR, VIDEOS_DIR, COMPOSED_DIR


async def _run_ffmpeg(cmd: list[str]) -> tuple[int, str]:
    """Run an FFmpeg command asynchronously."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stderr.decode()


async def ken_burns_shot(image_path: str, duration: float, output_path: str,
                         movement: str = "zoom_in") -> bool:
    """Apply Ken Burns effect to a single image.

    movement: zoom_in, zoom_out, pan_left, pan_right, pan_up, pan_down
    """
    # 9:16 vertical output: 1080x1920
    w, h = 1080, 1920
    fps = 30
    total_frames = int(duration * fps)

    # zoompan filter for Ken Burns
    # Zoom from 1.0 to 1.15 over the duration (or reverse for zoom_out)
    if movement == "zoom_in":
        zp = f"zoompan=z='min(zoom+0.0005,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={w}x{h}:fps={fps}"
    elif movement == "zoom_out":
        zp = f"zoompan=z='if(eq(on,1),1.15,max(zoom-0.0005,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={w}x{h}:fps={fps}"
    elif movement == "pan_left":
        zp = f"zoompan=z='1.1':x='iw*0.1*(1-on/{total_frames})':y='ih/2-(ih/zoom/2)':d={total_frames}:s={w}x{h}:fps={fps}"
    elif movement == "pan_right":
        zp = f"zoompan=z='1.1':x='iw*0.1*on/{total_frames}':y='ih/2-(ih/zoom/2)':d={total_frames}:s={w}x{h}:fps={fps}"
    elif movement == "pan_up":
        zp = f"zoompan=z='1.1':x='iw/2-(iw/zoom/2)':y='ih*0.1*(1-on/{total_frames})':d={total_frames}:s={w}x{h}:fps={fps}"
    elif movement == "pan_down":
        zp = f"zoompan=z='1.1':x='iw/2-(iw/zoom/2)':y='ih*0.1*on/{total_frames}':d={total_frames}:s={w}x{h}:fps={fps}"
    else:
        zp = f"zoompan=z='min(zoom+0.0005,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={w}x{h}:fps={fps}"

    cmd = [
        "ffmpeg", "-y",
        "-i", image_path,
        "-vf", zp,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-t", str(duration),
        output_path,
    ]

    rc, err = await _run_ffmpeg(cmd)
    if rc != 0:
        print(f"FFmpeg ken_burns failed: {err}")
    return rc == 0


def _camera_to_movement(camera_movement: str) -> str:
    """Map shot camera_movement to Ken Burns movement type."""
    mapping = {
        "zoom": "zoom_in", "dolly": "zoom_in",
        "pan": "pan_right", "tilt": "pan_up",
        "crane": "pan_up", "tracking": "pan_right",
        "static": "zoom_in",  # subtle zoom for static shots
        "handheld": "zoom_in", "steadicam": "pan_right",
    }
    return mapping.get(camera_movement, "zoom_in")


async def compose_scene(shots: list[dict], scene_id: int) -> str | None:
    """Compose a scene from shot images into a single video.

    Args:
        shots: list of shot dicts with current_image, duration, camera_movement, transition_type
        scene_id: for naming output

    Returns: relative path to composed video, or None on failure
    """
    if not shots:
        return None

    # Step 1: Generate individual shot clips with Ken Burns
    clip_paths = []
    for i, shot in enumerate(shots):
        img = shot.get("current_image")
        if not img or not img.get("file_path"):
            continue

        image_path = str(IMAGES_DIR.parent / img["file_path"])
        if not os.path.exists(image_path):
            continue

        clip_path = str(VIDEOS_DIR / f"scene_{scene_id}_shot_{i}.mp4")
        movement = _camera_to_movement(shot.get("camera_movement", "static"))
        duration = shot.get("duration", 4.0)

        ok = await ken_burns_shot(image_path, duration, clip_path, movement)
        if ok:
            clip_paths.append((clip_path, shot.get("transition_type", "cut"),
                               shot.get("transition_duration", 0.5)))

    if not clip_paths:
        return None

    # Step 2: If only one clip, just copy it
    output_path = str(COMPOSED_DIR / f"scene_{scene_id}.mp4")
    if len(clip_paths) == 1:
        import shutil
        shutil.copy2(clip_paths[0][0], output_path)
        return f"composed/scene_{scene_id}.mp4"

    # Step 3: Concatenate with xfade transitions
    # Build a complex filter for xfade between clips
    filter_parts = []
    inputs = []
    for i, (path, _, _) in enumerate(clip_paths):
        inputs.extend(["-i", path])

    # Chain xfade transitions
    prev = "0:v"
    for i in range(1, len(clip_paths)):
        trans_type = clip_paths[i][1]
        trans_dur = min(clip_paths[i][2], 1.0)

        # Map our transition types to ffmpeg xfade transitions
        xfade_map = {
            "dissolve": "dissolve", "fade": "fade",
            "wipe": "wiperight", "cut": "fade",
        }
        xfade = xfade_map.get(trans_type, "fade")

        # Calculate offset (cumulative duration minus transition overlaps)
        # For simplicity, use a concat approach for cuts and xfade for others
        if trans_type == "cut" or trans_dur <= 0:
            continue  # handled by concat below

        out_label = f"v{i}"
        # This is simplified — for production you'd calculate exact offsets
        filter_parts.append(
            f"[{prev}][{i}:v]xfade=transition={xfade}:duration={trans_dur}:offset=0[{out_label}]"
        )
        prev = out_label

    # If we have complex filters, use them; otherwise simple concat
    if filter_parts:
        filter_str = ";".join(filter_parts)
        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", filter_str,
            "-map", f"[{prev}]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            output_path,
        ]
    else:
        # Simple concat via concat demuxer
        concat_file = str(VIDEOS_DIR / f"concat_{scene_id}.txt")
        with open(concat_file, "w") as f:
            for path, _, _ in clip_paths:
                f.write(f"file '{path}'\n")
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            output_path,
        ]

    rc, err = await _run_ffmpeg(cmd)
    if rc != 0:
        print(f"FFmpeg compose failed: {err}")
        return None

    return f"composed/scene_{scene_id}.mp4"
