"""Stage: generate images for each scene."""

from pathlib import Path

from providers.base import ImageProvider
from utils.logging import get_logger

logger = get_logger(__name__)


def generate_images(
    image_provider: ImageProvider,
    script: dict,
    images_dir: Path,
) -> list[Path]:
    """Generate one image per scene. Returns list of image paths."""
    images_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    for scene in script.get("scenes", []):
        num = scene.get("scene_number", len(paths) + 1)
        img_path = images_dir / f"scene_{num:03d}.png"

        if img_path.exists():
            logger.debug("Scene %d image cached: %s", num, img_path)
            paths.append(img_path)
            continue

        prompt = scene.get("image_prompt", scene.get("visual_description", "colorful dinosaur scene"))
        try:
            result = image_provider.generate_image(prompt, img_path)
            paths.append(result)
        except Exception as e:
            logger.error("Failed to generate image for scene %d: %s", num, e)
            # Generate a minimal fallback
            _create_fallback_image(img_path, f"Scene {num}")
            paths.append(img_path)

    logger.info("Generated %d scene images in %s", len(paths), images_dir)
    return paths


def _create_fallback_image(path: Path, text: str):
    """Create a minimal fallback image."""
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (1080, 1920), (100, 100, 100))
        draw = ImageDraw.Draw(img)
        draw.text((540, 960), text, fill="white", anchor="mm")
        img.save(str(path))
    except ImportError:
        # If even Pillow is missing, create a tiny placeholder
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")  # empty file
