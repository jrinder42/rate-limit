"""Async Leaky Bucket Rate Limiter (predictable, queue-based version)"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from types import TracebackType
from typing import Any, NamedTuple


@dataclass
class LeakyBucketConfig:
    capacity: float = 10
    seconds: float = 1.0

    def __post_init__(self) -> None:
        leak_rate_per_sec = self.capacity / self.seconds
        if leak_rate_per_sec <= 0:
            raise ValueError("leak_rate_per_sec must be positive and non-zero")
        if self.capacity < 1:
            raise ValueError("capacity must be at least 1")


class Capacity(NamedTuple):
    """Information about the current capacity of the leaky bucket"""

    has_capacity: bool
    """Indicates if the bucket has enough capacity to accommodate the requested amount"""

    needed_capacity: float
    """Amount of capacity needed to accommodate the request, if any"""


class AsyncLeakyBucket:
    """Async Leaky Bucket Rate Limiter - Queue-based implementation

    Args:
        leaky_bucket_config: Configuration for the leaky bucket with the max capacity and time period in seconds

    Note:
        This implementation is synchronous and supports bursts up to the capacity within the specified time period
    """

    def __init__(self, leaky_bucket_config: LeakyBucketConfig | None = None):
        config = leaky_bucket_config or LeakyBucketConfig()
        self.capacity = config.capacity
        self.seconds = config.seconds

        self.leak_rate = self.capacity / self.seconds
        self._bucket_level = 0.0
        self._last_leak = time.monotonic()
        self._queue: asyncio.Queue[Any] = asyncio.Queue()
        self._worker_task = asyncio.create_task(self._worker())

    def _leak(self) -> None:
        """Leak the bucket based on the elapsed time since the last leak"""
        now = time.monotonic()
        elapsed = now - self._last_leak
        self._bucket_level = max(0.0, self._bucket_level - elapsed * self.leak_rate)
        self._last_leak = now

    def capacity_info(self, amount: float = 1) -> Capacity:
        """Get the current capacity information of the leaky bucket

        Args:
            amount: The amount of capacity to check for, defaults to 1

        Returns:
            A named tuple indicating if the bucket has enough capacity and how much more is needed
        """
        self._leak()
        needed = self._bucket_level + amount - self.capacity
        return Capacity(has_capacity=needed <= 0, needed_capacity=needed)

    async def _worker(self) -> None:  # single-worker coroutine
        """Worker coroutine that processes requests from the queue."""
        while True:
            item = await self._queue.get()
            if item is None:
                self._queue.task_done()
                break

            amount, future, timeout = item
            try:
                await self._timeout_acquire(amount, timeout)
                future.set_result(True)  # note: this can be set to anything
            except Exception as error:
                future.set_exception(error)

            self._queue.task_done()

    async def _acquire_logic(self, amount: float) -> None:
        """Core logic for acquiring capacity from the leaky bucket.

        Args:
            amount: The amount of capacity to check for, defaults to 1

        Notes:
            Adding a lock here ensures that the acquire logic is atomic, but it also means that the
                requests are going to be done in the order they were received  i.e. not out-of-order like
                most async programs.
            The benefit is that with multiple concurrent requests, we can ensure that the bucket level
                is updated correctly and that we don't have multiple requests trying to update the bucket level
                at the same time, which could lead to an inconsistent state i.e. a race condition.
        """
        capacity_info = self.capacity_info()
        while not capacity_info.has_capacity:
            needed = capacity_info.needed_capacity
            # amount we need to wait to leak (either part or the entire capacity)
            # needed is guaranteed to be positive here, so we can use it directly
            wait_time = needed / self.leak_rate
            if wait_time > 0:
                await asyncio.sleep(wait_time)

            capacity_info = self.capacity_info()

        self._bucket_level += amount

    async def _timeout_acquire(self, amount: float, timeout: float | None) -> None:
        """Acquire capacity from the leaky bucket, waiting asynchronously until allowed.

        Supports timeout and cancellation.

        Args:
            amount: The amount of capacity to acquire, defaults to 1
            timeout: Optional timeout in seconds for the acquire operation

        Raises:
            ValueError: If the requested amount exceeds the bucket's capacity
            TimeoutError: If the acquire operation times out after the specified timeout period
        """
        if amount > self.capacity:
            raise ValueError(f"Cannot acquire more than the bucket's capacity: {self.capacity}")

        if timeout is not None:
            try:
                await asyncio.wait_for(self._acquire_logic(amount), timeout=timeout)
            except TimeoutError as error:
                raise TimeoutError(f"Acquire timed out after {timeout} seconds for amount={amount}") from error
        else:
            await self._acquire_logic(amount)

    async def acquire(self, amount: float = 1.0, timeout: float | None = None) -> None:
        """Acquire capacity from the leaky bucket, waiting asynchronously until allowed.

        Args:
            amount: The amount of capacity to acquire, defaults to 1
            timeout: Optional timeout in seconds for the acquire operation
        """
        future = asyncio.get_event_loop().create_future()
        await self._queue.put((amount, future, timeout))
        await future

    async def shutdown(self) -> None:
        """Gracefully shut down the worker task."""
        await self._queue.put(None)  # Sentinel value
        await self._worker_task

    async def __aenter__(self) -> AsyncLeakyBucket:
        """Enter the context manager, acquiring resources if necessary"""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type: type[BaseException], exc_val: BaseException, exc_tb: TracebackType) -> None:
        """Exit the context manager, releasing any resources if necessary"""
        await self.shutdown()
        return None


# --- Examples ---
# ruff: noqa
# pylint: disable=all
if __name__ == "__main__":
    print("Predictable queue example (no context manager)")

    async def request_with_timeout(bucket: AsyncLeakyBucket, amount: float, idx: int, timeout: float) -> None:
        try:
            await bucket.acquire(amount, timeout=timeout)
            print(f"Request {idx} (amount={amount}, timeout={timeout}) allowed at {time.strftime('%X')}")
        except TimeoutError as e:
            print(f"Request {idx} (amount={amount}, timeout={timeout}) timed out: {e}")

    async def main() -> None:
        bucket = AsyncLeakyBucket(LeakyBucketConfig(capacity=2, seconds=2))
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

    asyncio.run(main())

    print("Even steven queue example (no context manager)")

    async def main() -> None:
        bucket = AsyncLeakyBucket(LeakyBucketConfig(capacity=2, seconds=2))
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

    asyncio.run(main())

    # --- New Example: Using async context manager with concurrent requests ---
    print("Context manager example (concurrent requests, one per context)")

    async def request_cm(bucket: AsyncLeakyBucket, idx: int) -> None:
        async with bucket:
            print(f"[Context Manager] Request {idx} allowed at {time.strftime('%X')}")
            # await asyncio.sleep(0.2)  # Simulate work

    async def main() -> None:
        bucket = AsyncLeakyBucket(LeakyBucketConfig(capacity=2, seconds=2))
        tasks = [asyncio.create_task(request_cm(bucket, i)) for i in range(1, 7)]
        await asyncio.gather(*tasks)

    asyncio.run(main())
