import asyncio
import random
import time

import httpx

from limitor.configs import BucketConfig
from limitor.extra.leaky_bucket.core import AsyncLeakyBucket
from limitor.leaky_bucket.core import AsyncLeakyBucket as ALB

# --------------------------- #

# Queue-based

# --------------------------- #

print("Predictable queue example (no context manager)\n")


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


print("\nEven steven queue example\n")


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

print("\nSimple Leaky Bucket Algorithm\n")


async def main():
    bucket = ALB(BucketConfig(capacity=2, seconds=2))
    for i in range(10):
        await bucket.acquire()
        print(f"Request {i + 1} allowed at {time.strftime('%X')}")


asyncio.run(main())

print("\nAnther Uneven Leaky Bucket Algorithm\n")


async def request(bucket, amount, idx):
    await bucket.acquire(amount)
    print(f"Request {idx} (amount={amount}) allowed at {time.strftime('%X')}")


async def main():
    bucket = ALB(bucket_config=BucketConfig(capacity=3, seconds=3), max_concurrent=5)
    amounts = [1, 3, 2, 1, 2, 3, 1]
    tasks = [asyncio.create_task(request(bucket, amt, i)) for i, amt in enumerate(amounts, 1)]
    await asyncio.gather(*tasks)


asyncio.run(main())

print("\nGeneral Example: Async HTTP Requests\n")


async def fetch_url(bucket, client, url, idx, timeout):
    try:
        await bucket.acquire(timeout=timeout)
        response = await client.get(url, timeout=timeout)
        text = response.text
        print(f"Request {idx} succeeded: {len(text)} bytes at {time.strftime('%X')}")
        return url
    except TimeoutError:
        print(f"Request {idx} timed out by rate limiter at {time.strftime('%X')}")
    except Exception as e:
        print(f"Request {idx} failed: {e}")


async def main():
    bucket = AsyncLeakyBucket(BucketConfig(capacity=2, seconds=2))
    urls = [
        "https://example.com",
        "https://httpbin.org/get",
        "https://httpbin.org/delay/1",
        "https://httpbin.org/delay/2",
        "https://example.com",
        "https://httpbin.org/get",
    ]
    res = []
    async with httpx.AsyncClient() as client:
        tasks = [fetch_url(bucket, client, url, idx, random.uniform(0.5, 2.5)) for idx, url in enumerate(urls, 1)]
        res = await asyncio.gather(*tasks)
    await bucket.shutdown()

    return res


results = asyncio.run(main())
print(results)  # make sure things are returns in order
