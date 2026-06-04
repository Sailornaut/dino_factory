"""Structured logging setup."""

import codecs
import io
import logging
import sys

_configured = False


class _SafeStreamHandler(logging.StreamHandler):
    """StreamHandler that replaces unencodable characters instead of crashing.

    On Windows the default stdout codec is 'charmap' which cannot encode emoji
    that appear in generated content.  This wrapper encodes each record to
    UTF-8 with errors='replace' before writing, so the pipeline never crashes
    on a stray dinosaur emoji.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            stream = self.stream
            # Write safely regardless of the stream's native encoding
            if hasattr(stream, "buffer"):
                stream.buffer.write((msg + self.terminator).encode("utf-8", errors="replace"))
                stream.buffer.flush()
            else:
                stream.write(msg + self.terminator)
                stream.flush()
        except Exception:
            self.handleError(record)


def setup_logging(level: int = logging.INFO):
    """Configure structured logging for the application."""
    global _configured
    if _configured:
        return
    _configured = True

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-7s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    handler = _SafeStreamHandler(sys.stdout)
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
