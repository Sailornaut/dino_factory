"""Pipeline runner — orchestrates all stages for a batch of Shorts."""

import json
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from pipeline.background_audio import generate_background_audio
from pipeline.captions import generate_captions
from pipeline.images import generate_images
from pipeline.metadata import generate_batch_csv, generate_metadata
from pipeline.script import generate_script
from pipeline.topics import generate_topics
from pipeline.video import assemble_video
from pipeline.voiceover import generate_voiceover
from presets import get_preset
from providers.image import create_image_provider
from providers.llm import create_llm_provider
from providers.video import create_video_assembler
from providers.voice import create_voice_provider
from utils.logging import get_logger

logger = get_logger(__name__)


class PipelineCancelled(Exception):
    """Raised when the user cancels the pipeline."""


def _check_cancel(cancel_event: threading.Event | None,
                  pause_event: threading.Event | None = None):
    """Block while paused; raise PipelineCancelled if cancelled."""
    if pause_event is not None:
        while pause_event.is_set():
            # Check cancel while paused so cancel unblocks immediately
            if cancel_event is not None and cancel_event.is_set():
                raise PipelineCancelled("Pipeline cancelled by user")
            pause_event.wait(0.5)  # re-check every 500ms
    if cancel_event is not None and cancel_event.is_set():
        raise PipelineCancelled("Pipeline cancelled by user")


def _should_resume_batch(batch_dir: Path, cfg: dict) -> str:
    """Decide whether to resume a previous batch.

    Returns:
        "resume"         — batch is incomplete and matches current settings
        "skip_complete"  — batch finished with no errors
        "skip_mismatch"  — batch was for a different prompt/genre/count
        "skip_empty"     — batch dir is empty or unreadable
    """
    cfg_path = batch_dir / "config.yaml"
    shorts_dir = batch_dir / "shorts"
    errors_dir = batch_dir / "errors"

    if not cfg_path.exists():
        return "skip_empty"

    # Load the saved config to compare against current request
    try:
        with open(cfg_path, encoding="utf-8") as f:
            prev_cfg = yaml.safe_load(f) or {}
    except Exception:
        return "skip_empty"

    # Check if the prompt / genre / count match
    same_idea  = prev_cfg.get("idea", "").strip() == cfg.get("idea", "").strip()
    same_genre = prev_cfg.get("genre", "dino_facts") == cfg.get("genre", "dino_facts")
    same_count = prev_cfg.get("number_of_shorts", 5) == cfg.get("number_of_shorts", 5)

    if not (same_idea and same_genre and same_count):
        return "skip_mismatch"

    # Count completed videos vs expected
    expected = prev_cfg.get("number_of_shorts", 5)
    completed_videos = list(shorts_dir.glob("*/video.mp4")) if shorts_dir.exists() else []
    error_files = list(errors_dir.glob("*.error.txt")) if errors_dir.exists() else []

    if len(completed_videos) >= expected and len(error_files) == 0:
        return "skip_complete"

    # Has incomplete work (or errors to retry)
    return "resume"


def run_pipeline(cfg: dict[str, Any], resume: bool = True,
                 cancel_event: threading.Event | None = None,
                 pause_event: threading.Event | None = None):
    """Run the full Short generation pipeline."""

    # Create batch output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_base = Path(cfg.get("output_dir", "output"))
    batch_dir = output_base / f"batch_{timestamp}"

    # If resuming, look for the most recent existing batch — but only
    # resume if it's (a) incomplete and (b) for the same prompt/genre.
    if resume and output_base.exists():
        existing = sorted(output_base.glob("batch_*"), reverse=True)
        for candidate in existing:
            reason = _should_resume_batch(candidate, cfg)
            if reason == "resume":
                batch_dir = candidate
                logger.info("Resuming incomplete batch: %s", batch_dir)
                break
            elif reason == "skip_complete":
                logger.info("Previous batch complete — starting fresh")
                break
            elif reason == "skip_mismatch":
                logger.info("Previous batch has different settings — starting fresh")
                break
            # reason == "skip_empty" — try next candidate

    batch_dir.mkdir(parents=True, exist_ok=True)
    shorts_dir = batch_dir / "shorts"
    shorts_dir.mkdir(exist_ok=True)
    errors_dir = batch_dir / "errors"
    errors_dir.mkdir(exist_ok=True)

    # Save config snapshot
    cfg_snapshot = batch_dir / "config.yaml"
    if not cfg_snapshot.exists():
        with open(cfg_snapshot, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, default_flow_style=False)

    # Initialize providers
    llm = create_llm_provider(cfg)
    image_provider = create_image_provider(cfg)
    voice_provider = create_voice_provider(cfg)
    assembler = create_video_assembler(cfg)

    count = cfg.get("number_of_shorts", 5)

    # Stage 1: Generate topics
    _check_cancel(cancel_event, pause_event)
    logger.info("=" * 60)
    logger.info("STAGE 1: Generating %d topics", count)
    logger.info("=" * 60)
    genre = cfg.get("genre", "dino_facts")
    preset = get_preset(genre)

    topics = generate_topics(
        llm=llm,
        idea=cfg["idea"],
        count=count,
        audience=cfg.get("audience", preset.audience),
        cache_path=batch_dir / "topics.json",
        genre=genre,
    )
    logger.info("Got %d topics", len(topics))

    # Process each Short
    all_metadata = []
    for i, topic in enumerate(topics, 1):
        slug = topic.get("slug", f"short_{i:03d}")
        short_dir = shorts_dir / f"{i:03d}_{slug}"

        _check_cancel(cancel_event, pause_event)

        logger.info("")
        logger.info("=" * 60)
        logger.info("SHORT %d/%d: %s", i, len(topics), topic.get("title", slug))
        logger.info("=" * 60)

        # Check if already complete
        video_path = short_dir / "video.mp4"
        if resume and video_path.exists():
            logger.info("✓ Already complete — skipping")
            meta_path = short_dir / "metadata.json"
            if meta_path.exists():
                with open(meta_path, encoding="utf-8") as f:
                    all_metadata.append(json.load(f))
            else:
                all_metadata.append({"title": topic.get("title", "")})
            continue

        try:
            _process_single_short(
                topic=topic,
                short_dir=short_dir,
                cfg=cfg,
                llm=llm,
                image_provider=image_provider,
                voice_provider=voice_provider,
                assembler=assembler,
                all_metadata=all_metadata,
                cancel_event=cancel_event,
                pause_event=pause_event,
            )
        except PipelineCancelled:
            raise  # let it bubble up cleanly
        except Exception as e:
            logger.error("Failed to process Short '%s': %s", slug, e)
            # Move to errors folder
            err_file = errors_dir / f"{slug}.error.txt"
            err_file.write_text(f"Topic: {json.dumps(topic)}\nError: {e}")
            all_metadata.append({"title": topic.get("title", ""), "error": str(e)})

    # Final: generate batch CSV
    if cfg.get("youtube_metadata_enabled", True):
        logger.info("")
        logger.info("Generating batch metadata CSV...")
        generate_batch_csv(batch_dir, topics, all_metadata)

    # Summary
    completed = sum(1 for m in all_metadata if "error" not in m)
    failed = sum(1 for m in all_metadata if "error" in m)
    logger.info("")
    logger.info("=" * 60)
    logger.info("BATCH COMPLETE")
    logger.info("Output: %s", batch_dir)
    logger.info("Completed: %d / %d", completed, len(topics))
    if failed:
        logger.warning("Failed: %d (see %s)", failed, errors_dir)
    logger.info("=" * 60)


