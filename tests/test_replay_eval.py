"""Tests for the replay engine and evaluation harness."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from specops_ai.eval import (
    EvalCase,
    _default_comparator,
    _parse_judge_response,
    eval_golden_set,
    eval_golden_set_async,
    llm_judge,
    llm_judge_async,
)
from specops_ai.replay import (
    RecordedCall,
    ReplayMismatchError,
    ReplaySession,
    ReplayStore,
    _hash_args,
    recording,
    replayable,
    replaying,
)

# --- Replay Engine Tests ---


class TestReplayStore:
    def test_save_and_load(self, tmp_path: Path):
        store = ReplayStore(base_dir=tmp_path / "replays")
        session = ReplaySession(
            session_id="test-1",
            seed=42,
            recorded_at="2026-01-01T00:00:00Z",
            calls=[
                RecordedCall(
                    func_name="my_func",
                    args_hash="abc123",
                    result="hello",
                    timestamp="2026-01-01T00:00:01Z",
                    call_index=0,
                )
            ],
        )
        path = store.save(session)
        assert path.exists()

        loaded = store.load("test-1")
        assert loaded.session_id == "test-1"
        assert loaded.seed == 42
        assert len(loaded.calls) == 1
        assert loaded.calls[0].result == "hello"

    def test_list_sessions(self, tmp_path: Path):
        store = ReplayStore(base_dir=tmp_path / "replays")
        assert store.list_sessions() == []

        s1 = ReplaySession(session_id="a", seed=1, recorded_at="t")
        s2 = ReplaySession(session_id="b", seed=2, recorded_at="t")
        store.save(s1)
        store.save(s2)
        assert sorted(store.list_sessions()) == ["a", "b"]


class TestHashArgs:
    def test_deterministic(self):
        h1 = _hash_args(("hello",), {"x": 1})
        h2 = _hash_args(("hello",), {"x": 1})
        assert h1 == h2

    def test_different_args(self):
        h1 = _hash_args(("a",), {})
        h2 = _hash_args(("b",), {})
        assert h1 != h2


class TestRecording:
    def test_record_and_replay_sync(self, tmp_path: Path):
        store = ReplayStore(base_dir=tmp_path / "replays")

        @replayable
        def nondeterministic() -> int:
            return random.randint(1, 1000000)

        # Record
        with recording(session_id="s1", seed=99, store=store) as session:
            r1 = nondeterministic()
            r2 = nondeterministic()

        assert len(session.calls) == 2
        assert session.seed == 99

        # Replay
        with replaying("s1", store=store):
            r1_replay = nondeterministic()
            r2_replay = nondeterministic()

        assert r1 == r1_replay
        assert r2 == r2_replay

    @pytest.mark.asyncio
    async def test_record_and_replay_async(self, tmp_path: Path):
        store = ReplayStore(base_dir=tmp_path / "replays")

        @replayable
        async def async_random() -> int:
            return random.randint(1, 1000000)

        with recording(session_id="async-s1", seed=7, store=store) as session:
            r1 = await async_random()

        assert len(session.calls) == 1

        with replaying("async-s1", store=store):
            r1_replay = await async_random()

        assert r1 == r1_replay

    def test_replay_from_path(self, tmp_path: Path):
        store = ReplayStore(base_dir=tmp_path / "replays")

        @replayable
        def get_val() -> str:
            return f"val-{random.randint(1, 100)}"

        with recording(session_id="path-test", seed=5, store=store) as session:  # noqa: F841
            original = get_val()

        # Replay from file path
        json_path = tmp_path / "replays" / "path-test.json"
        with replaying(json_path):
            replayed = get_val()

        assert original == replayed

    def test_replay_mismatch_error(self, tmp_path: Path):
        store = ReplayStore(base_dir=tmp_path / "replays")

        @replayable
        def func_a() -> str:
            return "a"

        @replayable
        def func_b() -> str:
            return "b"

        with recording(session_id="mismatch", seed=1, store=store):
            func_a()

        with replaying("mismatch", store=store), pytest.raises(ReplayMismatchError):
            func_b()

    def test_no_context_passthrough(self):
        """Without recording/replaying context, functions execute normally."""

        @replayable
        def normal_fn(x: int) -> int:
            return x * 2

        assert normal_fn(5) == 10

    def test_deterministic_seed(self, tmp_path: Path):
        store = ReplayStore(base_dir=tmp_path / "replays")

        results: list[int] = []

        @replayable
        def seeded_fn() -> int:
            return random.randint(1, 1000000)

        # Same seed should produce same random sequence
        with recording(session_id="seed-a", seed=42, store=store):
            results.append(seeded_fn())

        with recording(session_id="seed-b", seed=42, store=store):
            results.append(seeded_fn())

        assert results[0] == results[1]


class TestReplayableDecorator:
    def test_preserves_function_name(self):
        @replayable
        def my_function() -> str:
            """My docstring."""
            return "hi"

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."


# --- Evaluation Harness Tests ---


class TestDefaultComparator:
    def test_exact_match(self):
        assert _default_comparator("hello", "hello") == 1.0

    def test_case_insensitive_match(self):
        assert _default_comparator("Hello", "hello") == 0.9

    def test_no_match(self):
        assert _default_comparator("hello", "world") == 0.0


class TestEvalGoldenSet:
    def test_all_pass(self):
        def agent(x: str) -> str:
            return x.upper()

        cases = [
            EvalCase(input="hello", expected="HELLO"),
            EvalCase(input="world", expected="WORLD"),
        ]
        results = eval_golden_set(agent, cases)
        assert all(r.passed for r in results)
        assert all(r.score == 1.0 for r in results)

    def test_partial_pass(self):
        def agent(x: str) -> str:
            return "HELLO" if x == "hello" else "wrong"

        cases = [
            EvalCase(input="hello", expected="HELLO"),
            EvalCase(input="world", expected="WORLD"),
        ]
        results = eval_golden_set(agent, cases)
        assert results[0].passed
        assert not results[1].passed

    def test_custom_comparator(self):
        def agent(x: int) -> int:
            return x + 1

        def close_enough(expected: int, actual: int) -> float:
            return 1.0 if abs(expected - actual) <= 1 else 0.0

        cases = [EvalCase(input=5, expected=7)]
        results = eval_golden_set(agent, cases, comparator=close_enough)
        assert results[0].passed  # 6 is within 1 of 7

    def test_exception_handling(self):
        def bad_agent(x: str) -> str:
            raise ValueError("boom")

        cases = [EvalCase(input="x", expected="y")]
        results = eval_golden_set(bad_agent, cases)
        assert not results[0].passed
        assert results[0].score == 0.0
        assert "Exception" in results[0].details

    @pytest.mark.asyncio
    async def test_async_eval(self):
        async def agent(x: str) -> str:
            return x.upper()

        cases = [EvalCase(input="hi", expected="HI")]
        results = await eval_golden_set_async(agent, cases)
        assert results[0].passed


class TestLlmJudge:
    def test_json_response(self):
        def mock_llm(prompt: str) -> str:
            return '{"score": 0.85, "reasoning": "Good answer"}'

        verdict = llm_judge("test output", criteria="quality", judge_fn=mock_llm)
        assert verdict.score == 0.85
        assert verdict.reasoning == "Good answer"
        assert verdict.criteria == "quality"

    def test_markdown_json_response(self):
        def mock_llm(prompt: str) -> str:
            return '```json\n{"score": 0.7, "reasoning": "Decent"}\n```'

        verdict = llm_judge("output", criteria="accuracy", judge_fn=mock_llm)
        assert verdict.score == 0.7

    def test_fallback_parsing(self):
        def mock_llm(prompt: str) -> str:
            return "I'd give this a 0.6 out of 1.0"

        verdict = llm_judge("output", criteria="quality", judge_fn=mock_llm)
        assert verdict.score == 0.6

    def test_with_context(self):
        prompts_received: list[str] = []

        def mock_llm(prompt: str) -> str:
            prompts_received.append(prompt)
            return '{"score": 1.0, "reasoning": "Perfect"}'

        llm_judge(
            "answer",
            criteria="correctness",
            judge_fn=mock_llm,
            context="User asked about Python",
        )
        assert "Python" in prompts_received[0]

    @pytest.mark.asyncio
    async def test_async_judge(self):
        async def mock_llm(prompt: str) -> str:
            return '{"score": 0.9, "reasoning": "Great"}'

        verdict = await llm_judge_async("output", criteria="quality", judge_fn=mock_llm)
        assert verdict.score == 0.9


class TestParseJudgeResponse:
    def test_valid_json(self):
        v = _parse_judge_response('{"score": 0.5, "reasoning": "ok"}', "test")
        assert v.score == 0.5

    def test_invalid_json_with_number(self):
        v = _parse_judge_response("The score is 0.8 because...", "test")
        assert v.score == 0.8

    def test_no_number_fallback(self):
        v = _parse_judge_response("no numbers here", "test")
        assert v.score == 0.0

    def test_score_capped_at_1(self):
        v = _parse_judge_response("score: 5.0", "test")
        assert v.score == 1.0
