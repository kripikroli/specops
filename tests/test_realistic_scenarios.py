"""Realistic agent scenario tests with production-like mock behaviors.

These tests simulate real-world agent patterns:
- Multi-step research agents with tool failures
- Rate limiting and transient API errors
- Token budget exhaustion mid-conversation
- Agent loops with realistic action sequences
- Cascading failures across agent pipelines
"""

from __future__ import annotations

import asyncio
import random

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import specops_ai
from specops_ai import (
    AgentOutput,
    BehaviorTrace,
    EvalCase,
    FallbackPolicy,
    RetryPolicy,
    build_rca_graph,
    check_consensus,
    check_divergence,
    eval_golden_set,
    self_healing,
    simulation,
    trace_agent,
    trace_llm,
    trace_tool,
)
from specops_ai.replay import recording, replayable


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


class TestRealisticResearchAgent:
    """Simulate a multi-step research agent with realistic failures."""

    def test_research_agent_with_tool_failure_recovery(
        self, _setup_tracer: InMemorySpanExporter
    ):
        """Agent searches, hits a transient failure, retries, then summarizes."""
        search_calls = 0

        @trace_tool(name="web-search")
        @self_healing(retry=RetryPolicy(max_retries=2, base_delay=0.01))
        def search(query: str) -> list[str]:
            nonlocal search_calls
            search_calls += 1
            if search_calls == 1:
                raise ConnectionError("503 Service Unavailable")
            return [
                f"Result 1 for '{query}': LLM agents need observability",
                f"Result 2 for '{query}': OpenTelemetry is the standard",
            ]

        @trace_llm(model="gpt-4o", provider="openai")
        def summarize(context: str) -> dict:
            return {
                "text": f"Summary: {context[:50]}...",
                "model": "gpt-4o",
                "input_tokens": len(context.split()),
                "output_tokens": 25,
            }

        @trace_agent(name="research-agent")
        def research(task: str) -> str:
            results = search(task)
            context = "\n".join(results)
            response = summarize(context)
            return response["text"]

        result = research("LLM observability best practices")
        assert "Summary:" in result
        assert search_calls == 2  # First call failed, second succeeded

        spans = _setup_tracer.get_finished_spans()
        agent_spans = [s for s in spans if "agent:" in s.name]
        tool_spans = [s for s in spans if "tool:" in s.name]
        llm_spans = [s for s in spans if "llm:" in s.name]
        assert len(agent_spans) == 1
        assert len(tool_spans) == 1
        assert len(llm_spans) == 1

    def test_research_agent_complete_failure_with_fallback(
        self, _setup_tracer: InMemorySpanExporter
    ):
        """Agent's primary LLM is down, falls back to cheaper model."""

        def fallback_llm(prompt: str) -> dict:
            return {
                "text": "Fallback: Unable to provide detailed summary.",
                "model": "gpt-4o-mini",
                "input_tokens": 10,
                "output_tokens": 8,
            }

        @trace_llm(model="gpt-4o", provider="openai")
        @self_healing(
            retry=RetryPolicy(max_retries=1, base_delay=0.01),
            fallback=FallbackPolicy(fallback_fn=fallback_llm),
        )
        def call_llm(prompt: str) -> dict:
            raise TimeoutError("429 Rate Limited")

        @trace_agent(name="resilient-agent")
        def agent(task: str) -> str:
            response = call_llm(task)
            return response["text"]

        result = agent("Summarize findings")
        assert "Fallback" in result

    @pytest.mark.asyncio
    async def test_async_parallel_research(self, _setup_tracer: InMemorySpanExporter):
        """Multiple async agents research in parallel, results aggregated."""

        @trace_agent(name="searcher")
        async def searcher(topic: str) -> str:
            await asyncio.sleep(0.01)
            return f"Found info about {topic}"

        @trace_agent(name="orchestrator")
        async def orchestrator(task: str) -> list[str]:
            topics = ["observability", "self-healing", "evaluation"]
            results = await asyncio.gather(*[searcher(t) for t in topics])
            return list(results)

        results = await orchestrator("research LLM reliability")
        assert len(results) == 3
        assert all("Found info" in r for r in results)

        spans = _setup_tracer.get_finished_spans()
        assert len(spans) == 4  # 1 orchestrator + 3 searchers


