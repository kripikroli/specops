"""SpecOps — Agent Reliability Kit."""

__version__ = "0.1.0"

from specops.adapters import BaseAdapter, PlainAdapter, get_adapter, register_adapter
from specops.config import configure, get_tracer, reset
from specops.trace import trace_agent, trace_llm, trace_tool

__all__ = [
    "BaseAdapter",
    "PlainAdapter",
    "configure",
    "get_adapter",
    "get_tracer",
    "register_adapter",
    "reset",
    "trace_agent",
    "trace_llm",
    "trace_tool",
]
