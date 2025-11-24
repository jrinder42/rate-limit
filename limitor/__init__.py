"""Main module for rate limiting functionality."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar, overload

from limitor.base import AsyncRateLimit, SyncRateLimit
from limitor.configs import BucketConfig
from limitor.leaky_bucket.core import (
    AsyncLeakyBucket,
    SyncLeakyBucket,
)

P = ParamSpec("P")  # parameters
R = TypeVar("R")  # return type


@overload
def rate_limit[**P, R](
    _func: None = None,
    *,
    capacity: float = 10,
    seconds: float = 1,
    bucket_cls: type[SyncRateLimit] = SyncLeakyBucket,
) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


@overload
def rate_limit[**P, R](
    _func: Callable[P, R],
    *,
    capacity: float = 10,
    seconds: float = 1,
    bucket_cls: type[SyncRateLimit] = SyncLeakyBucket,
) -> Callable[P, R]: ...


def rate_limit[**P, R](
    _func: Callable[P, R] | None = None,
    *,
    capacity: float = 10,
    seconds: float = 1,
    bucket_cls: type[SyncRateLimit] = SyncLeakyBucket,
) -> Callable[P, R] | Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to apply a synchronous leaky bucket rate limit to a function.

    Args:
        _func: Function to apply the rate limit to the function
        capacity: Maximum number of requests allowed in the bucket, defaults to 10
        seconds: Time period in seconds for the bucket to refill, defaults to 1
        bucket_cls: Bucket class, defaults to SyncLeakyBucket

    Returns:
        A decorator that applies the rate limit to the function
    """
    bucket = bucket_cls(BucketConfig(capacity=capacity, seconds=seconds))

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with bucket:
                return func(*args, **kwargs)

        return wrapper

    if _func is None:
        return decorator
    return decorator(_func)


@overload
def async_rate_limit[**P, R](
    _func: None = None,
    *,
    capacity: float = 10,
    seconds: float = 1,
    max_concurrent: int | None = None,
    bucket_cls: type[AsyncRateLimit] = AsyncLeakyBucket,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]: ...


@overload
def async_rate_limit[**P, R](
    _func: Callable[P, Awaitable[R]],
    *,
    capacity: float = 10,
    seconds: float = 1,
    max_concurrent: int | None = None,
    bucket_cls: type[AsyncRateLimit] = AsyncLeakyBucket,
) -> Callable[P, Awaitable[R]]: ...


def async_rate_limit[**P, R](
    _func: Callable[P, Awaitable[R]] | None = None,
    *,
    capacity: float = 10,
    seconds: float = 1,
    max_concurrent: int | None = None,
    bucket_cls: type[AsyncRateLimit] = AsyncLeakyBucket,
) -> Callable[P, Awaitable[R]] | Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator to apply an asynchronous leaky bucket rate limit to a function.

    Args:
        _func: Function to apply the rate limit to the function
        capacity: Maximum number of requests allowed in the bucket, defaults to 10
        seconds: Time period in seconds for the bucket to refill, defaults to 1
        max_concurrent: Maximum number of concurrent requests allowed, defaults to None (no limit)
        bucket_cls: Bucket class, defaults to AsyncLeakyBucket

    Returns:
        A decorator that applies the rate limit to the function
    """
    bucket = bucket_cls(BucketConfig(capacity=capacity, seconds=seconds), max_concurrent=max_concurrent)

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            async with bucket:
                return await func(*args, **kwargs)

        return wrapper

    if _func is None:
        return decorator
    return decorator(_func)
