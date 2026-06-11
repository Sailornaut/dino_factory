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
    characters_prompt = cfg.get("characters_prompt", "")
    characters_visual = cfg.get("characters_visual", "")

    system_prompt = preset.system_prompt

    # Build the genre-specific prompt
    genre = preset.name

    if genre == "bedtime_stories":
        prompt = _bedtime_prompt(topic, target_len, style, audience, channel,
                                 scenes_count, characters_prompt, characters_visual)
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

    # Log word count so we can spot short scripts
    voiceover_text = script.get("voiceover", "")
    word_count = len(voiceover_text.split())
    est_minutes = word_count / 130  # conservative wpm
    logger.info("Voiceover: %d words (~%.1f min at 130 wpm) for %ds target",
                word_count, est_minutes, target_len)
    if word_count < (target_len * 100 / 60):  # very generous floor
        logger.warning("Voiceover may be SHORT — %d words for %ds target. "
                       "Video will be trimmed to match narration length.",
                       word_count, target_len)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2, ensure_ascii=False)
    logger.info("Script generated → %s", cache_path)
    return script


# ── Genre-specific prompts ───────────────────────────────────────────────


def _dino_facts_prompt(topic, target_len, style, audience, channel, scenes_count):
    # ~150 words per minute for upbeat kids narration
    word_target = int(target_len * 150 / 60)
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
  "voiceover": "The full narration text — MUST be at least {word_target} words. Natural and conversational.",
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
- CRITICAL: The voiceover text MUST be at least {word_target} words — count carefully!
  At 150 words/minute, {word_target} words fills {target_len} seconds.
  If you write fewer words, the video will have awkward silence.
- Return ONLY the JSON, no other text
"""


def _bedtime_prompt(topic, target_len, style, audience, channel, scenes_count,
                    characters_prompt, characters_visual):
    character_instruction = ""
    if characters_prompt:
        character_instruction = f"""
IMPORTANT — RECURRING CHARACTERS:
These characters MUST be the protagonist(s) of this story. Use their names,
personalities, and appearances CONSISTENTLY throughout — the child listening
should feel like these are THEIR characters going on a new gentle adventure.

{characters_prompt}

VISUAL CONSISTENCY: Every image_prompt that includes a character MUST describe
their appearance exactly as defined above so they look the same across all scenes.
Character visual reference: {characters_visual}
"""

    # ~120 words per minute for slow, gentle bedtime narration
    word_target = int(target_len * 120 / 60)

    return f"""Create a gentle bedtime story script for a calming YouTube video.

Story concept: {topic['title']}
Story seed: {topic.get('fun_fact', topic['title'])}
{character_instruction}
Requirements:
- Target length: {target_len} seconds (~{target_len // 60} minutes)
- WORD COUNT: The voiceover MUST be at least {word_target} words (at 120 words/minute for slow bedtime pacing, {word_target} words = {target_len // 60} minutes)
- Audience: {audience}
- Visual style: {style}
- Channel name: {channel}
- Number of scenes: {scenes_count}
- Scene durations should total ~{target_len - 11}s (leaving room for gentle title/outro)

Return a JSON object with this exact structure:
{{
  "title": "...",
  "hook": "A soft, inviting opening line that sets the sleepy mood",
  "voiceover": "The FULL story narration — MUST be at least {word_target} words. This is the complete text read aloud at a slow, gentle pace. Write it as flowing prose, not bullet points.",
  "scenes": [
    {{
      "scene_number": 1,
      "duration_seconds": {target_len // scenes_count},
      "visual_description": "What the illustration shows",
      "image_prompt": "Detailed image generation prompt in style: {style}. IMPORTANT: if a character appears, describe their appearance explicitly: {characters_visual or 'N/A'}",
      "caption": "Short gentle text overlay"
    }}
  ],
  "call_to_action": "A whispered goodnight message",
  "youtube_title": "Gentle title with a moon or star emoji, under 100 chars",
  "youtube_description": "2-3 calm sentences with #bedtimestory #kidssleep hashtags",
  "tags": ["bedtime story", "kids sleep", "calming", "children's story"]
}}

CRITICAL STORYTELLING RULES:
- MOST IMPORTANT: The voiceover MUST be at least {word_target} words! Count carefully.
  A 6-minute bedtime story at 120 wpm needs ~720 words. Write a FULL, COMPLETE story.
  Expand scenes with sensory details, gentle dialogue, and descriptive passages.
  If your voiceover is under {word_target} words, the video will have awkward silence.
- Pacing: start gently, wind DOWN toward sleep, end with the character(s) drifting off
- Use sensory details: soft moonlight, warm blankets, gentle breezes, quiet sounds
- NO excitement, tension, or loud moments — this is meant to help children fall asleep
- The final 2-3 scenes must describe settling down, closing eyes, and peaceful sleep
- Each image_prompt MUST include the full visual appearance of any character shown so that
  image generation produces a consistent look across all scenes
- Captions should be short and calming
- Return ONLY the JSON, no other text
"""


def _creepypasta_prompt(topic, target_len, style, audience, channel, scenes_count):
    # ~130 words per minute for deliberate, atmospheric horror narration
    word_target = int(target_len * 130 / 60)

    return f"""Create a creepypasta-style horror narration script for a YouTube video.

Story concept: {topic['title']}
Story seed: {topic.get('fun_fact', topic['title'])}

Requirements:
- Target length: {target_len} seconds (~{target_len // 60} minutes)
- WORD COUNT: The voiceover MUST be at least {word_target} words (at 130 words/minute for slow horror pacing, {word_target} words = {target_len // 60} minutes)
- Audience: {audience}
- Visual style: {style}
- Channel name: {channel}
- Number of scenes: {scenes_count}
- Scene durations should total ~{target_len - 9}s

Return a JSON object with this exact structure:
{{
  "title": "...",
  "hook": "A disturbing opening line that immediately creates unease",
  "voiceover": "The FULL narration — MUST be at least {word_target} words. A complete first-person horror story at a deliberate pace. Write as flowing, atmospheric prose. Build slow dread.",
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
- MOST IMPORTANT: The voiceover MUST be at least {word_target} words! Count carefully.
  A 10-minute creepypasta at 130 wpm needs ~1300 words. Write a FULL, COMPLETE story.
  Expand with atmospheric details, internal monologue, specific sensory descriptions.
  If your voiceover is under {word_target} words, the video will have awkward silence.
- Write in FIRST PERSON — "I", "my", "me" — the narrator experienced this
- Build SLOWLY: normal → one wrong detail → escalating dread → revelation
- Use SPECIFIC mundane details (dates, places, routines) to make it feel real
- Horror is PSYCHOLOGICAL — what's implied, not what's shown
- Leave the ending AMBIGUOUS or HAUNTING
- Each image_prompt should create a dark, moody, atmospheric scene
- Captions should be short and unsettling
- NO gore, no gratuitous violence — the horror is in what you DON'T see
- Return ONLY the JSON, no other text
"""
