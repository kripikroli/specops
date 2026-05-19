"""Tests for config.py OTLP exporter protocol detection."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from specops_ai.config import configure, get_tracer, reset


@pytest.fixture(autouse=True)
def _reset_config(monkeypatch: pytest.MonkeyPatch):
    """Reset config state and clear OTEL env vars before each test."""
    reset()
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_PROTOCOL", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    yield
    reset()


class TestProtocolDetection:
    """Test OTEL_EXPORTER_OTLP_PROTOCOL env var handling."""

    def test_default_protocol_is_http_json(self, monkeypatch: pytest.MonkeyPatch):
        """Default protocol is http/json when PROTOCOL env var is unset."""
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:8000")
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_PROTOCOL", raising=False)

        with patch(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter"
        ) as mock_http:
            mock_http.return_value = MagicMock()
            configure()

        mock_http.assert_called_once_with(endpoint="http://localhost:8000/v1/traces")

    def test_explicit_http_json_protocol(self, monkeypatch: pytest.MonkeyPatch):
        """OTEL_EXPORTER_OTLP_PROTOCOL=http/json uses HTTP exporter."""
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:8000")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/json")

        with patch(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter"
        ) as mock_http:
            mock_http.return_value = MagicMock()
            configure()

        mock_http.assert_called_once_with(endpoint="http://localhost:8000/v1/traces")

    def test_grpc_protocol(self, monkeypatch: pytest.MonkeyPatch):
        """OTEL_EXPORTER_OTLP_PROTOCOL=grpc uses gRPC exporter."""
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")

        with patch(
            "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter"
        ) as mock_grpc:
            mock_grpc.return_value = MagicMock()
            configure()

        mock_grpc.assert_called_once_with(endpoint="http://localhost:4317")

    def test_traces_endpoint_overrides_base(self, monkeypatch: pytest.MonkeyPatch):
        """TRACES_ENDPOINT takes precedence over base + /v1/traces."""
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:8000")
        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://custom:9999/v1/traces"
        )

        with patch(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter"
        ) as mock_http:
            mock_http.return_value = MagicMock()
            configure()

        mock_http.assert_called_once_with(endpoint="http://custom:9999/v1/traces")

    def test_traces_endpoint_with_grpc(self, monkeypatch: pytest.MonkeyPatch):
        """OTEL_EXPORTER_OTLP_TRACES_ENDPOINT works with gRPC protocol too."""
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://custom:4317")

        with patch(
            "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter"
        ) as mock_grpc:
            mock_grpc.return_value = MagicMock()
            configure()

        mock_grpc.assert_called_once_with(endpoint="http://custom:4317")

    def test_http_import_failure_falls_back_to_console(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """If HTTP exporter not installed, falls back to ConsoleSpanExporter."""
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:8000")

        with patch.dict(
            "sys.modules",
            {"opentelemetry.exporter.otlp.proto.http.trace_exporter": None},
        ):
            configure()

        # Should not crash — tracer still works
        tracer = get_tracer()
        assert tracer is not None

    def test_no_endpoint_uses_console(self, monkeypatch: pytest.MonkeyPatch):
        """Without OTEL_EXPORTER_OTLP_ENDPOINT, uses ConsoleSpanExporter."""
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        configure()
        tracer = get_tracer()
        assert tracer is not None

    def test_endpoint_trailing_slash_stripped(self, monkeypatch: pytest.MonkeyPatch):
        """Trailing slash on endpoint is stripped before appending /v1/traces."""
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:8000/")

        with patch(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter"
        ) as mock_http:
            mock_http.return_value = MagicMock()
            configure()

        mock_http.assert_called_once_with(endpoint="http://localhost:8000/v1/traces")
