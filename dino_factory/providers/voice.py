"""Voice/TTS provider implementations."""

import math
import os
import struct
import time
import wave
from pathlib import Path

from providers.base import VoiceProvider
from utils.logging import get_logger

logger = get_logger(__name__)


class PlaceholderVoiceProvider(VoiceProvider):
    """Generates a silent WAV file with the right estimated duration."""

    WORDS_PER_SECOND = 2.5  # typical narration pace for kids

    def generate_speech(self, text: str, output_path: Path, voice: str = "alloy") -> Path:
        word_count = len(text.split())
        duration = max(3.0, word_count / self.WORDS_PER_SECOND)

        sample_rate = 22050
        num_samples = int(sample_rate * duration)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            # Generate a very soft tone so it's not dead silence (aids debugging)
            data = b""
            for i in range(num_samples):
                # Gentle 220 Hz tone at low volume
                val = int(800 * math.sin(2 * math.pi * 220 * i / sample_rate))
                data += struct.pack("<h", val)
            wf.writeframes(data)

        logger.debug("Placeholder audio (%.1fs) saved: %s", duration, output_path)
        return output_path


class OpenAIVoiceProvider(VoiceProvider):
    """Uses OpenAI TTS API."""

    def __init__(self, api_key: str | None = None, model: str = "tts-1"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model
        if not self.api_key:
            raise ValueError("No OpenAI API key for TTS")
        try:
            import openai
            self.client = openai.OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("pip install openai")

    def generate_speech(self, text: str, output_path: Path, voice: str = "alloy") -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(3):
            try:
                response = self.client.audio.speech.create(
                    model=self.model,
                    voice=voice,
                    input=text,
                    response_format="mp3",
                )
                response.stream_to_file(str(output_path))
                logger.info("TTS audio saved: %s", output_path)
                return output_path
            except Exception as e:
                logger.warning("TTS attempt %d failed: %s", attempt + 1, e)
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                else:
                    raise


def create_voice_provider(cfg: dict) -> VoiceProvider:
    """Factory function."""
    provider = cfg.get("voice_provider", "placeholder")
    if provider == "placeholder" or not cfg.get("voice_generation_enabled", True):
        logger.info("Using PlaceholderVoiceProvider")
        return PlaceholderVoiceProvider()
    if provider == "openai":
        api_key = cfg.get("openai_api_key", os.getenv("OPENAI_API_KEY", ""))
        if not api_key:
            logger.warning("No API key for OpenAI TTS — falling back to placeholder")
            return PlaceholderVoiceProvider()
        return OpenAIVoiceProvider(api_key=api_key)
    raise ValueError(f"Unknown voice_provider: {provider}")
