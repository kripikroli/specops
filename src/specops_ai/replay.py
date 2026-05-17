"""Deterministic replay engine for SpecOps.

Records non-deterministic function outputs during agent execution and replays
them deterministically for debugging and evaluation.
"""

from __future__ import annotations

import functools
import hashlib
import inspect
import json
import random
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

from opentelemetry import trace

from specops_ai._constants import REPLAY_SEED, REPLAY_SESSION_ID

F = TypeVar("F", bound=Callable[..., Any])

# --- Core Types ---


@dataclass
class RecordedCall:
    """A single recorded function call."""

    func_name: str
    args_hash: str
    result: Any
    timestamp: str
    call_index: int


@dataclass
class ReplaySession:
    """A recorded session containing all captured calls."""

    session_id: str
    seed: int
    recorded_at: str
    calls: list[RecordedCall] = field(default_factory=list)


# --- Context State ---


class _ReplayState:
    """Mutable state for the current replay context."""

    def __init__(self, mode: str, session: ReplaySession) -> None:
        self.mode = mode  # "record" or "replay"
        self.session = session
        self.call_counter = 0
        self.replay_index = 0


_replay_ctx: ContextVar[_ReplayState | None] = ContextVar(
    "specops_replay_ctx", default=None
)


def _hash_args(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """Create a deterministic hash of function arguments."""
    try:
        payload = json.dumps(
            {"args": args, "kwargs": kwargs}, default=str, sort_keys=True
        )
    except (TypeError, ValueError):
        payload = str((args, kwargs))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# --- Storage ---


class ReplayStore:
    """Persist and load replay sessions as JSON files."""

    def __init__(self, base_dir: Path | str = ".specops/replays") -> None:
        self.base_dir = Path(base_dir)

    def save(self, session: ReplaySession) -> Path:
        """Save a session to disk."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self.base_dir / f"{session.session_id}.json"
        path.write_text(json.dumps(asdict(session), indent=2, default=str))
        return path

    def load(self, session_id: str) -> ReplaySession:
        """Load a session from disk."""
        path = self.base_dir / f"{session_id}.json"
        data = json.loads(path.read_text())
        calls = [RecordedCall(**c) for c in data.pop("calls", [])]
        return ReplaySession(**data, calls=calls)

    def list_sessions(self) -> list[str]:
        """List all stored session IDs."""
        if not self.base_dir.exists():
            return []
        return [p.stem for p in self.base_dir.glob("*.json")]


# --- Context Managers ---

_default_store = ReplayStore()


@contextmanager
def recording(
    session_id: str | None = None,
    seed: int | None = None,
    store: ReplayStore | None = None,
) -> Iterator[ReplaySession]:
    """Record all @replayable calls within this block.

    Args:
        session_id: Unique session identifier. Auto-generated if None.
        seed: Random seed for determinism. Auto-generated if None.
        store: ReplayStore instance for persistence. Uses default if None.
    """
    sid = session_id or uuid.uuid4().hex[:12]
    s = seed if seed is not None else random.randint(0, 2**32 - 1)
    session = ReplaySession(
        session_id=sid,
        seed=s,
        recorded_at=datetime.now(timezone.utc).isoformat(),
    )
    state = _ReplayState(mode="record", session=session)
    token = _replay_ctx.set(state)

    # Set deterministic seed
    prev_state = random.getstate()
    random.seed(s)

    # Set OTel attributes on current span
    span = trace.get_current_span()
    if span.is_recording():
        span.set_attribute(REPLAY_SESSION_ID, sid)
        span.set_attribute(REPLAY_SEED, s)

    try:
        yield session
    finally:
        random.setstate(prev_state)
        _replay_ctx.reset(token)
        # Persist
        st = store or _default_store
        st.save(session)


@contextmanager
def replaying(
    session: ReplaySession | str | Path,
    store: ReplayStore | None = None,
) -> Iterator[ReplaySession]:
    """Replay from a stored session.

    Args:
        session: A ReplaySession object, session_id string, or path to JSON file.
        store: ReplayStore instance for loading. Uses default if None.
    """
    st = store or _default_store

    if isinstance(session, (str, Path)):
        p = Path(session)
        if p.suffix == ".json" and p.exists():
            data = json.loads(p.read_text())
            calls = [RecordedCall(**c) for c in data.pop("calls", [])]
            sess = ReplaySession(**data, calls=calls)
        else:
            sess = st.load(str(session))
    else:
        sess = session

    state = _ReplayState(mode="replay", session=sess)
    token = _replay_ctx.set(state)

    # Set deterministic seed
    prev_state = random.getstate()
    random.seed(sess.seed)

    span = trace.get_current_span()
    if span.is_recording():
        span.set_attribute(REPLAY_SESSION_ID, sess.session_id)
        span.set_attribute(REPLAY_SEED, sess.seed)

    try:
        yield sess
    finally:
        random.setstate(prev_state)
        _replay_ctx.reset(token)


# --- Decorator ---


def replayable(fn: F) -> F:
    """Mark a function as replayable.

    In RECORD mode: executes normally, captures result.
    In REPLAY mode: returns the previously recorded result.
    """
    is_async = inspect.iscoroutinefunction(fn)
    func_name = fn.__qualname__

    @functools.wraps(fn)
    async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
        state = _replay_ctx.get()
        if state is None:
            return await fn(*args, **kwargs)

        args_hash = _hash_args(args, kwargs)

        if state.mode == "record":
            result = await fn(*args, **kwargs)
            call = RecordedCall(
                func_name=func_name,
                args_hash=args_hash,
                result=result,
                timestamp=datetime.now(timezone.utc).isoformat(),
                call_index=state.call_counter,
            )
            state.session.calls.append(call)
            state.call_counter += 1
            return result

        # Replay mode
        return _find_replay_result(state, func_name, args_hash)

    @functools.wraps(fn)
    def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        state = _replay_ctx.get()
        if state is None:
            return fn(*args, **kwargs)

        args_hash = _hash_args(args, kwargs)

        if state.mode == "record":
            result = fn(*args, **kwargs)
            call = RecordedCall(
                func_name=func_name,
                args_hash=args_hash,
                result=result,
                timestamp=datetime.now(timezone.utc).isoformat(),
                call_index=state.call_counter,
            )
            state.session.calls.append(call)
            state.call_counter += 1
            return result

        # Replay mode
        return _find_replay_result(state, func_name, args_hash)

    return _async_wrapper if is_async else _sync_wrapper  # type: ignore[return-value]


def _find_replay_result(state: _ReplayState, func_name: str, args_hash: str) -> Any:
    """Find the matching recorded call for replay."""
    # Try sequential match first
    if state.replay_index < len(state.session.calls):
        call = state.session.calls[state.replay_index]
        if call.func_name == func_name and call.args_hash == args_hash:
            state.replay_index += 1
            return call.result

    # Fall back to scanning all calls
    for call in state.session.calls:
        if call.func_name == func_name and call.args_hash == args_hash:
            return call.result

    raise ReplayMismatchError(
        f"No recorded call found for {func_name} with args_hash={args_hash}"
    )


class ReplayMismatchError(Exception):
    """Raised when replay cannot find a matching recorded call."""


# --- Shareable Replay File ---


@dataclass
class ReplayFile:
    """A portable, self-contained replay file bundling session + metadata.

    Includes the replay session, environment info, and optional diagnostics
    (health report, chaos results, regression data) for full reproducibility.
    """

    version: str = "1.0"
    session: ReplaySession | None = None
    environment: dict[str, Any] = field(default_factory=dict)
    health: dict[str, Any] | None = None
    chaos: dict[str, Any] | None = None
    regression: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _collect_environment() -> dict[str, Any]:
    """Collect current environment metadata for portability."""
    import platform
    import sys

    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "specops_version": "0.4.0",
    }


def _serialize_health(health: Any) -> dict[str, Any] | None:
    """Serialize a HealthReport to dict if provided."""
    if health is None:
        return None
    if hasattr(health, "__dataclass_fields__"):
        return asdict(health)
    if isinstance(health, dict):
        return health
    return None


def _serialize_chaos(chaos: Any) -> dict[str, Any] | None:
    """Serialize a ChaosResult to dict if provided."""
    if chaos is None:
        return None
    if hasattr(chaos, "__dataclass_fields__"):
        data = asdict(chaos)
        # Convert enum values to strings
        for event in data.get("events", []):
            ct = event.get("chaos_type")
            if hasattr(ct, "value") or isinstance(ct, Enum):
                event["chaos_type"] = ct.value
        return data
    if isinstance(chaos, dict):
        return chaos
    return None


def _serialize_regression(regression: Any) -> dict[str, Any] | None:
    """Serialize a GoldenRun to dict if provided."""
    if regression is None:
        return None
    if hasattr(regression, "__dataclass_fields__"):
        return asdict(regression)
    if isinstance(regression, dict):
        return regression
    return None


def export_replay(
    session: ReplaySession | str,
    path: str | Path,
    *,
    store: ReplayStore | None = None,
    health: Any | None = None,
    chaos: Any | None = None,
    regression: Any | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Export a replay session to a portable JSON file.

    Bundles the session with environment info and optional diagnostics
    for sharing, debugging, or archival.

    Args:
        session: A ReplaySession object or session_id string.
        path: Destination file path for the exported JSON.
        store: ReplayStore to load from if session is a string.
        health: Optional HealthReport to include.
        chaos: Optional ChaosResult to include.
        regression: Optional GoldenRun to include.
        metadata: Optional extra metadata dict.

    Returns:
        Path to the written file.
    """
    st = store or _default_store
    sess = st.load(session) if isinstance(session, str) else session

    replay_file = ReplayFile(
        session=sess,
        environment=_collect_environment(),
        health=_serialize_health(health),
        chaos=_serialize_chaos(chaos),
        regression=_serialize_regression(regression),
        metadata=metadata or {},
    )

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(asdict(replay_file), indent=2, default=str), encoding="utf-8"
    )
    return out


def import_replay(path: str | Path) -> ReplayFile:
    """Import a replay file from disk.

    Loads the full ReplayFile including session, environment, and diagnostics.
    The returned session can be passed directly to `replaying()`.

    Args:
        path: Path to the exported replay JSON file.

    Returns:
        A ReplayFile with the deserialized session and metadata.
    """
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))

    session_data = data.get("session")
    sess: ReplaySession | None = None
    if session_data:
        calls = [RecordedCall(**c) for c in session_data.pop("calls", [])]
        sess = ReplaySession(**session_data, calls=calls)

    return ReplayFile(
        version=data.get("version", "1.0"),
        session=sess,
        environment=data.get("environment", {}),
        health=data.get("health"),
        chaos=data.get("chaos"),
        regression=data.get("regression"),
        metadata=data.get("metadata", {}),
    )
