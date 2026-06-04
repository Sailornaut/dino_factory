"""Stage: assemble final video from components."""

from pathlib import Path

from providers.base import VideoAssembler
from utils.logging import get_logger

logger = get_logger(__name__)


def assemble_video(
    assembler: VideoAssembler,
    script: dict,
    image_paths: list[Path],
    audio_path: Path | None,
    captions_path: Path | None,
    output_path: Path,
    music_path: str = "",
) -> Path:
    """Assemble the final vertical Short video."""
    if output_path.exists():
        logger.info("Video already assembled: %s", output_path)
        return output_path

    scenes = script.get("scenes", [])
    durations = [s.get("duration_seconds", 5.0) for s in scenes]

    # Pad if mismatched
    while len(durations) < len(image_paths):
        durations.append(5.0)
    while len(image_paths) < len(durations):
        durations = durations[: len(image_paths)]

    title_text = script.get("title", "")
    outro_text = script.get("call_to_action", "Which dino should we explore next?")

    music = Path(music_path) if music_path else None

    try:
        result = assembler.assemble(
            image_paths=image_paths,
            scene_durations=durations,
            audio_path=audio_path,
            captions_path=captions_path,
            output_path=output_path,
            music_path=music,
            title_text=title_text,
            outro_text=outro_text,
        )
        return result
    except Exception as e:
        logger.error("Video assembly failed: %s", e)
        raise
