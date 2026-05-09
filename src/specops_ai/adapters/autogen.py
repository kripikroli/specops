"""AutoGen adapter for SpecOps tracing.

Stub implementation for Microsoft AutoGen's multi-agent chat patterns.
"""

from __future__ import annotations

from typing import Any

from specops_ai.adapters import BaseAdapter


class AutoGenAdapter(BaseAdapter):
    """Adapter for Microsoft AutoGen framework (stub).

    Handles basic AutoGen chat patterns:
    - Task extracted from message content or initiate_chat args.
    - LLM metadata extracted from response dicts.
    - Tool metadata from function call results.

    Note: This is a minimal stub. Full support for GroupChat, nested chats,
    and custom speaker selection will be added in a future release.
    """

    def extract_task(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        """Extract task from AutoGen message or initiate_chat call."""
        message = kwargs.get("message", "")
        if message:
            return str(message)
        if args:
            first = args[0]
            if isinstance(first, dict):
                return str(first.get("content", first.get("message", first)))
            return str(first)
        return ""

    def extract_llm_metadata(self, result: Any) -> dict[str, Any]:
        """Extract LLM metadata from AutoGen response."""
        meta: dict[str, Any] = {}
        if isinstance(result, dict):
            meta["model"] = result.get("model", "")
            usage = result.get("usage", {})
            if isinstance(usage, dict):
                meta["input_tokens"] = usage.get("prompt_tokens", 0)
                meta["output_tokens"] = usage.get("completion_tokens", 0)
        return meta

    def extract_tool_metadata(
        self, args: tuple[Any, ...], kwargs: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        """Extract tool metadata from AutoGen function calls."""
        meta: dict[str, Any] = {"args": args, "kwargs": kwargs}
        if isinstance(result, dict):
            meta["result"] = result.get("content", result)
        else:
            meta["result"] = result
        return meta
