#!/usr/bin/env python3
"""DinoFactAdventures Factory — GUI launcher."""

import json
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, scrolledtext

# Make sure imports resolve when run from this directory
sys.path.insert(0, str(Path(__file__).parent))

from config import load_config, merge_cli_into_config
from pipeline.runner import run_pipeline, PipelineCancelled
from presets import ALL_PRESETS, get_preset
from utils.logging import setup_logging, get_logger


LENGTH_OPTIONS_SHORT  = [15, 30, 45, 60]
LENGTH_OPTIONS_LONG   = [180, 300, 360, 480, 600, 900]
QUANTITY_OPTIONS      = [1, 3, 5, 10, 25]
VOICE_PROVIDERS       = ["elevenlabs", "openai", "placeholder"]

# Genre names for the combobox
GENRE_NAMES = list(ALL_PRESETS.keys())
GENRE_LABELS = [p.label for p in ALL_PRESETS.values()]

# Settings file — stored next to the script (inside the project)
SETTINGS_PATH = Path(__file__).parent / "user_settings.json"


class LogRedirector:
    """Forwards writes to a tkinter Text widget (thread-safe)."""

    def __init__(self, widget: scrolledtext.ScrolledText):
        self._widget = widget

    def write(self, msg: str):
        self._widget.after(0, self._append, msg)

    def _append(self, msg: str):
        self._widget.configure(state="normal")
        self._widget.insert(tk.END, msg)
        self._widget.see(tk.END)
        self._widget.configure(state="disabled")

    def flush(self):
        pass


# ── Character parsing helpers ────────────────────────────────────────────

def parse_characters(raw_text: str) -> list[dict]:
    """Parse multi-line character definitions.

    Each line: Name | personality | appearance
    Returns list of {"name": ..., "personality": ..., "appearance": ...}
    """
    characters = []
    for line in raw_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        char = {
            "name": parts[0] if len(parts) >= 1 else "",
            "personality": parts[1] if len(parts) >= 2 else "",
            "appearance": parts[2] if len(parts) >= 3 else "",
        }
        if char["name"]:
            characters.append(char)
    return characters


def format_characters_for_prompt(characters: list[dict]) -> str:
    """Build a detailed character block for LLM prompts."""
    if not characters:
        return ""
    lines = []
    for c in characters:
        parts = [f"- {c['name']}"]
        if c.get("personality"):
            parts.append(f"  Personality: {c['personality']}")
        if c.get("appearance"):
            parts.append(f"  Appearance: {c['appearance']}")
        lines.append("\n".join(parts))
    return "\n".join(lines)


