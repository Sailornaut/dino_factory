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
from pipeline.runner import run_pipeline
from utils.logging import setup_logging, get_logger


LENGTH_OPTIONS = [15, 30, 45, 60]
QUANTITY_OPTIONS = [1, 3, 5, 10, 25]


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
        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}

        # ── Prompt ──────────────────────────────────────────────────────────
        tk.Label(self, text="Idea / Prompt", anchor="w").grid(
            row=0, column=0, sticky="w", **pad
        )
        self._idea = tk.StringVar(value="fun dinosaur facts for kids")
        tk.Entry(self, textvariable=self._idea, width=52).grid(
            row=0, column=1, columnspan=2, sticky="ew", **pad
        )

        # ── Length ──────────────────────────────────────────────────────────
        tk.Label(self, text="Target length (sec)", anchor="w").grid(
            row=1, column=0, sticky="w", **pad
        )
        self._length = tk.IntVar(value=30)
        ttk.Combobox(
            self,
            textvariable=self._length,
            values=LENGTH_OPTIONS,
            state="readonly",
            width=10,
        ).grid(row=1, column=1, sticky="w", **pad)

        # ── Quantity ─────────────────────────────────────────────────────────
        tk.Label(self, text="Number of Shorts", anchor="w").grid(
            row=2, column=0, sticky="w", **pad
        )
        self._quantity = tk.IntVar(value=3)
        ttk.Combobox(
            self,
            textvariable=self._quantity,
            values=QUANTITY_OPTIONS,
            state="readonly",
            width=10,
        ).grid(row=2, column=1, sticky="w", **pad)

        # ── Run button ───────────────────────────────────────────────────────
        self._run_btn = tk.Button(
            self, text="Generate", width=14, command=self._on_generate
        )
        self._run_btn.grid(row=2, column=2, **pad)

        # ── Log output ───────────────────────────────────────────────────────
        tk.Label(self, text="Output", anchor="w").grid(
            row=3, column=0, sticky="w", padx=12, pady=(6, 0)
        )
        self._log = scrolledtext.ScrolledText(
            self, width=72, height=18, state="disabled", font=("Courier", 9)
        )
        self._log.grid(row=4, column=0, columnspan=3, padx=12, pady=(0, 12))

    def _on_generate(self):
        idea = self._idea.get().strip()
        if not idea:
            self._log_line("Please enter an idea before generating.\n")
            return

        self._run_btn.configure(state="disabled", text="Running…")
        self._log.configure(state="normal")
        self._log.delete("1.0", tk.END)
        self._log.configure(state="disabled")

        redirector = LogRedirector(self._log)
        thread = threading.Thread(
            target=self._run_pipeline,
            args=(idea, self._length.get(), self._quantity.get(), redirector),
            daemon=True,
        )
        thread.start()

    def _run_pipeline(self, idea: str, length: int, quantity: int, redirector):
        import logging

        handler = logging.StreamHandler(redirector)
        handler.setFormatter(logging.Formatter("%(levelname)s  %(message)s"))
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        setup_logging()

        try:

            class _Args:
                config = "config.yaml"
                no_resume = False
                dry_run = False
                output_dir = None
                audience = None
                style = None
                channel_name = None

            args = _Args()
            cfg = load_config(args.config)
            cfg["idea"] = idea
            cfg["target_length"] = length
            cfg["number_of_shorts"] = quantity
            cfg = merge_cli_into_config(cfg, args)

            run_pipeline(cfg, resume=True)
            redirector.write("\nDone! Check the output/ folder.\n")
        except Exception as exc:
            redirector.write(f"\nERROR: {exc}\n")
        finally:
            root_logger.removeHandler(handler)
            self.after(0, self._run_btn.configure, {"state": "normal", "text": "Generate"})

    def _log_line(self, msg: str):
        self._log.configure(state="normal")
        self._log.insert(tk.END, msg)
        self._log.configure(state="disabled")


if __name__ == "__main__":
    app = App()
    app.mainloop()
