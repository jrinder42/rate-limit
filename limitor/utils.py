from __future__ import annotations

from typing import ParamSpec, TypeVar

from limitor.base import HasCapacity

# https://docs.python.org/3/reference/compound_stmts.html#type-parameter-lists
P = ParamSpec("P")  # parameters
R = TypeVar("R")  # return type


def validate_amount(rate_limiter: HasCapacity, amount: float) -> None:
    """Validate the requested amount for acquire

    Args:
        rate_limiter: the rate limiter i.e. SyncLeakyBucket or AsyncTokenBucket
        amount: The amount of capacity to acquire

    Raises:
        ValueError: If the requested amount exceeds the bucket's capacity or is negative
    """
    if amount > rate_limiter.capacity:
        raise ValueError(f"Cannot acquire more than the bucket's capacity: {rate_limiter.capacity}")

    if amount < 0:
        raise ValueError(f"Cannot acquire less than 0 amount with amount: {amount}")
