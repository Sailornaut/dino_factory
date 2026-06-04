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
        with open(cache_path) as f:
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

Rules:
- All topics must be unique and distinct
- Keep it educational, cheerful, and age-appropriate
- Each topic should be surprising or "wow" worthy
- No scary, violent, or inappropriate content
- Return ONLY the JSON array, no other text
"""
    topics = llm.generate_json(prompt, system=SAFETY_SYSTEM_PROMPT)

    if not isinstance(topics, list):
        raise ValueError(f"Expected list of topics, got {type(topics)}")

    # Validate and clean
    cleaned = []
    for t in topics[:count]:
        if not isinstance(t, dict):
            continue
        slug = t.get("slug", "").replace(" ", "_").replace("-", "_").lower()
        slug = "".join(c for c in slug if c.isalnum() or c == "_")
        cleaned.append({
            "title": t.get("title", f"Topic {len(cleaned)+1}"),
            "slug": slug or f"topic_{len(cleaned)+1:03d}",
            "fun_fact": t.get("fun_fact", ""),
        })

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(cleaned, f, indent=2)
    logger.info("Generated %d topics → %s", len(cleaned), cache_path)
    return cleaned
