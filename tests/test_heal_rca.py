"""Tests for self-healing policies, RCA graph, and visualization."""

from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import specops
from specops import (
    EscalatePolicy,
    FallbackPolicy,
    HealingChain,
    PruneMemoryPolicy,
    RCAEdge,
    RCAGraph,
    RCANode,
    RetryPolicy,
    build_rca_graph,
    self_healing,
    to_dot,
    trace_agent,
    trace_llm,
)
from specops.heal import HEAL_OUTCOME, HEAL_POLICY


@pytest.fixture(autouse=True)
def _setup_tracer(monkeypatch: pytest.MonkeyPatch):
    """Set up in-memory exporter for each test."""
    specops.reset()

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    monkeypatch.setattr(
        trace, "_TRACER_PROVIDER_SET_ONCE", trace._TRACER_PROVIDER_SET_ONCE.__class__()
    )
    trace.set_tracer_provider(provider)

    monkeypatch.setattr("specops.config._configured", True)
    monkeypatch.setattr("specops.config._tracer", provider.get_tracer("specops-test"))

    yield exporter

    provider.shutdown()


# --- Self-Healing Tests ---


class TestRetryPolicy:
    def test_retry_succeeds_on_second_attempt(
        self, _setup_tracer: InMemorySpanExporter
    ) -> None:
        call_count = 0

        @self_healing(retry=RetryPolicy(max_retries=3, base_delay=0.01))
        def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("fail")
            return "ok"

        result = flaky()
        assert result == "ok"
        assert call_count == 2

    def test_retry_exhausted_raises(self) -> None:
        @self_healing(retry=RetryPolicy(max_retries=2, base_delay=0.01))
        def always_fails() -> str:
            raise ValueError("always")

        with pytest.raises(ValueError, match="always"):
            always_fails()

    def test_retry_respects_retryable_predicate(self) -> None:
        @self_healing(
            retry=RetryPolicy(
                max_retries=3,
                base_delay=0.01,
                retryable=lambda e: isinstance(e, TimeoutError),
            )
        )
        def wrong_error() -> str:
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            wrong_error()

    def test_exponential_backoff_calculation(self) -> None:
        policy = RetryPolicy(base_delay=1.0, max_delay=10.0)
        assert policy.get_delay(1) == 1.0
        assert policy.get_delay(2) == 2.0
        assert policy.get_delay(3) == 4.0
        assert policy.get_delay(4) == 8.0
        assert policy.get_delay(5) == 10.0  # capped


class TestFallbackPolicy:
    def test_fallback_on_failure(self) -> None:
        def backup(x: int) -> int:
            return x * 10

        @self_healing(fallback=FallbackPolicy(fallback_fn=backup))
        def primary(x: int) -> int:
            raise RuntimeError("primary down")

        assert primary(5) == 50

    def test_fallback_trigger_predicate(self) -> None:
        def backup() -> str:
            return "backup"

        @self_healing(
            fallback=FallbackPolicy(
                fallback_fn=backup,
                trigger=lambda e: isinstance(e, TimeoutError),
            )
        )
        def primary() -> str:
            raise ValueError("not a timeout")

        # Fallback should NOT trigger for ValueError
        with pytest.raises(ValueError):
            primary()


class TestEscalatePolicy:
    def test_escalate_calls_handler(self) -> None:
        escalated: list[str] = []

        def handler(fn_name: str, args: object, kwargs: object, exc: Exception) -> str:
            escalated.append(fn_name)
            return "human answer"

        @self_healing(escalate=EscalatePolicy(handler=handler))
        def failing() -> str:
            raise RuntimeError("need human")

        result = failing()
        assert result == "human answer"
        assert escalated == ["failing"]


