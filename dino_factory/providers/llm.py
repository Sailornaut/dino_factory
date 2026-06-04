"""LLM provider implementations."""

import json
import os
import time
from typing import Any

from providers.base import LLMProvider
from utils.logging import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 2


class OpenAILLMProvider(LLMProvider):
    """Uses the OpenAI chat completions API."""

    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "No OpenAI API key found. Set OPENAI_API_KEY env var or use PlaceholderLLMProvider."
            )
        try:
            import openai
            self.client = openai.OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("pip install openai  to use OpenAILLMProvider")

    def generate(self, prompt: str, system: str = "", temperature: float = 0.7) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                logger.warning("LLM attempt %d/%d failed: %s", attempt, MAX_RETRIES, e)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)
                else:
                    raise

    def generate_json(self, prompt: str, system: str = "", temperature: float = 0.4) -> dict | list:
        raw = self.generate(prompt, system=system, temperature=temperature)
        # Strip markdown fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
        return json.loads(cleaned)


class PlaceholderLLMProvider(LLMProvider):
    """Generates deterministic placeholder content for testing without API keys."""

    def generate(self, prompt: str, system: str = "", temperature: float = 0.7) -> str:
        return "Placeholder response for: " + prompt[:100]

    def generate_json(self, prompt: str, system: str = "", temperature: float = 0.4) -> dict | list:
        # Detect what kind of JSON is expected from the prompt
        lower = prompt.lower()
        if "topic" in lower and ("list" in lower or "array" in lower or "generate" in lower):
            return self._placeholder_topics()
        elif "script" in lower or "scene" in lower:
            return self._placeholder_script()
        else:
            return {"placeholder": True}

    def _placeholder_topics(self) -> list[dict]:
        topics = [
            {"title": "T-Rex Had Tiny Arms!", "slug": "trex_tiny_arms", "fun_fact": "T-Rex arms were only about 3 feet long."},
            {"title": "Brachiosaurus Was HUGE!", "slug": "brachiosaurus_huge", "fun_fact": "Brachiosaurus was as tall as a 4-story building."},
            {"title": "Triceratops Had 3 Horns", "slug": "triceratops_horns", "fun_fact": "Triceratops means three-horned face."},
            {"title": "Velociraptors Were Small", "slug": "velociraptor_small", "fun_fact": "Velociraptors were only about the size of a turkey."},
            {"title": "Stegosaurus Had a Tiny Brain", "slug": "stegosaurus_brain", "fun_fact": "Stegosaurus brain was the size of a walnut."},
            {"title": "Pterodactyls Could Fly!", "slug": "pterodactyl_fly", "fun_fact": "Pterodactyls had wingspans up to 33 feet."},
            {"title": "Ankylosaurus Had Armor", "slug": "ankylosaurus_armor", "fun_fact": "Ankylosaurus was covered in bony plates like a tank."},
            {"title": "Diplodocus Had a Whip Tail", "slug": "diplodocus_tail", "fun_fact": "Diplodocus could crack its tail like a whip."},
            {"title": "Spinosaurus Loved Water", "slug": "spinosaurus_water", "fun_fact": "Spinosaurus was the biggest fish-eating dinosaur."},
            {"title": "Parasaurolophus Had a Horn Crest", "slug": "parasaurolophus_crest", "fun_fact": "Its crest could make trumpet sounds."},
        ]
        return topics

    def _placeholder_script(self) -> dict:
        return {
            "title": "T-Rex Had Tiny Arms!",
            "hook": "Did you know T-Rex had super tiny arms?",
            "voiceover": (
                "Hey friends! Did you know that the mighty T-Rex had really tiny arms? "
                "Even though T-Rex was one of the biggest dinosaurs ever, its arms were only "
                "about three feet long! That's shorter than YOUR arms! Scientists think T-Rex "
                "used its tiny arms to hold onto food. Isn't that wild? See you next time for "
                "more amazing dino facts!"
            ),
            "scenes": [
                {
                    "scene_number": 1,
                    "duration_seconds": 5,
                    "visual_description": "A friendly cartoon T-Rex waving hello",
                    "image_prompt": "cute 3D cartoon T-Rex waving, bright colors, friendly smile, kids illustration style",
                    "caption": "Did you know T-Rex had tiny arms?",
                },
                {
                    "scene_number": 2,
                    "duration_seconds": 8,
                    "visual_description": "T-Rex standing next to a size comparison chart",
                    "image_prompt": "cute 3D cartoon T-Rex standing next to a ruler showing 3 feet, bright colors, educational",
                    "caption": "Its arms were only 3 feet long!",
                },
                {
                    "scene_number": 3,
                    "duration_seconds": 7,
                    "visual_description": "A kid comparing arm length to T-Rex",
                    "image_prompt": "cute cartoon kid and T-Rex comparing arm sizes, bright colors, funny, friendly",
                    "caption": "That's shorter than YOUR arms!",
                },
                {
                    "scene_number": 4,
                    "duration_seconds": 8,
                    "visual_description": "T-Rex holding a snack with its tiny arms",
                    "image_prompt": "cute 3D cartoon T-Rex holding food with tiny arms, bright jungle, kids style",
                    "caption": "Scientists think they used their arms to hold food!",
                },
                {
                    "scene_number": 5,
                    "duration_seconds": 5,
                    "visual_description": "Happy T-Rex waving goodbye with sparkles",
                    "image_prompt": "cute 3D cartoon T-Rex waving goodbye, sparkles, bright colors, cheerful",
                    "caption": "See you next time for more dino facts!",
                },
            ],
            "call_to_action": "Which dino should we explore next? Tell us in the comments!",
            "youtube_title": "T-Rex Had TINY Arms! 🦖 Fun Dinosaur Facts for Kids",
            "youtube_description": (
                "Did you know T-Rex had really tiny arms? Learn fun dinosaur facts "
                "in this kid-friendly Short! #dinosaurs #kidsfacts #trex"
            ),
            "tags": ["dinosaurs", "T-Rex", "kids facts", "fun facts", "dinosaur facts for kids"],
        }


def create_llm_provider(cfg: dict) -> LLMProvider:
    """Factory function to create the right LLM provider."""
    provider = cfg.get("llm_provider", "openai")
    if provider == "placeholder":
        logger.info("Using PlaceholderLLMProvider (no API calls)")
        return PlaceholderLLMProvider()
    if provider == "openai":
        api_key = cfg.get("openai_api_key", os.getenv("OPENAI_API_KEY", ""))
        if not api_key:
            logger.warning("No OPENAI_API_KEY found — falling back to PlaceholderLLMProvider")
            return PlaceholderLLMProvider()
        return OpenAILLMProvider(model=cfg.get("openai_model", "gpt-4o-mini"), api_key=api_key)
    raise ValueError(f"Unknown llm_provider: {provider}")
