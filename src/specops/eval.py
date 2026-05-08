"""Behavioral evaluation harness for SpecOps.

Provides golden-set comparison and LLM-as-judge evaluation primitives
for measuring agent quality.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# --- Core Types ---


@dataclass
class EvalCase:
    """A single evaluation test case."""

    input: Any
    expected: Any
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalResult:
    """Result of evaluating one case."""

    case: EvalCase
    actual: Any
    passed: bool
    score: float
    details: str = ""


@dataclass
class JudgeVerdict:
    """Verdict from an LLM judge."""

    score: float
    reasoning: str
    criteria: str


# --- Golden-Set Evaluation ---


def _default_comparator(expected: Any, actual: Any) -> float:
    """Default exact-match comparator. Returns 1.0 if equal, 0.0 otherwise."""
    if expected == actual:
        return 1.0
    # Try string normalization
    if str(expected).strip().lower() == str(actual).strip().lower():
        return 0.9
    return 0.0


def eval_golden_set(
    agent_fn: Callable[..., Any],
    cases: list[EvalCase],
    *,
    comparator: Callable[[Any, Any], float] | None = None,
    threshold: float = 0.8,
) -> list[EvalResult]:
    """Run agent against golden-set cases and score results.

    Args:
        agent_fn: The agent function to evaluate. Called with case.input.
        cases: List of evaluation cases with expected outputs.
        comparator: Scoring function(expected, actual) -> float [0.0-1.0].
            Defaults to exact match.
        threshold: Minimum score to consider a case as passed.

    Returns:
        List of EvalResult for each case.
    """
    cmp = comparator or _default_comparator
    results: list[EvalResult] = []

    for case in cases:
        try:
            actual = agent_fn(case.input)
            score = cmp(case.expected, actual)
            results.append(
                EvalResult(
                    case=case,
                    actual=actual,
                    passed=score >= threshold,
                    score=score,
                )
            )
        except Exception as exc:
            results.append(
                EvalResult(
                    case=case,
                    actual=None,
                    passed=False,
                    score=0.0,
                    details=f"Exception: {exc}",
                )
            )

    return results


async def eval_golden_set_async(
    agent_fn: Callable[..., Any],
    cases: list[EvalCase],
    *,
    comparator: Callable[[Any, Any], float] | None = None,
    threshold: float = 0.8,
) -> list[EvalResult]:
    """Async version of eval_golden_set."""
    cmp = comparator or _default_comparator
    results: list[EvalResult] = []

    for case in cases:
        try:
            actual = await agent_fn(case.input)
            score = cmp(case.expected, actual)
            results.append(
                EvalResult(
                    case=case,
                    actual=actual,
                    passed=score >= threshold,
                    score=score,
                )
            )
        except Exception as exc:
            results.append(
                EvalResult(
                    case=case,
                    actual=None,
                    passed=False,
                    score=0.0,
                    details=f"Exception: {exc}",
                )
            )

    return results


# --- LLM-as-Judge ---

_JUDGE_PROMPT_TEMPLATE = """\
You are an evaluation judge. Score the following agent output \
on a scale of 0.0 to 1.0.

Criteria: {criteria}

{context_section}

Agent Output:
{output}

Respond in JSON format:
{{"score": <float 0.0-1.0>, "reasoning": "<brief explanation>"}}"""


def llm_judge(
    agent_output: Any,
    *,
    criteria: str,
    judge_fn: Callable[[str], str],
    context: str = "",
) -> JudgeVerdict:
    """Use an LLM to judge agent output quality.

    Args:
        agent_output: The output to evaluate.
        criteria: What to evaluate (e.g. "correctness", "helpfulness").
        judge_fn: A callable that takes a prompt string and returns LLM text response.
        context: Optional context about the task.

    Returns:
        JudgeVerdict with score, reasoning, and criteria.
    """
    context_section = f"Context: {context}" if context else ""
    prompt = _JUDGE_PROMPT_TEMPLATE.format(
        criteria=criteria,
        context_section=context_section,
        output=str(agent_output),
    )

    response = judge_fn(prompt)
    return _parse_judge_response(response, criteria)


async def llm_judge_async(
    agent_output: Any,
    *,
    criteria: str,
    judge_fn: Callable[[str], Any],
    context: str = "",
) -> JudgeVerdict:
    """Async version of llm_judge."""
    context_section = f"Context: {context}" if context else ""
    prompt = _JUDGE_PROMPT_TEMPLATE.format(
        criteria=criteria,
        context_section=context_section,
        output=str(agent_output),
    )

    response = await judge_fn(prompt)
    return _parse_judge_response(response, criteria)


def _parse_judge_response(response: str, criteria: str) -> JudgeVerdict:
    """Parse LLM judge response into a JudgeVerdict."""
    try:
        # Try to extract JSON from response
        text = response.strip()
        # Handle markdown code blocks
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        data = json.loads(text)
        return JudgeVerdict(
            score=float(data.get("score", 0.0)),
            reasoning=str(data.get("reasoning", "")),
            criteria=criteria,
        )
    except (json.JSONDecodeError, ValueError, IndexError):
        # Fallback: try to extract a number
        import re

        match = re.search(r"(\d+\.?\d*)", response)
        score = float(match.group(1)) if match else 0.0
        score = min(score, 1.0)
        return JudgeVerdict(
            score=score,
            reasoning=response[:200],
            criteria=criteria,
        )
