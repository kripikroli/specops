"""Context propagation utilities for SpecOps tracing."""

from __future__ import annotations

from contextvars import ContextVar, Token

from opentelemetry.context import Context

_current_agent_ctx: ContextVar[Context | None] = ContextVar(
    "specops_agent_ctx", default=None
)


def get_current_context() -> Context | None:
    """Return the active SpecOps trace context."""
    return _current_agent_ctx.get()


def set_current_context(ctx: Context) -> Token[Context | None]:
    """Set the active context. Returns a token for reset."""
    return _current_agent_ctx.set(ctx)
