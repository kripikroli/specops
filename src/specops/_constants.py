"""Semantic attribute keys for SpecOps OTel spans."""

# Agent
AGENT_NAME = "specops.agent.name"
AGENT_TASK = "specops.agent.task"
AGENT_FRAMEWORK = "specops.agent.framework"
AGENT_STEP = "specops.agent.step"
AGENT_DECISION = "specops.agent.decision"

# Tool
TOOL_NAME = "specops.tool.name"
TOOL_ARGS = "specops.tool.args"
TOOL_RESULT = "specops.tool.result"

# LLM
LLM_MODEL = "specops.llm.model"
LLM_PROVIDER = "specops.llm.provider"
LLM_TOKENS_INPUT = "specops.llm.tokens.input"
LLM_TOKENS_OUTPUT = "specops.llm.tokens.output"
LLM_TEMPERATURE = "specops.llm.temperature"
LLM_SEED = "specops.llm.seed"
LLM_RESULT = "specops.llm.result"

# Coordination / multi-agent
COORDINATION_EVENT = "specops.coordination.event"
MEMORY_ACCESS = "specops.memory.access"

# Replay
REPLAY_SEED = "specops.replay.seed"
REPLAY_SESSION_ID = "specops.replay.session_id"

# Limits
MAX_ATTR_LENGTH = 1024
