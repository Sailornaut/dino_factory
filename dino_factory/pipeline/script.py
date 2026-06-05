"""Stage: generate a full script for one Short."""

import json
from pathlib import Path

from providers.base import LLMProvider
from utils.logging import get_logger
from utils.safety import SAFETY_SYSTEM_PROMPT
from utils.validation import validate_script

logger = get_logger(__name__)


def generate_script(
    llm: LLMProvider,
    topic: dict,
    cfg: dict,
    cache_path: Path,
) -> dict:
    """Generate a complete script JSON for one Short."""
    if cache_path.exists():
        logger.info("Loading cached script: %s", cache_path)
        with open(cache_path, encoding="utf-8") as f:
            script = json.load(f)
        if validate_script(script):
            return script
        logger.warning("Cached script invalid — regenerating")

    target_len = cfg.get("target_length_seconds", 45)
    style = cfg.get("visual_style", "cute 3D cartoon")
    audience = cfg.get("audience", "kids ages 4-8")
    channel = cfg.get("channel_name", "DinoFactAdventures")
    scenes_count = cfg.get("scenes_per_short", 6)

    prompt = f"""Create a YouTube Shorts script about this topic:

Title: {topic['title']}
Fun fact: {topic['fun_fact']}

Requirements:
- Target length: {target_len} seconds
- Audience: {audience}
- Visual style: {style}
- Channel name: {channel}
- Number of scenes: {scenes_count} (scene durations should total ~{target_len - 7}s, leaving room for intro/outro)

Return a JSON object with this exact structure:
{{
  "title": "...",
  "hook": "A 1-sentence attention grabber for the first 3 seconds",
  "voiceover": "The full narration text, natural and conversational",
  "scenes": [
    {{
      "scene_number": 1,
      "duration_seconds": 5,
      "visual_description": "What should be shown on screen",
      "image_prompt": "Detailed image generation prompt in style: {style}",
      "caption": "Short caption text overlay"
    }}
  ],
  "call_to_action": "Engaging CTA for the end",
  "youtube_title": "Catchy title with emoji, under 100 chars",
  "youtube_description": "2-3 sentences with hashtags",
  "tags": ["tag1", "tag2", "tag3"]
}}

Rules:
- Use simple vocabulary suitable for {audience}
- Keep the tone cheerful, friendly, and educational
- The hook must grab attention immediately
- Each image_prompt should be detailed and include the visual style
- Captions should be short (under 10 words each)
- The voiceover should sound natural, not robotic
- Include "wow" moments that make kids say "that's so cool!"
- Return ONLY the JSON, no other text
"""
    script = llm.generate_json(prompt, system=SAFETY_SYSTEM_PROMPT)

    if not validate_script(script):
        logger.warning("Generated script failed validation — using as-is with defaults")
        script.setdefault("title", topic["title"])
        script.setdefault("hook", "")
        script.setdefault("voiceover", topic.get("fun_fact", ""))
        script.setdefault("scenes", [])
        script.setdefault("call_to_action", "")
        script.setdefault("youtube_title", topic["title"])
        script.setdefault("youtube_description", "")
        script.setdefault("tags", [])

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2, ensure_ascii=False)
    logger.info("Script generated → %s", cache_path)
    return script
