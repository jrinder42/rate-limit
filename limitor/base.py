"""Rate Limit Protocols for Synchronous and Asynchronous Context Managers"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol

from limitor.configs import BucketConfig


class HasCapacity(Protocol):  # pylint: disable=too-few-public-methods
    """Protocol for objects that have a capacity attribute"""

    capacity: float
    """Maximum number of items the bucket can hold i.e. number of requests that can be processed at once"""


class SyncRateLimit(Protocol):
    """Synchronous Rate Limit Protocol

    Args:
        bucket_config: Configuration for the rate limit
    """

    def __init__(self, bucket_config: BucketConfig) -> None: ...

    def acquire(self, amount: float = 1) -> None:
        """Acquire an item from the rate limit. This method should block until a token is available

        Args:
            amount: The amount of capacity to acquire, defaults to 1
        """

    def __enter__(self) -> SyncRateLimit:
        """Enter the context manager, acquiring resources if necessary

        This method should return an instance of SyncRateLimit

        Returns:
            An instance of the rate limit context manager
        """

    def __exit__(self, exc_type: type[BaseException], exc_val: BaseException, exc_tb: TracebackType) -> None:
        """Exit the context manager, releasing any resources if necessary

        Args:
            exc_type: The type of the exception raised, if any
            exc_val: The value of the exception raised, if any
            exc_tb: The traceback object, if any
        """


class AsyncRateLimit(Protocol):
    """Asynchronous Rate Limit Protocol

    Args:
        bucket_config: Configuration for the rate limit
        max_concurrent: Maximum number of concurrent requests allowed to acquire capacity
    """

    def __init__(self, bucket_config: BucketConfig, max_concurrent: int | None = None) -> None: ...

    async def acquire(self, amount: float = 1, timeout: float | None = None) -> None:
        """Acquire an item from the rate limit. This method should block until a token is available

        Args:
            amount: The amount of capacity to acquire, defaults to 1
            timeout: Optional timeout in seconds for the acquire operation
        """

    async def __aenter__(self) -> AsyncRateLimit:
        """Enter the context manager, acquiring resources if necessary

        This method should return an instance of AsyncRateLimit

        Returns:
            An instance of the rate limit context manager
        """

    async def __aexit__(self, exc_type: type[BaseException], exc_val: BaseException, exc_tb: TracebackType) -> None:
        """Exit the context manager, releasing any resources if necessary

        Args:
            exc_type: The type of the exception raised, if any
            exc_val: The value of the exception raised, if any
            exc_tb: The traceback object, if any
        """
