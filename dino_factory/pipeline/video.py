"""Stage: assemble final video from components."""

import subprocess
from pathlib import Path

from providers.base import VideoAssembler
from utils.logging import get_logger

logger = get_logger(__name__)


def get_audio_duration(audio_path: Path) -> float | None:
    """Probe the duration of an audio file using ffprobe.

    Returns duration in seconds, or None if probing fails.
    """
    if not audio_path or not audio_path.exists():
        return None
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-show_entries",
                "format=duration", "-of", "csv=p=0",
                str(audio_path),
            ],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as e:
        logger.warning("ffprobe failed for %s: %s", audio_path, e)
    return None


def fit_durations_to_audio(
    scene_durations: list[float],
    audio_duration: float,
    title_dur: float = 3.0,
    outro_dur: float = 4.0,
) -> list[float]:
    """Redistribute scene durations so they fit the actual narration length.

    Keeps relative proportions but scales total to match the real audio,
    minus time reserved for title/outro cards.
    """
    available = audio_duration - title_dur - outro_dur
    if available <= 0:
        return scene_durations  # audio too short to matter

    scripted_total = sum(scene_durations)
    if scripted_total <= 0:
        # Equal split
        n = len(scene_durations)
        return [available / n] * n if n else scene_durations

    scale = available / scripted_total
    return [max(2.0, d * scale) for d in scene_durations]


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

    # ── Fit scene durations to actual narration length ────────────────
    if audio_path:
        narration_dur = get_audio_duration(audio_path)
        if narration_dur:
            scripted_total = sum(durations) + 7  # rough title+outro
            if abs(narration_dur - scripted_total) > 5:
                logger.info(
                    "Narration audio is %.1fs, scripted scenes total %.1fs — "
                    "rescaling scene durations to match audio",
                    narration_dur, scripted_total,
                )
            durations = fit_durations_to_audio(durations, narration_dur)
            logger.info(
                "Adjusted scene durations: total %.1fs for %.1fs narration",
                sum(durations), narration_dur,
            )

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
