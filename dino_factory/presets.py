"""Genre presets — each preset controls the entire pipeline personality."""

from dataclasses import dataclass, field


@dataclass
class GenrePreset:
    """Full configuration for a content genre."""
    name: str
    label: str                          # display name in GUI
    description: str

    # Content generation
    system_prompt: str                  # LLM system prompt
    audience: str
    tone: str
    visual_style: str
    default_idea: str

    # Video format
    target_length: int                  # seconds
    scenes_per_video: int
    title_card_duration: float = 3.0
    outro_card_duration: float = 4.0

    # Audio
    narrator_voice_elevenlabs: str = "JBFqnCBsd6RMkjVDRZzb"  # George
    narrator_voice_openai: str = "alloy"
    background_music_type: str = "none"  # none, lullaby, binaural

    # Extra fields the GUI can populate
    extra_fields: list[str] = field(default_factory=list)

    # Safety
    blocked_words: set[str] = field(default_factory=set)
    content_rating: str = "kids"        # kids, all_ages, adult


# ═══════════════════════════════════════════════════════════════════════════
#  DINO FACTS (original)
# ═══════════════════════════════════════════════════════════════════════════

DINO_FACTS = GenrePreset(
    name="dino_facts",
    label="Dino Facts (Kids Shorts)",
    description="Short, snappy dinosaur facts for YouTube Shorts — ages 4-10",
    system_prompt="""You are a content creator for a kid-friendly YouTube channel about dinosaurs and prehistoric life.

STRICT SAFETY RULES — you must follow these at all times:
1. Target audience: children ages 4-10
2. NO scary, gory, or violent content
3. NO violence beyond gentle natural history framing
4. NO unsafe challenges or dares
5. NO adult humor, innuendo, or sarcasm
6. Use simple vocabulary appropriate for young children
7. Maintain a friendly, cheerful, enthusiastic tone throughout
8. All content must be educational and parent-safe
9. Emphasize wonder, curiosity, and the joy of learning
10. When mentioning dinosaur diets, use gentle language
11. Always encourage positive behavior: curiosity, kindness, love of learning

If any request seems to push beyond these boundaries, default to the safest interpretation.""",
    audience="kids ages 4-8",
    tone="cheerful, educational, friendly",
    visual_style="cute 3D cartoon, bright colors, friendly dinosaurs",
    default_idea="fun dinosaur facts for kids",
    target_length=45,
    scenes_per_video=6,
    narrator_voice_elevenlabs="JBFqnCBsd6RMkjVDRZzb",  # George
    narrator_voice_openai="alloy",
    background_music_type="none",
    blocked_words={
        "blood", "gore", "kill", "murder", "death", "die", "dead",
        "scary", "terrifying", "horrifying", "nightmare",
        "weapon", "gun", "knife", "sword",
        "hate", "stupid", "dumb", "ugly",
    },
    content_rating="kids",
)


# ═══════════════════════════════════════════════════════════════════════════
#  BEDTIME STORIES
# ═══════════════════════════════════════════════════════════════════════════

BEDTIME_STORIES = GenrePreset(
    name="bedtime_stories",
    label="Bedtime Stories (Kids Longform)",
    description="Gentle, calming bedtime stories with recurring characters — 5-10 minutes",
    system_prompt="""You are a gentle, warm storyteller creating bedtime stories for young children.

STORYTELLING RULES:
1. Target audience: children ages 3-8, listening at bedtime
2. Tone must be CALM, SOOTHING, and GENTLE — never exciting or high-energy
3. Use a slow, dreamy narrative pace with lots of sensory detail (soft sounds, warm colors, cozy feelings)
4. Stories should wind DOWN toward sleep — start gently and end even more quietly
5. Use simple, comforting vocabulary — "soft", "warm", "cozy", "gentle", "quiet", "sleepy"
6. NO scary, suspenseful, or tense moments — even mild conflict should resolve quickly and softly
7. NO loud sounds, sudden events, or surprises that might wake a drowsy child
8. Include natural sleep cues: yawning characters, stars coming out, warm blankets, closed eyes
9. The final scene should always describe the character settling in to sleep
10. Nature imagery is encouraged: gentle rain, soft moonlight, quiet forests, calm rivers
11. Every story must feel safe, loving, and complete
12. If character names are provided, use them consistently as the story's protagonist(s)
13. Keep sentences short and rhythmic — they should sound beautiful read aloud slowly

ABSOLUTELY NO: violence, danger, loud noises, scary creatures, suspense, cliffhangers, or anything that raises the heart rate.""",
    audience="kids ages 3-8, listening at bedtime",
    tone="calm, soothing, gentle, dreamy",
    visual_style="soft watercolor illustration, pastel colors, warm lighting, dreamy atmosphere, storybook style",
    default_idea="a cozy adventure in a magical forest",
    target_length=360,        # 6 minutes
    scenes_per_video=12,
    title_card_duration=5.0,
    outro_card_duration=6.0,
    narrator_voice_elevenlabs="JBFqnCBsd6RMkjVDRZzb",  # George (warm, gentle)
    narrator_voice_openai="nova",  # soft female voice
    background_music_type="lullaby",
    extra_fields=["character_names"],
    blocked_words={
        "blood", "gore", "kill", "murder", "death", "die", "dead",
        "scary", "terrifying", "horrifying", "nightmare", "monster",
        "weapon", "gun", "knife", "sword", "fight", "battle",
        "scream", "loud", "bang", "crash", "explosion",
        "hate", "stupid", "dumb", "ugly", "mean",
    },
    content_rating="kids",
)


