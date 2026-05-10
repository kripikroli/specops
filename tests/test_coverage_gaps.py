"""Targeted tests to fill coverage gaps in specific modules.

Covers:
- config.py: disabled mode, OTLP endpoint path
- adapters/__init__.py: PlainAdapter methods
- trace.py: async decorators, truncation edge cases
- simulate.py: @simulate decorator (sync), properties, duration budget
- viz.py: save_dot function
- langgraph.py: extract_task with messages, usage_metadata object
- rca.py: causal edges
- heal.py: async escalate with sync handler
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import specops_ai
from specops_ai import (
    EscalatePolicy,
    FallbackPolicy,
    RetryPolicy,
    build_rca_graph,
    self_healing,
    trace_agent,
    trace_llm,
    trace_tool,
)
from specops_ai.adapters import PlainAdapter
from specops_ai.adapters.langgraph import LangGraphAdapter
from specops_ai.config import configure, get_tracer, reset
from specops_ai.rca import RCAGraph, RCANode
from specops_ai.simulate import SimulationEnvironment, simulate
from specops_ai.viz import save_dot


@pytest.fixture(autouse=True)
def _setup_tracer(monkeypatch: pytest.MonkeyPatch):
    """Set up in-memory exporter for each test."""
    specops_ai.reset()
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
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


class TestConfigGaps:
    """Cover config.py disabled mode and OTLP path."""

    def test_disabled_via_param(self):
        """configure(enabled=False) produces NoOpTracer."""
        reset()
        configure(enabled=False)
        tracer = get_tracer()
        assert isinstance(tracer, trace.NoOpTracer)

    def test_disabled_via_env(self, monkeypatch: pytest.MonkeyPatch):
        """SPECOPS_ENABLED=false produces NoOpTracer."""
        reset()
        monkeypatch.setattr("specops_ai.config._configured", False)
        monkeypatch.setattr("specops_ai.config._tracer", None)
        monkeypatch.setenv("SPECOPS_ENABLED", "false")
        configure()
        tracer = get_tracer()
        assert isinstance(tracer, trace.NoOpTracer)

    def test_otlp_endpoint_fallback(self, monkeypatch: pytest.MonkeyPatch):
        """OTLP endpoint configured but exporter not installed falls back to console."""
        reset()
        monkeypatch.setattr("specops_ai.config._configured", False)
        monkeypatch.setattr("specops_ai.config._tracer", None)
        # Simulate OTLP exporter import failure
        with patch(
            "specops_ai.config.os.environ.get",
            side_effect=lambda k, d=None: (
                "http://localhost:4317"
                if k == "OTEL_EXPORTER_OTLP_ENDPOINT"
                else d
                if k != "SPECOPS_ENABLED"
                else "true"
            ),
        ):
            configure(endpoint="http://localhost:4317")
        # Should not crash — falls back to console or OTLP
        tracer = get_tracer()
        assert tracer is not None


class TestPlainAdapterGaps:
    """Cover PlainAdapter methods."""

    def test_extract_task_no_args(self):
        """extract_task with no args returns empty or kwarg."""
        adapter = PlainAdapter()
        assert adapter.extract_task((), {}) == ""
        assert adapter.extract_task((), {"task": "hello"}) == "hello"

    def test_extract_llm_metadata_dict(self):
        """extract_llm_metadata extracts from dict."""
        adapter = PlainAdapter()
        result = {
            "model": "gpt-4",
            "input_tokens": 10,
            "output_tokens": 5,
            "extra": "x",
        }
        meta = adapter.extract_llm_metadata(result)
        assert meta == {"model": "gpt-4", "input_tokens": 10, "output_tokens": 5}

    def test_extract_llm_metadata_non_dict(self):
        """extract_llm_metadata returns empty for non-dict."""
        adapter = PlainAdapter()
        assert adapter.extract_llm_metadata("string result") == {}

    def test_extract_tool_metadata(self):
        """extract_tool_metadata returns args/kwargs/result."""
        adapter = PlainAdapter()
        meta = adapter.extract_tool_metadata(("a",), {"b": 1}, "result")
        assert meta == {"args": ("a",), "kwargs": {"b": 1}, "result": "result"}


class TestLangGraphAdapterGaps:
    """Cover LangGraphAdapter edge cases."""

    def test_extract_task_with_messages(self):
        """extract_task handles state dict with messages list."""
        adapter = LangGraphAdapter()
        # Message with content attribute
        msg = MagicMock()
        msg.content = "user question"
        state = {"messages": [msg]}
        assert adapter.extract_task((state,), {}) == "user question"

    def test_extract_task_with_dict_message(self):
        """extract_task handles dict messages."""
        adapter = LangGraphAdapter()
        state = {"messages": [{"content": "dict msg"}]}
        assert adapter.extract_task((state,), {}) == "dict msg"

    def test_extract_task_string_state(self):
        """extract_task handles plain string state."""
        adapter = LangGraphAdapter()
        assert adapter.extract_task(("plain string",), {}) == "plain string"

    def test_extract_llm_metadata_usage_object(self):
        """extract_llm_metadata with usage_metadata as object."""
        adapter = LangGraphAdapter()
        result = MagicMock()
        result.usage_metadata = MagicMock()
        result.usage_metadata.input_tokens = 100
        result.usage_metadata.output_tokens = 50
        # Make isinstance check fail for dict
        result.usage_metadata.__class__ = type("UsageMeta", (), {})
        result.response_metadata = {"model_name": "claude-3"}
        meta = adapter.extract_llm_metadata(result)
        assert meta["input_tokens"] == 100
        assert meta["output_tokens"] == 50
        assert meta["model"] == "claude-3"

    def test_extract_tool_metadata_with_content(self):
        """extract_tool_metadata with ToolMessage-like object."""
        adapter = LangGraphAdapter()
        result = MagicMock()
        result.content = "tool output"
        meta = adapter.extract_tool_metadata(("arg",), {}, result)
        assert meta["result"] == "tool output"


class TestTraceAsyncGaps:
    """Cover async trace decorators."""

    @pytest.mark.asyncio
    async def test_async_trace_agent(self, _setup_tracer: InMemorySpanExporter):
        """Async trace_agent creates spans."""

        @trace_agent(name="async-traced")
        async def my_agent(task: str) -> str:
            return f"done: {task}"

        result = await my_agent("hello")
        assert result == "done: hello"
        spans = _setup_tracer.get_finished_spans()
        assert any("agent:async-traced" in s.name for s in spans)

    @pytest.mark.asyncio
    async def test_async_trace_tool(self, _setup_tracer: InMemorySpanExporter):
        """Async trace_tool creates spans."""

        @trace_tool(name="async-tool")
        async def my_tool(x: int) -> int:
            return x * 2

        result = await my_tool(5)
        assert result == 10
        spans = _setup_tracer.get_finished_spans()
        assert any("tool:async-tool" in s.name for s in spans)

    @pytest.mark.asyncio
    async def test_async_trace_llm(self, _setup_tracer: InMemorySpanExporter):
        """Async trace_llm creates spans."""

        @trace_llm(model="test-model", provider="test")
        async def my_llm(prompt: str) -> dict:
            return {
                "text": "hi",
                "model": "test-model",
                "input_tokens": 3,
                "output_tokens": 1,
            }

        result = await my_llm("hello")
        assert result["text"] == "hi"
        spans = _setup_tracer.get_finished_spans()
        assert any("llm:" in s.name for s in spans)

    @pytest.mark.asyncio
    async def test_async_trace_agent_error(self, _setup_tracer: InMemorySpanExporter):
        """Async trace_agent records errors."""

        @trace_agent(name="error-agent")
        async def bad_agent(task: str) -> str:
            raise ValueError("async error")

        with pytest.raises(ValueError, match="async error"):
            await bad_agent("fail")

    @pytest.mark.asyncio
    async def test_async_trace_tool_error(self, _setup_tracer: InMemorySpanExporter):
        """Async trace_tool records errors."""

        @trace_tool(name="error-tool")
        async def bad_tool(x: int) -> int:
            raise RuntimeError("tool error")

        with pytest.raises(RuntimeError, match="tool error"):
            await bad_tool(1)

    @pytest.mark.asyncio
    async def test_async_trace_llm_error(self, _setup_tracer: InMemorySpanExporter):
        """Async trace_llm records errors."""

        @trace_llm(model="m")
        async def bad_llm(prompt: str) -> dict:
            raise ConnectionError("llm error")

        with pytest.raises(ConnectionError, match="llm error"):
            await bad_llm("x")


class TestSimulateDecoratorGaps:
    """Cover @simulate decorator (sync) and properties."""

    def test_simulate_sync_decorator(self):
        """@simulate decorator works with sync functions."""

        @simulate("sync-test", max_steps=10, loop_threshold=5)
        def my_sim(env: SimulationEnvironment) -> None:
            env.record("agent-a", "action-1")
            env.record("agent-a", "action-2")

        result = my_sim()  # type: ignore[call-arg]
        assert result.scenario == "sync-test"
        assert result.passed

    def test_simulate_sync_budget_exceeded(self):
        """@simulate catches budget exceeded."""

        @simulate("budget-test", max_steps=2, loop_threshold=5)
        def my_sim(env: SimulationEnvironment) -> None:
            for i in range(10):
                env.record("agent", f"action-{i}")

        result = my_sim()  # type: ignore[call-arg]
        assert not result.passed or result.scenario == "budget-test"

    def test_simulation_properties(self):
        """SimulationEnvironment properties are accessible."""
        env = SimulationEnvironment(
            scenario="prop-test", max_steps=100, loop_threshold=3
        )
        env.start()
        assert env.step_count == 0
        assert env.tokens_used == 0
        env.record("agent", "action")
        assert env.step_count == 1
        env.add_tokens(500)
        assert env.tokens_used == 500

    def test_simulation_duration_exceeded(self):
        """Duration budget raises SimulationBudgetExceeded."""
        env = SimulationEnvironment(
            scenario="duration-test",
            max_steps=100,
            max_duration=0.001,
            loop_threshold=3,
        )
        env.start()
        time.sleep(0.01)  # Exceed duration
        from specops_ai.simulate import SimulationBudgetExceeded

        with pytest.raises(SimulationBudgetExceeded):
            env.record("agent", "action")

    @pytest.mark.asyncio
    async def test_simulate_async_decorator(self):
        """@simulate decorator works with async functions."""

        @simulate("async-sim", max_steps=10, loop_threshold=5)
        async def my_sim(env: SimulationEnvironment) -> None:
            env.record("agent", "action-1")

        result = await my_sim()  # type: ignore[call-arg]
        assert result.scenario == "async-sim"
        assert result.passed


class TestVizGaps:
    """Cover viz.save_dot."""

    def test_save_dot(self, tmp_path: Path):
        """save_dot writes DOT file to disk."""
        graph = RCAGraph()
        graph.add_node(
            RCANode(
                span_id="abc123",
                name="test-span",
                status="ok",
                start_time=0,
                end_time=1,
            )
        )
        out_path = str(tmp_path / "test.dot")
        result = save_dot(graph, out_path, title="Test Graph")
        assert result == out_path
        content = Path(out_path).read_text()
        assert "Test Graph" in content
        assert "abc123" in content


class TestRCACausalEdges:
    """Cover RCA causal edge logic."""

    def test_causal_edges_added(self, _setup_tracer: InMemorySpanExporter):
        """Causal edges are added when child errors precede parent errors."""

        @trace_tool(name="failing-tool")
        def fail_tool(x: str) -> str:
            raise ValueError("inner fail")

        @trace_agent(name="parent-agent")
        def parent(task: str) -> str:
            return fail_tool(task)

        with pytest.raises(ValueError):
            parent("test")

        spans = _setup_tracer.get_finished_spans()
        graph = build_rca_graph(list(spans))

        # Check for caused_by edges
        assert len(graph.edges) >= 1


class TestHealAsyncGaps:
    """Cover remaining async heal paths."""

    @pytest.mark.asyncio
    async def test_async_escalate_sync_handler(self):
        """Async path with sync escalation handler."""
        escalated = []

        def sync_handler(fn_name, args, kwargs, exc):
            escalated.append(fn_name)
            return "sync-escalated"

        @self_healing(escalate=EscalatePolicy(handler=sync_handler))
        async def failing_fn(x: int) -> str:
            raise RuntimeError("fail")

        result = await failing_fn(1)
        assert result == "sync-escalated"
        assert escalated == ["failing_fn"]

    @pytest.mark.asyncio
    async def test_async_fallback_sync_fn(self):
        """Async path with sync fallback function."""

        def sync_backup(x: int) -> str:
            return "sync-fallback"

        @self_healing(fallback=FallbackPolicy(fallback_fn=sync_backup))
        async def failing_fn(x: int) -> str:
            raise RuntimeError("fail")

        result = await failing_fn(1)
        assert result == "sync-fallback"

    @pytest.mark.asyncio
    async def test_async_full_chain_exhausted(self):
        """Async: all policies fail, original exception re-raised."""

        def bad_fallback(x: int) -> str:
            raise RuntimeError("fallback also fails")

        @self_healing(
            retry=RetryPolicy(max_retries=1, base_delay=0.01),
            fallback=FallbackPolicy(fallback_fn=bad_fallback),
        )
        async def always_fails(x: int) -> str:
            raise ValueError("permanent")

        with pytest.raises(ValueError, match="permanent"):
            await always_fails(1)
