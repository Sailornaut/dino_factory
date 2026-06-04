"""Structured logging setup."""

import logging
import sys

_configured = False


def setup_logging(level: int = logging.INFO):
    """Configure structured logging for the application."""
    global _configured
    if _configured:
        return
    _configured = True

    # Reconfigure stdout to UTF-8 once, so emoji in log messages don't crash
    # on Windows where the default console codec is charmap.
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-7s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    # Force UTF-8 on Windows where the default console codec (charmap) rejects emoji
    stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1) \
        if hasattr(sys.stdout, "fileno") else sys.stdout
    handler = logging.StreamHandler(stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("moviepy").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(name)