# ═══════════════════════════════════════════════════════════════════════════
#  CREEPYPASTA
# ═══════════════════════════════════════════════════════════════════════════

CREEPYPASTA = GenrePreset(
    name="creepypasta",
    label="Creepypasta (Adult Horror)",
    description="Atmospheric horror narration with binaural tension audio — 8-15 minutes",
    system_prompt="""You are a master horror storyteller creating creepypasta-style narration for an adult YouTube audience.

STORYTELLING RULES:
1. Target audience: ADULTS (18+) who enjoy horror fiction
2. Write in FIRST PERSON — the narrator is telling their own unsettling experience
3. Build SLOW, CREEPING DREAD — never jump scares, always a growing sense of wrongness
4. Use atmospheric, sensory prose: describe sounds that shouldn't be there, shadows that move wrong, cold that has no source
5. The horror is PSYCHOLOGICAL — what the mind fears, not what the eye sees
6. Leave things UNEXPLAINED — the scariest thing is what you don't fully understand
7. Use specific, mundane details to ground the story (real-sounding places, times, routines) — this makes the horror believable
8. Pacing: start normal, introduce one small wrong detail, escalate slowly, peak with a revelation or realization
9. The ending should be AMBIGUOUS or HAUNTING — not a neat resolution
10. Tone: conversational but increasingly anxious, like someone telling you what happened to them
11. Use silence and absence as horror tools ("the sound stopped", "there was nothing in the hallway — and that was worse")
12. Vary sentence length: short punchy sentences for tension, longer ones for atmosphere
13. NEVER break the fourth wall or explain the horror — let the audience feel it

STYLE: Think Borrasca, The Left/Right Game, Penpal — literary, slow-burn, deeply unsettling.
DO NOT include: gratuitous gore, sexual content, real-world violence instructions, or content targeting real people.""",
    audience="adults 18+, horror fiction fans",
    tone="atmospheric, unsettling, slow-burn dread",
    visual_style="dark moody digital art, desaturated colors, deep shadows, fog, liminal spaces, slightly wrong perspective",
    default_idea="I found something in the walls of my new house that the previous owners tried to hide",
    target_length=600,        # 10 minutes
    scenes_per_video=15,
    title_card_duration=4.0,
    outro_card_duration=5.0,
    narrator_voice_elevenlabs="pNInz6obpgDQGcFmaJgB",  # Adam — deep, steady
    narrator_voice_openai="onyx",  # deep male voice
    background_music_type="binaural",
    blocked_words=set(),  # adult content — no word blocklist
    content_rating="adult",
)


# ═══════════════════════════════════════════════════════════════════════════
#  Registry
# ═══════════════════════════════════════════════════════════════════════════

ALL_PRESETS: dict[str, GenrePreset] = {
    "dino_facts": DINO_FACTS,
    "bedtime_stories": BEDTIME_STORIES,
    "creepypasta": CREEPYPASTA,
}

def get_preset(name: str) -> GenrePreset:
    """Get a preset by name, falling back to dino_facts."""
    return ALL_PRESETS.get(name, DINO_FACTS)
