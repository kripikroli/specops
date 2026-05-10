"""Run all examples and report results.

Usage:
    uv run examples/run_all.py          # Uses real API keys from .env (live mode)
    uv run examples/run_all.py --mock   # Uses mock mode (no API keys needed)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent
PROVIDERS_DIR = EXAMPLES_DIR / "providers"

CORE_EXAMPLES = sorted(p for p in EXAMPLES_DIR.glob("*.py") if p.name != "run_all.py")

PROVIDER_EXAMPLES = sorted(PROVIDERS_DIR.glob("*/*.py"))
PROVIDER_EXAMPLES = [p for p in PROVIDER_EXAMPLES if p.name != "__init__.py"]


def main() -> int:
    """Run all examples, return non-zero if any fail."""
    mock = "--mock" in sys.argv
    env = {**os.environ}
    if mock:
        env["SPECOPS_EXAMPLE_MODE"] = "mock"
        print("Mode: MOCK (no real API calls)\n")
    else:
        env.pop("SPECOPS_EXAMPLE_MODE", None)
        print("Mode: LIVE (using API keys from .env)\n")

    failed: list[str] = []
    total = 0

    all_examples = CORE_EXAMPLES + PROVIDER_EXAMPLES

    for path in all_examples:
        total += 1
        rel = path.relative_to(EXAMPLES_DIR)
        try:
            result = subprocess.run(
                [sys.executable, str(path)],
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
        except subprocess.TimeoutExpired:
            print(f"  ✗ {rel} (timed out)")
            failed.append(str(rel))
            continue
        if result.returncode != 0:
            print(f"  ✗ {rel}")
            if result.stderr:
                print(f"    {result.stderr.strip().splitlines()[-1]}")
            failed.append(str(rel))
        else:
            print(f"  ✓ {rel}")

    print(f"\n{'=' * 40}")
    print(f"Results: {total - len(failed)}/{total} passed")
    if failed:
        print(f"Failed: {', '.join(failed)}")
        return 1
    print("All examples passed! ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
