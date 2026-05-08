"""Framework adapters for SpecOps tracing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAdapter(ABC):
    """Base class for framework adapters.

    Adapters normalize framework-specific metadata into SpecOps semantic attributes.
    """

    @abstractmethod
    def extract_task(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        """Extract the agent task from function arguments."""

    @abstractmethod
    def extract_llm_metadata(self, result: Any) -> dict[str, Any]:
        """Extract LLM metadata (tokens, model) from a call result."""

    @abstractmethod
    def extract_tool_metadata(
        self, args: tuple[Any, ...], kwargs: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        """Extract tool metadata from a call."""


class PlainAdapter(BaseAdapter):
    """Default adapter for plain Python agent code.

    Assumes:
    - First positional arg is the task string.
    - LLM results are dicts with `model`, `input_tokens`, `output_tokens`.
    - Tool results are returned directly.
    """

    def extract_task(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        """First positional arg or 'task' kwarg."""
        if args:
            return str(args[0])
        return str(kwargs.get("task", ""))

    def extract_llm_metadata(self, result: Any) -> dict[str, Any]:
        """Extract from dict result."""
        if isinstance(result, dict):
            return {
                k: v
                for k, v in result.items()
                if k in ("model", "input_tokens", "output_tokens")
            }
        return {}

    def extract_tool_metadata(
        self, args: tuple[Any, ...], kwargs: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        """Return args and result as metadata."""
        return {"args": args, "kwargs": kwargs, "result": result}


_ADAPTERS: dict[str, type[BaseAdapter]] = {
    "plain": PlainAdapter,
}


def get_adapter(framework: str) -> BaseAdapter:
    """Get an adapter instance by framework name."""
    cls = _ADAPTERS.get(framework, PlainAdapter)
    return cls()


def register_adapter(framework: str, adapter_cls: type[BaseAdapter]) -> None:
    """Register a custom adapter for a framework."""
    _ADAPTERS[framework] = adapter_cls


def _auto_register() -> None:
    """Auto-register framework adapters if their libraries are available."""
    try:
        from specops.adapters.langgraph import LangGraphAdapter

        _ADAPTERS.setdefault("langgraph", LangGraphAdapter)
    except ImportError:
        pass

    try:
        from specops.adapters.crewai import CrewAIAdapter

        _ADAPTERS.setdefault("crewai", CrewAIAdapter)
    except ImportError:
        pass

    try:
        from specops.adapters.autogen import AutoGenAdapter

        _ADAPTERS.setdefault("autogen", AutoGenAdapter)
    except ImportError:
        pass


_auto_register()
