"""Central model configuration for SpecOps AI provider examples.

Defines default models per provider and supports environment variable overrides.

Override any model via environment variables:
    SPECOPS_OPENAI_MODEL=gpt-4o
    SPECOPS_ANTHROPIC_MODEL=claude-sonnet-4-20250514
    SPECOPS_GROK_MODEL=grok-3
"""

from __future__ import annotations

import os

PROVIDER_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
    "grok": "grok-3-mini",
}

_ENV_OVERRIDES: dict[str, str] = {
    "openai": "SPECOPS_OPENAI_MODEL",
    "anthropic": "SPECOPS_ANTHROPIC_MODEL",
    "grok": "SPECOPS_GROK_MODEL",
}


def get_model(provider: str) -> str:
    """Return the model name for a provider, respecting env overrides."""
    env_var = _ENV_OVERRIDES.get(provider, "")
    return os.environ.get(env_var, "") or PROVIDER_MODELS[provider]
