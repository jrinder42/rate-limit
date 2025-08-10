"""Main module for rate limiting functionality."""
from __future__ import annotations

from typing import Callable

from limitor.base import AsyncRateLimit, SyncRateLimit
from limitor.leaky_bucket.core import (
    AsyncLeakyBucket,
    LeakyBucketConfig,
    SyncLeakyBucket,
)


def rate_limit(capacity: int = 10, seconds: float = 1, bucket_cls: type[SyncRateLimit] = SyncLeakyBucket) -> Callable:
    """Decorator to apply a synchronous leaky bucket rate limit to a function.

    Args:
        capacity: Maximum number of requests allowed in the bucket, defaults to 10
        seconds: Time period in seconds for the bucket to refill, defaults to 1
        bucket_cls: Bucket class, defaults to SyncLeakyBucket

    Returns:
        A decorator that applies the rate limit to the function
    """
    bucket = bucket_cls(LeakyBucketConfig(capacity=capacity, seconds=seconds))

    def decorator(func):
        def wrapper(*args, **kwargs):
            with bucket:
                return func(*args, **kwargs)

        return wrapper

    return decorator


def async_rate_limit(
    capacity: int = 10,
    seconds: float = 1,
    max_concurrent: int | None = None,
    bucket_cls: type[AsyncRateLimit] = AsyncLeakyBucket,
) -> Callable:
    """Decorator to apply an asynchronous leaky bucket rate limit to a function.

    Args:
        capacity: Maximum number of requests allowed in the bucket, defaults to 10
        seconds: Time period in seconds for the bucket to refill, defaults to 1
        max_concurrent: Maximum number of concurrent requests allowed, defaults to None (no limit)
        bucket_cls: Bucket class, defaults to AsyncLeakyBucket

    Returns:
        A decorator that applies the rate limit to the function
    """
    bucket = bucket_cls(LeakyBucketConfig(capacity=capacity, seconds=seconds), max_concurrent=max_concurrent)

    def decorator(func):
        async def wrapper(*args, **kwargs):
            async with bucket:
                return await func(*args, **kwargs)

        return wrapper

    return decorator


# pylint: disable=all
# ruff: noqa
if __name__ == "__main__":
    import asyncio
    import time

    @rate_limit(capacity=2, seconds=2)
    def something():
        print(f"This is a rate-limited function: {time.strftime('%X')}")

    for _ in range(10):
        try:
            something()
        except Exception as e:
            print(f"Rate limit exceeded: {e}")

    print("-----")
    print("async")

    @async_rate_limit(capacity=2, seconds=2)
    async def something_async():
        print(f"This is a rate-limited function: {time.strftime('%X')}")

    async def main():
        for _ in range(10):
            try:
                await something_async()
            except Exception as e:
                print(f"Rate limit exceeded: {e}")

    asyncio.run(main())
