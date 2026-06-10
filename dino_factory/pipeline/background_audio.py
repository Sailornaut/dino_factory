"""Generate background audio tracks: lullaby tones and binaural beats."""

import math
import struct
import wave
from pathlib import Path

from utils.logging import get_logger

logger = get_logger(__name__)

SAMPLE_RATE = 44100


def generate_background_audio(audio_type: str, duration: float, output_path: Path) -> Path | None:
    """Generate a background audio track.

    audio_type: "lullaby", "binaural", or "none"
    duration: length in seconds
    output_path: where to save the .wav
    """
    if audio_type == "none" or not audio_type:
        return None

    if output_path.exists():
        logger.debug("Background audio cached: %s", output_path)
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if audio_type == "lullaby":
        _generate_lullaby(duration, output_path)
    elif audio_type == "binaural":
        _generate_binaural(duration, output_path)
    else:
        logger.warning("Unknown background audio type: %s", audio_type)
        return None

    logger.info("Background audio generated: %s (%.0fs)", output_path, duration)
    return output_path


def _generate_lullaby(duration: float, output_path: Path):
    """Generate a gentle, dreamy lullaby pad using soft sine waves.

    Creates a warm, evolving chord that slowly shifts — like a music box
    heard from another room. Very quiet, meant to sit underneath narration.
    """
    num_samples = int(SAMPLE_RATE * duration)
    amplitude = 1200  # very quiet — narration sits on top

    # Gentle chord: C major 7th with octave doubling (dreamy, warm)
    # Frequencies slowly drift to create a "breathing" feel
    base_freqs = [130.81, 164.81, 196.00, 246.94]  # C3, E3, G3, B3

    data = bytearray()
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        sample = 0.0

        for j, freq in enumerate(base_freqs):
            # Each note gently wobbles in pitch (vibrato) at different rates
            vibrato = 1.0 + 0.003 * math.sin(2 * math.pi * (0.15 + j * 0.05) * t)
            f = freq * vibrato

            # Volume swells gently like breathing
            swell = 0.6 + 0.4 * math.sin(2 * math.pi * (0.08 + j * 0.02) * t)

            sample += swell * math.sin(2 * math.pi * f * t)

        # Soft fade in / fade out (5 seconds each)
        fade_in = min(1.0, t / 5.0)
        fade_out = min(1.0, (duration - t) / 5.0)
        envelope = fade_in * fade_out

        val = int(amplitude * envelope * sample / len(base_freqs))
        val = max(-32767, min(32767, val))

        # Stereo: same on both channels (warm, centered)
        data += struct.pack("<hh", val, val)

    with wave.open(str(output_path), "w") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(bytes(data))


def _generate_binaural(duration: float, output_path: Path):
    """Generate binaural beats that create subtle unease and tension.

    Uses a low-frequency binaural beat (4-7 Hz theta range) combined with
    a sub-bass drone and occasional dissonant undertones. The beat frequency
    slowly shifts, creating a sense of something being slightly wrong.

    Left ear gets one frequency, right ear gets a slightly different one —
    the brain perceives the difference as a pulsing tone, which at theta
    frequencies creates an uneasy, trance-like state.
    """
    num_samples = int(SAMPLE_RATE * duration)

    # Carrier frequency: low drone
    carrier = 85.0  # Hz — just above perception threshold, chest-resonant

    # Binaural beat: difference between L/R channels
    # Starts at 7Hz (anxiety-adjacent theta) and slowly drops to 4Hz (deeper unease)
    beat_start = 7.0
    beat_end = 4.0

    # Dissonant undertone: tritone interval, very quiet
    dissonant_freq = carrier * math.sqrt(2)  # tritone ≈ 120 Hz

    amplitude_main = 2800    # moderate — present but not overwhelming
    amplitude_dissonant = 600  # barely there, subliminal tension

    data = bytearray()
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        progress = t / duration

        # Beat frequency slides down over the track
        beat_freq = beat_start + (beat_end - beat_start) * progress
        half_beat = beat_freq / 2.0

        # Left channel: carrier - half_beat
        freq_l = carrier - half_beat
        # Right channel: carrier + half_beat
        freq_r = carrier + half_beat

        # Main drone
        left = math.sin(2 * math.pi * freq_l * t)
        right = math.sin(2 * math.pi * freq_r * t)

        # Dissonant layer — fades in during middle third, creating peak tension
        dissonant_envelope = math.sin(math.pi * progress) ** 2  # peaks at center
        dissonant_l = dissonant_envelope * math.sin(2 * math.pi * dissonant_freq * t)
        dissonant_r = dissonant_envelope * math.sin(2 * math.pi * (dissonant_freq + 1.5) * t)

        # Occasional "presence" — a very quiet high tone that fades in/out
        # like something watching, then looking away
        presence_cycle = math.sin(2 * math.pi * 0.02 * t)  # 50-second cycle
        presence = max(0, presence_cycle) ** 3  # only present half the time, sharply
        presence_tone = presence * 0.3 * math.sin(2 * math.pi * 3520 * t)  # A7 — piercing but quiet

        # Combine
        val_l = int(amplitude_main * left + amplitude_dissonant * dissonant_l
                     + 400 * presence_tone)
        val_r = int(amplitude_main * right + amplitude_dissonant * dissonant_r
                     + 400 * presence_tone)

        # Fade in/out (8 seconds each)
        fade_in = min(1.0, t / 8.0)
        fade_out = min(1.0, (duration - t) / 8.0)
        envelope = fade_in * fade_out

        val_l = max(-32767, min(32767, int(val_l * envelope)))
        val_r = max(-32767, min(32767, int(val_r * envelope)))

        data += struct.pack("<hh", val_l, val_r)

    with wave.open(str(output_path), "w") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(bytes(data))
