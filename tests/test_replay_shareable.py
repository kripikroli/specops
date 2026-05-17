"""Tests for shareable replay sessions (export/import)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specops_ai.chaos import ChaosEvent, ChaosResult, ChaosType
from specops_ai.health import HealthReport, HealthSignal
from specops_ai.regression import BehaviorStep, GoldenRun
from specops_ai.replay import (
    RecordedCall,
    ReplayFile,
    ReplaySession,
    ReplayStore,
    export_replay,
    import_replay,
    recording,
    replayable,
    replaying,
)

# --- Fixtures ---


@pytest.fixture()
def sample_session() -> ReplaySession:
    return ReplaySession(
        session_id="test-share-1",
        seed=42,
        recorded_at="2026-01-01T00:00:00Z",
        calls=[
            RecordedCall(
                func_name="call_llm",
                args_hash="abc123",
                result="Paris is the capital of France.",
                timestamp="2026-01-01T00:00:01Z",
                call_index=0,
            ),
            RecordedCall(
                func_name="search",
                args_hash="def456",
                result=["r1", "r2"],
                timestamp="2026-01-01T00:00:02Z",
                call_index=1,
            ),
        ],
    )


@pytest.fixture()
def sample_health() -> HealthReport:
    return HealthReport(
        score=85.0,
        grade="B+",
        signals=[HealthSignal(name="loop_rate", value=0.95, weight=0.15)],
        agent_name="test-agent",
    )


@pytest.fixture()
def sample_chaos() -> ChaosResult:
    return ChaosResult(
        events=[
            ChaosEvent(
                chaos_type=ChaosType.HALLUCINATION,
                detected=True,
                healed=True,
                description="Injected hallucination",
            )
        ],
        total_injected=1,
        total_detected=1,
        total_healed=1,
    )


@pytest.fixture()
def sample_regression() -> GoldenRun:
    return GoldenRun(
        run_id="golden-1",
        agent_name="test-agent",
        task="answer question",
        steps=[BehaviorStep(name="llm_call", step_type="llm_call")],
        final_output="done",
        total_duration_ms=150.0,
    )


# --- export_replay tests ---


class TestExportReplay:
    def test_export_session_object(self, tmp_path: Path, sample_session: ReplaySession):
        out = export_replay(sample_session, tmp_path / "out.json")
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["version"] == "1.0"
        assert data["session"]["session_id"] == "test-share-1"
        assert data["session"]["seed"] == 42
        assert len(data["session"]["calls"]) == 2
        assert "python_version" in data["environment"]

    def test_export_by_session_id(self, tmp_path: Path, sample_session: ReplaySession):
        store = ReplayStore(base_dir=tmp_path / "replays")
        store.save(sample_session)
        out = export_replay("test-share-1", tmp_path / "out.json", store=store)
        data = json.loads(out.read_text())
        assert data["session"]["session_id"] == "test-share-1"

    def test_export_with_health(
        self, tmp_path: Path, sample_session: ReplaySession, sample_health: HealthReport
    ):
        out = export_replay(sample_session, tmp_path / "out.json", health=sample_health)
        data = json.loads(out.read_text())
        assert data["health"]["score"] == 85.0
        assert data["health"]["grade"] == "B+"

    def test_export_with_chaos(
        self, tmp_path: Path, sample_session: ReplaySession, sample_chaos: ChaosResult
    ):
        out = export_replay(sample_session, tmp_path / "out.json", chaos=sample_chaos)
        data = json.loads(out.read_text())
        assert data["chaos"]["total_injected"] == 1
        assert data["chaos"]["total_healed"] == 1

    def test_export_with_regression(
        self,
        tmp_path: Path,
        sample_session: ReplaySession,
        sample_regression: GoldenRun,
    ):
        out = export_replay(
            sample_session, tmp_path / "out.json", regression=sample_regression
        )
        data = json.loads(out.read_text())
        assert data["regression"]["run_id"] == "golden-1"
        assert data["regression"]["agent_name"] == "test-agent"

    def test_export_with_metadata(self, tmp_path: Path, sample_session: ReplaySession):
        out = export_replay(
            sample_session,
            tmp_path / "out.json",
            metadata={"author": "test", "purpose": "debug"},
        )
        data = json.loads(out.read_text())
        assert data["metadata"]["author"] == "test"

    def test_export_creates_parent_dirs(
        self, tmp_path: Path, sample_session: ReplaySession
    ):
        out = export_replay(sample_session, tmp_path / "nested" / "dir" / "out.json")
        assert out.exists()

    def test_export_full_bundle(
        self,
        tmp_path: Path,
        sample_session: ReplaySession,
        sample_health: HealthReport,
        sample_chaos: ChaosResult,
        sample_regression: GoldenRun,
    ):
        out = export_replay(
            sample_session,
            tmp_path / "full.json",
            health=sample_health,
            chaos=sample_chaos,
            regression=sample_regression,
            metadata={"team": "reliability"},
        )
        data = json.loads(out.read_text())
        assert data["session"] is not None
        assert data["health"] is not None
        assert data["chaos"] is not None
        assert data["regression"] is not None
        assert data["metadata"]["team"] == "reliability"


# --- import_replay tests ---


class TestImportReplay:
    def test_import_basic(self, tmp_path: Path, sample_session: ReplaySession):
        export_replay(sample_session, tmp_path / "out.json")
        rf = import_replay(tmp_path / "out.json")
        assert isinstance(rf, ReplayFile)
        assert rf.session is not None
        assert rf.session.session_id == "test-share-1"
        assert rf.session.seed == 42
        assert len(rf.session.calls) == 2

    def test_import_preserves_calls(
        self, tmp_path: Path, sample_session: ReplaySession
    ):
        export_replay(sample_session, tmp_path / "out.json")
        rf = import_replay(tmp_path / "out.json")
        assert rf.session is not None
        assert rf.session.calls[0].func_name == "call_llm"
        assert rf.session.calls[0].result == "Paris is the capital of France."
        assert rf.session.calls[1].func_name == "search"
        assert rf.session.calls[1].result == ["r1", "r2"]

    def test_import_with_diagnostics(
        self,
        tmp_path: Path,
        sample_session: ReplaySession,
        sample_health: HealthReport,
        sample_chaos: ChaosResult,
    ):
        export_replay(
            sample_session,
            tmp_path / "out.json",
            health=sample_health,
            chaos=sample_chaos,
        )
        rf = import_replay(tmp_path / "out.json")
        assert rf.health is not None
        assert rf.health["score"] == 85.0
        assert rf.chaos is not None
        assert rf.chaos["total_injected"] == 1

    def test_import_environment(self, tmp_path: Path, sample_session: ReplaySession):
        export_replay(sample_session, tmp_path / "out.json")
        rf = import_replay(tmp_path / "out.json")
        assert "python_version" in rf.environment
        assert "platform" in rf.environment

    def test_import_version(self, tmp_path: Path, sample_session: ReplaySession):
        export_replay(sample_session, tmp_path / "out.json")
        rf = import_replay(tmp_path / "out.json")
        assert rf.version == "1.0"


# --- Round-trip tests ---


class TestRoundTrip:
    def test_export_import_replay_deterministic(self, tmp_path: Path):
        """Full round-trip: record → export → import → replay produces same results."""

        @replayable
        def mock_llm(prompt: str) -> str:
            return f"answer to: {prompt}"

        store = ReplayStore(base_dir=tmp_path / "replays")

        # Record
        with recording(session_id="rt-1", seed=99, store=store) as session:
            r1 = mock_llm("hello")
            r2 = mock_llm("world")

        # Export
        export_replay(session, tmp_path / "shared.json")

        # Import
        rf = import_replay(tmp_path / "shared.json")
        assert rf.session is not None

        # Replay from imported session
        with replaying(rf.session) as _:
            assert mock_llm("hello") == r1
            assert mock_llm("world") == r2

    def test_export_import_with_dict_health(
        self, tmp_path: Path, sample_session: ReplaySession
    ):
        """Health can be passed as a plain dict too."""
        export_replay(
            sample_session,
            tmp_path / "out.json",
            health={"score": 90.0, "grade": "A"},
        )
        rf = import_replay(tmp_path / "out.json")
        assert rf.health == {"score": 90.0, "grade": "A"}

    def test_none_optionals_stay_none(
        self, tmp_path: Path, sample_session: ReplaySession
    ):
        export_replay(sample_session, tmp_path / "out.json")
        rf = import_replay(tmp_path / "out.json")
        assert rf.health is None
        assert rf.chaos is None
        assert rf.regression is None
