"""End-to-end tests that run the examples as integration tests.

Provider examples (examples/providers/) gracefully exit(0) when API keys are missing,
so they always pass in CI without secrets configured.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
PROVIDERS_DIR = EXAMPLES_DIR / "providers"
SRC_DIR = str(Path(__file__).parent.parent / "src")


def run_example(path: str | Path) -> subprocess.CompletedProcess[str]:
    """Run an example script with src on PYTHONPATH."""
    env = {**os.environ, "PYTHONPATH": SRC_DIR}
    # Strip real keys so CI tests exercise the graceful-skip path
    env.pop("OPENAI_API_KEY", None)
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("GROK_API_KEY", None)
    return subprocess.run(
        [sys.executable, str(path)],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def run_example_mock(path: str | Path) -> subprocess.CompletedProcess[str]:
    """Run an example in mock mode (SPECOPS_EXAMPLE_MODE=mock)."""
    env = {**os.environ, "PYTHONPATH": SRC_DIR, "SPECOPS_EXAMPLE_MODE": "mock"}
    return subprocess.run(
        [sys.executable, str(path)],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


class TestCoreExamples:
    """Tests for framework-agnostic examples that need no API keys."""

    def test_plain_agent(self):
        result = run_example(EXAMPLES_DIR / "plain_agent.py")
        assert result.returncode == 0, result.stderr
        assert "Agent response:" in result.stdout

    @pytest.mark.asyncio
    async def test_async_pipeline_import(self):
        """Test async pipeline by importing and running directly."""
        sys.path.insert(0, str(EXAMPLES_DIR))
        try:
            from async_pipeline import orchestrator

            results = await orchestrator("test")
            assert len(results) == 3
            assert all("Analysis complete" in r for r in results)
        finally:
            sys.path.pop(0)

    def test_async_pipeline_subprocess(self):
        result = run_example(EXAMPLES_DIR / "async_pipeline.py")
        assert result.returncode == 0, result.stderr
        assert "Pipeline results (3 sources):" in result.stdout


class TestProviderExamples:
    """Provider examples: graceful skip when keys missing, mock mode works."""

    def test_openai_langgraph_graceful_skip(self):
        """Without OPENAI_API_KEY, exits 0 with skip message."""
        result = run_example(PROVIDERS_DIR / "openai" / "langgraph_agent.py")
        assert result.returncode == 0, result.stderr
        assert "[SKIP]" in result.stdout or "Agent response:" in result.stdout

    def test_openai_langgraph_mock_mode(self):
        """In mock mode, runs fully and produces output."""
        result = run_example_mock(PROVIDERS_DIR / "openai" / "langgraph_agent.py")
        assert result.returncode == 0, result.stderr
        assert "Agent response:" in result.stdout

    def test_legacy_langgraph_agent(self):
        """Original langgraph_agent.py still works (exits 0 regardless of key)."""
        result = run_example(EXAMPLES_DIR / "langgraph_agent.py")
        assert result.returncode == 0, result.stderr
