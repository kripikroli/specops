"""Tests for the SpecOps Demo visual examples runner.

Tests cover example discovery, metadata extraction, API endpoints,
WebSocket execution, and the HTML UI serving.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from specops_ai.demo import (
    EXAMPLES_DIR,
    EXCLUDE_FILES,
    MODULE_TAGS,
    _extract_metadata,
    app,
    discover_examples,
)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


# === Example Discovery ===


class TestDiscoverExamples:
    def test_returns_list(self) -> None:
        result = discover_examples()
        assert isinstance(result, list)

    def test_discovers_core_examples(self) -> None:
        result = discover_examples()
        core = [e for e in result if e["category"] == "core"]
        assert len(core) > 0

    def test_discovers_provider_examples(self) -> None:
        result = discover_examples()
        providers = [e for e in result if e["category"] == "provider"]
        assert len(providers) > 0

    def test_excludes_run_all(self) -> None:
        result = discover_examples()
        ids = [e["id"] for e in result]
        assert "run_all" not in ids

    def test_excludes_init_files(self) -> None:
        result = discover_examples()
        names = [Path(e["abs_path"]).name for e in result]
        assert "__init__.py" not in names

    def test_example_has_required_fields(self) -> None:
        result = discover_examples()
        assert len(result) > 0
        ex = result[0]
        assert "id" in ex
        assert "name" in ex
        assert "path" in ex
        assert "abs_path" in ex
        assert "category" in ex
        assert "description" in ex
        assert "tag" in ex

    def test_provider_examples_have_provider_field(self) -> None:
        result = discover_examples()
        providers = [e for e in result if e["category"] == "provider"]
        if providers:
            assert "provider" in providers[0]

    def test_returns_empty_if_dir_missing(self) -> None:
        with patch("specops_ai.demo.EXAMPLES_DIR", Path("/nonexistent")):
            result = discover_examples()
            assert result == []


# === Metadata Extraction ===


class TestExtractMetadata:
    def test_extracts_docstring_description(self, tmp_path: Path) -> None:
        f = tmp_path / "example.py"
        f.write_text('"""My cool example."""\nprint("hi")\n')
        meta = _extract_metadata(f)
        assert meta["description"] == "My cool example."

    def test_multiline_docstring_uses_first_line(self, tmp_path: Path) -> None:
        f = tmp_path / "example.py"
        f.write_text('"""First line.\n\nMore details here."""\n')
        meta = _extract_metadata(f)
        assert meta["description"] == "First line."

    def test_no_docstring_uses_stem(self, tmp_path: Path) -> None:
        f = tmp_path / "my_example.py"
        f.write_text("print('hello')\n")
        meta = _extract_metadata(f)
        assert meta["description"] == "My Example"

    def test_unreadable_file_returns_stem(self, tmp_path: Path) -> None:
        f = tmp_path / "broken.py"
        # File doesn't exist
        meta = _extract_metadata(f)
        assert meta["description"] == "broken"
        assert meta["tag"] == "Other"

    def test_tag_from_filename(self, tmp_path: Path) -> None:
        f = tmp_path / "replay_basic.py"
        f.write_text('"""Replay test."""\n')
        meta = _extract_metadata(f)
        assert meta["tag"] == "Replay"

    def test_tag_chaos(self, tmp_path: Path) -> None:
        f = tmp_path / "chaos_demo.py"
        f.write_text('"""Chaos."""\n')
        meta = _extract_metadata(f)
        assert meta["tag"] == "Chaos"

    def test_tag_unknown_defaults_to_other(self, tmp_path: Path) -> None:
        f = tmp_path / "something_random.py"
        f.write_text('"""Random."""\n')
        meta = _extract_metadata(f)
        assert meta["tag"] == "Other"


# === API Endpoints ===


class TestAPIExamples:
    def test_list_examples(self, client: TestClient) -> None:
        r = client.get("/api/examples")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_code_valid(self, client: TestClient) -> None:
        examples = client.get("/api/examples").json()
        first_id = examples[0]["id"]
        r = client.get(f"/api/code/{first_id}")
        assert r.status_code == 200
        data = r.json()
        assert "code" in data
        assert len(data["code"]) > 0
        assert "path" in data

    def test_get_code_not_found(self, client: TestClient) -> None:
        r = client.get("/api/code/nonexistent_example_xyz")
        assert r.status_code == 404
        assert "error" in r.json()


# === HTML UI ===


class TestHTMLUI:
    def test_index_returns_html(self, client: TestClient) -> None:
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_index_contains_title(self, client: TestClient) -> None:
        r = client.get("/")
        assert "SpecOps Demo" in r.text

    def test_index_contains_layout_elements(self, client: TestClient) -> None:
        r = client.get("/")
        assert "sidebar" in r.text
        assert "code-area" in r.text
        assert "output-panel" in r.text

    def test_index_contains_collapsible_panels(self, client: TestClient) -> None:
        r = client.get("/")
        assert "Traces" in r.text
        assert "Health Score" in r.text
        assert "Replay Summary" in r.text

    def test_index_contains_theme_toggle(self, client: TestClient) -> None:
        r = client.get("/")
        assert "toggleTheme" in r.text

    def test_index_contains_run_all_button(self, client: TestClient) -> None:
        r = client.get("/")
        assert "Run All" in r.text


# === WebSocket Execution ===


class TestWebSocketRun:
    def test_run_single_example(self, client: TestClient) -> None:
        with client.websocket_connect("/ws/run/plain_agent") as ws:
            messages = []
            while True:
                msg = ws.receive_json()
                messages.append(msg)
                if msg["type"] == "done":
                    break
            assert any(m["type"] == "output" for m in messages)
            done = messages[-1]
            assert done["data"]["success"] is True
            assert done["data"]["returncode"] == 0

    def test_run_nonexistent_example(self, client: TestClient) -> None:
        with client.websocket_connect("/ws/run/nonexistent_xyz") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "not found" in msg["data"].lower()

    def test_run_streams_stdout(self, client: TestClient) -> None:
        with client.websocket_connect("/ws/run/plain_agent") as ws:
            stdout_lines = []
            while True:
                msg = ws.receive_json()
                if msg["type"] == "output" and msg["data"]["stream"] == "stdout":
                    stdout_lines.append(msg["data"]["line"])
                if msg["type"] == "done":
                    break
            assert len(stdout_lines) > 0


# === Module Constants ===


class TestConstants:
    def test_exclude_files(self) -> None:
        assert "run_all.py" in EXCLUDE_FILES
        assert "__init__.py" in EXCLUDE_FILES

    def test_module_tags_has_entries(self) -> None:
        assert len(MODULE_TAGS) > 0
        assert "replay" in MODULE_TAGS
        assert "chaos" in MODULE_TAGS

    def test_examples_dir_exists(self) -> None:
        assert EXAMPLES_DIR.exists()
