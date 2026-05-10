"""SpecOps — Agent Reliability Kit."""

__version__ = "0.3.2"

from specops_ai.adapters import BaseAdapter, PlainAdapter, get_adapter, register_adapter
from specops_ai.chaos import ChaosEngine, ChaosEvent, ChaosResult, ChaosType
from specops_ai.config import configure, get_tracer, reset
from specops_ai.coordinate import (
    AgentOutput,
    BehaviorTrace,
    CoordinationIssue,
    CoordinationResult,
    MemorySnapshot,
    check_consensus,
    check_divergence,
    check_memory_integrity,
)
from specops_ai.eval import (
    EvalCase,
    EvalResult,
    JudgeVerdict,
    eval_golden_set,
    eval_golden_set_async,
    llm_judge,
    llm_judge_async,
)
from specops_ai.heal import (
    EscalatePolicy,
    FallbackPolicy,
    HealingChain,
    PolicyAction,
    PolicyResult,
    PruneMemoryPolicy,
    RetryPolicy,
    self_healing,
)
from specops_ai.rca import RCAEdge, RCAGraph, RCANode, build_rca_graph
from specops_ai.regression import (
    BehaviorStep,
    Drift,
    GoldenRun,
    RegressionError,
    RegressionResult,
    RegressionStore,
    check_regression,
    compare_behavior,
    golden,
    record_step,
    regression_test,
)
from specops_ai.replay import (
    RecordedCall,
    ReplayMismatchError,
    ReplaySession,
    ReplayStore,
    recording,
    replayable,
    replaying,
)
from specops_ai.simulate import (
    AnomalyType,
    SimEvent,
    SimResult,
    SimulationBudgetExceeded,
    SimulationEnvironment,
    get_current_simulation,
    simulate,
    simulation,
)
from specops_ai.trace import trace_agent, trace_llm, trace_tool
from specops_ai.viz import save_dot, to_dot

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
    # Regression
    "BehaviorStep",
    "Drift",
    "GoldenRun",
    "RegressionError",
    "RegressionResult",
    "RegressionStore",
    "check_regression",
    "compare_behavior",
    "golden",
    "record_step",
    "regression_test",
    # Viz
    "save_dot",
    "to_dot",
    # Simulation
    "AnomalyType",
    "SimEvent",
    "SimResult",
    "SimulationBudgetExceeded",
    "SimulationEnvironment",
    "get_current_simulation",
    "simulate",
    "simulation",
    # Coordination
    "AgentOutput",
    "BehaviorTrace",
    "CoordinationIssue",
    "CoordinationResult",
    "MemorySnapshot",
    "check_consensus",
    "check_divergence",
    "check_memory_integrity",
    # Chaos
    "ChaosEngine",
    "ChaosEvent",
    "ChaosResult",
    "ChaosType",
]
