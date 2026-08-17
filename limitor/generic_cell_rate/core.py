"""A simple synchronous implementation of the Generic Cell Rate Algorithm (GCRA)

References:
- https://en.wikipedia.org/wiki/Generic_cell_rate_algorithm
- https://en.wikipedia.org/wiki/Leaky_bucket
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import AsyncGenerator, Generator
from contextlib import (
    AbstractAsyncContextManager,
    asynccontextmanager,
    contextmanager,
    nullcontext,
)
from types import TracebackType
from typing import Any

from limitor.configs import BucketConfig
from limitor.utils import validate_amount


class SyncVirtualSchedulingGCRA:
    """Virtual Scheduling Generic Cell Rate Algorithm Rate Limiter

    Args:
        bucket_config: Configuration for the GCR algorithm with the max capacity and time period in seconds

    Note:
        This implementation is synchronous and supports bursts up to the capacity within the specified time period

    References:
        https://en.wikipedia.org/wiki/Generic_cell_rate_algorithm
    """

    def __init__(self, bucket_config: BucketConfig | None = None):
        # import config and set attributes
        config = bucket_config or BucketConfig()
        self.capacity = config.capacity
        self.seconds = config.seconds

        self.leak_rate = self.capacity / self.seconds  # units per second
        self.T = 1 / self.leak_rate  # time to leak one unit

        # burst rate, but can't do this if the amount is variable
        # self.tau = self.T * self.burst

        # theoretical arrival time (TAT)
        self._tat: float | None = None

        # thread-safe
        self._lock = threading.Lock()

    def acquire(self, amount: float = 1) -> None:
        """Acquire resources, blocking if necessary to conform to the rate limit

        Args:
            amount: The amount of resources to acquire (default is 1)
        """
        validate_amount(self, amount=amount)

        with self._lock:
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

    @contextmanager
    def acquire_ctx(self, amount: float = 1) -> Generator[SyncVirtualSchedulingGCRA]:
        """Context manager that acquires a specific amount of capacity.

        Args:
            amount: The amount of capacity to acquire, defaults to 1

        Yields:
            SyncVirtualSchedulingGCRA: The SyncVirtualSchedulingGCRA instance
        """
        self.acquire(amount=amount)
        try:
            yield self
        finally:
            pass

    def reconcile(self, actual: float, estimated: float) -> None:
        """Reconcile the actual tokens/capacity used against the estimated amount.

        Args:
            actual: The actual amount of tokens/capacity used
            estimated: The estimated amount of tokens/capacity previously acquired
        """
        diff = actual - estimated
        if diff > 0:
            self.acquire(amount=diff)
        elif diff < 0:
            with self._lock:
                if self._tat is not None:
                    self._tat = max(time.monotonic(), self._tat + diff * self.T)

    def __enter__(self) -> SyncVirtualSchedulingGCRA:
        """Enter the context manager, acquiring resources if necessary

        Returns:
            An instance of the VirtualSchedulingGCRA class
        """
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
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
        bucket_config: Configuration for the GCR algorithm with the max capacity and time period in seconds

    Note:
        This implementation is synchronous and supports bursts up to the capacity within the specified time period

    References:
        https://en.wikipedia.org/wiki/Generic_cell_rate_algorithm
    """

    def __init__(self, bucket_config: BucketConfig | None = None):
        # import config and set attributes
        config = bucket_config or BucketConfig()
        self.capacity = config.capacity
        self.seconds = config.seconds

        self.leak_rate = self.capacity / self.seconds  # units per second
        self.T = 1 / self.leak_rate  # time to leak one unit

        # burst rate, but can't do this if the amount is variable
        # self.tau = self.T * self.burst

        self._bucket_level = 0.0  # current volume in the bucket
        self._last_leak: float | None = None  # same as last conforming time or LCT

        # thread-safe
        self._lock = threading.Lock()

    def acquire(self, amount: float = 1) -> None:
        """Acquire resources, blocking if necessary to conform to the rate limit

        Args:
            amount: The amount of resources to acquire (default is 1)
        """
        validate_amount(self, amount=amount)

        with self._lock:
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

    @contextmanager
    def acquire_ctx(self, amount: float = 1) -> Generator[SyncLeakyBucketGCRA]:
        """Context manager that acquires a specific amount of capacity.

        Args:
            amount: The amount of capacity to acquire, defaults to 1

        Yields:
            SyncLeakyBucketGCRA: The SyncLeakyBucketGCRA instance
        """
        self.acquire(amount=amount)
        try:
            yield self
        finally:
            pass

    def reconcile(self, actual: float, estimated: float) -> None:
        """Reconcile the actual tokens/capacity used against the estimated amount.

        Args:
            actual: The actual amount of tokens/capacity used
            estimated: The estimated amount of tokens/capacity previously acquired
        """
        diff = actual - estimated
        if diff > 0:
            self.acquire(amount=diff)
        elif diff < 0:
            with self._lock:
                t_a = time.monotonic()
                if self._last_leak is not None:
                    elapsed = t_a - self._last_leak
                    self._bucket_level = max(0.0, self._bucket_level - elapsed)
                    self._last_leak = t_a
                self._bucket_level = max(0.0, self._bucket_level + diff * self.T)

    def __enter__(self) -> SyncLeakyBucketGCRA:
        """Enter the context manager, acquiring resources if necessary

        Returns:
            An instance of the LeakyBucketGCRA class
        """
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context manager, releasing any resources if necessary

        Args:
            exc_type: The type of the exception raised
            exc_val: The value of the exception raised
            exc_tb: The traceback object
        """
        return None


class AsyncVirtualSchedulingGCRA:
    """Virtual Scheduling Generic Cell Rate Algorithm Rate Limiter

    Args:
        bucket_config: Configuration for the GCR algorithm with the max capacity and time period in seconds
        max_concurrent: Maximum number of concurrent requests allowed to acquire capacity

    Note:
        This implementation is asynchronous and supports bursts up to the capacity within the specified time period

    References:
        https://en.wikipedia.org/wiki/Generic_cell_rate_algorithm
    """

    def __init__(
        self,
        bucket_config: BucketConfig | None = None,
        max_concurrent: int | None = None,
    ):
        # import config and set attributes
        config = bucket_config or BucketConfig()
        self.capacity = config.capacity
        self.seconds = config.seconds

        self.leak_rate = self.capacity / self.seconds  # units per second
        self.T = 1 / self.leak_rate  # time to leak one unit

        # burst rate, but can't do this if the amount is variable
        # self.tau = self.T * self.burst

        # theoretical arrival time (TAT)
        self._tat: float | None = None

        self.max_concurrent = max_concurrent
        self._lock = asyncio.Lock()
        self._semaphore: asyncio.Semaphore | AbstractAsyncContextManager[Any] | None = (
            None
        )

    async def _acquire_logic(self, amount: float = 1) -> None:
        """Acquire resources, blocking if necessary to conform to the rate limit

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
        async with (
            self._lock
        ):  # ensure atomicity given we can have multiple concurrent requests
            t_a = time.monotonic()
            if self._tat is None:
                # first cell
                self._tat = t_a

            # note: we can also make `self.capacity - amount` as class param = burst i.e. independent of capacity
            tau = self.T * (self.capacity - amount)
            if t_a < self._tat - tau:
                delay = (self._tat - tau) - t_a
                await asyncio.sleep(delay)

            self._tat = max(t_a, self._tat) + amount * self.T

    async def _semaphore_acquire(self, amount: float = 1) -> None:
        """Acquire capacity using a semaphore to limit concurrency.

        Args:
            amount: The amount of capacity to acquire, defaults to 1
        """
        if self._semaphore is None:
            self._semaphore = (
                asyncio.Semaphore(self.max_concurrent)
                if self.max_concurrent
                else nullcontext()
            )

        async with self._semaphore:
            await self._acquire_logic(amount)

    async def acquire(self, amount: float = 1, timeout: float | None = None) -> None:
        """Acquire capacity, waiting asynchronously until allowed.

        Supports timeout and cancellation.

        Args:
            amount: The amount of capacity to acquire, defaults to 1
            timeout: Optional timeout in seconds for the acquire operation

        Raises:
            TimeoutError: If the acquire operation times out after the specified timeout period
        """
        validate_amount(self, amount=amount)

        if timeout is not None:
            try:
                await asyncio.wait_for(self._semaphore_acquire(amount), timeout=timeout)
            except TimeoutError as error:
                raise TimeoutError(
                    f"Acquire timed out after {timeout} seconds for amount={amount}"
                ) from error
        else:
            await self._semaphore_acquire(amount)

    @asynccontextmanager
    async def acquire_ctx(
        self, amount: float = 1, timeout: float | None = None
    ) -> AsyncGenerator[AsyncVirtualSchedulingGCRA]:
        """Async context manager that acquires a specific amount of capacity.

        Args:
            amount: The amount of capacity to acquire, defaults to 1
            timeout: Optional timeout in seconds for the acquire operation

        Yields:
            AsyncVirtualSchedulingGCRA: The AsyncVirtualSchedulingGCRA instance
        """
        await self.acquire(amount=amount, timeout=timeout)
        try:
            yield self
        finally:
            pass

    async def reconcile(self, actual: float, estimated: float) -> None:
        """Reconcile the actual tokens/capacity used against the estimated amount.

        Args:
            actual: The actual amount of tokens/capacity used
            estimated: The estimated amount of tokens/capacity previously acquired
        """
        diff = actual - estimated
        if diff > 0:
            await self.acquire(amount=diff)
        elif diff < 0:
            async with self._lock:
                if self._tat is not None:
                    self._tat = max(time.monotonic(), self._tat + diff * self.T)

    async def __aenter__(self) -> AsyncVirtualSchedulingGCRA:
        """Enter the context manager, acquiring resources if necessary

        Returns:
            An instance of the VirtualSchedulingGCRA class
        """
        await self.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context manager, releasing any resources if necessary

        Args:
            exc_type: The type of the exception raised
            exc_val: The value of the exception raised
            exc_tb: The traceback object
        """
        return None


class AsyncLeakyBucketGCRA:
    """Continuous-state Leaky Bucket Rate Limiter

    Args:
        bucket_config: Configuration for the GCR algorithm with the max capacity and time period in seconds
        max_concurrent: Maximum number of concurrent requests allowed to acquire capacity

    Note:
        This implementation is asynchronous and supports bursts up to the capacity within the specified time period

    References:
        https://en.wikipedia.org/wiki/Generic_cell_rate_algorithm
    """

    def __init__(
        self,
        bucket_config: BucketConfig | None = None,
        max_concurrent: int | None = None,
    ):
        # import config and set attributes
        config = bucket_config or BucketConfig()
        self.capacity = config.capacity
        self.seconds = config.seconds

        self.leak_rate = self.capacity / self.seconds  # units per second
        self.T = 1 / self.leak_rate  # time to leak one unit

        # burst rate, but can't do this if the amount is variable
        # self.tau = self.T * self.burst

        self._bucket_level = 0.0  # current volume in the bucket
        self._last_leak: float | None = None  # same as last conforming time or LCT

        self.max_concurrent = max_concurrent
        self._lock = asyncio.Lock()
        self._semaphore: asyncio.Semaphore | AbstractAsyncContextManager[Any] | None = (
            None
        )

    async def _acquire_logic(self, amount: float = 1) -> None:
        """Acquire resources, blocking if necessary to conform to the rate limit

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
        async with (
            self._lock
        ):  # ensure atomicity given we can have multiple concurrent requests
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
                await asyncio.sleep(delay)

                self._bucket_level = self._bucket_level - delay
                t_a += delay

            self._bucket_level = max(0.0, self._bucket_level) + amount * self.T
            self._last_leak = t_a

    async def _semaphore_acquire(self, amount: float = 1) -> None:
        """Acquire capacity using a semaphore to limit concurrency.

        Args:
            amount: The amount of capacity to acquire, defaults to 1
        """
        if self._semaphore is None:
            self._semaphore = (
                asyncio.Semaphore(self.max_concurrent)
                if self.max_concurrent
                else nullcontext()
            )

        async with self._semaphore:
            await self._acquire_logic(amount)

    async def acquire(self, amount: float = 1, timeout: float | None = None) -> None:
        """Acquire capacity, waiting asynchronously until allowed.

        Supports timeout and cancellation.

        Args:
            amount: The amount of capacity to acquire, defaults to 1
            timeout: Optional timeout in seconds for the acquire operation

        Raises:
            TimeoutError: If the acquire operation times out after the specified timeout period
        """
        validate_amount(self, amount=amount)

        if timeout is not None:
            try:
                await asyncio.wait_for(self._semaphore_acquire(amount), timeout=timeout)
            except TimeoutError as error:
                raise TimeoutError(
                    f"Acquire timed out after {timeout} seconds for amount={amount}"
                ) from error
        else:
            await self._semaphore_acquire(amount)

    @asynccontextmanager
    async def acquire_ctx(
        self, amount: float = 1, timeout: float | None = None
    ) -> AsyncGenerator[AsyncLeakyBucketGCRA]:
        """Async context manager that acquires a specific amount of capacity.

        Args:
            amount: The amount of capacity to acquire, defaults to 1
            timeout: Optional timeout in seconds for the acquire operation

        Yields:
            AsyncLeakyBucketGCRA: The AsyncLeakyBucketGCRA instance
        """
        await self.acquire(amount=amount, timeout=timeout)
        try:
            yield self
        finally:
            pass

    async def reconcile(self, actual: float, estimated: float) -> None:
        """Reconcile the actual tokens/capacity used against the estimated amount.

        Args:
            actual: The actual amount of tokens/capacity used
            estimated: The estimated amount of tokens/capacity previously acquired
        """
        diff = actual - estimated
        if diff > 0:
            await self.acquire(amount=diff)
        elif diff < 0:
            async with self._lock:
                t_a = time.monotonic()
                if self._last_leak is not None:
                    elapsed = t_a - self._last_leak
                    self._bucket_level = max(0.0, self._bucket_level - elapsed)
                    self._last_leak = t_a
                self._bucket_level = max(0.0, self._bucket_level + diff * self.T)

    async def __aenter__(self) -> AsyncLeakyBucketGCRA:
        """Enter the context manager, acquiring resources if necessary

        Returns:
            An instance of the AsyncLeakyBucketGCRA class
        """
        await self.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context manager, releasing any resources if necessary

        Args:
            exc_type: The type of the exception raised
            exc_val: The value of the exception raised
            exc_tb: The traceback object
        """
        return None


if __name__ == "__main__":  # pragma: no cover
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
