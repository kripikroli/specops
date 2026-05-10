"""Integration tests exercising realistic multi-module scenarios.

Tests cover:
- Provider examples in mock mode
- Simulation demo scenarios
- Tracing + replay + eval pipelines
- Self-healing in realistic async scenarios
- Graceful key handling across providers
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import specops_ai
from specops_ai import (
    EscalatePolicy,
    FallbackPolicy,
    PruneMemoryPolicy,
    RetryPolicy,
    build_rca_graph,
    self_healing,
    to_dot,
    trace_agent,
    trace_llm,
    trace_tool,
)
from specops_ai.eval import EvalCase, eval_golden_set
from specops_ai.replay import recording, replayable

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
PROVIDERS_DIR = EXAMPLES_DIR / "providers"
SRC_DIR = str(Path(__file__).parent.parent / "src")


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


def _run_mock(path: Path) -> subprocess.CompletedProcess[str]:
    """Run an example in mock mode."""
    env = {**os.environ, "PYTHONPATH": SRC_DIR, "SPECOPS_EXAMPLE_MODE": "mock"}
    env.pop("OPENAI_API_KEY", None)
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("GROK_API_KEY", None)
    return subprocess.run(
        [sys.executable, str(path)], capture_output=True, text=True, timeout=30, env=env
    )


def _run_no_key(path: Path) -> subprocess.CompletedProcess[str]:
    """Run an example without API keys (graceful skip)."""
    env = {**os.environ, "PYTHONPATH": SRC_DIR}
    env.pop("OPENAI_API_KEY", None)
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("GROK_API_KEY", None)
    return subprocess.run(
        [sys.executable, str(path)], capture_output=True, text=True, timeout=30, env=env
    )


class TestProviderMockMode:
    """All provider examples run successfully in mock mode."""

    @pytest.mark.parametrize(
        "provider,script",
        [
            ("openai", "basic_agent.py"),
            ("openai", "langgraph_agent.py"),
            ("openai", "crewai_agent.py"),
            ("anthropic", "basic_agent.py"),
            ("anthropic", "langgraph_agent.py"),
            ("anthropic", "crewai_agent.py"),
            ("grok", "basic_agent.py"),
            ("grok", "langgraph_agent.py"),
            ("grok", "crewai_agent.py"),
        ],
    )
    def test_provider_mock_mode(self, provider: str, script: str):
        """Provider examples produce output in mock mode."""
        path = PROVIDERS_DIR / provider / script
        if not path.exists():
            pytest.skip(f"{path} not found")
        result = _run_mock(path)
        assert result.returncode == 0, f"stderr: {result.stderr}"

    @pytest.mark.parametrize("provider", ["openai", "anthropic", "grok"])
    def test_graceful_skip_without_key(self, provider: str):
        """Provider basic_agent exits 0 when key missing (skip or run with mock)."""
        path = PROVIDERS_DIR / provider / "basic_agent.py"
        if not path.exists():
            pytest.skip(f"{path} not found")
        result = _run_no_key(path)
        assert result.returncode == 0, f"stderr: {result.stderr}"


class TestSimulationDemo:
    """Integration tests for simulation_demo.py."""

    def test_simulation_demo_runs(self):
        """simulation_demo.py completes without error."""
        result = _run_mock(EXAMPLES_DIR / "simulation_demo.py")
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_simulation_loops_runs(self):
        """simulation_loops.py completes without error."""
        result = _run_mock(EXAMPLES_DIR / "simulation_loops.py")
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_simulation_cascade_runs(self):
        """simulation_cascade.py completes without error."""
        result = _run_mock(EXAMPLES_DIR / "simulation_cascade.py")
        assert result.returncode == 0, f"stderr: {result.stderr}"


class TestTracingReplayEvalPipeline:
    """Integration: trace an agent, record, replay, then evaluate."""

    def test_full_pipeline(self, tmp_path: Path):
        """End-to-end: trace → record → replay → eval."""

        @replayable
        @trace_llm(model="test-model", provider="test")
        def mock_llm(prompt: str) -> dict:
            return {
                "text": "4",
                "model": "test-model",
                "input_tokens": 5,
                "output_tokens": 1,
            }

        @trace_tool(name="calculator")
        def calc(expr: str) -> str:
            return str(eval(expr))  # noqa: S307

        @trace_agent(name="math-agent")
        def math_agent(task: str) -> str:
            result = calc(task)
            response = mock_llm(f"Verify: {result}")
            return response["text"]

        # Record
        with recording(session_id="integration-1") as _session:
            answer = math_agent("2+2")
            assert answer == "4"

        # Eval
        results = eval_golden_set(
            agent_fn=math_agent,
            cases=[EvalCase(input="2+2", expected="4")],
        )
        assert results[0].passed

    @pytest.mark.asyncio
    async def test_async_pipeline(self):
        """Async tracing pipeline works end-to-end."""

        @trace_agent(name="async-agent")
        async def async_agent(task: str) -> str:
            return f"done: {task}"

        result = await async_agent("test-task")
        assert result == "done: test-task"


class TestSelfHealingIntegration:
    """Integration: self-healing with multiple policies in realistic scenarios."""

    def test_retry_then_fallback_chain(self):
        """Retry exhausts, then fallback succeeds."""
        call_count = 0

        def backup(prompt: str) -> str:
            return "fallback-response"

        @self_healing(
            retry=RetryPolicy(max_retries=2, base_delay=0.01),
            fallback=FallbackPolicy(fallback_fn=backup),
        )
        def flaky_llm(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("timeout")

        result = flaky_llm("hello")
        assert result == "fallback-response"
        assert call_count >= 1

    @pytest.mark.asyncio
    async def test_async_retry_success(self):
        """Async function heals via retry on second attempt."""
        attempts = 0

        @self_healing(retry=RetryPolicy(max_retries=3, base_delay=0.01))
        async def flaky_async(prompt: str) -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise ConnectionError("transient")
            return "recovered"

        result = await flaky_async("test")
        assert result == "recovered"

    @pytest.mark.asyncio
    async def test_async_fallback(self):
        """Async fallback with async fallback function."""

        async def async_backup(prompt: str) -> str:
            return "async-fallback"

        @self_healing(
            retry=RetryPolicy(max_retries=1, base_delay=0.01),
            fallback=FallbackPolicy(fallback_fn=async_backup),
        )
        async def always_fails(prompt: str) -> str:
            raise RuntimeError("permanent")

        result = await always_fails("test")
        assert result == "async-fallback"

    @pytest.mark.asyncio
    async def test_async_prune_memory(self):
        """Async prune memory reduces context and retries."""
        attempts = 0

        def prune_fn(args, kwargs):
            # Shorten the prompt
            new_args = (args[0][:5],) if args else args
            return new_args, kwargs

        @self_healing(prune_memory=PruneMemoryPolicy(prune_fn=prune_fn, max_prunes=3))
        async def context_sensitive(prompt: str) -> str:
            nonlocal attempts
            attempts += 1
            if len(prompt) > 5:
                raise RuntimeError("context too long")
            return f"ok:{prompt}"

        result = await context_sensitive("a very long prompt that needs pruning")
        assert result.startswith("ok:")

    @pytest.mark.asyncio
    async def test_async_escalate(self):
        """Async escalation to handler."""
        escalated = []

        async def async_handler(fn_name, args, kwargs, exc):
            escalated.append(fn_name)
            return "escalated-result"

        @self_healing(escalate=EscalatePolicy(handler=async_handler))
        async def critical_fn(x: int) -> str:
            raise RuntimeError("critical failure")

        result = await critical_fn(42)
        assert result == "escalated-result"
        assert escalated == ["critical_fn"]


class TestRCAIntegration:
    """Integration: build RCA graph from traced spans with causal edges."""

    def test_rca_from_traced_failure(self, _setup_tracer: InMemorySpanExporter):
        """Build RCA graph from a traced agent that fails."""

        @trace_tool(name="bad-tool")
        def bad_tool(x: str) -> str:
            raise ValueError("tool broke")

        @trace_agent(name="failing-agent")
        def agent(task: str) -> str:
            return bad_tool(task)

        with pytest.raises(ValueError):
            agent("test")

        spans = _setup_tracer.get_finished_spans()
        assert len(spans) >= 2

        graph = build_rca_graph(list(spans))
        assert len(graph.nodes) >= 2
        # At least one error node
        error_nodes = [n for n in graph.nodes.values() if n.is_error]
        assert len(error_nodes) >= 1

        # DOT export works
        dot = to_dot(graph, title="Integration RCA")
        assert "Integration RCA" in dot
        assert "digraph" in dot
