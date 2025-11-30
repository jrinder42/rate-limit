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


def ensure_decimal_amount[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Decorator to ensure that the 'amount' argument is of type Decimal

    Args:
        func: The function to decorate

    Returns:
        A decorated function that ensures 'amount' is a Decimal
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        """Wrapper function to ensure 'amount' is a Decimal

        Args:
            *args: Positional arguments to the function
            **kwargs: Keyword arguments to the function

        Returns:
            The result of the decorated function

        Raises:
            TypeError: If 'amount' is not of type int, float, or Decimal
        """
        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        if "amount" in bound.arguments:
            amt = bound.arguments["amount"]
            if not isinstance(amt, (int, float, Decimal)):  # noqa: UP038
                raise TypeError(f"amount must be of type int, float, or Decimal, got {type(amt)}")
            if isinstance(amt, Decimal):
                bound.arguments["amount"] = Decimal(amt)

        return func(*bound.args, **bound.kwargs)

    return wrapper


@ensure_decimal_amount
def validate_amount(rate_limiter: HasCapacity, amount: Decimal) -> None:
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
