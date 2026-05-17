"""Tests for the Agent Health Score engine.

All tests are fully mocked — no real API calls. Tests cover the core
compute_health_score function, HealthReport/HealthSignal dataclasses,
the @health_check decorator, custom weights, edge cases, and grading.
"""

from __future__ import annotations

import pytest

from specops_ai.health import (
    DEFAULT_WEIGHTS,
    HealthCheckFailed,
    HealthReport,
    HealthSignal,
    _clamp,
    _extract_signals,
    _grade,
    compute_health_score,
    health_check,
)

# === HealthSignal Dataclass ===


class TestHealthSignal:
    def test_defaults(self):
        s = HealthSignal(name="loop_rate", value=0.85)
        assert s.name == "loop_rate"
        assert s.value == 0.85
        assert s.weight == 0.0
        assert s.details == ""

    def test_custom_values(self):
        s = HealthSignal(name="consensus", value=1.0, weight=0.15, details="all passed")
        assert s.weight == 0.15
        assert s.details == "all passed"


# === HealthReport Dataclass ===


class TestHealthReport:
    def test_passed_above_threshold(self):
        r = HealthReport(score=75.0, grade="C")
        assert r.passed is True

    def test_failed_below_threshold(self):
        r = HealthReport(score=49.9, grade="F")
        assert r.passed is False

    def test_passed_at_boundary(self):
        r = HealthReport(score=50.0, grade="D")
        assert r.passed is True

    def test_agent_name(self):
        r = HealthReport(score=90.0, grade="A", agent_name="my-agent")
        assert r.agent_name == "my-agent"


# === Grade Helper ===


class TestGrade:
    def test_grade_a(self):
        assert _grade(90.0) == "A"
        assert _grade(100.0) == "A"

    def test_grade_b(self):
        assert _grade(80.0) == "B"
        assert _grade(89.9) == "B"

    def test_grade_c(self):
        assert _grade(70.0) == "C"
        assert _grade(79.9) == "C"

    def test_grade_d(self):
        assert _grade(60.0) == "D"
        assert _grade(69.9) == "D"

    def test_grade_f(self):
        assert _grade(0.0) == "F"
        assert _grade(59.9) == "F"


# === Clamp Helper ===


class TestClamp:
    def test_within_range(self):
        assert _clamp(0.5) == 0.5

    def test_below_zero(self):
        assert _clamp(-0.5) == 0.0

    def test_above_one(self):
        assert _clamp(1.5) == 1.0

    def test_boundaries(self):
        assert _clamp(0.0) == 0.0
        assert _clamp(1.0) == 1.0


# === compute_health_score ===


class TestComputeHealthScore:
    def test_perfect_score(self):
        report = compute_health_score(
            loop_rate=0.0,
            consensus=1.0,
            memory_integrity=1.0,
            self_healing=1.0,
            chaos_resilience=1.0,
            regression_stability=1.0,
            anomaly_frequency=0.0,
        )
        assert report.score == 100.0
        assert report.grade == "A"

    def test_worst_score(self):
        report = compute_health_score(
            loop_rate=1.0,
            consensus=0.0,
            memory_integrity=0.0,
            self_healing=0.0,
            chaos_resilience=0.0,
            regression_stability=0.0,
            anomaly_frequency=1.0,
        )
        assert report.score == 0.0
        assert report.grade == "F"

    def test_default_values_give_perfect(self):
        report = compute_health_score()
        assert report.score == 100.0

    def test_partial_degradation(self):
        report = compute_health_score(loop_rate=0.5, consensus=0.5)
        assert 50.0 < report.score < 100.0

    def test_custom_weights(self):
        # Only care about self_healing
        report = compute_health_score(
            self_healing=0.5,
            weights={"self_healing": 1.0},
        )
        assert report.score == 50.0

    def test_signals_in_report(self):
        report = compute_health_score(loop_rate=0.2)
        assert len(report.signals) == 7
        names = [s.name for s in report.signals]
        assert "loop_rate" in names
        assert "consensus" in names

    def test_agent_name_in_report(self):
        report = compute_health_score(agent_name="test-agent")
        assert report.agent_name == "test-agent"

    def test_clamping_out_of_range(self):
        report = compute_health_score(loop_rate=2.0, anomaly_frequency=-1.0)
        # loop_rate clamped to 1.0 → signal = 0.0
        # anomaly_frequency clamped to 0.0 → signal = 1.0
        assert 0.0 <= report.score <= 100.0

    def test_empty_weights(self):
        # All zero weights → total_weight fallback to 1.0
        report = compute_health_score(
            weights={"loop_rate": 0.0, "consensus": 0.0},
        )
        assert report.score == 0.0

    def test_single_signal_weight(self):
        report = compute_health_score(
            consensus=0.8,
            weights={"consensus": 1.0},
        )
        assert report.score == 80.0


