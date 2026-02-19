"""Claude API client for segmentation and shot breakdown."""

import json
import anthropic
from app.config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
MODEL = "claude-sonnet-4-20250514"


def segment_story(raw_text: str, title: str = "") -> dict:
    """Segment story into chapters and scenes using Jim Butcher's structure.

    Returns: {
        "chapters": [{
            "title": str,
            "summary": str,
            "source_text": str,
            "scenes": [{
                "scene_type": "scene"|"sequel",
                "source_text": str,
                "goal": str, "conflict": str, "outcome": str,
                "emotion": str, "logic": str, "decision": str,  (for sequels)
                "opening_emotion": str, "closing_emotion": str,
                "intensity": float (0-1),
                "target_duration": int (15-60 seconds)
            }]
        }]
    }
    """
    prompt = f"""Analyze this story text and segment it into chapters and scenes.

Use Jim Butcher's Scene & Sequel structure:
- **Scene**: Has a Goal (what the POV character wants), Conflict (what opposes them), and Outcome (usually a disaster or partial success that creates new tension)
- **Sequel**: The character's reaction — Emotion (immediate response), Logic (processing what happened), Decision (what to do next, leading to next scene's goal)

For each scene/sequel, also determine:
- opening_emotion and closing_emotion (the dominant emotional tone)
- intensity: 0.0 to 1.0 (how dramatically intense this beat is)
- target_duration: 15-60 seconds (how long this scene should be as a video short — action scenes shorter and punchier, emotional beats can breathe)

The story text:
---
{raw_text}
---

If the text is a single chapter, create one chapter. If it naturally breaks into multiple chapters, break it up.

Return ONLY valid JSON with this exact structure:
{{
    "chapters": [
        {{
            "title": "Chapter Title",
            "summary": "Brief chapter summary",
            "source_text": "The relevant portion of source text for this chapter",
            "scenes": [
                {{
                    "scene_type": "scene",
                    "source_text": "The relevant portion of source text",
                    "goal": "What the character wants",
                    "conflict": "What opposes them",
                    "outcome": "How it resolves (usually badly)",
                    "emotion": "",
                    "logic": "",
                    "decision": "",
                    "opening_emotion": "e.g. curiosity",
                    "closing_emotion": "e.g. dread",
                    "intensity": 0.6,
                    "target_duration": 30
                }}
            ]
        }}
    ]
}}"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    # Extract JSON from possible markdown code block
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def breakdown_scene(scene_data: dict, story_context: dict) -> list[dict]:
    """Break a scene into shots with full visual direction.

    Args:
        scene_data: The scene dict (goal, conflict, outcome, source_text, etc.)
        story_context: { visual_style, music_style, color_script }

    Returns: list of shot dicts [{
        "description": str,
        "dialogue": str,
        "shot_type": str,  (wide, medium, close-up, extreme-close-up, etc.)
        "camera_movement": str,  (static, pan, tilt, zoom, dolly, crane, etc.)
        "camera_movement_detail": str,
        "color_palette": [hex colors],
        "color_mood": str,
        "lighting": str,
        "music_tempo": str,
        "music_mood": str,
        "music_instruments": str,
        "music_note": str,
        "duration": float (2-8 seconds),
        "transition_type": str (cut, dissolve, fade, wipe),
        "transition_duration": float
    }]
    """
    visual_style = story_context.get("visual_style", "Cinematic, dark, dramatic")
    music_style = story_context.get("music_style", "")
    target_dur = scene_data.get("target_duration", 30)

    prompt = f"""Break this scene into individual shots for a TikTok/YouTube Shorts video.

SCENE CONTEXT:
- Type: {scene_data.get('scene_type', 'scene')}
- Goal: {scene_data.get('goal', '')}
- Conflict: {scene_data.get('conflict', '')}
- Outcome: {scene_data.get('outcome', '')}
- Opening emotion: {scene_data.get('opening_emotion', '')}
- Closing emotion: {scene_data.get('closing_emotion', '')}
- Intensity: {scene_data.get('intensity', 0.5)}
- Target total duration: {target_dur} seconds

SOURCE TEXT:
{scene_data.get('source_text', '')}

VISUAL STYLE: {visual_style}
MUSIC STYLE: {music_style}

Create 4-8 shots that:
1. Tell this scene's story visually in {target_dur} seconds total
2. Follow cinematic shot progression (establishing → action → reaction → transition)
3. Use Pixar-style color scripting — color palette shifts WITH emotional beats
4. Each shot's description should be concrete and visual (what we SEE, not abstract concepts)
5. Camera movements should serve the emotion (static for tension, dynamic for action)
6. Transitions between shots should be intentional (cuts for urgency, dissolves for time passage)

Return ONLY valid JSON — an array of shot objects:
[
    {{
        "description": "Concrete visual description of what we see",
        "dialogue": "Any dialogue or voiceover text (empty string if none)",
        "shot_type": "wide|medium|close-up|extreme-close-up|over-the-shoulder|birds-eye|low-angle|dutch-angle|pov",
        "camera_movement": "static|pan|tilt|zoom|dolly|crane|tracking|handheld|steadicam",
        "camera_movement_detail": "Specific movement description, e.g. 'Slow push in toward character's face'",
        "color_palette": ["#hex1", "#hex2", "#hex3"],
        "color_mood": "e.g. cold steel blues, warm amber tension",
        "lighting": "e.g. harsh overhead fluorescent, soft rim lighting from window",
        "music_tempo": "e.g. 80 BPM, building",
        "music_mood": "e.g. ominous, building tension",
        "music_instruments": "e.g. low strings, distant percussion",
        "music_note": "Any specific music direction for this shot",
        "duration": 4.0,
        "transition_type": "cut|dissolve|fade|wipe",
        "transition_duration": 0.5
    }}
]"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)
