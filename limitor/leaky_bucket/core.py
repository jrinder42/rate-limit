"""Leaky Bucket Rate Limiter Implementation"""

from __future__ import annotations

import asyncio
import time
from contextlib import nullcontext
from dataclasses import dataclass
from types import TracebackType
from typing import NamedTuple


@dataclass
class LeakyBucketConfig:
    """Configuration for the Leaky Bucket Rate Limiter"""

    capacity: float = 10
    """Maximum number of items the bucket can hold i.e. number of requests that can be processed at once"""

    seconds: float = 1
    """Up to `capacity` acquisitions are allowed within this time period in a burst"""

    def __post_init__(self) -> None:
        """Validate the configuration parameters"""
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


class SyncLeakyBucket:
    """Leaky Bucket Rate Limiter

    Args:
        leaky_bucket_config: Configuration for the leaky bucket with the max capacity and time period in seconds

    Note:
        This implementation is synchronous and supports bursts up to the capacity within the specified time period
    """

    def __init__(self, leaky_bucket_config: LeakyBucketConfig | None):
        # import config and set attributes
        config = leaky_bucket_config or LeakyBucketConfig()
        self.capacity = config.capacity
        self.seconds = config.seconds

        self.leak_rate = self.capacity / self.seconds  # units per second

        self._bucket_level = 0.0  # current volume in the bucket
        self._last_leak = time.monotonic()  # last leak time

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

    def acquire(self, amount: float = 1) -> None:
        """Acquire capacity from the leaky bucket, blocking until enough capacity is available.

        This method will block and sleep until the requested amount can be acquired
        without exceeding the bucket's capacity, simulating rate limiting.

        Args:
            amount: The amount of capacity to acquire, defaults to 1

        Raises:
            ValueError: If the requested amount exceeds the bucket's capacity

        Notes:
            The while loop is just to make sure nothing funny happens while waiting
        """
        if amount > self.capacity:
            raise ValueError(f"Cannot acquire more than the bucket's capacity: {self.capacity}")

        capacity_info = self.capacity_info()
        while not capacity_info.has_capacity:
            needed = capacity_info.needed_capacity
            # amount we need to wait to leak (either part or the entire capacity)
            # needed is guaranteed to be positive here, so we can use it directly
            wait_time = needed / self.leak_rate
            if wait_time > 0:
                time.sleep(wait_time)

            capacity_info = self.capacity_info()

        self._bucket_level += amount

    def __enter__(self) -> SyncLeakyBucket:
        """Enter the context manager, acquiring resources if necessary"""
        self.acquire()
        return self

    def __exit__(self, exc_type: type[BaseException], exc_val: BaseException, exc_tb: TracebackType) -> None:
        """Exit the context manager, releasing any resources if necessary"""
        return None


class AsyncLeakyBucket:
    """Asynchronous Leaky Bucket Rate Limiter

    Args:
        leaky_bucket_config: Configuration for the leaky bucket with the max capacity and time period in seconds
        max_concurrent: Maximum number of concurrent requests allowed to acquire capacity

    Note:
        This implementation is synchronous and supports bursts up to the capacity within the specified time period
    """

    def __init__(self, leaky_bucket_config: LeakyBucketConfig | None = None, max_concurrent: int | None = None):
        config = leaky_bucket_config or LeakyBucketConfig()
        self.capacity = config.capacity
        self.seconds = config.seconds

        self.leak_rate = self.capacity / self.seconds
        self._bucket_level = 0.0
        self._last_leak = time.monotonic()

        self.max_concurrent = max_concurrent
        self._lock = asyncio.Lock()

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

    async def _acquire_logic(self, amount: float = 1) -> None:
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
        async with self._lock:  # ensures atomicity given we can have multiple concurrent requests
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

    async def _semaphore_acquire(self, amount: float = 1) -> None:
        """Acquire capacity using a semaphore to limit concurrency.

        Args:
            amount: The amount of capacity to acquire, defaults to 1
        """
        semaphore = asyncio.Semaphore(self.max_concurrent) if self.max_concurrent else nullcontext()
        async with semaphore:
            await self._acquire_logic(amount)

    async def acquire(self, amount: float = 1, timeout: float | None = None) -> None:
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
                await asyncio.wait_for(self._semaphore_acquire(amount), timeout=timeout)
            except TimeoutError as error:
                raise TimeoutError(f"Acquire timed out after {timeout} seconds for amount={amount}") from error
        else:
            await self._semaphore_acquire(amount)

    async def __aenter__(self) -> AsyncLeakyBucket:
        """Enter the context manager, acquiring resources if necessary"""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type: type[BaseException], exc_val: BaseException, exc_tb: TracebackType) -> None:
        """Exit the context manager, releasing any resources if necessary"""
        return None
