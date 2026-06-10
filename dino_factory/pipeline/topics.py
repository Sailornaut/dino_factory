"""Stage: generate topics from seed idea."""

import json
from pathlib import Path

from providers.base import LLMProvider
from utils.logging import get_logger

logger = get_logger(__name__)


def generate_topics(
    llm: LLMProvider,
    idea: str,
    count: int,
    audience: str,
    cache_path: Path,
    genre: str = "dino_facts",
) -> list[dict]:
    """Generate a list of video topics from a seed idea.

    Returns list of dicts with keys: title, slug, fun_fact
    """
    from presets import get_preset
    preset = get_preset(genre)

    if cache_path.exists():
        logger.info("Loading cached topics from %s", cache_path)
        with open(cache_path, encoding="utf-8") as f:
            topics = json.load(f)
        if len(topics) >= count:
            return topics[:count]
        logger.info("Cached topics (%d) fewer than requested (%d) — regenerating", len(topics), count)

    prompt = _build_topic_prompt(idea, count, audience, preset)
    topics = llm.generate_json(prompt, system=preset.system_prompt)

    if not isinstance(topics, list):
        raise ValueError(f"Expected list of topics, got {type(topics)}")

    # Validate, clean, and deduplicate
    cleaned = []
    seen_slugs = set()
    seen_subjects = set()

    for t in topics:
        if len(cleaned) >= count:
            break
        if not isinstance(t, dict):
            continue

        slug = t.get("slug", "").replace(" ", "_").replace("-", "_").lower()
        slug = "".join(c for c in slug if c.isalnum() or c == "_")
        if not slug:
            slug = f"topic_{len(cleaned)+1:03d}"

        if slug in seen_slugs:
            logger.debug("Skipping duplicate slug: %s", slug)
            continue

        subject_words = _extract_subject(slug, t.get("title", "").lower())
        if subject_words and subject_words in seen_subjects:
            logger.debug("Skipping near-duplicate topic: %s (subject=%s)", slug, subject_words)
            continue

        seen_slugs.add(slug)
        if subject_words:
            seen_subjects.add(subject_words)

        cleaned.append({
            "title": t.get("title", f"Topic {len(cleaned)+1}"),
            "slug": slug,
            "fun_fact": t.get("fun_fact", ""),
        })

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)
    logger.info("Generated %d topics → %s", len(cleaned), cache_path)
    return cleaned


def _build_topic_prompt(idea: str, count: int, audience: str, preset) -> str:
    """Build a genre-appropriate topic generation prompt."""
    genre = preset.name

    if genre == "bedtime_stories":
        return f"""Generate exactly {count} unique bedtime story ideas based on this seed:

"{idea}"

Target audience: {audience}

For each story, provide:
- title: a gentle, dreamy title (include a moon/star emoji)
- slug: a short filename-safe slug (lowercase, underscores)
- fun_fact: a one-sentence story premise

Return a JSON array. Example:
[
  {{"title": "Luna's Moonlit Garden", "slug": "lunas_moonlit_garden", "fun_fact": "A little bunny discovers a secret garden that only blooms under moonlight."}}
]

RULES:
- Every story must be UNIQUE — different settings, different adventures, different themes
- Themes: nature, friendship, dreams, seasons, gentle magic, animals, cozy places
- NO scary, tense, or exciting plots — these must be CALMING
- Variety in settings: forests, oceans, meadows, clouds, gardens, cozy homes, starlit fields
- Return ONLY the JSON array
"""

    elif genre == "creepypasta":
        return f"""Generate exactly {count} unique creepypasta story concepts based on this seed:

"{idea}"

Target audience: {audience}

For each story, provide:
- title: an intriguing, unsettling title (no emoji)
- slug: a short filename-safe slug (lowercase, underscores)
- fun_fact: a one-sentence premise that hooks the reader

Return a JSON array. Example:
[
  {{"title": "The House Remembered Me", "slug": "house_remembered_me", "fun_fact": "A man moves into his childhood home and finds drawings he doesn't remember making — of things that haven't happened yet."}}
]

RULES:
- Every story must be COMPLETELY UNIQUE — different settings, different types of horror, different premises
- Mix horror subgenres: cosmic, psychological, found footage, internet horror, rural, urban, historical
- Premises should be SPECIFIC and ORIGINAL, not generic ("haunted house")
- The fun_fact should make someone think "I need to hear this story"
- NO two stories about similar locations (e.g. don't have two "abandoned building" stories)
- NO two stories with similar entities (e.g. don't have two "mysterious stranger" stories)
- Return ONLY the JSON array
"""

    else:  # dino_facts
        return f"""Generate exactly {count} unique YouTube Shorts topic ideas based on this seed idea:

"{idea}"

Target audience: {audience}

For each topic, provide:
- title: a catchy, kid-friendly title (include an emoji)
- slug: a short filename-safe slug (lowercase, underscores, no spaces)
- fun_fact: the core fun fact in one sentence

Return a JSON array of objects. Example:
[
  {{"title": "T-Rex Had Tiny Arms!", "slug": "trex_tiny_arms", "fun_fact": "T-Rex arms were only 3 feet long."}}
]

CRITICAL RULES FOR UNIQUENESS:
- Every topic MUST be about a DIFFERENT specific dinosaur species OR a completely different aspect of paleontology
- NEVER repeat the same dinosaur in two topics
- NEVER repeat the same theme in two topics
- NEVER have two "fastest dino" or two "biggest dino" topics
- Each slug must be unique
- Aim for maximum variety: mix species spotlights, behaviors, anatomy, habitats, time periods, fossils, and comparisons
- Keep it educational, cheerful, and age-appropriate
- Each topic should be surprising or "wow" worthy
- No scary, violent, or inappropriate content
- Return ONLY the JSON array, no other text
"""


def _extract_subject(slug: str, title: str) -> str:
    """Extract the core subject from a slug/title for dedup."""
    filler = {"the", "a", "an", "was", "were", "had", "is", "are", "did", "do",
              "dino", "dinos", "dinosaur", "dinosaurs", "fun", "facts", "fact",
              "amazing", "cool", "super", "really", "very", "so", "meet",
              "story", "tales", "tale", "adventure", "adventures"}
    parts = [p for p in slug.split("_") if p and p not in filler]
    if len(parts) >= 2:
        return "_".join(parts[:2])
    elif parts:
        return parts[0]
    return ""
