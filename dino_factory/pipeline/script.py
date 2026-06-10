"""Stage: generate a full script for one video."""

import json
from pathlib import Path

from providers.base import LLMProvider
from utils.logging import get_logger
from utils.validation import validate_script

logger = get_logger(__name__)


def generate_script(
    llm: LLMProvider,
    topic: dict,
    cfg: dict,
    cache_path: Path,
) -> dict:
    """Generate a complete script JSON for one video."""
    if cache_path.exists():
        logger.info("Loading cached script: %s", cache_path)
        with open(cache_path, encoding="utf-8") as f:
            script = json.load(f)
        if validate_script(script):
            return script
        logger.warning("Cached script invalid — regenerating")

    # Load preset for genre-specific behavior
    from presets import get_preset
    preset = get_preset(cfg.get("genre", "dino_facts"))

    target_len = cfg.get("target_length_seconds", preset.target_length)
    style = cfg.get("visual_style", preset.visual_style)
    audience = cfg.get("audience", preset.audience)
    channel = cfg.get("channel_name", "DinoFactAdventures")
    scenes_count = cfg.get("scenes_per_video", cfg.get("scenes_per_short", preset.scenes_per_video))
    character_names = cfg.get("character_names", "")

    system_prompt = preset.system_prompt

    # Build the genre-specific prompt
    genre = preset.name

    if genre == "bedtime_stories":
        prompt = _bedtime_prompt(topic, target_len, style, audience, channel,
                                 scenes_count, character_names)
    elif genre == "creepypasta":
        prompt = _creepypasta_prompt(topic, target_len, style, audience, channel,
                                     scenes_count)
    else:
        prompt = _dino_facts_prompt(topic, target_len, style, audience, channel,
                                    scenes_count)

    script = llm.generate_json(prompt, system=system_prompt)

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


# ── Genre-specific prompts ───────────────────────────────────────────────


def _dino_facts_prompt(topic, target_len, style, audience, channel, scenes_count):
    return f"""Create a YouTube Shorts script about this topic:

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


def _bedtime_prompt(topic, target_len, style, audience, channel, scenes_count, character_names):
    character_instruction = ""
    if character_names:
        character_instruction = f"""
IMPORTANT — RECURRING CHARACTERS:
The following character name(s) must be the protagonist(s) of this story: {character_names}
Use these names consistently throughout. The child listening should feel like these are THEIR characters who go on a new gentle adventure each episode.
"""

    return f"""Create a gentle bedtime story script for a calming YouTube video.

Story concept: {topic['title']}
Story seed: {topic.get('fun_fact', topic['title'])}
{character_instruction}
Requirements:
- Target length: {target_len} seconds (~{target_len // 60} minutes)
- Audience: {audience}
- Visual style: {style}
- Channel name: {channel}
- Number of scenes: {scenes_count}
- Scene durations should total ~{target_len - 11}s (leaving room for gentle title/outro)

Return a JSON object with this exact structure:
{{
  "title": "...",
  "hook": "A soft, inviting opening line that sets the sleepy mood",
  "voiceover": "The FULL story narration — this is the complete text that will be read aloud. It should be {target_len // 60}-{target_len // 60 + 2} minutes when read at a slow, gentle pace. Write it as flowing prose, not bullet points.",
  "scenes": [
    {{
      "scene_number": 1,
      "duration_seconds": {target_len // scenes_count},
      "visual_description": "What the illustration shows",
      "image_prompt": "Detailed image generation prompt in style: {style}",
      "caption": "Short gentle text overlay"
    }}
  ],
  "call_to_action": "A whispered goodnight message",
  "youtube_title": "Gentle title with a moon or star emoji, under 100 chars",
  "youtube_description": "2-3 calm sentences with #bedtimestory #kidssleep hashtags",
  "tags": ["bedtime story", "kids sleep", "calming", "children's story"]
}}

CRITICAL STORYTELLING RULES:
- The voiceover must be LONG — a full story that fills {target_len // 60} minutes read slowly
- Pacing: start gently, wind DOWN toward sleep, end with the character(s) drifting off
- Use sensory details: soft moonlight, warm blankets, gentle breezes, quiet sounds
- NO excitement, tension, or loud moments — this is meant to help children fall asleep
- The final 2-3 scenes must describe settling down, closing eyes, and peaceful sleep
- Each image_prompt should create a soft, dreamy, watercolor-style illustration
- Captions should be short and calming
- Return ONLY the JSON, no other text
"""


def _creepypasta_prompt(topic, target_len, style, audience, channel, scenes_count):
    return f"""Create a creepypasta-style horror narration script for a YouTube video.

Story concept: {topic['title']}
Story seed: {topic.get('fun_fact', topic['title'])}

Requirements:
- Target length: {target_len} seconds (~{target_len // 60} minutes)
- Audience: {audience}
- Visual style: {style}
- Channel name: {channel}
- Number of scenes: {scenes_count}
- Scene durations should total ~{target_len - 9}s

Return a JSON object with this exact structure:
{{
  "title": "...",
  "hook": "A disturbing opening line that immediately creates unease",
  "voiceover": "The FULL narration — a complete first-person horror story, {target_len // 60}-{target_len // 60 + 3} minutes when read at a deliberate pace. Write as flowing, atmospheric prose. Build slow dread.",
  "scenes": [
    {{
      "scene_number": 1,
      "duration_seconds": {target_len // scenes_count},
      "visual_description": "What the dark, atmospheric image shows",
      "image_prompt": "Detailed image generation prompt in style: {style}",
      "caption": "Short unsettling text overlay"
    }}
  ],
  "call_to_action": "A haunting final line that lingers",
  "youtube_title": "Intriguing horror title, under 100 chars",
  "youtube_description": "2-3 atmospheric sentences with #creepypasta #horror hashtags",
  "tags": ["creepypasta", "horror", "scary story", "narration"]
}}

STORYTELLING RULES:
- Write in FIRST PERSON — "I", "my", "me" — the narrator experienced this
- The voiceover must be LONG — a complete story filling {target_len // 60} minutes
- Build SLOWLY: normal → one wrong detail → escalating dread → revelation
- Use SPECIFIC mundane details (dates, places, routines) to make it feel real
- Horror is PSYCHOLOGICAL — what's implied, not what's shown
- Leave the ending AMBIGUOUS or HAUNTING
- Each image_prompt should create a dark, moody, atmospheric scene
- Captions should be short and unsettling
- NO gore, no gratuitous violence — the horror is in what you DON'T see
- Return ONLY the JSON, no other text
"""
