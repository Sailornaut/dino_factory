"""Abstract base classes for all pluggable providers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class LLMProvider(ABC):
    """Generates text: topics, scripts, storyboards, metadata."""

    @abstractmethod
    def generate(self, prompt: str, system: str = "", temperature: float = 0.7) -> str:
        """Return raw text completion."""

    @abstractmethod
    def generate_json(self, prompt: str, system: str = "", temperature: float = 0.4) -> dict | list:
        """Return parsed JSON from the model."""


class ImageProvider(ABC):
    """Generates scene images from text prompts."""

    @abstractmethod
    def generate_image(self, prompt: str, output_path: Path, width: int = 1080, height: int = 1920) -> Path:
        """Generate an image and save to output_path. Return the path."""


class VoiceProvider(ABC):
    """Generates narration audio from text."""

    @abstractmethod
    def generate_speech(self, text: str, output_path: Path, voice: str = "alloy") -> Path:
        """Generate speech audio and save. Return the path."""


class VideoAssembler(ABC):
    """Assembles final video from images, audio, captions."""

    @abstractmethod
    def assemble(
        self,
        image_paths: list[Path],
        scene_durations: list[float],
        audio_path: Path | None,
        captions_path: Path | None,
        output_path: Path,
        music_path: Path | None = None,
        title_text: str = "",
        outro_text: str = "Which dino should we explore next?",
        fps: int = 30,
    ) -> Path:
        """Assemble a vertical Short and return the output path."""
