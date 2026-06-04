"""Configuration loading and merging."""

import os
from pathlib import Path
from typing import Any

import yaml


def _load_dotenv(env_path: Path | None = None):
    """Load a .env file into os.environ (simple implementation, no dependency)."""
    candidates = [env_path] if env_path else [
        Path.cwd() / ".env",
        Path(__file__).parent / ".env",
    ]
    for p in candidates:
        if p and p.exists():
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("'\"")
                    # Only set if not already in env (real env vars win)
                    if key and not os.getenv(key):
                        os.environ[key] = value
            return

DEFAULTS: dict[str, Any] = {
    "channel_name": "DinoFactAdventures",
    "audience": "kids ages 4-8",
    "number_of_shorts": 5,
    "target_length_seconds": 45,
    "tone": "cheerful, educational, friendly",
    "visual_style": "cute 3D cartoon, bright colors, friendly dinosaurs",
    "narrator_voice": "alloy",
    "output_dir": "output",
    "openai_model": "gpt-4o-mini",
    "image_generation_enabled": True,
    "voice_generation_enabled": True,
    "video_generation_enabled": True,
    "background_music_path": "",
    "include_captions": True,
    "youtube_metadata_enabled": True,
    "idea": "",
    "scenes_per_short": 6,
    "image_provider": "placeholder",
    "voice_provider": "placeholder",
    "llm_provider": "openai",
}


def load_config(path: str = "config.yaml") -> dict[str, Any]:
    """Load config from YAML file, falling back to defaults."""
    # Load .env first so env vars are available for the rest
    _load_dotenv()

    cfg = dict(DEFAULTS)
    p = Path(path)
    if p.exists():
        with open(p) as f:
            file_cfg = yaml.safe_load(f) or {}
        cfg.update({k: v for k, v in file_cfg.items() if v is not None})
    # Environment overrides
    if os.getenv("OPENAI_API_KEY"):
        cfg["openai_api_key"] = os.getenv("OPENAI_API_KEY")
    if os.getenv("OPENAI_MODEL"):
        cfg["openai_model"] = os.getenv("OPENAI_MODEL")
    if os.getenv("ELEVENLABS_API_KEY"):
        cfg["elevenlabs_api_key"] = os.getenv("ELEVENLABS_API_KEY")
    if os.getenv("ELEVENLABS_VOICE_ID"):
        cfg["elevenlabs_voice_id"] = os.getenv("ELEVENLABS_VOICE_ID")
    return cfg


def merge_cli_into_config(cfg: dict[str, Any], args) -> dict[str, Any]:
    """Merge CLI arguments into config, CLI wins."""
    mapping = {
        "idea": "idea",
        "shorts": "number_of_shorts",
        "target_length": "target_length_seconds",
        "audience": "audience",
        "style": "visual_style",
        "channel_name": "channel_name",
        "output_dir": "output_dir",
    }
    for cli_key, cfg_key in mapping.items():
        val = getattr(args, cli_key, None)
        if val is not None:
            cfg[cfg_key] = val
    return cfg
