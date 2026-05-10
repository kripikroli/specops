"""Example: Automated Behavioral Regression Testing.

Demonstrates how to record a 'golden' agent run and detect behavioral drift
in future runs — even when the final output looks the same.

Drift types detected:
  1. Step count — agent takes more/fewer steps
  2. Step order — agent reorders its reasoning
  3. Tool usage — agent uses different tools
  4. Loops — agent repeats actions excessively
  5. Timing — agent takes significantly longer

Run:
    uv run examples/regression_demo.py

Supports mock mode (no API key needed):
    SPECOPS_EXAMPLE_MODE=mock uv run examples/regression_demo.py

With a real OpenAI key:
    Set OPENAI_API_KEY in .env
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from specops_ai import (  # noqa: E402
    RegressionStore,
    check_regression,
    golden,
    record_step,
    trace_agent,
    trace_tool,
)

# ============================================================
# Configuration
# ============================================================

MOCK_MODE = os.environ.get("SPECOPS_EXAMPLE_MODE") == "mock" or not os.environ.get(
    "OPENAI_API_KEY"
)

_tmp_dir = tempfile.mkdtemp(prefix="specops_regression_")
store = RegressionStore(base_dir=_tmp_dir)


# ============================================================
# Simulated Agent (mock or live)
# ============================================================


def _call_llm(prompt: str) -> str:
    """Call LLM — real OpenAI or mock."""
    if MOCK_MODE:
        time.sleep(0.05)
        return "Paris is the capital of France, known for the Eiffel Tower."

    import openai

    client = openai.OpenAI()
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
    )
    return resp.choices[0].message.content or ""


@trace_tool(name="search")
def search(query: str) -> list[str]:
    """Simulate a search tool."""
    start = time.time()
    results = [f"Wikipedia: {query}", f"Encyclopedia: {query} overview"]
    duration = (time.time() - start) * 1000
    record_step("search", "tool_call", inputs={"query": query}, duration_ms=duration)
    return results


@trace_agent(name="research-agent")
def research_agent(task: str) -> str:
    """A simple research agent: search → summarize."""
    results = search(task)
    start = time.time()
    prompt = f"Summarize in one sentence: {results}"
    answer = _call_llm(prompt)
    duration = (time.time() - start) * 1000
    record_step(
        "llm_summarize",
        "llm_call",
        inputs={"prompt": prompt[:50]},
        duration_ms=duration,
    )
    return answer


@trace_agent(name="research-agent-v2")
def research_agent_drifted(task: str) -> str:
    """Same agent but with behavioral drift (extra loop, different tools)."""
    # Drift 1: extra validation step
    record_step("validate_input", "action", duration_ms=5.0)

    # Drift 2: uses database instead of search
    record_step(
        "database_lookup", "tool_call", inputs={"query": task}, duration_ms=30.0
    )

    # Drift 3: loops on retry
    for _i in range(3):
        record_step("retry_fetch", "action", duration_ms=10.0)

    # Still calls LLM
    start = time.time()
    answer = _call_llm(f"Summarize: {task}")
    duration = (time.time() - start) * 1000
    record_step("llm_summarize", "llm_call", duration_ms=duration)

    return answer  # Output may look the same!


# ============================================================
# Demo
# ============================================================


def main() -> None:
    mode_label = "MOCK" if MOCK_MODE else "LIVE (OpenAI)"
    print("=" * 62)
    print("  SpecOps AI — Behavioral Regression Testing Demo")
    print(f"  Mode: {mode_label}")
    print("=" * 62)

    # --- Step 1: Record Golden Run ---
    print("\n[1] Recording Golden Run...")
    print("    Agent: research-agent | Task: 'capital of France'")

    with golden(
        "golden-1", agent_name="research-agent", task="capital of France", store=store
    ) as run:
        result = research_agent("capital of France")
        run.final_output = result

    print(f"    ✅ Recorded {len(run.steps)} steps")
    print(f"    Output: {result[:60]}...")
    print(f"    Steps: {[s.name for s in run.steps]}")

    # --- Step 2: Check with identical behavior (should pass) ---
    print("\n[2] Checking Identical Behavior (should PASS)...")

    with check_regression("golden-1", store=store) as check:
        research_agent("capital of France")

    _print_result(check)

    # --- Step 3: Check with drifted behavior (should detect drift) ---
    print("\n[3] Checking Drifted Behavior (should DETECT DRIFT)...")
    print("    Injecting: extra steps, different tools, retry loops")

    with check_regression("golden-1", store=store, threshold=0.8) as check:
        result3 = research_agent_drifted("capital of France")

    _print_result(check)

    # --- Summary ---
    print("\n" + "=" * 62)
    print("  Summary")
    print("=" * 62)
    print(f"  Golden output:  {result[:50]}...")
    print(f"  Drifted output: {result3[:50]}...")
    print("  → Output may look similar, but BEHAVIOR diverged!")
    print(f"  → {len(check.drifts)} drift(s) detected automatically")
    print("=" * 62)


def _print_result(result) -> None:
    status = "✅ PASSED" if result.passed else "❌ REGRESSION DETECTED"
    print(f"    {status} (score: {result.score:.2f})")
    if result.drifts:
        for d in result.drifts:
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}[d.severity]
            print(f"      {icon} [{d.drift_type}] {d.message}")


if __name__ == "__main__":
    main()
