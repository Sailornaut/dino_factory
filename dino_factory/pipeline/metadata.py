"""Stage: generate YouTube upload metadata."""

import csv
import json
from pathlib import Path

from utils.logging import get_logger

logger = get_logger(__name__)


def generate_metadata(script: dict, metadata_path: Path) -> dict:
    """Save YouTube metadata JSON for one Short."""
    if metadata_path.exists():
        logger.debug("Metadata cached: %s", metadata_path)
        with open(metadata_path, encoding="utf-8") as f:
            return json.load(f)

    meta = {
        "title": script.get("youtube_title", script.get("title", "")),
        "description": script.get("youtube_description", ""),
        "tags": script.get("tags", []),
        "category": "Education",
        "privacy": "public",
        "made_for_kids": True,
        "language": "en",
    }

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    logger.info("Metadata saved → %s", metadata_path)
    return meta


def generate_batch_csv(batch_dir: Path, topics: list[dict], all_metadata: list[dict]):
    """Generate a metadata.csv summarizing all Shorts for bulk upload."""
    csv_path = batch_dir / "metadata.csv"
    fieldnames = ["slug", "title", "description", "tags", "video_file", "category", "privacy", "made_for_kids"]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for topic, meta in zip(topics, all_metadata):
            slug = topic.get("slug", "unknown")
            writer.writerow({
                "slug": slug,
                "title": meta.get("title", ""),
                "description": meta.get("description", ""),
                "tags": "|".join(meta.get("tags", [])),
                "video_file": f"shorts/{slug}/video.mp4",
                "category": meta.get("category", "Education"),
                "privacy": meta.get("privacy", "public"),
                "made_for_kids": meta.get("made_for_kids", True),
            })

    logger.info("Batch metadata CSV → %s", csv_path)
    return csv_path
