"""CrewAI adapter for SpecOps tracing.

Extracts metadata from CrewAI's Crew, Agent, Task, and Process patterns.
"""

from __future__ import annotations

from typing import Any

from specops_ai.adapters import BaseAdapter


class CrewAIAdapter(BaseAdapter):
    """Adapter for CrewAI framework.

    Handles CrewAI conventions:
    - Task extracted from CrewAI Task objects or description strings.
    - LLM metadata extracted from CrewAI's LLM response patterns.
    - Tool metadata extracted from CrewAI tool execution results.
    """

    def extract_task(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        """Extract task from CrewAI Task object or kickoff inputs.

        CrewAI patterns:
        - crew.kickoff(inputs={"topic": "..."})
        - Task(description="...")
        - Plain string as first arg
        """
        # Check kwargs for CrewAI kickoff inputs
        inputs = kwargs.get("inputs", {})
        if isinstance(inputs, dict) and inputs:
            return str(next(iter(inputs.values())))

        if not args:
            return str(kwargs.get("task", kwargs.get("description", "")))

        first = args[0]
        # CrewAI Task object
        if hasattr(first, "description"):
            return str(first.description)
        # Dict with task info
        if isinstance(first, dict):
            return str(first.get("description", first.get("task", first)))
        return str(first)

    def extract_llm_metadata(self, result: Any) -> dict[str, Any]:
        """Extract LLM metadata from CrewAI results.

        Supports CrewAI's output objects and plain dicts.
        """
        meta: dict[str, Any] = {}
        # CrewAI TaskOutput / CrewOutput with token_usage
        if hasattr(result, "token_usage"):
            usage = result.token_usage
            if isinstance(usage, dict):
                meta["input_tokens"] = usage.get("prompt_tokens", 0)
                meta["output_tokens"] = usage.get("completion_tokens", 0)
                meta["model"] = usage.get("model", "")
        # Dict fallback
        if isinstance(result, dict):
            meta.setdefault("model", result.get("model", ""))
            usage = result.get("token_usage", result.get("usage", {}))
            if isinstance(usage, dict):
                meta.setdefault("input_tokens", usage.get("prompt_tokens", 0))
                meta.setdefault("output_tokens", usage.get("completion_tokens", 0))
        return meta

    def extract_tool_metadata(
        self, args: tuple[Any, ...], kwargs: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        """Extract tool metadata from CrewAI tool executions."""
        meta: dict[str, Any] = {"args": args, "kwargs": kwargs}
        if hasattr(result, "output"):
            meta["result"] = result.output
        elif isinstance(result, dict):
            meta["result"] = result.get("output", result.get("result", result))
        else:
            meta["result"] = result
        return meta