# === _extract_signals ===


class TestExtractSignals:
    def test_dict_with_known_keys(self):
        result = {"loop_rate": 0.1, "consensus": 0.9, "unknown": 42}
        signals = _extract_signals(result)
        assert signals == {"loop_rate": 0.1, "consensus": 0.9}

    def test_non_dict_returns_empty(self):
        assert _extract_signals("hello") == {}
        assert _extract_signals(42) == {}
        assert _extract_signals(None) == {}

    def test_empty_dict(self):
        assert _extract_signals({}) == {}


# === @health_check Decorator ===


class TestHealthCheckDecorator:
    def test_passes_when_healthy(self):
        @health_check(name="test-agent", threshold=50.0)
        def agent():
            return {"self_healing": 1.0, "consensus": 1.0}

        result = agent()
        assert result == {"self_healing": 1.0, "consensus": 1.0}
        assert agent.last_health_report is not None
        assert agent.last_health_report.score >= 50.0

    def test_raises_when_unhealthy(self):
        @health_check(name="bad-agent", threshold=80.0)
        def agent():
            return {"self_healing": 0.0, "consensus": 0.0, "loop_rate": 1.0}

        with pytest.raises(HealthCheckFailed) as exc_info:
            agent()
        assert exc_info.value.report.score < 80.0

    def test_custom_weights_in_decorator(self):
        @health_check(weights={"consensus": 1.0}, threshold=0.0)
        def agent():
            return {"consensus": 0.7}

        agent()
        assert agent.last_health_report.score == 70.0

    def test_non_dict_result_uses_defaults(self):
        @health_check(threshold=0.0)
        def agent():
            return "plain string"

        result = agent()
        assert result == "plain string"
        assert agent.last_health_report.score == 100.0

    def test_initial_report_is_none(self):
        @health_check(threshold=0.0)
        def agent():
            return {}

        assert agent.last_health_report is None

    def test_preserves_function_name(self):
        @health_check(threshold=0.0)
        def my_agent():
            return {}

        assert my_agent.__name__ == "my_agent"


# === DEFAULT_WEIGHTS ===


class TestDefaultWeights:
    def test_all_signals_present(self):
        expected = {
            "loop_rate",
            "consensus",
            "memory_integrity",
            "self_healing",
            "chaos_resilience",
            "regression_stability",
            "anomaly_frequency",
        }
        assert set(DEFAULT_WEIGHTS.keys()) == expected

    def test_weights_sum_to_one(self):
        assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9

    def test_all_positive(self):
        assert all(v > 0 for v in DEFAULT_WEIGHTS.values())


# === HealthCheckFailed Exception ===


class TestHealthCheckFailed:
    def test_message_contains_score(self):
        report = HealthReport(score=30.0, grade="F")
        exc = HealthCheckFailed(report)
        assert "30.0" in str(exc)
        assert "F" in str(exc)

    def test_report_attached(self):
        report = HealthReport(score=45.0, grade="F")
        exc = HealthCheckFailed(report)
        assert exc.report is report
