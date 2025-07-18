"""Token Bucket Rate Limiter Implementation"""

from __future__ import annotations

import time
from dataclasses import dataclass
from types import TracebackType
from typing import NamedTuple


@dataclass
class TokenBucketConfig:
    """Configuration for the Token Bucket Rate Limiter"""

    capacity: int = 10
    """Maximum number of tokens the bucket can hold i.e. number of requests that can be processed at once"""

    seconds: float = 1
    """Up to `capacity` acquisitions are allowed within this time period in a burst"""

    def __post_init__(self):
        """Validate the configuration parameters"""
        fill_rate_per_sec = self.capacity / self.seconds
        if fill_rate_per_sec <= 0:
            raise ValueError("fill_rate_per_sec must be positive and non-zero")

        if self.capacity < 1:
            raise ValueError("capacity must be at least 1")


# TODO: pull this out into a config module (same as the leaky bucket file)
class Capacity(NamedTuple):
    """Information about the current capacity of the leaky bucket"""

    has_capacity: bool
    """Indicates if the bucket has enough capacity to accommodate the requested amount"""

    needed_capacity: float
    """Amount of capacity needed to accommodate the request, if any"""


class SyncTokenBucket:
    """Token Bucket Rate Limiter

    Args:
        token_bucket_config: Configuration for the token bucket with the max capacity and time period in seconds

    Note:
        This implementation is synchronous and supports bursts up to the capacity within the specified time period
    """

    def __init__(self, token_bucket_config: TokenBucketConfig | None):
        # import config and set attributes
        config = token_bucket_config or TokenBucketConfig()
        for key, value in vars(config).items():
            setattr(self, key, value)

        self.fill_rate = self.capacity / self.seconds  # units per second

        self._bucket_level = self.capacity  # current volume of tokens in the bucket
        self._last_fill = time.monotonic()  # last refill time

    def _fill(self) -> None:
        """Fill the bucket based on the elapsed time since the last fill"""
        now = time.monotonic()
        elapsed = now - self._last_fill
        self._bucket_level = min(self.capacity, self._bucket_level + elapsed * self.fill_rate)
        self._last_fill = now

    def capacity_info(self, amount: float = 1) -> Capacity:
        """Get the current capacity information of the leaky bucket

        Args:
            amount: The amount of capacity to check for, defaults to 1

        Returns:
            A named tuple indicating if the bucket has enough capacity and how much more is needed
        """
        self._fill()
        # we need at least `amount` tokens to proceed
        needed = amount - self._bucket_level
        return Capacity(has_capacity=needed <= 0, needed_capacity=needed)

    def acquire(self, amount: float = 1) -> None:
        """Acquire capacity from the token bucket, blocking until enough capacity is available.

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
            # amount we need to wait to leak
            # needed is guaranteed to be positive here, so we can use it directly
            wait_time = needed / self.fill_rate
            if wait_time > 0:
                time.sleep(wait_time)

            capacity_info = self.capacity_info()

        self._bucket_level -= amount

    def __enter__(self) -> SyncTokenBucket:
        """Enter the context manager, acquiring resources if necessary"""
        self.acquire()
        return self

    def __exit__(self, exc_type: type[BaseException], exc_val: BaseException, exc_tb: TracebackType) -> None:
        """Exit the context manager, releasing any resources if necessary"""
        return None
