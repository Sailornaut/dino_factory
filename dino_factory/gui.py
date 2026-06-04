#!/usr/bin/env python3
"""DinoFactAdventures Factory — simple GUI launcher."""

import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, scrolledtext

# Make sure imports resolve when run from this directory
sys.path.insert(0, str(Path(__file__).parent))

from config import load_config, merge_cli_into_config
from pipeline.runner import run_pipeline, PipelineCancelled
from utils.logging import setup_logging, get_logger


LENGTH_OPTIONS  = [15, 30, 45, 60]
QUANTITY_OPTIONS = [1, 3, 5, 10, 25]
VOICE_PROVIDERS  = ["elevenlabs", "openai", "placeholder"]


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


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DinoFactAdventures Factory")
        self.resizable(False, False)
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()   # when set, pipeline pauses
        self._running = False
        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        pad  = {"padx": 12, "pady": 5}

        # ── Section: Idea ────────────────────────────────────────────────────
        self._section("Idea", row=0)

        tk.Label(self, text="Prompt", anchor="w").grid(row=1, column=0, sticky="w", **pad)
        self._idea = tk.StringVar(value="fun dinosaur facts for kids")
        tk.Entry(self, textvariable=self._idea, width=56).grid(
            row=1, column=1, columnspan=3, sticky="ew", **pad
        )

        # ── Section: Batch settings ──────────────────────────────────────────
        self._section("Batch settings", row=2)

        tk.Label(self, text="Target length (sec)", anchor="w").grid(row=3, column=0, sticky="w", **pad)
        self._length = tk.IntVar(value=30)
        ttk.Combobox(self, textvariable=self._length, values=LENGTH_OPTIONS,
                     state="readonly", width=10).grid(row=3, column=1, sticky="w", **pad)

        tk.Label(self, text="Number of Shorts", anchor="w").grid(row=4, column=0, sticky="w", **pad)
        self._quantity = tk.IntVar(value=3)
        ttk.Combobox(self, textvariable=self._quantity, values=QUANTITY_OPTIONS,
                     state="readonly", width=10).grid(row=4, column=1, sticky="w", **pad)

        # ── Section: API keys ────────────────────────────────────────────────
        self._section("API keys", row=5)

        tk.Label(self, text="OpenAI key", anchor="w").grid(row=6, column=0, sticky="w", **pad)
        self._openai_key = tk.StringVar()
        tk.Entry(self, textvariable=self._openai_key, width=48, show="*").grid(
            row=6, column=1, columnspan=3, sticky="ew", **pad
        )

        tk.Label(self, text="ElevenLabs key", anchor="w").grid(row=7, column=0, sticky="w", **pad)
        self._eleven_key = tk.StringVar()
        tk.Entry(self, textvariable=self._eleven_key, width=48, show="*").grid(
            row=7, column=1, columnspan=3, sticky="ew", **pad
        )

        # ── Section: Providers ───────────────────────────────────────────────
        self._section("Providers", row=8)

        tk.Label(self, text="Voice provider", anchor="w").grid(row=9, column=0, sticky="w", **pad)
        self._voice_provider = tk.StringVar(value="elevenlabs")
        ttk.Combobox(self, textvariable=self._voice_provider, values=VOICE_PROVIDERS,
                     state="readonly", width=14).grid(row=9, column=1, sticky="w", **pad)

        tk.Label(self, text="ElevenLabs voice ID", anchor="w").grid(row=10, column=0, sticky="w", **pad)
        self._eleven_voice = tk.StringVar(value="")
        tk.Entry(self, textvariable=self._eleven_voice, width=36).grid(
            row=10, column=1, columnspan=3, sticky="ew", **pad
        )
        tk.Label(self, text="(blank = default George voice)", fg="gray", anchor="w").grid(
            row=11, column=1, columnspan=3, sticky="w", padx=12, pady=0
        )

        # ── Buttons row ─────────────────────────────────────────────────────
        btn_frame = tk.Frame(self)
        btn_frame.grid(row=12, column=0, columnspan=4, sticky="e", padx=12, pady=10)

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

        # ── Log output ───────────────────────────────────────────────────────
        self._section("Output log", row=13)
        self._log = scrolledtext.ScrolledText(
            self, width=76, height=16, state="disabled", font=("Courier", 9)
        )
        self._log.grid(row=14, column=0, columnspan=4, padx=12, pady=(0, 14))

    def _section(self, label: str, row: int):
        """Draws a subtle section header."""
        frm = tk.Frame(self, height=1, bg="#cccccc")
        frm.grid(row=row, column=0, columnspan=4, sticky="ew", padx=12, pady=(10, 0))
        tk.Label(self, text=f"  {label}  ", fg="#555555",
                 font=("TkDefaultFont", 8)).grid(row=row, column=0, sticky="w", padx=18)

    # ── Event handlers ───────────────────────────────────────────────────────

    def _on_generate(self):
        idea = self._idea.get().strip()
        if not idea:
            self._log_append("Please enter an idea before generating.\n")
            return

        # Reset events
        self._cancel_event.clear()
        self._pause_event.clear()
        self._running = True

        # Update button states
        self._run_btn.configure(state="disabled", text="Running...")
        self._pause_btn.configure(state="normal", text="Pause")
        self._cancel_btn.configure(state="normal")

        # Clear log
        self._log.configure(state="normal")
        self._log.delete("1.0", tk.END)
        self._log.configure(state="disabled")

        params = {
            "idea":            idea,
            "length":          self._length.get(),
            "quantity":        self._quantity.get(),
            "openai_key":      self._openai_key.get().strip(),
            "eleven_key":      self._eleven_key.get().strip(),
            "voice_provider":  self._voice_provider.get(),
            "eleven_voice_id": self._eleven_voice.get().strip(),
        }
        redirector = LogRedirector(self._log)
        threading.Thread(target=self._run_pipeline, args=(params, redirector),
                         daemon=True).start()

    def _on_pause(self):
        if self._pause_event.is_set():
            # Resume
            self._pause_event.clear()
            self._pause_btn.configure(text="Pause")
            self._log_append("[RESUMED] Pipeline continuing...\n")
        else:
            # Pause
            self._pause_event.set()
            self._pause_btn.configure(text="Resume")
            self._log_append("[PAUSED] Pipeline will pause before the next stage...\n")

    def _on_cancel(self):
        self._cancel_event.set()
        self._pause_event.clear()  # unblock if paused so cancel can take effect
        self._cancel_btn.configure(state="disabled")
        self._pause_btn.configure(state="disabled")
        self._log_append("[CANCELLING] Pipeline will stop after current step...\n")

    def _pipeline_finished(self):
        """Reset UI after pipeline completes."""
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
            cfg["target_length"]      = params["length"]
            cfg["number_of_shorts"]   = params["quantity"]
            cfg["voice_provider"]     = params["voice_provider"]

            if params["openai_key"]:
                cfg["openai_api_key"] = params["openai_key"]
            if params["eleven_key"]:
                cfg["elevenlabs_api_key"] = params["eleven_key"]
            if params["eleven_voice_id"]:
                cfg["elevenlabs_voice_id"] = params["eleven_voice_id"]

            # Always use openai for LLM and images
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
