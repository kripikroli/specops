"""Self-healing policy engine for SpecOps.

Provides pluggable recovery policies (retry, fallback, escalate, prune_memory)
and a @self_healing decorator that applies them to agent functions.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

from opentelemetry import trace

from specops.config import get_tracer

F = TypeVar("F", bound=Callable[..., Any])

logger = logging.getLogger("specops.heal")

# --- Constants ---

HEAL_POLICY = "specops.heal.policy"
HEAL_ATTEMPT = "specops.heal.attempt"
HEAL_OUTCOME = "specops.heal.outcome"
HEAL_FALLBACK = "specops.heal.fallback"


# --- Policy Types ---


class PolicyAction(Enum):
    """Actions a policy can take."""

    RETRY = "retry"
    FALLBACK = "fallback_agent"
    ESCALATE = "escalate_to_human"
    PRUNE_MEMORY = "prune_memory"


@dataclass
class PolicyResult:
    """Result of a policy execution."""

    action: PolicyAction
    success: bool
    result: Any = None
    error: Exception | None = None
    attempts: int = 0


@dataclass
class RetryPolicy:
    """Retry with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay cap in seconds.
        retryable: Optional predicate to check if exception is retryable.
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    retryable: Callable[[Exception], bool] | None = None

    def should_retry(self, exc: Exception) -> bool:
        """Check if the exception is retryable."""
        if self.retryable:
            return self.retryable(exc)
        return True

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt (exponential backoff)."""
        delay = self.base_delay * (2 ** (attempt - 1))
        return float(min(delay, self.max_delay))


@dataclass
class FallbackPolicy:
    """Fallback to an alternative callable on failure.

    Args:
        fallback_fn: The fallback function to call.
        trigger: Optional predicate; if provided, only triggers on matching exceptions.
    """

    fallback_fn: Callable[..., Any]
    trigger: Callable[[Exception], bool] | None = None

    def should_fallback(self, exc: Exception) -> bool:
        """Check if fallback should be triggered."""
        if self.trigger:
            return self.trigger(exc)
        return True


@dataclass
class EscalatePolicy:
    """Escalate to a human handler on failure.

    Args:
        handler: Callable that receives (function_name, args, kwargs, exception).
    """

    handler: Callable[..., Any]


@dataclass
class PruneMemoryPolicy:
    """Prune context/memory and retry on token limit errors.

    Args:
        prune_fn: Callable that takes (args, kwargs) and returns pruned (args, kwargs).
        max_prunes: Maximum number of prune-and-retry cycles.
    """

    prune_fn: Callable[
        [tuple[Any, ...], dict[str, Any]], tuple[tuple[Any, ...], dict[str, Any]]
    ]
    max_prunes: int = 2


# --- Healing Chain ---


@dataclass
class HealingChain:
    """Ordered chain of policies to apply on failure.

    Policies are tried in order. The first successful policy wins.
    """

    policies: list[
        RetryPolicy | FallbackPolicy | EscalatePolicy | PruneMemoryPolicy
    ] = field(default_factory=list)

    def add(
        self, policy: RetryPolicy | FallbackPolicy | EscalatePolicy | PruneMemoryPolicy
    ) -> HealingChain:
        """Add a policy to the chain. Returns self for chaining."""
        self.policies.append(policy)
        return self


# --- Policy Executor ---


def _execute_retry_sync(
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    policy: RetryPolicy,
    span: trace.Span,
) -> PolicyResult:
    """Execute retry policy synchronously."""
    last_exc: Exception | None = None
    for attempt in range(1, policy.max_retries + 1):
        span.set_attribute(HEAL_ATTEMPT, attempt)
        delay = policy.get_delay(attempt)
        time.sleep(delay)
        try:
            result = fn(*args, **kwargs)
            return PolicyResult(
                action=PolicyAction.RETRY, success=True, result=result, attempts=attempt
            )
        except Exception as exc:
            last_exc = exc
            if not policy.should_retry(exc):
                break
    return PolicyResult(
        action=PolicyAction.RETRY,
        success=False,
        error=last_exc,
        attempts=policy.max_retries,
    )


async def _execute_retry_async(
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    policy: RetryPolicy,
    span: trace.Span,
) -> PolicyResult:
    """Execute retry policy asynchronously."""
    last_exc: Exception | None = None
    for attempt in range(1, policy.max_retries + 1):
        span.set_attribute(HEAL_ATTEMPT, attempt)
        delay = policy.get_delay(attempt)
        await asyncio.sleep(delay)
        try:
            result = await fn(*args, **kwargs)
            return PolicyResult(
                action=PolicyAction.RETRY, success=True, result=result, attempts=attempt
            )
        except Exception as exc:
            last_exc = exc
            if not policy.should_retry(exc):
                break
    return PolicyResult(
        action=PolicyAction.RETRY,
        success=False,
        error=last_exc,
        attempts=policy.max_retries,
    )


def _execute_fallback_sync(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    policy: FallbackPolicy,
) -> PolicyResult:
    """Execute fallback policy synchronously."""
    try:
        result = policy.fallback_fn(*args, **kwargs)
        return PolicyResult(action=PolicyAction.FALLBACK, success=True, result=result)
    except Exception as exc:
        return PolicyResult(action=PolicyAction.FALLBACK, success=False, error=exc)


async def _execute_fallback_async(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    policy: FallbackPolicy,
) -> PolicyResult:
    """Execute fallback policy asynchronously."""
    try:
        if inspect.iscoroutinefunction(policy.fallback_fn):
            result = await policy.fallback_fn(*args, **kwargs)
        else:
            result = policy.fallback_fn(*args, **kwargs)
        return PolicyResult(action=PolicyAction.FALLBACK, success=True, result=result)
    except Exception as exc:
        return PolicyResult(action=PolicyAction.FALLBACK, success=False, error=exc)


def _execute_prune_sync(
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    policy: PruneMemoryPolicy,
) -> PolicyResult:
    """Execute prune-memory policy synchronously."""
    current_args, current_kwargs = args, kwargs
    for i in range(policy.max_prunes):
        current_args, current_kwargs = policy.prune_fn(current_args, current_kwargs)
        try:
            result = fn(*current_args, **current_kwargs)
            return PolicyResult(
                action=PolicyAction.PRUNE_MEMORY,
                success=True,
                result=result,
                attempts=i + 1,
            )
        except Exception:
            continue
    return PolicyResult(
        action=PolicyAction.PRUNE_MEMORY, success=False, attempts=policy.max_prunes
    )


async def _execute_prune_async(
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    policy: PruneMemoryPolicy,
) -> PolicyResult:
    """Execute prune-memory policy asynchronously."""
    current_args, current_kwargs = args, kwargs
    for i in range(policy.max_prunes):
        current_args, current_kwargs = policy.prune_fn(current_args, current_kwargs)
        try:
            result = await fn(*current_args, **current_kwargs)
            return PolicyResult(
                action=PolicyAction.PRUNE_MEMORY,
                success=True,
                result=result,
                attempts=i + 1,
            )
        except Exception:
            continue
    return PolicyResult(
        action=PolicyAction.PRUNE_MEMORY, success=False, attempts=policy.max_prunes
    )


# --- Decorator ---


def self_healing(
    chain: HealingChain | None = None,
    *,
    retry: RetryPolicy | None = None,
    fallback: FallbackPolicy | None = None,
    escalate: EscalatePolicy | None = None,
    prune_memory: PruneMemoryPolicy | None = None,
) -> Callable[[F], F]:
    """Apply self-healing policies to a function.

    Can accept either a pre-built HealingChain or individual policies.
    Individual policies are applied in order:
    retry -> prune_memory -> fallback -> escalate.

    Args:
        chain: A pre-built HealingChain. Overrides individual policies.
        retry: Retry policy with exponential backoff.
        fallback: Fallback to alternative function.
        escalate: Escalate to human handler.
        prune_memory: Prune context and retry.

    Example:
        @self_healing(retry=RetryPolicy(max_retries=3))
        def call_llm(prompt: str) -> str:
            ...
    """
    healing_chain = chain or HealingChain()
    if not chain:
        if retry:
            healing_chain.add(retry)
        if prune_memory:
            healing_chain.add(prune_memory)
        if fallback:
            healing_chain.add(fallback)
        if escalate:
            healing_chain.add(escalate)

    def decorator(fn: F) -> F:
        is_async = inspect.iscoroutinefunction(fn)

        @functools.wraps(fn)
        async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.start_as_current_span(f"heal:{fn.__name__}") as span:
                # Try original call first
                try:
                    return await fn(*args, **kwargs)
                except Exception as original_exc:
                    span.record_exception(original_exc)
                    # Apply policies in order
                    for policy in healing_chain.policies:
                        pr = await _apply_policy_async(
                            fn, args, kwargs, policy, original_exc, span
                        )
                        if pr and pr.success:
                            span.set_attribute(HEAL_OUTCOME, "healed")
                            span.set_attribute(HEAL_POLICY, pr.action.value)
                            return pr.result
                    span.set_attribute(HEAL_OUTCOME, "failed")
                    span.set_status(trace.StatusCode.ERROR, str(original_exc))
                    raise

        @functools.wraps(fn)
        def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.start_as_current_span(f"heal:{fn.__name__}") as span:
                try:
                    return fn(*args, **kwargs)
                except Exception as original_exc:
                    span.record_exception(original_exc)
                    for policy in healing_chain.policies:
                        pr = _apply_policy_sync(
                            fn, args, kwargs, policy, original_exc, span
                        )
                        if pr and pr.success:
                            span.set_attribute(HEAL_OUTCOME, "healed")
                            span.set_attribute(HEAL_POLICY, pr.action.value)
                            return pr.result
                    span.set_attribute(HEAL_OUTCOME, "failed")
                    span.set_status(trace.StatusCode.ERROR, str(original_exc))
                    raise

        return _async_wrapper if is_async else _sync_wrapper  # type: ignore[return-value]

    return decorator


def _apply_policy_sync(
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    policy: RetryPolicy | FallbackPolicy | EscalatePolicy | PruneMemoryPolicy,
    exc: Exception,
    span: trace.Span,
) -> PolicyResult | None:
    """Apply a single policy synchronously."""
    if isinstance(policy, RetryPolicy):
        if policy.should_retry(exc):
            return _execute_retry_sync(fn, args, kwargs, policy, span)
    elif isinstance(policy, FallbackPolicy):
        if policy.should_fallback(exc):
            span.set_attribute(HEAL_FALLBACK, str(policy.fallback_fn.__name__))
            return _execute_fallback_sync(args, kwargs, policy)
    elif isinstance(policy, PruneMemoryPolicy):
        return _execute_prune_sync(fn, args, kwargs, policy)
    elif isinstance(policy, EscalatePolicy):
        try:
            result = policy.handler(fn.__name__, args, kwargs, exc)
            return PolicyResult(
                action=PolicyAction.ESCALATE, success=True, result=result
            )
        except Exception as handler_exc:
            return PolicyResult(
                action=PolicyAction.ESCALATE, success=False, error=handler_exc
            )
    return None


async def _apply_policy_async(
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    policy: RetryPolicy | FallbackPolicy | EscalatePolicy | PruneMemoryPolicy,
    exc: Exception,
    span: trace.Span,
) -> PolicyResult | None:
    """Apply a single policy asynchronously."""
    if isinstance(policy, RetryPolicy):
        if policy.should_retry(exc):
            return await _execute_retry_async(fn, args, kwargs, policy, span)
    elif isinstance(policy, FallbackPolicy):
        if policy.should_fallback(exc):
            span.set_attribute(HEAL_FALLBACK, str(policy.fallback_fn.__name__))
            return await _execute_fallback_async(args, kwargs, policy)
    elif isinstance(policy, PruneMemoryPolicy):
        return await _execute_prune_async(fn, args, kwargs, policy)
    elif isinstance(policy, EscalatePolicy):
        try:
            if inspect.iscoroutinefunction(policy.handler):
                result = await policy.handler(fn.__name__, args, kwargs, exc)
            else:
                result = policy.handler(fn.__name__, args, kwargs, exc)
            return PolicyResult(
                action=PolicyAction.ESCALATE, success=True, result=result
            )
        except Exception as handler_exc:
            return PolicyResult(
                action=PolicyAction.ESCALATE, success=False, error=handler_exc
            )
    return None
