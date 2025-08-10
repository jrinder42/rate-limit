"""A simple synchronous implementation of the Generic Cell Rate Algorithm (GCRA)

References:
- https://en.wikipedia.org/wiki/Generic_cell_rate_algorithm
- https://en.wikipedia.org/wiki/Leaky_bucket
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from types import TracebackType


@dataclass
class GCRAConfig:
    """Configuration for the Token Bucket Rate Limiter"""

    capacity: int = 10
    """Maximum number of units we can hold i.e. number of requests that can be processed at once"""

    seconds: float = 1
    """Up to `capacity` acquisitions are allowed within this time period in a burst"""

    def __post_init__(self):
        """Validate the configuration parameters"""
        fill_rate_per_sec = self.capacity / self.seconds
        if fill_rate_per_sec <= 0:
            raise ValueError("fill_rate_per_sec must be positive and non-zero")

        if self.capacity < 1:
            raise ValueError("capacity must be at least 1")


class SyncVirtualSchedulingGCRA:
    """Virtual Scheduling Generic Cell Rate Algorithm Rate Limiter

    Args:
        gcra_config: Configuration for the GCR algorithm with the max capacity and time period in seconds

    Note:
        This implementation is synchronous and supports bursts up to the capacity within the specified time period

    References:
        https://en.wikipedia.org/wiki/Generic_cell_rate_algorithm
    """

    def __init__(self, gcra_config: GCRAConfig | None):
        # import config and set attributes
        config = gcra_config or GCRAConfig()
        for key, value in vars(config).items():
            setattr(self, key, value)

        self.leak_rate = self.capacity / self.seconds  # units per second
        self.T = 1 / self.leak_rate  # time to leak one unit

        # burst rate, but can't do this if the amount is variable
        # self.tau = self.T * self.burst

        # theoretical arrival time (TAT)
        self._tat = None

    def acquire(self, amount: float = 1) -> None:
        """Acquire resources, blocking if necessary to conform to the rate limit

        Args:
            amount: The amount of resources to acquire (default is 1)

        Raises:
            ValueError: If the amount exceeds the configured capacity
        """
        if amount > self.capacity:
            raise ValueError(f"Cannot acquire more than the capacity: {self.capacity}")

        t_a = time.monotonic()
        if self._tat is None:
            # first cell
            self._tat = t_a

        # note: we can also make `self.capacity - amount` as class param = burst i.e. independent of capacity
        tau = self.T * (self.capacity - amount)
        if t_a < self._tat - tau:
            delay = (self._tat - tau) - t_a
            time.sleep(delay)

        self._tat = max(t_a, self._tat) + amount * self.T

    def __enter__(self) -> SyncVirtualSchedulingGCRA:
        """Enter the context manager, acquiring resources if necessary

        Returns:
            An instance of the VirtualSchedulingGCRA class
        """
        self.acquire()
        return self

    def __exit__(self, exc_type: type[BaseException], exc_val: BaseException, exc_tb: TracebackType) -> None:
        """Exit the context manager, releasing any resources if necessary

        Args:
            exc_type: The type of the exception raised
            exc_val: The value of the exception raised
            exc_tb: The traceback object
        """
        return None


class SyncLeakyBucketGCRA:
    """Continuous-state Leaky Bucket Rate Limiter

    Args:
        gcra_config: Configuration for the GCR algorithm with the max capacity and time period in seconds

    Note:
        This implementation is synchronous and supports bursts up to the capacity within the specified time period

    References:
        https://en.wikipedia.org/wiki/Generic_cell_rate_algorithm
    """

    def __init__(self, gcra_config: GCRAConfig | None):
        # import config and set attributes
        config = gcra_config or GCRAConfig()
        for key, value in vars(config).items():
            setattr(self, key, value)

        self.leak_rate = self.capacity / self.seconds  # units per second
        self.T = 1 / self.leak_rate  # time to leak one unit

        # burst rate, but can't do this if the amount is variable
        # self.tau = self.T * self.burst

        self._bucket_level = 0  # current volume in the bucket
        self._last_leak = None  # same as last conforming time or LCT

    def acquire(self, amount: float = 1) -> None:
        """Acquire resources, blocking if necessary to conform to the rate limit

        Args:
            amount: The amount of resources to acquire (default is 1)

        Raises:
            ValueError: If the amount exceeds the configured capacity
        """
        if amount > self.capacity:
            raise ValueError(f"Cannot acquire more than the capacity: {self.capacity}")

        t_a = time.monotonic()
        if self._last_leak is None:
            # first cell
            self._bucket_level = 0
            self._last_leak = t_a

        elapsed = t_a - self._last_leak
        self._bucket_level = self._bucket_level - elapsed

        # note: we can also make `self.capacity - amount` as class param = burst i.e. independent of capacity
        tau = self.T * (self.capacity - amount)
        if self._bucket_level > tau:
            delay = self._bucket_level - tau
            time.sleep(delay)

            self._bucket_level = self._bucket_level - delay
            t_a += delay

        self._bucket_level = max(0.0, self._bucket_level) + amount * self.T
        self._last_leak = t_a

    def __enter__(self) -> SyncLeakyBucketGCRA:
        """Enter the context manager, acquiring resources if necessary

        Returns:
            An instance of the LeakyBucketGCRA class
        """
        self.acquire()
        return self

    def __exit__(self, exc_type: type[BaseException], exc_val: BaseException, exc_tb: TracebackType) -> None:
        """Exit the context manager, releasing any resources if necessary

        Args:
            exc_type: The type of the exception raised
            exc_val: The value of the exception raised
            exc_tb: The traceback object
        """
        return None


if __name__ == "__main__":
    """
    The Generic Cell Rate Algorithm (GCRA) offers several benefits
    over other rate limiting algorithms like the classic
    leaky bucket or token bucket:

    1. Precise Rate Enforcement:
    GCRA enforces both the average rate and burst size with mathematical
    precision, making it ideal for telecom and networking applications
    where strict compliance is required.

    2. Low Memory and Computational Overhead:
    GCRA only needs to track a single timestamp
    (theoretical arrival time, TAT), rather than maintaining a
    queue or counter. This makes it very efficient in terms of memory
    and CPU usage.

    3. Deterministic Behavior:
    Because it is based on time calculations rather than random drops or
    queue lengths, GCRA provides deterministic and predictable rate limiting.

    4. Smooth Handling of Bursts:
    GCRA allows for controlled bursts up to a defined burst size,
    but strictly enforces the average rate over time. This is useful
    for applications that need to tolerate short bursts but not
     sustained overload.

    5. Widely Used in Networking:
    GCRA is the standard for ATM networks and is used in other
    telecom protocols, so it is well-tested and trusted in
    high-reliability environments.

    Summary:
    GCRA is chosen when you need strict, mathematically precise rate and burst enforcement,
    minimal resource usage, and predictable, deterministic behavior—especially in networking and telecom scenarios.
    For general-purpose rate limiting, simpler algorithms may suffice, but GCRA is preferred for high-precision,
    high-performance needs.
    """

    """
    Policer: Fast-fails (returns False) if capacity is not available.
    Shaper: Waits (blocks) until capacity is available, then proceeds.
    """