def _process_single_short(
    topic: dict,
    short_dir: Path,
    cfg: dict,
    llm,
    image_provider,
    voice_provider,
    assembler,
    all_metadata: list,
    cancel_event: threading.Event | None = None,
    pause_event: threading.Event | None = None,
):
    """Process a single Short through all stages."""
    short_dir.mkdir(parents=True, exist_ok=True)

    # Stage 2: Generate script
    _check_cancel(cancel_event, pause_event)
    logger.info("  → Generating script...")
    script = generate_script(
        llm=llm,
        topic=topic,
        cfg=cfg,
        cache_path=short_dir / "script.json",
    )

    # Stage 3: Generate images
    _check_cancel(cancel_event, pause_event)
    if cfg.get("image_generation_enabled", True):
        logger.info("  → Generating images...")
        image_paths = generate_images(
            image_provider=image_provider,
            script=script,
            images_dir=short_dir / "images",
        )
    else:
        logger.info("  → Image generation disabled — skipping")
        image_paths = []

    # Stage 4: Generate voiceover
    _check_cancel(cancel_event, pause_event)
    if cfg.get("voice_generation_enabled", True):
        logger.info("  → Generating voiceover...")
        audio_path = generate_voiceover(
            voice_provider=voice_provider,
            script=script,
            audio_dir=short_dir / "audio",
            voice=cfg.get("narrator_voice", "alloy"),
        )
    else:
        logger.info("  → Voice generation disabled — skipping")
        audio_path = None

    # Stage 5: Generate captions
    _check_cancel(cancel_event, pause_event)
    if cfg.get("include_captions", True):
        logger.info("  → Generating captions...")
        captions_path = generate_captions(
            script=script,
            captions_path=short_dir / "captions.srt",
        )
    else:
        captions_path = None

    # Stage 5b: Generate background audio (if genre requires it)
    _check_cancel(cancel_event, pause_event)
    genre = cfg.get("genre", "dino_facts")
    preset = get_preset(genre)
    bg_audio_path = None
    if preset.background_music_type != "none":
        logger.info("  → Generating background audio (%s)...", preset.background_music_type)
        # Estimate total video duration from scene durations
        total_dur = sum(s.get("duration_seconds", 5) for s in script.get("scenes", []))
        total_dur += preset.title_card_duration + preset.outro_card_duration + 5  # padding
        bg_audio_path = generate_background_audio(
            audio_type=preset.background_music_type,
            duration=total_dur,
            output_path=short_dir / "audio" / "background.wav",
        )

    # Use explicit music path from config, or the generated background audio
    music_path = cfg.get("background_music_path", "")
    if not music_path and bg_audio_path:
        music_path = str(bg_audio_path)

    # Stage 6: Assemble video
    _check_cancel(cancel_event, pause_event)
    if cfg.get("video_generation_enabled", True) and image_paths:
        logger.info("  → Assembling video...")
        assemble_video(
            assembler=assembler,
            script=script,
            image_paths=image_paths,
            audio_path=audio_path,
            captions_path=captions_path,
            output_path=short_dir / "video.mp4",
            music_path=music_path,
        )
    else:
        logger.info("  → Video assembly skipped (disabled or no images)")

    # Stage 7: Generate metadata
    if cfg.get("youtube_metadata_enabled", True):
        logger.info("  → Generating metadata...")
        meta = generate_metadata(
            script=script,
            metadata_path=short_dir / "metadata.json",
        )
        all_metadata.append(meta)
    else:
        all_metadata.append({"title": script.get("title", "")})

    logger.info("  ✓ Short complete: %s", short_dir.name)
