"""End-to-end tests that run the examples as integration tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
SRC_DIR = str(Path(__file__).parent.parent / "src")


def run_example(name: str) -> subprocess.CompletedProcess[str]:
    """Run an example script with src on PYTHONPATH."""
    env = {**os.environ, "PYTHONPATH": SRC_DIR}
    return subprocess.run(
        [sys.executable, str(EXAMPLES_DIR / name)],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


class TestExamplesE2E:
    def test_plain_agent(self):
        result = run_example("plain_agent.py")
        assert result.returncode == 0, result.stderr
        assert "Agent response:" in result.stdout

    def test_langgraph_agent(self):
        result = run_example("langgraph_agent.py")
        assert result.returncode == 0, result.stderr
        assert "Agent response:" in result.stdout
        assert "tool:calculator" in result.stdout

    def test_crewai_agent(self):
        result = run_example("crewai_agent.py")
        assert result.returncode == 0, result.stderr
        assert "Crew output:" in result.stdout

    @pytest.mark.asyncio
    async def test_async_pipeline_import(self):
        """Test async pipeline by importing and running directly."""
        # Import the module's orchestrator function
        sys.path.insert(0, str(EXAMPLES_DIR))
        try:
            from async_pipeline import orchestrator

            results = await orchestrator("test")
            assert len(results) == 3
            assert all("Analysis complete" in r for r in results)
        finally:
            sys.path.pop(0)

    def test_async_pipeline_subprocess(self):
        result = run_example("async_pipeline.py")
        assert result.returncode == 0, result.stderr
        assert "Pipeline results (3 sources):" in result.stdout
