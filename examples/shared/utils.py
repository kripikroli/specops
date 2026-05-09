"""Shared utilities for provider examples: API key loading and graceful skipping."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")


def require_api_key(key_name: str, provider: str) -> str:
    """Load and return an API key, or exit gracefully if missing.

    In mock mode (SPECOPS_EXAMPLE_MODE=mock), returns a placeholder.
    """
    if os.environ.get("SPECOPS_EXAMPLE_MODE") == "mock":
        return "mock-key"

    value = os.environ.get(key_name, "")
    if not value:
        print(f"[SKIP] {provider} example requires {key_name}.")
        print(f"  To run this live example, create .env with {key_name}=...")
        print("  (See .env.example)")
        sys.exit(0)
    return value
