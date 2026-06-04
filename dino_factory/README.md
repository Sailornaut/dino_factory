# DinoFactAdventures Factory 🦖

A Python CLI tool that batch-generates kid-friendly YouTube Shorts from a single idea prompt. Given a seed like "fun dinosaur facts for kids," it produces topics, scripts, images, voiceovers, and assembled vertical videos — all ready for upload.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and edit config (optional)
cp config.example.yaml config.yaml
cp .env.example .env

# 3. Run with placeholder providers (no API keys needed)
python dino_factory.py \
  --idea "fun dinosaur facts for kids" \
  --shorts 3
```

This produces a complete batch in `output/batch_YYYYMMDD_HHMM/` with placeholder images and audio so you can test the full pipeline without spending on APIs.

## Using Real Providers

Set your OpenAI API key to enable LLM-generated scripts:

```bash
export OPENAI_API_KEY=sk-your-key-here

python dino_factory.py \
  --idea "fun dinosaur facts for kids" \
  --shorts 25 \
  --target-length 45 \
  --audience "kids ages 4-8" \
  --style "cute 3D cartoon, bright colors, friendly dinosaurs" \
  --channel-name "DinoFactAdventures"
```

Provider configuration in `config.yaml`:

| Provider       | Options              | Notes                                   |
|---------------|----------------------|-----------------------------------------|
| `llm_provider`  | `openai`, `placeholder` | Script & topic generation             |
| `image_provider`| `openai`, `placeholder` | Scene images (DALL-E 3 or colored cards)|
| `voice_provider`| `openai`, `placeholder` | Narration TTS or silent WAV            |

## Pipeline Stages

1. **Topics** — Generate N unique Short ideas from the seed
2. **Script** — Full script with hook, voiceover, scenes, CTA, and YouTube metadata
3. **Images** — One image per scene (placeholder or DALL-E)
4. **Voiceover** — Narration audio (placeholder or OpenAI TTS)
5. **Captions** — SRT subtitle file from scene captions
6. **Video** — Assembled 1080×1920 vertical video with zoom effects and title/outro cards
7. **Metadata** — YouTube upload metadata JSON + batch CSV

## Output Structure

```
output/
  batch_20240115_1430/
    config.yaml
    topics.json
    metadata.csv
    shorts/
      001_trex_tiny_arms/
        script.json
        images/
          scene_001.png
          scene_002.png
        audio/
          narration.wav
        captions.srt
        video.mp4
        metadata.json
      002_brachiosaurus_huge/
        ...
    errors/
```

## Resume Support

The pipeline automatically resumes from where it left off. If a Short already has `video.mp4`, it's skipped. To force regeneration:

```bash
python dino_factory.py --idea "..." --no-resume
```

## Configuration Reference

All CLI flags can also be set in `config.yaml`. CLI flags take priority.

See `config.example.yaml` for the full list of options.

## Adding Custom Providers

Implement the abstract interfaces in `providers/base.py`:

- `LLMProvider` — text generation
- `ImageProvider` — image generation
- `VoiceProvider` — text-to-speech
- `VideoAssembler` — video assembly

Then register your provider in the corresponding `create_*_provider()` factory function.

## Kid Safety

All generated content enforces strict child-safety rules:

- Ages 4–10 vocabulary and tone
- No scary, gory, or violent content
- No unsafe challenges or adult humor
- Cheerful, educational, parent-safe
- Blocked word filtering on all outputs

## Requirements

- Python 3.10+
- FFmpeg (for video assembly): `sudo apt install ffmpeg` or `brew install ffmpeg`
- System fonts for text overlays (DejaVu Sans recommended)
