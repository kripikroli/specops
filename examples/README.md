# SpecOps Examples

| Example | Description | Module |
|---------|-------------|--------|
| [plain_agent.py](plain_agent.py) | Simple research agent with search + LLM | Tracing |
| [langgraph_agent.py](langgraph_agent.py) | StateGraph-style agent with tool routing | Adapters |
| [crewai_agent.py](crewai_agent.py) | Multi-agent crew (researcher + writer) | Adapters |
| [async_pipeline.py](async_pipeline.py) | Async multi-agent pipeline with nested spans | Tracing |
| [replay_basic.py](replay_basic.py) | Record and replay agent sessions | Replay |
| [replay_async_eval.py](replay_async_eval.py) | Async replay with evaluation | Replay + Eval |
| [eval_golden_set.py](eval_golden_set.py) | Golden-set evaluation with LLM judge | Eval |
| [self_healing_basic.py](self_healing_basic.py) | Retry and fallback policies | Heal |
| [self_healing_advanced.py](self_healing_advanced.py) | Escalation and memory pruning | Heal |
| [rca_analysis.py](rca_analysis.py) | Root-cause analysis from spans | RCA |
| [simulation_loops.py](simulation_loops.py) | Detect agent loops in a sandbox | Simulation |
| [simulation_cascade.py](simulation_cascade.py) | Test cascading failures | Simulation |
| [multi_agent_coordination.py](multi_agent_coordination.py) | Consensus and divergence checks | Coordination |

## Running

```bash
# All examples work with just the core package
uv run python examples/plain_agent.py

# Framework adapter examples (install extras first)
uv run python examples/langgraph_agent.py
uv run python examples/crewai_agent.py
```

## Viewing Traces

By default, traces are printed to the console. To send to Jaeger:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
uv run python examples/plain_agent.py
```
