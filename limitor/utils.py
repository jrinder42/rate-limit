from __future__ import annotations

import inspect
from collections.abc import Callable
from decimal import Decimal
from functools import wraps
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


def ensure_decimal_amount[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Decorator to ensure that the 'amount' argument is of type Decimal

    Args:
        func: The function to decorate

    Returns:
        A decorated function that ensures 'amount' is a Decimal
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        if "amount" in bound.arguments:
            amt = bound.arguments["amount"]
            if not isinstance(amt, Decimal):
                bound.arguments["amount"] = Decimal(amt)

        return func(*bound.args, **bound.kwargs)

    return wrapper
