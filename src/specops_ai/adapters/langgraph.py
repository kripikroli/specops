"""LangGraph adapter for SpecOps tracing.

Extracts metadata from LangGraph's StateGraph/Pregel execution patterns.
"""

from __future__ import annotations

from typing import Any

from specops_ai.adapters import BaseAdapter


class LangGraphAdapter(BaseAdapter):
    """Adapter for LangGraph (StateGraph, Pregel, MessageGraph).

    Handles LangGraph conventions:
    - Task extracted from state dict's "input", "messages", or "task" key.
    - LLM metadata extracted from AIMessage-like objects or dicts.
    - Tool metadata extracted from ToolMessage-like objects or dicts.
    """

    def extract_task(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        """Extract task from LangGraph state input.

        LangGraph invocations typically pass a state dict as the first arg
        with keys like 'input', 'messages', or 'task'.
        """
        state = args[0] if args else kwargs.get("state", kwargs.get("input", {}))
        if isinstance(state, dict):
            for key in ("input", "task", "question"):
                if key in state:
                    return str(state[key])
            # Check messages list — use last HumanMessage content
            messages = state.get("messages", [])
            if messages:
                last = messages[-1] if isinstance(messages, list) else messages
                if hasattr(last, "content"):
                    return str(last.content)
                if isinstance(last, dict):
                    return str(last.get("content", ""))
        if isinstance(state, str):
            return state
        return str(state)[:256] if state else ""

    def extract_llm_metadata(self, result: Any) -> dict[str, Any]:
        """Extract LLM metadata from LangGraph results.

        Supports AIMessage objects (with usage_metadata) and plain dicts.
        """
        meta: dict[str, Any] = {}
        # AIMessage with usage_metadata (langchain-core pattern)
        if hasattr(result, "usage_metadata"):
            usage = result.usage_metadata
            if isinstance(usage, dict):
                meta["input_tokens"] = usage.get("input_tokens", 0)
                meta["output_tokens"] = usage.get("output_tokens", 0)
            elif hasattr(usage, "input_tokens"):
                meta["input_tokens"] = usage.input_tokens
                meta["output_tokens"] = usage.output_tokens
        if hasattr(result, "response_metadata"):
            rm = result.response_metadata
            if isinstance(rm, dict):
                meta.setdefault("model", rm.get("model_name", rm.get("model", "")))
        # Dict fallback
        if isinstance(result, dict):
            if "model" in result:
                meta["model"] = result["model"]
            usage = result.get("usage_metadata", result.get("usage", {}))
            if isinstance(usage, dict):
                meta.setdefault("input_tokens", usage.get("input_tokens", 0))
                meta.setdefault("output_tokens", usage.get("output_tokens", 0))
        return meta

    def extract_tool_metadata(
        self, args: tuple[Any, ...], kwargs: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        """Extract tool metadata from LangGraph tool invocations.

        Supports ToolMessage objects and plain dicts.
        """
        meta: dict[str, Any] = {"args": args, "kwargs": kwargs}
        if hasattr(result, "content"):
            meta["result"] = result.content
        elif isinstance(result, dict):
            meta["result"] = result.get("content", result.get("output", result))
        else:
            meta["result"] = result
        return meta
