"""SpecOps — Agent Reliability Kit."""

__version__ = "0.2.0"

from specops.adapters import BaseAdapter, PlainAdapter, get_adapter, register_adapter
from specops.config import configure, get_tracer, reset
from specops.eval import (
    EvalCase,
    EvalResult,
    JudgeVerdict,
    eval_golden_set,
    eval_golden_set_async,
    llm_judge,
    llm_judge_async,
)
from specops.heal import (
    EscalatePolicy,
    FallbackPolicy,
    HealingChain,
    PolicyAction,
    PolicyResult,
    PruneMemoryPolicy,
    RetryPolicy,
    self_healing,
)
from specops.rca import RCAEdge, RCAGraph, RCANode, build_rca_graph
from specops.replay import (
    RecordedCall,
    ReplayMismatchError,
    ReplaySession,
    ReplayStore,
    recording,
    replayable,
    replaying,
)
from specops.trace import trace_agent, trace_llm, trace_tool
from specops.viz import save_dot, to_dot

__all__ = [
    # Adapters
    "BaseAdapter",
    "PlainAdapter",
    "get_adapter",
    "register_adapter",
    # Config
    "configure",
    "get_tracer",
    "reset",
    # Tracing
    "trace_agent",
    "trace_llm",
    "trace_tool",
    # Replay
    "RecordedCall",
    "ReplayMismatchError",
    "ReplaySession",
    "ReplayStore",
    "recording",
    "replayable",
    "replaying",
    # Eval
    "EvalCase",
    "EvalResult",
    "JudgeVerdict",
    "eval_golden_set",
    "eval_golden_set_async",
    "llm_judge",
    "llm_judge_async",
    # Heal
    "EscalatePolicy",
    "FallbackPolicy",
    "HealingChain",
    "PolicyAction",
    "PolicyResult",
    "PruneMemoryPolicy",
    "RetryPolicy",
    "self_healing",
    # RCA
    "RCAEdge",
    "RCAGraph",
    "RCANode",
    "build_rca_graph",
    # Viz
    "save_dot",
    "to_dot",
]
