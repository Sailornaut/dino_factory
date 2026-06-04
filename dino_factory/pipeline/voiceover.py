"""Stage: generate voiceover narration audio."""

from pathlib import Path

from providers.base import VoiceProvider
from utils.logging import get_logger

logger = get_logger(__name__)


def generate_voiceover(
    voice_provider: VoiceProvider,
    script: dict,
    audio_dir: Path,
    voice: str = "alloy",
) -> Path:
    """Generate narration audio for the full voiceover text."""
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / "narration.wav"

    if audio_path.exists():
        logger.debug("Narration audio cached: %s", audio_path)
        return audio_path

    text = script.get("voiceover", "")
    if not text:
        # Fallback: concatenate scene captions
        captions = [s.get("caption", "") for s in script.get("scenes", [])]
        text = " ".join(captions)

    if not text:
        text = script.get("title", "Hello friends!")

    try:
        result = voice_provider.generate_speech(text, audio_path, voice=voice)
        return result
    except Exception as e:
        logger.error("Voiceover generation failed: %s", e)
        raise