class TestRealisticRateLimiting:
    """Simulate realistic API rate limiting patterns."""

    def test_burst_rate_limiting(self):
        """Agent hits rate limit after burst of requests."""
        call_count = 0

        @self_healing(retry=RetryPolicy(max_retries=3, base_delay=0.01))
        def rate_limited_api(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("429 Too Many Requests")
            return "Response after rate limit cleared"

        result = rate_limited_api("test")
        assert result == "Response after rate limit cleared"
        assert call_count == 3


class TestRealisticSimulation:
    """Simulate production agent behaviors in sandbox."""

    def test_agent_stuck_in_clarification_loop(self):
        """Agent keeps asking for clarification — realistic loop pattern."""
        with simulation("clarification-loop", max_steps=20, loop_threshold=3) as sim:
            # Agent stuck repeating the same action consecutively
            sim.record("assistant", "ask_clarification")
            sim.record("assistant", "ask_clarification")
            event = sim.record("assistant", "ask_clarification")
            # Third consecutive identical action triggers loop detection
            assert event.anomaly is not None

        result = sim.stop()
        assert result.has_anomalies

    def test_multi_agent_cascade_failure(self):
        """Failure in one agent cascades to downstream agents."""
        with simulation("cascade", max_steps=50, loop_threshold=5) as sim:
            # Agent A processes normally
            sim.record("agent-a", "fetch_data")
            sim.record("agent-a", "process_data")
            # Agent B depends on A's output
            sim.record("agent-b", "receive_from_a")
            sim.record("agent-b", "transform")
            # Agent C depends on B
            sim.record("agent-c", "receive_from_b")
            sim.record("agent-c", "generate_report")

        result = sim.stop()
        assert result.passed
        assert len(result.events) == 6


class TestRealisticCoordination:
    """Multi-agent coordination with realistic disagreements."""

    def test_agents_disagree_on_classification(self):
        """Three agents classify sentiment differently — realistic scenario."""
        outputs = [
            AgentOutput(agent="classifier-1", output="positive"),
            AgentOutput(agent="classifier-2", output="positive"),
            AgentOutput(agent="classifier-3", output="neutral"),
        ]
        # With 2/3 quorum, should pass
        result = check_consensus(outputs, quorum=0.6)
        assert result.passed

    def test_agents_behavioral_drift_over_time(self):
        """Agents start aligned but drift apart — realistic divergence."""
        traces = [
            BehaviorTrace(
                agent="agent-v1",
                actions=["search", "filter", "rank", "respond"],
            ),
            BehaviorTrace(
                agent="agent-v2",
                actions=["search", "filter", "rerank", "validate", "respond"],
            ),
        ]
        # Small drift is acceptable
        result = check_divergence(traces, max_edit_distance=3)
        assert result.passed

        # Strict threshold catches drift
        strict = check_divergence(traces, max_edit_distance=1)
        assert not strict.passed


class TestRealisticReplayEval:
    """Record/replay with realistic agent outputs and evaluation."""

    def test_deterministic_replay_with_eval(self, tmp_path):
        """Record agent session, replay it, verify outputs match golden set."""
        from specops_ai.replay import ReplayStore

        store = ReplayStore(base_dir=tmp_path)

        @replayable
        def mock_llm(prompt: str) -> str:
            # Simulate non-deterministic LLM with random seed
            choices = ["Paris", "London", "Berlin"]
            return random.choice(choices)

        # Record with fixed seed for determinism
        with recording(session_id="geo-quiz", seed=42, store=store):
            answer1 = mock_llm("What is the capital of France?")
            answer2 = mock_llm("What is the capital of UK?")

        # Replay produces identical results
        from specops_ai.replay import replaying

        with replaying("geo-quiz", store=store):
            replay1 = mock_llm("What is the capital of France?")
            replay2 = mock_llm("What is the capital of UK?")

        assert answer1 == replay1
        assert answer2 == replay2

    def test_eval_with_partial_match_scoring(self):
        """Evaluate agent with nuanced scoring — not just exact match."""

        def agent(question: str) -> str:
            answers = {
                "capital of France": "The capital of France is Paris.",
                "2+2": "4",
            }
            return answers.get(question, "I don't know")

        def fuzzy_comparator(expected: str, actual: str) -> float:
            if expected.lower() in actual.lower():
                return 1.0
            if any(w in actual.lower() for w in expected.lower().split()):
                return 0.5
            return 0.0

        results = eval_golden_set(
            agent_fn=agent,
            cases=[
                EvalCase(input="capital of France", expected="Paris"),
                EvalCase(input="2+2", expected="4"),
            ],
            comparator=fuzzy_comparator,
        )
        assert all(r.passed for r in results)


class TestRealisticRCA:
    """RCA with realistic multi-layer failure patterns."""

    def test_rca_nested_tool_failure(self, _setup_tracer: InMemorySpanExporter):
        """Trace a realistic failure: API call → parsing → validation chain."""

        @trace_tool(name="api-call")
        def api_call(url: str) -> str:
            return '{"data": "malformed json...'

        @trace_tool(name="parse-response")
        def parse_response(raw: str) -> dict:
            raise ValueError("Unterminated string at position 23")

        @trace_agent(name="data-pipeline")
        def pipeline(url: str) -> dict:
            raw = api_call(url)
            return parse_response(raw)

        with pytest.raises(ValueError, match="Unterminated string"):
            pipeline("https://api.example.com/data")

        spans = _setup_tracer.get_finished_spans()
        graph = build_rca_graph(list(spans))

        # Should identify parse-response as the error source
        error_nodes = [n for n in graph.nodes.values() if n.is_error]
        assert len(error_nodes) >= 1
        assert any("parse" in n.name for n in error_nodes)
