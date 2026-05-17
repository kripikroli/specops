"""Example: Shareable Replay Sessions — Export & Import Agent Runs.

Demonstrates how to:
  1. Record an agent session with @replayable
  2. Export the session as a portable JSON file (with health + chaos data)
  3. Import the file on another machine / in another process
  4. Replay deterministically from the imported file

This enables sharing exact agent runs for debugging, review, or archival.

Run:
    uv run examples/replay_demo.py

No API key required — uses simulated LLM calls.
"""

from __future__ import annotations

import random
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from specops_ai import (
    ReplayFile,
    ReplayStore,
    export_replay,
    import_replay,
    recording,
    replayable,
    replaying,
)

# ============================================================
# Simulated Agent
# ============================================================


@replayable
def call_llm(prompt: str) -> str:
    """Simulate a non-deterministic LLM call."""
    responses = [
        "The answer is 42.",
        "According to my analysis, 42.",
        "42 — the ultimate answer.",
    ]
    return random.choice(responses)


@replayable
def search_tool(query: str) -> list[str]:
    """Simulate a search tool with variable results."""
    return [f"result_{random.randint(1, 1000)}" for _ in range(3)]


def research_agent(task: str) -> str:
    """A simple research agent that searches then summarizes."""
    results = search_tool(task)
    return call_llm(f"Summarize '{task}': {results}")


# ============================================================
# Main Demo
# ============================================================


def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    store = ReplayStore(base_dir=tmp / "replays")
    export_path = tmp / "shared_replay.json"

    # --- Step 1: Record ---
    print("=" * 60)
    print("  STEP 1: Record an agent session")
    print("=" * 60)

    with recording(session_id="demo-share", seed=42, store=store) as session:
        result = research_agent("meaning of life")

    print(f"  Session ID : {session.session_id}")
    print(f"  Seed       : {session.seed}")
    print(f"  Calls      : {len(session.calls)}")
    print(f"  Result     : {result}")

    # --- Step 2: Export ---
    print()
    print("=" * 60)
    print("  STEP 2: Export as portable replay file")
    print("=" * 60)

    out = export_replay(
        session,
        export_path,
        health={"score": 92.0, "grade": "A"},
        chaos={"total_injected": 3, "total_detected": 3, "total_healed": 2},
        metadata={"author": "demo", "purpose": "educational"},
    )
    print(f"  Exported to: {out}")
    print(f"  File size  : {out.stat().st_size} bytes")

    # Show a snippet of the file
    import json

    data = json.loads(out.read_text())
    print(f"  Version    : {data['version']}")
    print(f"  Environment: Python {data['environment']['python_version'][:10]}...")
    print(f"  Health     : {data['health']}")
    print(f"  Metadata   : {data['metadata']}")

    # --- Step 3: Import ---
    print()
    print("=" * 60)
    print("  STEP 3: Import on another machine / process")
    print("=" * 60)

    rf: ReplayFile = import_replay(export_path)
    assert rf.session is not None
    print(f"  Session ID : {rf.session.session_id}")
    print(f"  Calls      : {len(rf.session.calls)}")
    print(f"  Health     : {rf.health}")
    print(f"  Chaos      : {rf.chaos}")
    print(f"  Metadata   : {rf.metadata}")

    # --- Step 4: Replay ---
    print()
    print("=" * 60)
    print("  STEP 4: Replay deterministically from imported file")
    print("=" * 60)

    with replaying(rf.session) as _:
        replayed = research_agent("meaning of life")

    print(f"  Replayed   : {replayed}")
    print(f"  Match      : {result == replayed}")

    # --- Summary ---
    print()
    print("=" * 60)
    print("  ✅ Shareable Replay Complete")
    print("=" * 60)
    print()
    print("  The exported file is fully portable — share it via")
    print("  Slack, email, or git for exact reproduction of any")
    print("  agent session, including health and chaos diagnostics.")
    print()


if __name__ == "__main__":
    main()
