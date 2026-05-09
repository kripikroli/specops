"""Unit tests for SpecOps tracing decorators."""

from __future__ import annotations

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import specops_ai
from specops_ai import trace_agent, trace_llm, trace_tool
from specops_ai._constants import (
    AGENT_FRAMEWORK,
    AGENT_NAME,
    AGENT_TASK,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_TOKENS_INPUT,
    LLM_TOKENS_OUTPUT,
    TOOL_ARGS,
    TOOL_NAME,
    TOOL_RESULT,
)


@pytest.fixture(autouse=True)
def _setup_tracer(monkeypatch: pytest.MonkeyPatch):
    """Set up in-memory exporter for each test."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    specops_ai.reset()

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Bypass the "already set" guard by patching the global
    monkeypatch.setattr(
        trace, "_TRACER_PROVIDER_SET_ONCE", trace._TRACER_PROVIDER_SET_ONCE.__class__()
    )
    trace.set_tracer_provider(provider)

    monkeypatch.setattr("specops_ai.config._configured", True)
    monkeypatch.setattr(
        "specops_ai.config._tracer", provider.get_tracer("specops-test")
    )

    yield exporter

    provider.shutdown()


def get_spans(exporter: InMemorySpanExporter):
    return exporter.get_finished_spans()


# --- trace_agent tests ---


class TestTraceAgent:
    def test_sync_agent(self, _setup_tracer):
        @trace_agent(name="test-agent")
        def my_agent(task: str) -> str:
            return f"done: {task}"

        result = my_agent("hello")
        assert result == "done: hello"

        spans = get_spans(_setup_tracer)
        assert len(spans) == 1
        span = spans[0]
        assert span.name == "agent:test-agent"
        assert span.attributes[AGENT_NAME] == "test-agent"
        assert '"hello"' in span.attributes[AGENT_TASK]
        assert span.attributes[AGENT_FRAMEWORK] == "plain"

    @pytest.mark.asyncio
    async def test_async_agent(self, _setup_tracer):
        @trace_agent(name="async-agent")
        async def my_agent(task: str) -> str:
            return f"done: {task}"

        result = await my_agent("world")
        assert result == "done: world"

        spans = get_spans(_setup_tracer)
        assert len(spans) == 1
        assert spans[0].name == "agent:async-agent"

    def test_agent_exception(self, _setup_tracer):
        @trace_agent(name="fail-agent")
        def bad_agent(task: str) -> str:
            raise ValueError("oops")

        with pytest.raises(ValueError, match="oops"):
            bad_agent("fail")

        spans = get_spans(_setup_tracer)
        assert len(spans) == 1
        assert spans[0].status.status_code.name == "ERROR"

    def test_agent_framework_attr(self, _setup_tracer):
        @trace_agent(name="lg-agent", framework="langgraph")
        def my_agent(task: str) -> str:
            return task

        my_agent("x")
        spans = get_spans(_setup_tracer)
        assert spans[0].attributes[AGENT_FRAMEWORK] == "langgraph"


# --- trace_tool tests ---


class TestTraceTool:
    def test_sync_tool(self, _setup_tracer):
        @trace_tool(name="search")
        def search(query: str) -> list[str]:
            return ["result1", "result2"]

        result = search("test query")
        assert result == ["result1", "result2"]

        spans = get_spans(_setup_tracer)
        assert len(spans) == 1
        span = spans[0]
        assert span.name == "tool:search"
        assert span.attributes[TOOL_NAME] == "search"
        assert "test query" in span.attributes[TOOL_ARGS]
        assert "result1" in span.attributes[TOOL_RESULT]

    @pytest.mark.asyncio
    async def test_async_tool(self, _setup_tracer):
        @trace_tool()
        async def fetch_data(url: str) -> dict:
            return {"status": 200}

        result = await fetch_data("http://example.com")
        assert result == {"status": 200}

        spans = get_spans(_setup_tracer)
        assert len(spans) == 1
        assert spans[0].name == "tool:fetch_data"

    def test_tool_default_name(self, _setup_tracer):
        @trace_tool()
        def my_func(x: int) -> int:
            return x * 2

        my_func(5)
        spans = get_spans(_setup_tracer)
        assert spans[0].attributes[TOOL_NAME] == "my_func"

    def test_tool_exception(self, _setup_tracer):
        @trace_tool(name="bad-tool")
        def bad_tool() -> None:
            raise RuntimeError("broken")

        with pytest.raises(RuntimeError, match="broken"):
            bad_tool()

        spans = get_spans(_setup_tracer)
        assert spans[0].status.status_code.name == "ERROR"


# --- trace_llm tests ---


class TestTraceLlm:
    def test_sync_llm_with_dict_result(self, _setup_tracer):
        @trace_llm(model="gpt-4o", provider="openai")
        def call_llm(prompt: str) -> dict:
            return {
                "text": "response",
                "model": "gpt-4o",
                "input_tokens": 10,
                "output_tokens": 50,
            }

        result = call_llm("hello")
        assert result["text"] == "response"

        spans = get_spans(_setup_tracer)
        assert len(spans) == 1
        span = spans[0]
        assert span.name == "llm:gpt-4o"
        assert span.attributes[LLM_MODEL] == "gpt-4o"
        assert span.attributes[LLM_PROVIDER] == "openai"
        assert span.attributes[LLM_TOKENS_INPUT] == 10
        assert span.attributes[LLM_TOKENS_OUTPUT] == 50

    @pytest.mark.asyncio
    async def test_async_llm(self, _setup_tracer):
        @trace_llm(model="claude-3")
        async def call_claude(prompt: str) -> dict:
            return {"model": "claude-3", "input_tokens": 5, "output_tokens": 20}

        await call_claude("hi")
        spans = get_spans(_setup_tracer)
        assert spans[0].attributes[LLM_MODEL] == "claude-3"

    def test_llm_model_override_from_result(self, _setup_tracer):
        @trace_llm(model="default")
        def call_llm(prompt: str) -> dict:
            return {"model": "gpt-4o-mini", "input_tokens": 1, "output_tokens": 2}

        call_llm("x")
        spans = get_spans(_setup_tracer)
        assert spans[0].attributes[LLM_MODEL] == "gpt-4o-mini"

    def test_llm_exception(self, _setup_tracer):
        @trace_llm(model="gpt-4")
        def bad_llm(prompt: str) -> dict:
            raise TimeoutError("timeout")

        with pytest.raises(TimeoutError):
            bad_llm("x")

        spans = get_spans(_setup_tracer)
        assert spans[0].status.status_code.name == "ERROR"

    def test_llm_no_provider(self, _setup_tracer):
        @trace_llm(model="local-model")
        def call_local(prompt: str) -> str:
            return "response"

        call_local("x")
        spans = get_spans(_setup_tracer)
        assert LLM_PROVIDER not in spans[0].attributes


# --- Integration: nested spans ---


class TestNesting:
    def test_tool_inside_agent(self, _setup_tracer):
        @trace_tool(name="calculator")
        def calc(x: int) -> int:
            return x * 2

        @trace_agent(name="math-agent")
        def agent(task: str) -> int:
            return calc(21)

        result = agent("compute")
        assert result == 42

        spans = get_spans(_setup_tracer)
        assert len(spans) == 2
        agent_span = next(s for s in spans if s.name == "agent:math-agent")
        tool_span = next(s for s in spans if s.name == "tool:calculator")
        # Tool span should be child of agent span
        assert tool_span.parent.span_id == agent_span.context.span_id

    @pytest.mark.asyncio
    async def test_llm_inside_agent(self, _setup_tracer):
        @trace_llm(model="gpt-4")
        async def call_model(prompt: str) -> dict:
            return {"input_tokens": 5, "output_tokens": 10}

        @trace_agent(name="chat-agent")
        async def agent(task: str) -> dict:
            return await call_model(task)

        await agent("hello")
        spans = get_spans(_setup_tracer)
        assert len(spans) == 2
        agent_span = next(s for s in spans if s.name == "agent:chat-agent")
        llm_span = next(s for s in spans if s.name == "llm:gpt-4")
        assert llm_span.parent.span_id == agent_span.context.span_id
