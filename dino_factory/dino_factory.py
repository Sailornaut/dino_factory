#!/usr/bin/env python3
"""DinoFactAdventures Factory — batch YouTube Shorts generator for kids."""

import argparse
import sys
from pathlib import Path

from config import load_config, merge_cli_into_config
from pipeline.runner import run_pipeline
from utils.logging import setup_logging, get_logger

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="dino_factory",
        description="Generate kid-friendly YouTube Shorts from a single idea.",
    )
    p.add_argument("--idea", type=str, help="Seed idea for the batch")
    p.add_argument("--shorts", type=int, help="Number of Shorts to generate")
    p.add_argument("--target-length", type=int, help="Target length in seconds")
    p.add_argument("--audience", type=str, help='Target audience, e.g. "kids ages 4-8"')
    p.add_argument("--style", type=str, help="Visual style description")
    p.add_argument("--channel-name", type=str, help="YouTube channel name")
    p.add_argument("--config", type=str, default="config.yaml", help="Path to config file")
    p.add_argument("--output-dir", type=str, help="Override output directory")
    p.add_argument("--resume", action="store_true", default=True, help="Skip already-completed Shorts")
    p.add_argument("--no-resume", action="store_true", help="Regenerate everything")
    p.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging()

    cfg = load_config(args.config)
    cfg = merge_cli_into_config(cfg, args)

    if not cfg.get("idea"):
        logger.error("No --idea provided and none found in config.yaml")
        return 1

    logger.info("DinoFactAdventures Factory starting")
    logger.info("Idea: %s", cfg["idea"])
    logger.info("Shorts to generate: %d", cfg["number_of_shorts"])

    if args.dry_run:
        logger.info("[DRY RUN] Would generate %d shorts for idea: %s", cfg["number_of_shorts"], cfg["idea"])
        return 0

    resume = not args.no_resume
    try:
        run_pipeline(cfg, resume=resume)
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130
    except Exception:
        logger.exception("Pipeline failed")
        return 1

    logger.info("Pipeline complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