class TestPruneMemoryPolicy:
    def test_prune_and_retry(self) -> None:
        def prune(
            args: tuple[object, ...], kwargs: dict[str, object]
        ) -> tuple[tuple[object, ...], dict[str, object]]:
            prompt = str(args[0])
            return (prompt[len(prompt) // 2 :],), kwargs

        @self_healing(prune_memory=PruneMemoryPolicy(prune_fn=prune, max_prunes=3))
        def token_limited(prompt: str) -> str:
            if len(prompt) > 10:
                raise ValueError("too long")
            return f"ok:{prompt}"

        result = token_limited("a" * 80)
        assert result.startswith("ok:")
        assert len(result) < 20


class TestHealingChain:
    def test_chain_tries_policies_in_order(self) -> None:
        attempts: list[str] = []

        def fallback() -> str:
            attempts.append("fallback")
            return "fallback_result"

        chain = HealingChain()
        chain.add(RetryPolicy(max_retries=1, base_delay=0.01))
        chain.add(FallbackPolicy(fallback_fn=fallback))

        @self_healing(chain=chain)
        def always_fails() -> str:
            attempts.append("primary")
            raise RuntimeError("fail")

        result = always_fails()
        assert result == "fallback_result"
        # Primary called once, retry called once, then fallback
        assert "fallback" in attempts


class TestSelfHealingSpanAttributes:
    def test_healed_span_attributes(self, _setup_tracer: InMemorySpanExporter) -> None:
        call_count = 0

        @self_healing(retry=RetryPolicy(max_retries=2, base_delay=0.01))
        def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("fail")
            return "ok"

        flaky()
        spans = _setup_tracer.get_finished_spans()
        heal_spans = [s for s in spans if s.name.startswith("heal:")]
        assert len(heal_spans) == 1
        attrs = dict(heal_spans[0].attributes or {})
        assert attrs[HEAL_OUTCOME] == "healed"
        assert attrs[HEAL_POLICY] == "retry"


# --- Async Self-Healing Tests ---


class TestAsyncSelfHealing:
    @pytest.mark.asyncio
    async def test_async_retry(self) -> None:
        call_count = 0

        @self_healing(retry=RetryPolicy(max_retries=3, base_delay=0.01))
        async def flaky_async() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("fail")
            return "async_ok"

        result = await flaky_async()
        assert result == "async_ok"

    @pytest.mark.asyncio
    async def test_async_fallback(self) -> None:
        async def backup() -> str:
            return "async_backup"

        @self_healing(fallback=FallbackPolicy(fallback_fn=backup))
        async def primary() -> str:
            raise RuntimeError("down")

        result = await primary()
        assert result == "async_backup"


# --- RCA Graph Tests ---


class TestRCAGraph:
    def test_build_graph_from_spans(self, _setup_tracer: InMemorySpanExporter) -> None:
        @trace_agent(name="test-agent")
        def agent(task: str) -> str:
            @trace_llm(model="gpt-4o")
            def llm(prompt: str) -> dict[str, str | int]:
                raise ValueError("LLM error")

            import contextlib

            with contextlib.suppress(ValueError):
                llm("test")
            return "done"

        agent("test task")
        spans = list(_setup_tracer.get_finished_spans())
        graph = build_rca_graph(spans)

        assert len(graph.nodes) == 2
        assert len(graph.edges) >= 1
        assert len(graph.error_nodes) == 1

    def test_root_causes_identification(self) -> None:
        graph = RCAGraph()
        graph.add_node(
            RCANode(span_id="a", name="parent", status="error", error_message="cascade")
        )
        graph.add_node(
            RCANode(span_id="b", name="child", status="error", error_message="root")
        )
        graph.add_edge(RCAEdge(source="a", target="b"))

        roots = graph.root_causes
        # "a" is error parent, "b" is error child → "a" is root cause
        # (child with error parent is NOT root cause)
        assert len(roots) == 1
        assert roots[0].span_id == "a"

    def test_infection_paths(self) -> None:
        graph = RCAGraph()
        graph.add_node(RCANode(span_id="a", name="root", status="error"))
        graph.add_node(RCANode(span_id="b", name="mid", status="error"))
        graph.add_node(RCANode(span_id="c", name="leaf", status="ok"))
        graph.add_edge(RCAEdge(source="a", target="b"))
        graph.add_edge(RCAEdge(source="b", target="c"))

        paths = graph.infection_paths
        assert len(paths) == 1
        assert paths[0] == ["a", "b"]

    def test_empty_graph(self) -> None:
        graph = RCAGraph()
        assert graph.root_causes == []
        assert graph.infection_paths == []
        assert graph.error_nodes == []


# --- Visualization Tests ---


class TestVisualization:
    def test_to_dot_basic(self) -> None:
        graph = RCAGraph()
        graph.add_node(RCANode(span_id="1", name="agent:test", status="ok"))
        graph.add_node(
            RCANode(
                span_id="2", name="llm:gpt-4o", status="error", error_message="timeout"
            )
        )
        graph.add_edge(RCAEdge(source="1", target="2"))

        dot = to_dot(graph, title="Test")
        assert 'digraph "Test"' in dot
        assert "#ff6b6b" in dot  # error color
        assert "#69db7c" in dot  # ok color
        assert "timeout" in dot

    def test_to_dot_causal_edges(self) -> None:
        graph = RCAGraph()
        graph.add_node(RCANode(span_id="a", name="parent", status="error"))
        graph.add_node(RCANode(span_id="b", name="child", status="error"))
        graph.add_edge(RCAEdge(source="b", target="a", relationship="caused_by"))

        dot = to_dot(graph)
        assert "dashed" in dot
        assert 'color="red"' in dot

    def test_to_dot_empty_graph(self) -> None:
        graph = RCAGraph()
        dot = to_dot(graph)
        assert "digraph" in dot
        assert "}" in dot
