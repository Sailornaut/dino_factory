"""Stage: generate topics from seed idea."""

import json
from pathlib import Path

from providers.base import LLMProvider
from utils.logging import get_logger
from utils.safety import SAFETY_SYSTEM_PROMPT

logger = get_logger(__name__)


def generate_topics(
    llm: LLMProvider,
    idea: str,
    count: int,
    audience: str,
    cache_path: Path,
) -> list[dict]:
    """Generate a list of Short topics from a seed idea.

    Returns list of dicts with keys: title, slug, fun_fact
    """
    if cache_path.exists():
        logger.info("Loading cached topics from %s", cache_path)
        with open(cache_path, encoding="utf-8") as f:
            topics = json.load(f)
        if len(topics) >= count:
            return topics[:count]
        logger.info("Cached topics (%d) fewer than requested (%d) — regenerating", len(topics), count)

    prompt = f"""Generate exactly {count} unique YouTube Shorts topic ideas based on this seed idea:

"{idea}"

Target audience: {audience}

For each topic, provide:
- title: a catchy, kid-friendly title (include an emoji)
- slug: a short filename-safe slug (lowercase, underscores, no spaces)
- fun_fact: the core fun fact in one sentence

Return a JSON array of objects. Example:
[
  {{"title": "T-Rex Had Tiny Arms! 🦖", "slug": "trex_tiny_arms", "fun_fact": "T-Rex arms were only 3 feet long."}}
]

CRITICAL RULES FOR UNIQUENESS:
- Every single topic MUST be about a DIFFERENT specific dinosaur species OR a completely different aspect of paleontology
- NEVER repeat the same dinosaur in two topics (e.g. do NOT have both "T-Rex Speed" and "T-Rex Teeth")
- NEVER repeat the same theme in two topics (e.g. do NOT have both "Dino Eggs" and "Dino Babies" — those overlap too much)
- NEVER have two "fastest dino" or two "biggest dino" topics
- Each slug must be unique — no two topics can have similar slugs
- Aim for maximum variety: mix species spotlights, behaviors, anatomy, habitats, time periods, fossils, and comparisons
- Keep it educational, cheerful, and age-appropriate
- Each topic should be surprising or "wow" worthy
- No scary, violent, or inappropriate content
- Return ONLY the JSON array, no other text
"""
    topics = llm.generate_json(prompt, system=SAFETY_SYSTEM_PROMPT)

    if not isinstance(topics, list):
        raise ValueError(f"Expected list of topics, got {type(topics)}")

    # Validate, clean, and deduplicate
    cleaned = []
    seen_slugs = set()
    seen_subjects = set()  # track core subject to catch near-dupes

    for t in topics:
        if len(cleaned) >= count:
            break
        if not isinstance(t, dict):
            continue

        slug = t.get("slug", "").replace(" ", "_").replace("-", "_").lower()
        slug = "".join(c for c in slug if c.isalnum() or c == "_")
        if not slug:
            slug = f"topic_{len(cleaned)+1:03d}"

        # Skip duplicate slugs
        if slug in seen_slugs:
            logger.debug("Skipping duplicate slug: %s", slug)
            continue

        # Extract core subject words for near-dupe detection
        title_lower = t.get("title", "").lower()
        # Check if any key subject word group already appeared
        subject_words = _extract_subject(slug, title_lower)
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


def _extract_subject(slug: str, title: str) -> str:
    """Extract the core subject from a slug/title for dedup.

    E.g. "fastest_dino" and "the_fastest_dino" → "fastest_dino"
          "dino_eggs_huge" and "dino_eggs_treasure" → "dino_eggs"
    """
    # Remove common filler words from slug
    filler = {"the", "a", "an", "was", "were", "had", "is", "are", "did", "do",
              "dino", "dinos", "dinosaur", "dinosaurs", "fun", "facts", "fact",
              "amazing", "cool", "super", "really", "very", "so", "meet"}
    parts = [p for p in slug.split("_") if p and p not in filler]
    if len(parts) >= 2:
        return "_".join(parts[:2])  # first two meaningful words
    elif parts:
        return parts[0]
    return ""
