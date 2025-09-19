import asyncio
import time

from limitor.configs import BucketConfig
from limitor.extra.leaky_bucket.core import AsyncLeakyBucket

# --------------------------- #

# Queue-based

# --------------------------- #

print("Predictable queue example (no context manager)")


async def request_with_timeout(bucket: AsyncLeakyBucket, amount: float, idx: int, timeout: float) -> None:
    """Request with timeout"""
    try:
        await bucket.acquire(amount, timeout=timeout)
        print(f"Request {idx} (amount={amount}, timeout={timeout}) allowed at {time.strftime('%X')}")
    except TimeoutError as e:
        print(f"Request {idx} (amount={amount}, timeout={timeout}) timed out: {e}")


async def uneven_timeout() -> None:
    """Uneven timeout example"""
    bucket = AsyncLeakyBucket(BucketConfig(capacity=2, seconds=2))
    requests = [
        (2, 1, 1),  # should succeed (bucket full)
        (2, 2, 1),  # should timeout (needs refill)
        (1, 3, 1.5),  # should succeed (after partial refill)
        (2, 4, 2),  # should succeed (enough time to refill)
        (2, 5, 0.5),  # should timeout (not enough time)
        (1, 6, 2),  # should succeed (after refill)
    ]
    for amt, idx, timeout in requests:
        await request_with_timeout(bucket, amt, idx, timeout)
    await bucket.shutdown()


asyncio.run(uneven_timeout())


print("Even steven queue example (no context manager)")


async def even_timeout() -> None:
    """Even steven queue example"""
    bucket = AsyncLeakyBucket(BucketConfig(capacity=2, seconds=2))
    requests = [
        (1, 1, 1),  # should succeed (bucket full)
        (1, 2, 1),  # should timeout (needs refill)
        (1, 3, 1),  # should succeed (after partial refill)
        (1, 4, 1),  # should succeed (enough time to refill)
        (1, 5, 1),  # should timeout (not enough time)
        (1, 6, 1),  # should succeed (after refill)
    ]
    for amt, idx, timeout in requests:
        await request_with_timeout(bucket, amt, idx, timeout)
    await bucket.shutdown()


asyncio.run(even_timeout())
