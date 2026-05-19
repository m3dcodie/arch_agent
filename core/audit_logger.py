"""
Structured audit event logging for ADAG.

Provides trace-context propagation and timing spans for every significant
operation in an audit run: per-file iterations, per-agent steps, and LLM
calls.  All emitted events carry the same trace_id so they can be correlated
in any log-management system.

Design notes
------------
* Uses ``contextvars.ContextVar`` so trace/span IDs are safe across threads
  and async tasks — no global mutable state.
* Zero external dependencies — stdlib only.
* Events follow OpenTelemetry semantic-convention naming (dot-separated):
    audit.run.start / audit.run.complete
    file.scan.start  / file.scan.complete  / file.scan.error
    agent.start      / agent.complete      / agent.error
    llm.invoke

Quick-start
-----------
    from core.audit_logger import audit_trace, AuditSpan, audit_event

    with audit_trace() as trace_id:                   # sets trace_id for scope
        with AuditSpan("file.scan", file="main.tf") as span:
            ...do work...
            span.set(violations_found=3, status="FAILED")
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Generator

logger = logging.getLogger("adag.audit")

# ---------------------------------------------------------------------------
# Trace / span context — thread-safe via ContextVar
# ---------------------------------------------------------------------------

_trace_id_var: ContextVar[str] = ContextVar("adag_trace_id", default="")
_span_id_var: ContextVar[str] = ContextVar("adag_span_id", default="")


def get_trace_id() -> str:
    """Return the active trace ID, or an empty string when outside a trace."""
    return _trace_id_var.get()


def get_span_id() -> str:
    """Return the active span ID, or an empty string when outside a span."""
    return _span_id_var.get()


@contextmanager
def audit_trace(trace_id: str | None = None) -> Generator[str, None, None]:
    """
    Context manager that binds a trace ID for all log events within its scope.

    Args:
        trace_id: Explicit ID string.  Auto-generates a 12-hex-char UUID when
                  not provided.

    Yields:
        The active trace_id string.

    Example::

        with audit_trace() as tid:
            # all audit_event() calls here carry trace_id=tid
            ...
    """
    tid = trace_id or uuid.uuid4().hex[:12]
    token = _trace_id_var.set(tid)
    try:
        yield tid
    finally:
        _trace_id_var.reset(token)


# ---------------------------------------------------------------------------
# Structured event emitter
# ---------------------------------------------------------------------------


def audit_event(
    event: str,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    """
    Emit a structured log event with the active trace/span context attached.

    The event is emitted at *level* through the ``adag.audit`` logger.
    ``LOG_LEVEL=INFO`` (or lower) must be set for INFO events to be visible.

    Args:
        event:   Short dot-separated event name, e.g. ``'agent.complete'``.
        level:   Python logging level integer.  Default: ``logging.INFO``.
        **fields: Arbitrary structured key-value pairs merged into the record.

    Example::

        audit_event(
            "agent.complete",
            agent="auditor",
            duration_ms=1234.5,
            violations_found=2,
        )
    """
    extra: dict[str, Any] = {}

    trace_id = _trace_id_var.get()
    if trace_id:
        extra["trace_id"] = trace_id

    span_id = _span_id_var.get()
    if span_id:
        extra["span_id"] = span_id

    extra.update(fields)

    logger.log(level, event, extra=extra)


# ---------------------------------------------------------------------------
# Timing span
# ---------------------------------------------------------------------------


class AuditSpan:
    """
    Context manager that times an operation and emits start/complete/error events.

    On entry:  emits ``<name>.start``
    On exit:   emits ``<name>.complete`` (success) or ``<name>.error`` (exception),
               both carrying ``duration_ms``.

    Additional fields can be attached at any point via :meth:`set` — they will
    appear in the completion/error event.

    Args:
        name:     Dot-separated event prefix, e.g. ``'agent'``, ``'file.scan'``.
        **labels: Static key-value pairs emitted in both start and completion
                  events (e.g. ``agent="auditor"``, ``file="main.tf"``).

    Example::

        with AuditSpan("agent", agent="auditor") as span:
            result = auditor_node(state, llm)
            span.set(
                violations_found=len(result.get("violations", [])),
                status=result.get("status", "unknown"),
            )
    """

    def __init__(self, name: str, **labels: Any) -> None:
        self.name = name
        self.labels = labels
        self._extras: dict[str, Any] = {}
        self._start: float = 0.0
        self._span_id: str = uuid.uuid4().hex[:8]
        self._span_token: Any = None

    def set(self, **kwargs: Any) -> None:
        """Attach extra fields that will appear in the completion event."""
        self._extras.update(kwargs)

    def __enter__(self) -> "AuditSpan":
        self._start = time.perf_counter()
        self._span_token = _span_id_var.set(self._span_id)
        audit_event(f"{self.name}.start", **self.labels)
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        duration_ms = round((time.perf_counter() - self._start) * 1000, 2)
        _span_id_var.reset(self._span_token)

        if exc_type is None:
            audit_event(
                f"{self.name}.complete",
                duration_ms=duration_ms,
                **self.labels,
                **self._extras,
            )
        else:
            audit_event(
                f"{self.name}.error",
                level=logging.ERROR,
                duration_ms=duration_ms,
                error=str(exc_val),
                error_type=exc_type.__name__ if exc_type else "unknown",
                **self.labels,
                **self._extras,
            )

        return False  # never suppress exceptions
