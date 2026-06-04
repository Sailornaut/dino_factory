"""Stage: generate SRT captions from script."""

from pathlib import Path

from utils.logging import get_logger

logger = get_logger(__name__)


def generate_captions(script: dict, captions_path: Path) -> Path:
    """Generate an SRT subtitle file from script scene captions."""
    if captions_path.exists():
        logger.debug("Captions cached: %s", captions_path)
        return captions_path

    captions_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    current_time = 3.0  # account for title card

    for i, scene in enumerate(script.get("scenes", []), 1):
        caption = scene.get("caption", "")
        duration = scene.get("duration_seconds", 5)
        if not caption:
            current_time += duration
            continue

        start = _format_srt_time(current_time)
        end = _format_srt_time(current_time + duration)
        lines.append(f"{i}")
        lines.append(f"{start} --> {end}")
        lines.append(caption)
        lines.append("")
        current_time += duration

    with open(captions_path, "w") as f:
        f.write("\n".join(lines))

    logger.info("Captions generated → %s", captions_path)
    return captions_path


def _format_srt_time(seconds: float) -> str:
    """Convert seconds to SRT timestamp format HH:MM:SS,mmm."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
