import asyncio
import time

from limitor.configs import BucketConfig
from limitor.extra.leaky_bucket.core import AsyncLeakyBucket

print("Context manager example (concurrent requests, one per context)")


async def request_cm(bucket: AsyncLeakyBucket, idx: int) -> None:
    """Request with context manager

    Args:
        bucket: Leaky Bucket
        idx: Request index
    """
    async with bucket:
        print(f"[Context Manager] Request {idx} allowed at {time.strftime('%X')}")


async def main() -> None:
    """Main function to run the async context manager example"""
    bucket = AsyncLeakyBucket(BucketConfig(capacity=2, seconds=2))
    tasks = [asyncio.create_task(request_cm(bucket, i)) for i in range(1, 7)]
    await asyncio.gather(*tasks)


asyncio.run(main())
