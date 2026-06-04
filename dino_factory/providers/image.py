"""Image provider implementations."""

import os
import re
import time
from pathlib import Path

from providers.base import ImageProvider
from utils.logging import get_logger

logger = get_logger(__name__)

MAX_ATTEMPTS = 6  # more attempts to ride out rate limits
BASE_DELAY = 3    # seconds


def _parse_retry_after(error_msg: str) -> float | None:
    """Extract 'Please try again in Ns' from OpenAI rate-limit errors."""
    match = re.search(r"try again in (\d+\.?\d*)s", str(error_msg))
    if match:
        return float(match.group(1)) + 1.0  # add 1s buffer
    return None


class PlaceholderImageProvider(ImageProvider):
    """Generates solid-color placeholder images with text overlay using Pillow."""

    COLORS = [
        (76, 175, 80),   # green
        (33, 150, 243),  # blue
        (255, 152, 0),   # orange
        (156, 39, 176),  # purple
        (244, 67, 54),   # red
        (0, 188, 212),   # cyan
        (255, 235, 59),  # yellow
        (121, 85, 72),   # brown
    ]

    def generate_image(self, prompt: str, output_path: Path, width: int = 1080, height: int = 1920) -> Path:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            raise ImportError("pip install Pillow  to generate placeholder images")

        color_idx = hash(prompt) % len(self.COLORS)
        bg = self.COLORS[color_idx]

        img = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(img)

        # Draw a cute dino emoji-style placeholder
        cx, cy = width // 2, height // 2 - 100

        # Body circle
        body_r = 180
        draw.ellipse([cx - body_r, cy - body_r, cx + body_r, cy + body_r], fill=_lighten(bg, 40))

        # Eyes
        draw.ellipse([cx - 50, cy - 60, cx - 10, cy - 20], fill="white")
        draw.ellipse([cx + 10, cy - 60, cx + 50, cy - 20], fill="white")
        draw.ellipse([cx - 40, cy - 50, cx - 20, cy - 30], fill=(30, 30, 30))
        draw.ellipse([cx + 20, cy - 50, cx + 40, cy - 30], fill=(30, 30, 30))

        # Smile
        draw.arc([cx - 60, cy - 10, cx + 60, cy + 70], 0, 180, fill=(30, 30, 30), width=4)

        # Label
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
            small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        except OSError:
            font = ImageFont.load_default()
            small = font

        draw.text((cx, cy + 250), "PLACEHOLDER", font=font, fill="white", anchor="mm")

        # Wrap prompt text
        max_chars = 40
        lines = []
        words = prompt.split()
        line = ""
        for w in words:
            if len(line) + len(w) + 1 <= max_chars:
                line = f"{line} {w}".strip()
            else:
                lines.append(line)
                line = w
        if line:
            lines.append(line)
        for i, ln in enumerate(lines[:6]):
            draw.text((cx, cy + 310 + i * 30), ln, font=small, fill=(255, 255, 255, 200), anchor="mm")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path), quality=90)
        logger.debug("Placeholder image saved: %s", output_path)
        return output_path


class OpenAIImageProvider(ImageProvider):
    """Uses OpenAI DALL-E for image generation."""

    def __init__(self, api_key: str | None = None, model: str = "chatgpt-image-latest"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model
        if not self.api_key:
            raise ValueError("No OpenAI API key for image generation")
        try:
            import openai
            self.client = openai.OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("pip install openai")

    def generate_image(self, prompt: str, output_path: Path, width: int = 1080, height: int = 1920) -> Path:
        import base64
        import urllib.request

        size = "1024x1536"  # portrait — supported by chatgpt-image-latest and gpt-image-1
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                resp = self.client.images.generate(
                    model=self.model,
                    prompt=prompt,
                    size=size,
                    quality="medium",
                    n=1,
                )
                item = resp.data[0]
                output_path.parent.mkdir(parents=True, exist_ok=True)
                if item.b64_json:
                    output_path.write_bytes(base64.b64decode(item.b64_json))
                else:
                    urllib.request.urlretrieve(item.url, str(output_path))
                logger.info("Image generated: %s", output_path)
                return output_path
            except Exception as e:
                err_str = str(e)
                is_rate_limit = "429" in err_str or "rate_limit" in err_str.lower()
                is_auth_error = "401" in err_str and "Not authorized" in err_str

                if attempt < MAX_ATTEMPTS and (is_rate_limit or is_auth_error):
                    # Parse the wait time from the error, or use exponential backoff
                    wait = _parse_retry_after(err_str) or (BASE_DELAY * attempt)
                    logger.warning("Image gen attempt %d/%d: %s — waiting %.0fs",
                                   attempt, MAX_ATTEMPTS,
                                   "rate limited" if is_rate_limit else "transient 401",
                                   wait)
                    time.sleep(wait)
                elif attempt < MAX_ATTEMPTS:
                    wait = BASE_DELAY * attempt
                    logger.warning("Image gen attempt %d/%d failed: %s — retrying in %.0fs",
                                   attempt, MAX_ATTEMPTS, e, wait)
                    time.sleep(wait)
                else:
                    logger.error("Image gen failed after %d attempts: %s", MAX_ATTEMPTS, e)
                    raise


def _lighten(color: tuple, amount: int) -> tuple:
    return tuple(min(255, c + amount) for c in color)


def create_image_provider(cfg: dict) -> ImageProvider:
    """Factory function."""
    provider = cfg.get("image_provider", "placeholder")
    if provider == "placeholder" or not cfg.get("image_generation_enabled", True):
        logger.info("Using PlaceholderImageProvider")
        return PlaceholderImageProvider()
    if provider == "openai":
        api_key = cfg.get("openai_api_key", os.getenv("OPENAI_API_KEY", ""))
        if not api_key:
            logger.warning("No API key for OpenAI images — falling back to placeholder")
            return PlaceholderImageProvider()
        return OpenAIImageProvider(api_key=api_key)
    raise ValueError(f"Unknown image_provider: {provider}")
