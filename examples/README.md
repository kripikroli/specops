# SpecOps Examples

| Example | Description | Framework |
|---------|-------------|-----------|
| [plain_agent.py](plain_agent.py) | Simple research agent with search + LLM | Plain Python |
| [langgraph_agent.py](langgraph_agent.py) | StateGraph-style agent with tool routing | LangGraph |
| [crewai_agent.py](crewai_agent.py) | Multi-agent crew (researcher + writer) | CrewAI |
| [async_pipeline.py](async_pipeline.py) | Async multi-agent pipeline with nested spans | Plain Python (async) |

## Running

```bash
# All examples work with just the core package
uv run python examples/plain_agent.py
uv run python examples/langgraph_agent.py
uv run python examples/crewai_agent.py
uv run python examples/async_pipeline.py
```

## Viewing Traces

By default, traces are printed to the console. To send to Jaeger:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
uv run python examples/plain_agent.py
```
