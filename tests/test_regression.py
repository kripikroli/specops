"""Tests for the behavioral regression testing engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from specops_ai.regression import (
    BehaviorStep,
    Drift,
    GoldenRun,
    RegressionError,
    RegressionResult,
    RegressionStore,
    _compute_score,
    _detect_loops,
    _edit_distance,
    check_regression,
    compare_behavior,
    golden,
    record_step,
    regression_test,
)

# --- RegressionStore Tests ---


class TestRegressionStore:
    def test_save_and_load(self, tmp_path: Path):
        store = RegressionStore(base_dir=tmp_path / "regressions")
        run = GoldenRun(
            run_id="test-1",
            agent_name="my-agent",
            task="summarize",
            steps=[
                BehaviorStep(name="search", step_type="tool_call", duration_ms=50.0),
                BehaviorStep(name="llm", step_type="llm_call", duration_ms=200.0),
            ],
            final_output="summary",
            total_duration_ms=250.0,
        )
        path = store.save(run)
        assert path.exists()

        loaded = store.load("test-1")
        assert loaded.run_id == "test-1"
        assert loaded.agent_name == "my-agent"
        assert len(loaded.steps) == 2
        assert loaded.steps[0].name == "search"
        assert loaded.final_output == "summary"

    def test_load_missing_raises(self, tmp_path: Path):
        store = RegressionStore(base_dir=tmp_path / "regressions")
        with pytest.raises(FileNotFoundError, match="not found"):
            store.load("nonexistent")

    def test_list_runs(self, tmp_path: Path):
        store = RegressionStore(base_dir=tmp_path / "regressions")
        assert store.list_runs() == []

        store.save(GoldenRun(run_id="a", agent_name="x", task="t"))
        store.save(GoldenRun(run_id="b", agent_name="x", task="t"))
        assert sorted(store.list_runs()) == ["a", "b"]


# --- Context Manager Tests ---


class TestGoldenContextManager:
    def test_records_steps(self, tmp_path: Path):
        store = RegressionStore(base_dir=tmp_path)
        with golden("run-1", agent_name="agent", task="test", store=store) as run:
            record_step("search", "tool_call", inputs={"q": "hello"})
            record_step("llm", "llm_call", outputs={"text": "world"})
            run.final_output = "done"

        assert len(run.steps) == 2
        assert run.steps[0].name == "search"
        assert run.steps[1].step_type == "llm_call"
        assert run.total_duration_ms > 0

        # Verify persisted
        loaded = store.load("run-1")
        assert len(loaded.steps) == 2

    def test_record_step_outside_context_returns_none(self):
        result = record_step("orphan", "action")
        assert result is None


class TestCheckRegressionContextManager:
    def test_passes_when_identical(self, tmp_path: Path):
        store = RegressionStore(base_dir=tmp_path)
        # Record golden
        with golden("g1", agent_name="a", task="t", store=store):
            record_step("search", "tool_call")
            record_step("llm", "llm_call")

        # Check regression with same behavior
        with check_regression("g1", store=store) as result:
            record_step("search", "tool_call")
            record_step("llm", "llm_call")

        assert result.passed
        assert result.score == 1.0
        assert result.drifts == []

    def test_detects_step_count_drift(self, tmp_path: Path):
        store = RegressionStore(base_dir=tmp_path)
        with golden("g2", store=store):
            record_step("a", "action")
            record_step("b", "action")

        with check_regression("g2", store=store) as result:
            record_step("a", "action")
            record_step("b", "action")
            record_step("c", "action")
            record_step("d", "action")

        assert not result.passed or result.score < 1.0
        types = [d.drift_type for d in result.drifts]
        assert "step_count" in types

    def test_detects_tool_usage_drift(self, tmp_path: Path):
        store = RegressionStore(base_dir=tmp_path)
        with golden("g3", store=store):
            record_step("search", "tool_call")
            record_step("llm", "llm_call")

        with check_regression("g3", store=store) as result:
            record_step("database", "tool_call")
            record_step("llm", "llm_call")

        types = [d.drift_type for d in result.drifts]
        assert "tool_usage" in types


# --- Compare Behavior Tests ---


class TestCompareBehavior:
    def test_identical_no_drifts(self):
        steps = [BehaviorStep(name="a", step_type="action")]
        assert compare_behavior(steps, steps) == []

    def test_step_count_drift(self):
        golden_steps = [BehaviorStep(name="a", step_type="action")]
        current_steps = [
            BehaviorStep(name="a", step_type="action"),
            BehaviorStep(name="b", step_type="action"),
            BehaviorStep(name="c", step_type="action"),
        ]
        drifts = compare_behavior(golden_steps, current_steps)
        assert any(d.drift_type == "step_count" for d in drifts)
        count_drift = next(d for d in drifts if d.drift_type == "step_count")
        assert count_drift.details["golden"] == 1
        assert count_drift.details["current"] == 3

    def test_step_order_drift(self):
        golden_steps = [
            BehaviorStep(name="search", step_type="tool_call"),
            BehaviorStep(name="summarize", step_type="llm_call"),
        ]
        current_steps = [
            BehaviorStep(name="summarize", step_type="llm_call"),
            BehaviorStep(name="search", step_type="tool_call"),
        ]
        drifts = compare_behavior(golden_steps, current_steps)
        assert any(d.drift_type == "step_order" for d in drifts)

    def test_tool_usage_drift(self):
        golden_steps = [BehaviorStep(name="search", step_type="tool_call")]
        current_steps = [BehaviorStep(name="database", step_type="tool_call")]
        drifts = compare_behavior(golden_steps, current_steps)
        tool_drift = next(d for d in drifts if d.drift_type == "tool_usage")
        assert "database" in tool_drift.details["added"]
        assert "search" in tool_drift.details["removed"]
        assert tool_drift.severity == "high"

    def test_loop_detection(self):
        golden_steps = [BehaviorStep(name="act", step_type="action")]
        current_steps = [BehaviorStep(name="act", step_type="action")] * 5
        drifts = compare_behavior(golden_steps, current_steps)
        assert any(d.drift_type == "loop" for d in drifts)
        loop_drift = next(d for d in drifts if d.drift_type == "loop")
        assert "loops" in loop_drift.message.lower()

    def test_timing_drift(self):
        golden_steps = [BehaviorStep(name="a", step_type="action", duration_ms=100.0)]
        current_steps = [BehaviorStep(name="a", step_type="action", duration_ms=300.0)]
        drifts = compare_behavior(golden_steps, current_steps)
        assert any(d.drift_type == "timing" for d in drifts)

    def test_no_timing_drift_when_similar(self):
        golden_steps = [BehaviorStep(name="a", step_type="action", duration_ms=100.0)]
        current_steps = [BehaviorStep(name="a", step_type="action", duration_ms=120.0)]
        drifts = compare_behavior(golden_steps, current_steps)
        assert not any(d.drift_type == "timing" for d in drifts)


# --- Utility Tests ---


class TestEditDistance:
    def test_identical(self):
        assert _edit_distance(["a", "b"], ["a", "b"]) == 0

    def test_insertion(self):
        assert _edit_distance(["a", "b"], ["a", "c", "b"]) == 1

    def test_deletion(self):
        assert _edit_distance(["a", "b", "c"], ["a", "c"]) == 1

    def test_empty(self):
        assert _edit_distance([], ["a", "b"]) == 2
        assert _edit_distance(["a"], []) == 1


class TestDetectLoops:
    def test_no_loops(self):
        assert _detect_loops(["a", "b", "c"]) == 0

    def test_detects_loops(self):
        assert _detect_loops(["a", "a", "a", "a"]) == 2  # 4 - 3 + 1 = 2

    def test_threshold(self):
        assert _detect_loops(["a", "a"], threshold=3) == 0
        assert _detect_loops(["a", "a", "a"], threshold=3) == 1


class TestComputeScore:
    def test_no_drifts(self):
        assert _compute_score([]) == 1.0

    def test_low_severity(self):
        drifts = [Drift(drift_type="x", severity="low", message="m")]
        assert _compute_score(drifts) == 0.95

    def test_high_severity(self):
        drifts = [Drift(drift_type="x", severity="high", message="m")]
        assert _compute_score(drifts) == 0.7

    def test_multiple_drifts(self):
        drifts = [
            Drift(drift_type="a", severity="high", message="m"),
            Drift(drift_type="b", severity="high", message="m"),
            Drift(drift_type="c", severity="medium", message="m"),
        ]
        score = _compute_score(drifts)
        assert score < 0.5


# --- Decorator Tests ---


class TestRegressionTestDecorator:
    def test_passes_when_behavior_matches(self, tmp_path: Path):
        store = RegressionStore(base_dir=tmp_path)
        # Record golden
        with golden("dec-1", agent_name="a", task="t", store=store):
            record_step("search", "tool_call")
            record_step("respond", "llm_call")

        @regression_test("dec-1", store=store)
        def my_agent(task: str) -> str:
            record_step("search", "tool_call")
            record_step("respond", "llm_call")
            return "result"

        result = my_agent("test")
        assert result == "result"

    def test_raises_on_regression(self, tmp_path: Path):
        store = RegressionStore(base_dir=tmp_path)
        with golden("dec-2", store=store):
            record_step("search", "tool_call")

        @regression_test("dec-2", store=store, threshold=0.9)
        def my_agent(task: str) -> str:
            # Completely different behavior
            record_step("x", "action")
            record_step("y", "action")
            record_step("z", "action")
            record_step("z", "action")
            record_step("z", "action")
            record_step("z", "action")
            return "result"

        with pytest.raises(RegressionError) as exc_info:
            my_agent("test")
        assert exc_info.value.score < 0.9
        assert len(exc_info.value.drifts) > 0


# --- RegressionResult Tests ---


class TestRegressionResult:
    def test_has_regressions(self):
        r = RegressionResult(
            passed=False,
            golden_run_id="x",
            drifts=[Drift(drift_type="a", severity="high", message="m")],
        )
        assert r.has_regressions

    def test_no_regressions(self):
        r = RegressionResult(
            passed=True,
            golden_run_id="x",
            drifts=[Drift(drift_type="a", severity="low", message="m")],
        )
        assert not r.has_regressions