def format_characters_for_image(characters: list[dict]) -> str:
    """Build a visual-only character reference for image prompts."""
    if not characters:
        return ""
    parts = []
    for c in characters:
        desc = c["name"]
        if c.get("appearance"):
            desc += f" ({c['appearance']})"
        parts.append(desc)
    return "; ".join(parts)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video Factory")
        self.resizable(False, False)
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()
        self._running = False
        self._skip_genre_defaults = False  # flag to avoid overwriting loaded settings
        self._build_ui()
        self._load_settings()
        # Initialize genre-dependent UI (show/hide character field)
        self._on_genre_change(update_defaults=False)
        # Save settings on window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self):
        pad = {"padx": 12, "pady": 5}

        # ── Genre selector ───────────────────────────────────────────────
        self._section("Genre", row=0)

        tk.Label(self, text="Content type", anchor="w").grid(row=1, column=0, sticky="w", **pad)
        self._genre_var = tk.StringVar(value=GENRE_LABELS[0])
        genre_cb = ttk.Combobox(self, textvariable=self._genre_var, values=GENRE_LABELS,
                                state="readonly", width=30)
        genre_cb.grid(row=1, column=1, columnspan=2, sticky="w", **pad)
        genre_cb.bind("<<ComboboxSelected>>", lambda e: self._on_genre_change(update_defaults=True))

        self._genre_desc = tk.Label(self, text="", fg="#666666", anchor="w",
                                    font=("TkDefaultFont", 8), wraplength=400)
        self._genre_desc.grid(row=2, column=1, columnspan=2, sticky="w", padx=12, pady=0)

        # ── Idea ─────────────────────────────────────────────────────────
        self._section("Idea", row=3)

        tk.Label(self, text="Prompt", anchor="w").grid(row=4, column=0, sticky="w", **pad)
        self._idea = tk.StringVar(value="fun dinosaur facts for kids")
        tk.Entry(self, textvariable=self._idea, width=56).grid(
            row=4, column=1, columnspan=3, sticky="ew", **pad
        )

        # ── Characters (bedtime stories) ─────────────────────────────────
        self._char_label = tk.Label(self, text="Characters", anchor="nw")
        self._char_label.grid(row=5, column=0, sticky="nw", **pad)

        # Multi-line Text widget for structured character input
        self._char_frame = tk.Frame(self)
        self._char_frame.grid(row=5, column=1, columnspan=3, sticky="ew", **pad)

        self._char_text = tk.Text(self._char_frame, width=52, height=4,
                                  font=("Courier", 9), wrap="word")
        self._char_text.pack(fill="x")

        self._char_hint = tk.Label(
            self, fg="gray", anchor="w", wraplength=450,
            text="One character per line:  Name | personality | appearance\n"
                 "e.g.  Luna | curious, gentle, loves stars | small white bunny with a blue scarf",
            justify="left",
        )
        self._char_hint.grid(row=6, column=1, columnspan=3, sticky="w", padx=12, pady=0)

        # ── Batch settings ───────────────────────────────────────────────
        self._section("Batch settings", row=7)

        tk.Label(self, text="Target length (sec)", anchor="w").grid(row=8, column=0, sticky="w", **pad)
        self._length = tk.IntVar(value=30)
        self._length_cb = ttk.Combobox(self, textvariable=self._length,
                                       values=LENGTH_OPTIONS_SHORT,
                                       state="readonly", width=10)
        self._length_cb.grid(row=8, column=1, sticky="w", **pad)

        tk.Label(self, text="Number of videos", anchor="w").grid(row=9, column=0, sticky="w", **pad)
        self._quantity = tk.IntVar(value=3)
        ttk.Combobox(self, textvariable=self._quantity, values=QUANTITY_OPTIONS,
                     state="readonly", width=10).grid(row=9, column=1, sticky="w", **pad)

        # ── API keys ─────────────────────────────────────────────────────
        self._section("API keys", row=10)

        tk.Label(self, text="OpenAI key", anchor="w").grid(row=11, column=0, sticky="w", **pad)
        self._openai_key = tk.StringVar()
        tk.Entry(self, textvariable=self._openai_key, width=48, show="*").grid(
            row=11, column=1, columnspan=3, sticky="ew", **pad
        )

        tk.Label(self, text="ElevenLabs key", anchor="w").grid(row=12, column=0, sticky="w", **pad)
        self._eleven_key = tk.StringVar()
        tk.Entry(self, textvariable=self._eleven_key, width=48, show="*").grid(
            row=12, column=1, columnspan=3, sticky="ew", **pad
        )

        # ── Providers ────────────────────────────────────────────────────
        self._section("Providers", row=13)

        tk.Label(self, text="Voice provider", anchor="w").grid(row=14, column=0, sticky="w", **pad)
        self._voice_provider = tk.StringVar(value="elevenlabs")
        ttk.Combobox(self, textvariable=self._voice_provider, values=VOICE_PROVIDERS,
                     state="readonly", width=14).grid(row=14, column=1, sticky="w", **pad)

        tk.Label(self, text="ElevenLabs voice ID", anchor="w").grid(row=15, column=0, sticky="w", **pad)
        self._eleven_voice = tk.StringVar(value="")
        tk.Entry(self, textvariable=self._eleven_voice, width=36).grid(
            row=15, column=1, columnspan=3, sticky="ew", **pad
        )
        self._voice_hint = tk.Label(self, text="(blank = preset default)", fg="gray", anchor="w")
        self._voice_hint.grid(row=16, column=1, columnspan=3, sticky="w", padx=12, pady=0)

        # ── Buttons ──────────────────────────────────────────────────────
        btn_frame = tk.Frame(self)
        btn_frame.grid(row=17, column=0, columnspan=4, sticky="e", padx=12, pady=10)

        self._run_btn = tk.Button(btn_frame, text="Generate", width=14,
                                  command=self._on_generate,
                                  font=("TkDefaultFont", 10, "bold"))
        self._run_btn.pack(side="right", padx=(4, 0))

        self._cancel_btn = tk.Button(btn_frame, text="Cancel", width=10,
                                     command=self._on_cancel, state="disabled",
                                     fg="#cc0000")
        self._cancel_btn.pack(side="right", padx=(4, 0))

        self._pause_btn = tk.Button(btn_frame, text="Pause", width=10,
                                    command=self._on_pause, state="disabled")
        self._pause_btn.pack(side="right", padx=(4, 0))

        # ── Log output ──────────────────────────────────────────────────
        self._section("Output log", row=18)
        self._log = scrolledtext.ScrolledText(
            self, width=76, height=16, state="disabled", font=("Courier", 9)
        )
        self._log.grid(row=19, column=0, columnspan=4, padx=12, pady=(0, 14))

    def _section(self, label: str, row: int):
        frm = tk.Frame(self, height=1, bg="#cccccc")
        frm.grid(row=row, column=0, columnspan=4, sticky="ew", padx=12, pady=(10, 0))
        tk.Label(self, text=f"  {label}  ", fg="#555555",
                 font=("TkDefaultFont", 8)).grid(row=row, column=0, sticky="w", padx=18)

    # ── Settings persistence ─────────────────────────────────────────────

    def _save_settings(self):
        """Save all GUI field values to a JSON file."""
        settings = {
            "genre":          self._genre_var.get(),
            "idea":           self._idea.get(),
            "characters":     self._char_text.get("1.0", "end-1c"),
            "length":         self._length.get(),
            "quantity":       self._quantity.get(),
            "openai_key":     self._openai_key.get(),
            "eleven_key":     self._eleven_key.get(),
            "voice_provider": self._voice_provider.get(),
            "eleven_voice":   self._eleven_voice.get(),
        }
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
        except Exception:
            pass  # non-critical — don't crash if save fails

    def _load_settings(self):
        """Restore GUI fields from saved settings file."""
        if not SETTINGS_PATH.exists():
            return
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                s = json.load(f)
        except Exception:
            return

        # Restore genre first (controls which fields are visible)
        if s.get("genre") and s["genre"] in GENRE_LABELS:
            self._genre_var.set(s["genre"])

        if s.get("idea"):
            self._idea.set(s["idea"])

        # Restore characters text
        if s.get("characters"):
            self._char_text.delete("1.0", tk.END)
            self._char_text.insert("1.0", s["characters"])

        if s.get("length"):
            try:
                self._length.set(int(s["length"]))
            except (ValueError, tk.TclError):
                pass

        if s.get("quantity"):
            try:
                self._quantity.set(int(s["quantity"]))
            except (ValueError, tk.TclError):
                pass

        if s.get("openai_key"):
            self._openai_key.set(s["openai_key"])
        if s.get("eleven_key"):
            self._eleven_key.set(s["eleven_key"])
        if s.get("voice_provider"):
            self._voice_provider.set(s["voice_provider"])
        if s.get("eleven_voice"):
            self._eleven_voice.set(s["eleven_voice"])

    def _on_close(self):
        """Save settings and close the app."""
        self._save_settings()
        self.destroy()

    # ── Genre change handler ─────────────────────────────────────────────

    def _on_genre_change(self, update_defaults: bool = True):
        """Update UI when genre selection changes.

        update_defaults: if True, overwrite idea/length with preset defaults.
        Set to False when restoring saved settings so we don't clobber them.
        """
        label = self._genre_var.get()
        idx = GENRE_LABELS.index(label) if label in GENRE_LABELS else 0
        genre_name = GENRE_NAMES[idx]
        preset = get_preset(genre_name)

        # Update description
        self._genre_desc.configure(text=preset.description)

        if update_defaults:
            # Update default idea
            self._idea.set(preset.default_idea)

            # Update length options
            if preset.target_length > 120:
                self._length_cb.configure(values=LENGTH_OPTIONS_LONG)
                self._length.set(preset.target_length)
            else:
                self._length_cb.configure(values=LENGTH_OPTIONS_SHORT)
                self._length.set(preset.target_length)
        else:
            # Still update the combobox value list so the current value is valid
            if preset.target_length > 120:
                self._length_cb.configure(values=LENGTH_OPTIONS_LONG)
            else:
                self._length_cb.configure(values=LENGTH_OPTIONS_SHORT)

        # Show/hide character field (bedtime stories only)
        show_chars = "character_names" in preset.extra_fields
        if show_chars:
            self._char_label.grid()
            self._char_frame.grid()
            self._char_hint.grid()
        else:
            self._char_label.grid_remove()
            self._char_frame.grid_remove()
            self._char_hint.grid_remove()

        # Update voice hint with preset default
        voice_name = preset.narrator_voice_elevenlabs
        self._voice_hint.configure(text=f"(blank = preset default: {voice_name[:12]}...)")

    def _get_current_genre_name(self) -> str:
        label = self._genre_var.get()
        idx = GENRE_LABELS.index(label) if label in GENRE_LABELS else 0
        return GENRE_NAMES[idx]

    # ── Event handlers ───────────────────────────────────────────────────

    def _on_generate(self):
        idea = self._idea.get().strip()
        if not idea:
            self._log_append("Please enter an idea before generating.\n")
            return

        # Save settings before each run
        self._save_settings()

        self._cancel_event.clear()
        self._pause_event.clear()
        self._running = True
        self._run_btn.configure(state="disabled", text="Running...")
        self._pause_btn.configure(state="normal", text="Pause")
        self._cancel_btn.configure(state="normal")

        self._log.configure(state="normal")
        self._log.delete("1.0", tk.END)
        self._log.configure(state="disabled")

        genre_name = self._get_current_genre_name()
        preset = get_preset(genre_name)

        # Parse structured character definitions
        raw_chars = self._char_text.get("1.0", "end-1c").strip()
        characters = parse_characters(raw_chars) if raw_chars else []

        params = {
            "idea":            idea,
            "genre":           genre_name,
            "length":          self._length.get(),
            "quantity":        self._quantity.get(),
            "openai_key":      self._openai_key.get().strip(),
            "eleven_key":      self._eleven_key.get().strip(),
            "voice_provider":  self._voice_provider.get(),
            "eleven_voice_id": self._eleven_voice.get().strip(),
            "characters":      characters,    # list of dicts
            "characters_raw":  raw_chars,     # original text for config
        }
        redirector = LogRedirector(self._log)
        threading.Thread(target=self._run_pipeline, args=(params, redirector),
                         daemon=True).start()

    def _on_pause(self):
        if self._pause_event.is_set():
            self._pause_event.clear()
            self._pause_btn.configure(text="Pause")
            self._log_append("[RESUMED] Pipeline continuing...\n")
        else:
            self._pause_event.set()
            self._pause_btn.configure(text="Resume")
            self._log_append("[PAUSED] Pipeline will pause before the next stage...\n")

    def _on_cancel(self):
        self._cancel_event.set()
        self._pause_event.clear()
        self._cancel_btn.configure(state="disabled")
        self._pause_btn.configure(state="disabled")
        self._log_append("[CANCELLING] Pipeline will stop after current step...\n")

    def _pipeline_finished(self):
        self._running = False
        self._run_btn.configure(state="normal", text="Generate")
        self._pause_btn.configure(state="disabled", text="Pause")
        self._cancel_btn.configure(state="disabled")

    def _run_pipeline(self, params: dict, redirector):
        import logging

        handler = logging.StreamHandler(redirector)
        handler.setFormatter(logging.Formatter("%(levelname)s  %(message)s"))
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        setup_logging()

        try:
            genre_name = params["genre"]
            preset = get_preset(genre_name)

            class _Args:
                config     = "config.yaml"
                no_resume  = False
                dry_run    = False
                output_dir = None
                audience   = None
                style      = None
                channel_name = None

            cfg = load_config(_Args.config)
            cfg["idea"]               = params["idea"]
            cfg["genre"]              = genre_name
            cfg["target_length"]      = params["length"]
            cfg["target_length_seconds"] = params["length"]
            cfg["number_of_shorts"]   = params["quantity"]
            cfg["voice_provider"]     = params["voice_provider"]
            cfg["audience"]           = preset.audience
            cfg["visual_style"]       = preset.visual_style
            cfg["scenes_per_video"]   = preset.scenes_per_video

            # Structured character definitions for bedtime stories
            if params["characters"]:
                cfg["characters"] = params["characters"]
                cfg["characters_prompt"] = format_characters_for_prompt(params["characters"])
                cfg["characters_visual"] = format_characters_for_image(params["characters"])

            if params["openai_key"]:
                cfg["openai_api_key"] = params["openai_key"]
            if params["eleven_key"]:
                cfg["elevenlabs_api_key"] = params["eleven_key"]
            if params["eleven_voice_id"]:
                cfg["elevenlabs_voice_id"] = params["eleven_voice_id"]
            else:
                # Use the preset's recommended voice
                cfg["elevenlabs_voice_id"] = preset.narrator_voice_elevenlabs
                cfg["narrator_voice"] = preset.narrator_voice_openai

            cfg["llm_provider"]   = "openai"
            cfg["image_provider"] = "openai"

            cfg = merge_cli_into_config(cfg, _Args())
            run_pipeline(cfg, resume=True, cancel_event=self._cancel_event,
                         pause_event=self._pause_event)
            redirector.write("\nDone! Check the output/ folder.\n")
        except PipelineCancelled:
            redirector.write("\nPipeline cancelled. Partial output saved.\n")
        except Exception as exc:
            redirector.write(f"\nERROR: {exc}\n")
        finally:
            root_logger.removeHandler(handler)
            self.after(0, self._pipeline_finished)

    def _log_append(self, msg: str):
        self._log.configure(state="normal")
        self._log.insert(tk.END, msg)
        self._log.see(tk.END)
        self._log.configure(state="disabled")


if __name__ == "__main__":
    app = App()
    app.mainloop()
