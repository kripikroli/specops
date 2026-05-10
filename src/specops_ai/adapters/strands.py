"""Strands Agents SDK adapter for SpecOps tracing."""

from __future__ import annotations

from typing import Any

from specops_ai.adapters import BaseAdapter


class StrandsAdapter(BaseAdapter):
    """Adapter for AWS Strands Agents SDK.

    Handles Strands agent patterns:
    - Task extracted from prompt string or messages list.
    - LLM metadata extracted from response with usage/model info.
    - Tool metadata from tool call results.
    """

    def extract_task(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        """Extract task from Strands agent invocation."""
        prompt = kwargs.get("prompt", "")
        if prompt:
            return str(prompt)
        if args:
            first = args[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                return str(first.get("content", first.get("prompt", first)))
            if isinstance(first, list) and first:
                last = first[-1]
                if isinstance(last, dict):
                    return str(last.get("content", last))
                return str(last)
        return ""

    def extract_llm_metadata(self, result: Any) -> dict[str, Any]:
        """Extract LLM metadata from Strands response."""
        meta: dict[str, Any] = {}
        if isinstance(result, dict):
            meta["model"] = result.get("model", "")
            usage = result.get("usage")
            if isinstance(usage, dict):
                meta["input_tokens"] = usage.get(
                    "input_tokens", usage.get("prompt_tokens", 0)
                )
                meta["output_tokens"] = usage.get(
                    "output_tokens", usage.get("completion_tokens", 0)
                )
            elif "input_tokens" in result:
                meta["input_tokens"] = result["input_tokens"]
                meta["output_tokens"] = result.get("output_tokens", 0)
        elif hasattr(result, "usage"):
            usage = result.usage
            if isinstance(usage, dict):
                meta["input_tokens"] = usage.get("input_tokens", 0)
                meta["output_tokens"] = usage.get("output_tokens", 0)
            if hasattr(result, "model"):
                meta["model"] = result.model
        return meta

    def extract_tool_metadata(
        self, args: tuple[Any, ...], kwargs: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        """Extract tool metadata from Strands tool calls."""
        meta: dict[str, Any] = {"args": args, "kwargs": kwargs}
        if isinstance(result, dict):
            meta["result"] = result.get("content", result.get("output", result))
        else:
            meta["result"] = result
        return meta
