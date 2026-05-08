"""Core tracing decorators for SpecOps."""

from __future__ import annotations

import functools
import inspect
import json
from collections.abc import Callable
from typing import Any, TypeVar

from opentelemetry import context as otel_context
from opentelemetry import trace

from specops._constants import (
    AGENT_FRAMEWORK,
    AGENT_NAME,
    AGENT_TASK,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_RESULT,
    LLM_TOKENS_INPUT,
    LLM_TOKENS_OUTPUT,
    MAX_ATTR_LENGTH,
    TOOL_ARGS,
    TOOL_NAME,
    TOOL_RESULT,
)
from specops._context import (
    _current_agent_ctx,
    get_current_context,
    set_current_context,
)
from specops.config import get_tracer

F = TypeVar("F", bound=Callable[..., Any])


def _truncate(value: Any) -> str:
    """Serialize and truncate a value for span attributes."""
    try:
        s = json.dumps(value, default=str)
    except (TypeError, ValueError):
        s = str(value)
    return s[:MAX_ATTR_LENGTH]


def trace_agent(name: str, *, framework: str = "plain") -> Callable[[F], F]:
    """Trace an agent function as a root/parent span.

    Args:
        name: Human-readable agent name.
        framework: Agent framework identifier.

    The first positional arg is captured as the agent task.
    """

    def decorator(fn: F) -> F:
        is_async = inspect.iscoroutinefunction(fn)

        @functools.wraps(fn)
        async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            task = str(args[0]) if args else kwargs.get("task", "")
            parent_ctx = get_current_context()
            with tracer.start_as_current_span(
                f"agent:{name}", context=parent_ctx
            ) as span:
                span.set_attribute(AGENT_NAME, name)
                span.set_attribute(AGENT_TASK, _truncate(task))
                span.set_attribute(AGENT_FRAMEWORK, framework)
                token = set_current_context(otel_context.get_current())
                try:
                    return await fn(*args, **kwargs)
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(trace.StatusCode.ERROR, str(exc))
                    raise
                finally:
                    _current_agent_ctx.reset(token)

        @functools.wraps(fn)
        def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            task = str(args[0]) if args else kwargs.get("task", "")
            parent_ctx = get_current_context()
            with tracer.start_as_current_span(
                f"agent:{name}", context=parent_ctx
            ) as span:
                span.set_attribute(AGENT_NAME, name)
                span.set_attribute(AGENT_TASK, _truncate(task))
                span.set_attribute(AGENT_FRAMEWORK, framework)
                token = set_current_context(otel_context.get_current())
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(trace.StatusCode.ERROR, str(exc))
                    raise
                finally:
                    _current_agent_ctx.reset(token)

        return _async_wrapper if is_async else _sync_wrapper  # type: ignore[return-value]

    return decorator


def trace_tool(name: str | None = None) -> Callable[[F], F]:
    """Trace a tool/function call as a child span.

    Args:
        name: Tool name. Defaults to the function's __name__.
    """

    def decorator(fn: F) -> F:
        tool_name = name or fn.__name__
        is_async = inspect.iscoroutinefunction(fn)

        @functools.wraps(fn)
        async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.start_as_current_span(f"tool:{tool_name}") as span:
                span.set_attribute(TOOL_NAME, tool_name)
                tool_args = _truncate({"args": args, "kwargs": kwargs})
                span.set_attribute(TOOL_ARGS, tool_args)
                try:
                    result = await fn(*args, **kwargs)
                    span.set_attribute(TOOL_RESULT, _truncate(result))
                    return result
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(trace.StatusCode.ERROR, str(exc))
                    raise

        @functools.wraps(fn)
        def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.start_as_current_span(f"tool:{tool_name}") as span:
                span.set_attribute(TOOL_NAME, tool_name)
                tool_args = _truncate({"args": args, "kwargs": kwargs})
                span.set_attribute(TOOL_ARGS, tool_args)
                try:
                    result = fn(*args, **kwargs)
                    span.set_attribute(TOOL_RESULT, _truncate(result))
                    return result
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(trace.StatusCode.ERROR, str(exc))
                    raise

        return _async_wrapper if is_async else _sync_wrapper  # type: ignore[return-value]

    return decorator


def trace_llm(
    model: str = "",
    *,
    provider: str = "",
    capture_result: bool = False,
) -> Callable[[F], F]:
    """Trace an LLM invocation as a child span.

    Args:
        model: Model identifier (e.g. "gpt-4o").
        provider: Provider name (e.g. "openai").
        capture_result: If True, store the LLM response text as a span attribute.

    If the decorated function returns a dict with keys `input_tokens`, `output_tokens`,
    or `model`, those values populate span attributes.
    """

    def decorator(fn: F) -> F:
        is_async = inspect.iscoroutinefunction(fn)

        def _set_llm_attrs(span: trace.Span, result: Any) -> None:
            resolved_model = model
            if isinstance(result, dict):
                resolved_model = result.get("model", model)
                if "input_tokens" in result:
                    span.set_attribute(LLM_TOKENS_INPUT, result["input_tokens"])
                if "output_tokens" in result:
                    span.set_attribute(LLM_TOKENS_OUTPUT, result["output_tokens"])
            span.set_attribute(LLM_MODEL, resolved_model)
            if provider:
                span.set_attribute(LLM_PROVIDER, provider)
            if capture_result:
                span.set_attribute(LLM_RESULT, _truncate(result))

        @functools.wraps(fn)
        async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            span_name = f"llm:{model or fn.__name__}"
            with tracer.start_as_current_span(span_name) as span:
                try:
                    result = await fn(*args, **kwargs)
                    _set_llm_attrs(span, result)
                    return result
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(trace.StatusCode.ERROR, str(exc))
                    raise

        @functools.wraps(fn)
        def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            span_name = f"llm:{model or fn.__name__}"
            with tracer.start_as_current_span(span_name) as span:
                try:
                    result = fn(*args, **kwargs)
                    _set_llm_attrs(span, result)
                    return result
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(trace.StatusCode.ERROR, str(exc))
                    raise

        return _async_wrapper if is_async else _sync_wrapper  # type: ignore[return-value]

    return decorator
