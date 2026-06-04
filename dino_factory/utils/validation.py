"""Validation for generated JSON structures."""

from utils.logging import get_logger

logger = get_logger(__name__)

REQUIRED_SCRIPT_KEYS = {"title", "voiceover", "scenes"}
REQUIRED_SCENE_KEYS = {"scene_number", "duration_seconds"}


def validate_script(script: dict) -> bool:
    """Validate that a script dict has the required structure."""
    if not isinstance(script, dict):
        logger.warning("Script is not a dict")
        return False

    missing = REQUIRED_SCRIPT_KEYS - set(script.keys())
    if missing:
        logger.warning("Script missing keys: %s", missing)
        return False

    scenes = script.get("scenes", [])
    if not isinstance(scenes, list) or len(scenes) == 0:
        logger.warning("Script has no scenes")
        return False

    for i, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            logger.warning("Scene %d is not a dict", i)
            return False
        scene_missing = REQUIRED_SCENE_KEYS - set(scene.keys())
        if scene_missing:
            logger.warning("Scene %d missing keys: %s", i, scene_missing)
            return False

    return True


def validate_topics(topics: list) -> bool:
    """Validate topics list structure."""
    if not isinstance(topics, list) or len(topics) == 0:
        return False
    for t in topics:
        if not isinstance(t, dict):
            return False
        if "title" not in t or "slug" not in t:
            return False
    return True
