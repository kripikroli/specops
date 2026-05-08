"""Integration tests for framework adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from specops.adapters import (
    _ADAPTERS,
    PlainAdapter,
    get_adapter,
    register_adapter,
)
from specops.adapters.autogen import AutoGenAdapter
from specops.adapters.crewai import CrewAIAdapter
from specops.adapters.langgraph import LangGraphAdapter


class TestAdapterRegistry:
    def test_all_adapters_registered(self):
        assert "plain" in _ADAPTERS
        assert "langgraph" in _ADAPTERS
        assert "crewai" in _ADAPTERS
        assert "autogen" in _ADAPTERS

    def test_get_adapter_returns_correct_type(self):
        assert isinstance(get_adapter("plain"), PlainAdapter)
        assert isinstance(get_adapter("langgraph"), LangGraphAdapter)
        assert isinstance(get_adapter("crewai"), CrewAIAdapter)
        assert isinstance(get_adapter("autogen"), AutoGenAdapter)

    def test_unknown_framework_falls_back_to_plain(self):
        assert isinstance(get_adapter("unknown"), PlainAdapter)

    def test_register_custom_adapter(self):
        class Custom(PlainAdapter):
            pass

        register_adapter("custom", Custom)
        assert isinstance(get_adapter("custom"), Custom)
        del _ADAPTERS["custom"]


class TestLangGraphAdapter:
    @pytest.fixture
    def adapter(self) -> LangGraphAdapter:
        return LangGraphAdapter()

    def test_extract_task_from_input_key(self, adapter: LangGraphAdapter):
        assert adapter.extract_task(
            ({"input": "hello world"},), {}
        ) == "hello world"

    def test_extract_task_from_task_key(self, adapter: LangGraphAdapter):
        assert adapter.extract_task(
            ({"task": "do stuff"},), {}
        ) == "do stuff"

    def test_extract_task_from_messages(self, adapter: LangGraphAdapter):
        @dataclass
        class Msg:
            content: str

        state = {"messages": [Msg(content="user question")]}
        assert adapter.extract_task((state,), {}) == "user question"

    def test_extract_task_from_message_dict(self, adapter: LangGraphAdapter):
        state = {"messages": [{"content": "hi there"}]}
        assert adapter.extract_task((state,), {}) == "hi there"

    def test_extract_task_string_arg(self, adapter: LangGraphAdapter):
        assert adapter.extract_task(("plain string",), {}) == "plain string"

    def test_extract_task_from_kwargs(self, adapter: LangGraphAdapter):
        assert adapter.extract_task(
            (), {"state": {"input": "from kwargs"}}
        ) == "from kwargs"

    def test_extract_llm_metadata_from_ai_message(
        self, adapter: LangGraphAdapter
    ):
        @dataclass
        class AIMsg:
            content: str = "response"
            usage_metadata: dict[str, int] = field(
                default_factory=lambda: {"input_tokens": 10, "output_tokens": 20}
            )
            response_metadata: dict[str, str] = field(
                default_factory=lambda: {"model_name": "gpt-4o"}
            )

        meta = adapter.extract_llm_metadata(AIMsg())
        assert meta["input_tokens"] == 10
        assert meta["output_tokens"] == 20
        assert meta["model"] == "gpt-4o"

    def test_extract_llm_metadata_from_dict(self, adapter: LangGraphAdapter):
        result = {
            "model": "claude-3",
            "usage": {"input_tokens": 5, "output_tokens": 15},
        }
        meta = adapter.extract_llm_metadata(result)
        assert meta["model"] == "claude-3"
        assert meta["input_tokens"] == 5
        assert meta["output_tokens"] == 15

    def test_extract_llm_metadata_empty(self, adapter: LangGraphAdapter):
        assert adapter.extract_llm_metadata("plain string") == {}

    def test_extract_tool_metadata_with_content_attr(
        self, adapter: LangGraphAdapter
    ):
        @dataclass
        class ToolMsg:
            content: str = "tool output"

        meta = adapter.extract_tool_metadata(("arg",), {}, ToolMsg())
        assert meta["result"] == "tool output"

    def test_extract_tool_metadata_from_dict(self, adapter: LangGraphAdapter):
        meta = adapter.extract_tool_metadata(
            (), {}, {"content": "result data"}
        )
        assert meta["result"] == "result data"


class TestCrewAIAdapter:
    @pytest.fixture
    def adapter(self) -> CrewAIAdapter:
        return CrewAIAdapter()

    def test_extract_task_from_inputs_kwarg(self, adapter: CrewAIAdapter):
        result = adapter.extract_task((), {"inputs": {"topic": "AI safety"}})
        assert result == "AI safety"

    def test_extract_task_from_task_object(self, adapter: CrewAIAdapter):
        @dataclass
        class Task:
            description: str = "Write a report"

        assert adapter.extract_task((Task(),), {}) == "Write a report"

    def test_extract_task_from_dict(self, adapter: CrewAIAdapter):
        assert adapter.extract_task(
            ({"description": "analyze data"},), {}
        ) == "analyze data"

    def test_extract_task_from_string(self, adapter: CrewAIAdapter):
        assert adapter.extract_task(("simple task",), {}) == "simple task"

    def test_extract_llm_metadata_from_crew_output(
        self, adapter: CrewAIAdapter
    ):
        @dataclass
        class CrewOutput:
            raw: str = "output"
            token_usage: dict[str, Any] = field(
                default_factory=lambda: {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "model": "gpt-4o",
                }
            )

        meta = adapter.extract_llm_metadata(CrewOutput())
        assert meta["input_tokens"] == 100
        assert meta["output_tokens"] == 50
        assert meta["model"] == "gpt-4o"

    def test_extract_llm_metadata_from_dict(self, adapter: CrewAIAdapter):
        result = {
            "model": "gpt-4",
            "token_usage": {"prompt_tokens": 20, "completion_tokens": 30},
        }
        meta = adapter.extract_llm_metadata(result)
        assert meta["model"] == "gpt-4"
        assert meta["input_tokens"] == 20
        assert meta["output_tokens"] == 30

    def test_extract_tool_metadata_with_output_attr(
        self, adapter: CrewAIAdapter
    ):
        @dataclass
        class ToolResult:
            output: str = "tool done"

        meta = adapter.extract_tool_metadata((), {}, ToolResult())
        assert meta["result"] == "tool done"

    def test_extract_tool_metadata_from_dict(self, adapter: CrewAIAdapter):
        meta = adapter.extract_tool_metadata(
            (), {}, {"output": "dict result"}
        )
        assert meta["result"] == "dict result"


class TestAutoGenAdapter:
    @pytest.fixture
    def adapter(self) -> AutoGenAdapter:
        return AutoGenAdapter()

    def test_extract_task_from_message_kwarg(self, adapter: AutoGenAdapter):
        assert adapter.extract_task(
            (), {"message": "hello agent"}
        ) == "hello agent"

    def test_extract_task_from_dict_arg(self, adapter: AutoGenAdapter):
        assert adapter.extract_task(
            ({"content": "chat msg"},), {}
        ) == "chat msg"

    def test_extract_task_from_string_arg(self, adapter: AutoGenAdapter):
        assert adapter.extract_task(("direct",), {}) == "direct"

    def test_extract_task_empty(self, adapter: AutoGenAdapter):
        assert adapter.extract_task((), {}) == ""

    def test_extract_llm_metadata(self, adapter: AutoGenAdapter):
        result = {
            "model": "gpt-4o",
            "usage": {"prompt_tokens": 15, "completion_tokens": 25},
        }
        meta = adapter.extract_llm_metadata(result)
        assert meta["model"] == "gpt-4o"
        assert meta["input_tokens"] == 15
        assert meta["output_tokens"] == 25

    def test_extract_llm_metadata_non_dict(self, adapter: AutoGenAdapter):
        assert adapter.extract_llm_metadata("string") == {}

    def test_extract_tool_metadata_dict_result(self, adapter: AutoGenAdapter):
        meta = adapter.extract_tool_metadata(
            (), {}, {"content": "fn result"}
        )
        assert meta["result"] == "fn result"

    def test_extract_tool_metadata_plain_result(
        self, adapter: AutoGenAdapter
    ):
        meta = adapter.extract_tool_metadata((), {}, 42)
        assert meta["result"] == 42
