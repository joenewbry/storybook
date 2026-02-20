"""Rules-based transition intelligence engine.

Analyzes adjacent shot pairs and suggests the best cinematic transition
based on shot type, camera movement, dialogue, emotion, and scene context.
"""

TRANSITION_TYPES = {
    "cut":       {"duration": 0.0,  "icon": "/"},
    "dissolve":  {"duration": 1.0,  "icon": "~"},
    "fade":      {"duration": 1.5,  "icon": "..."},
    "wipe":      {"duration": 0.8,  "icon": ">"},
    "match-cut": {"duration": 0.0,  "icon": "="},
    "whip-pan":  {"duration": 0.3,  "icon": ">>"},
    "j-cut":     {"duration": 0.5,  "icon": "J"},
    "l-cut":     {"duration": 0.5,  "icon": "L"},
    "smash-cut": {"duration": 0.0,  "icon": "!"},
    "iris":      {"duration": 0.8,  "icon": "O"},
}


def suggest_transitions(shots: list[dict], scene: dict) -> list[dict]:
    """Suggest transitions for each adjacent shot pair in a scene.

    Args:
        shots: List of shot dicts (from Shot.to_dict()), ordered by order_index.
        scene: Scene dict (from Scene.to_dict()).

    Returns:
        List of suggestion dicts, one per adjacent pair:
        {from_shot_id, to_shot_id, suggested_type, suggested_duration, confidence, reason}
    """
    if len(shots) < 2:
        return []

    suggestions = []
    intensity = scene.get("intensity", 0.5)
    closing_emotion = (scene.get("closing_emotion") or "").lower()

    for i in range(len(shots) - 1):
        current = shots[i]
        next_shot = shots[i + 1]
        is_last_pair = (i == len(shots) - 2)

        suggestion = _pick_transition(current, next_shot, scene, intensity, closing_emotion, is_last_pair)
        suggestion["from_shot_id"] = current["id"]
        suggestion["to_shot_id"] = next_shot["id"]
        suggestions.append(suggestion)

    return suggestions


def _pick_transition(current: dict, next_shot: dict, scene: dict,
                     intensity: float, closing_emotion: str, is_last_pair: bool) -> dict:
    """Apply rules hierarchy (first match wins) to pick a transition."""

    # Rule 1: Scene terminus — last shot pair
    if is_last_pair:
        somber = closing_emotion in ("sadness", "melancholy", "grief", "despair", "resignation", "loss")
        shock = closing_emotion in ("shock", "surprise", "rage", "anger")
        if somber:
            return _make("fade", 0.85, f"Scene ends on somber emotion: {closing_emotion}")
        if shock:
            return _make("smash-cut", 0.80, f"Scene ends abruptly on: {closing_emotion}")
        return _make("dissolve", 0.70, "Scene terminus — smooth transition out")

    # Rule 2: Dialogue coverage
    cur_dialogue = bool(current.get("dialogue", "").strip())
    next_dialogue = bool(next_shot.get("dialogue", "").strip())
    cur_type = (current.get("shot_type") or "").lower()
    next_type = (next_shot.get("shot_type") or "").lower()

    dialogue_types = {"close-up", "extreme-close-up", "over-the-shoulder"}
    if cur_dialogue and next_dialogue and cur_type in dialogue_types and next_type in dialogue_types:
        return _make("cut", 0.90, "Dialogue coverage — alternating close-ups/OTS")
    if not cur_dialogue and next_dialogue:
        return _make("j-cut", 0.75, "Dialogue begins — audio leads the cut")
    if cur_dialogue and not next_dialogue:
        return _make("l-cut", 0.75, "Dialogue ends — audio trails into next shot")

    # Rule 3: Camera movement continuity
    cur_movement = (current.get("camera_movement_detail") or "").lower()
    next_movement = (next_shot.get("camera_movement_detail") or "").lower()
    cur_cam = (current.get("camera_movement") or "").lower()

    if "whip" in cur_movement or "whip" in next_movement:
        return _make("whip-pan", 0.85, "Whip movement detected in camera detail")
    if cur_cam == "tracking" and (next_shot.get("camera_movement") or "").lower() == "tracking":
        return _make("cut", 0.70, "Continuous tracking — invisible cut")

    # Rule 4: Shot type dramatic shift
    wide_types = {"wide", "birds-eye"}
    tight_types = {"extreme-close-up"}
    if (cur_type in wide_types and next_type in tight_types) or \
       (cur_type in tight_types and next_type in wide_types):
        return _make("match-cut", 0.75, f"Dramatic shift: {cur_type} to {next_type}")
    if cur_type == "pov":
        return _make("cut", 0.80, "POV shot — direct cut maintains subjectivity")

    # Rule 5: Emotional intensity
    if intensity > 0.7 and (current.get("duration", 4) <= 3 or next_shot.get("duration", 4) <= 3):
        return _make("cut", 0.65, "High intensity + short duration — rapid cuts")
    if intensity < 0.3:
        return _make("dissolve", 0.60, "Low intensity — gentle dissolve")

    # Rule 6: Establishing pattern
    if current.get("order_index", 0) == 0 and cur_type in wide_types:
        return _make("dissolve", 0.65, "Establishing shot — dissolve into scene")

    # Rule 7: Default
    return _make("cut", 0.30, "Default transition")


def _make(transition_type: str, confidence: float, reason: str) -> dict:
    """Build a suggestion dict."""
    info = TRANSITION_TYPES.get(transition_type, TRANSITION_TYPES["cut"])
    return {
        "suggested_type": transition_type,
        "suggested_duration": info["duration"],
        "confidence": confidence,
        "reason": reason,
    }
