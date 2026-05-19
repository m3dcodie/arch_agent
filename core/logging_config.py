"""
Structured logging configuration for ADAG.

Two output formats controlled by the LOG_FORMAT environment variable:

  LOG_FORMAT=text  (default) — human-readable, coloured when outputting to a TTY
  LOG_FORMAT=json            — one JSON object per line (ELK / CloudWatch / Datadog)

Log verbosity is controlled by LOG_LEVEL (default: WARNING).
Set LOG_LEVEL=INFO to surface timing, cost, and agent events.
Set LOG_LEVEL=DEBUG for full debug output.

Standard usage (call once at startup):

    from core.logging_config import configure_logging
    configure_logging()          # reads LOG_LEVEL and LOG_FORMAT from env
    configure_logging("INFO")    # explicit level, format from env
    configure_logging("DEBUG", "json")
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import TextIO

# ---------------------------------------------------------------------------
# Fields we never repeat in the structured output (they are promoted to top-
# level keys or derived from the LogRecord in a controlled way).
# ---------------------------------------------------------------------------
_RESERVED = frozenset(
    {
        "args",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class _JsonFormatter(logging.Formatter):
    """
    Emit each log record as a single-line JSON object.

    Fixed top-level keys (in order):
      timestamp  — ISO-8601 with milliseconds, UTC
      level      — DEBUG / INFO / WARNING / ERROR / CRITICAL
      logger     — dotted logger name
      event      — the formatted log message

    All ``extra={}`` fields passed to the logger call are merged at the top
    level after the fixed keys, so they are easy to filter in log-management
    systems.
    """

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
            timespec="milliseconds"
        )

        doc: dict = {
            "timestamp": ts,
            "level": record.levelname,
            "logger": record.name,
            "event": record.message,
        }

        # Merge structured extras (set via extra={} on the logger call).
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_") and key not in doc:
                doc[key] = value

        if record.exc_info:
            doc["exception"] = self.formatException(record.exc_info)

        return json.dumps(doc, default=str)


class _TextFormatter(logging.Formatter):
    """
    Compact, human-readable format that shows structured extras inline.

    Example output (coloured on TTY):
      INFO     adag.audit: agent.complete  agent=auditor  duration_ms=1523.4  violations_found=2
    """

    _COLOURS = {
        "DEBUG": "\033[36m",  # cyan
        "INFO": "\033[32m",  # green
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",  # red
        "CRITICAL": "\033[35m",  # magenta
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        use_colour = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()

        colour = (self._COLOURS.get(record.levelname, "") if use_colour else "")
        reset = self._RESET if use_colour else ""

        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _RESERVED and not k.startswith("_") and k != "levelname"
        }
        extra_str = "  ".join(f"{k}={v}" for k, v in extras.items())

        line = f"{colour}{record.levelname:<8}{reset} {record.name}: {record.message}"
        if extra_str:
            line = f"{line}  [{extra_str}]"

        if record.exc_info:
            line = f"{line}\n{self.formatException(record.exc_info)}"

        return line


def configure_logging(
    level: str | None = None,
    fmt: str | None = None,
    stream: TextIO | None = None,
) -> None:
    """
    Configure the root logger for the ADAG process.

    This should be called exactly once at process startup (CLI entry-point
    or test setup).  Subsequent calls replace the existing handlers.

    Args:
        level:  Log level string (DEBUG / INFO / WARNING / ERROR).
                Defaults to the LOG_LEVEL env var, then WARNING.
        fmt:    Output format: 'json' or 'text'.
                Defaults to the LOG_FORMAT env var, then 'text'.
        stream: Target output stream. Defaults to sys.stderr.
    """
    resolved_level = (level or os.getenv("LOG_LEVEL", "WARNING")).upper()
    resolved_fmt = (fmt or os.getenv("LOG_FORMAT", "text")).lower()

    handler = logging.StreamHandler(stream or sys.stderr)

    if resolved_fmt == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(_TextFormatter())

    root = logging.getLogger()
    # Replace all existing handlers to avoid duplicate output.
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(resolved_level)
