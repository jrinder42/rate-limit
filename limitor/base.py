"""Rate Limit Protocols for Synchronous and Asynchronous Context Managers"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Protocol


class SyncRateLimit(Protocol):
    """Synchronous Rate Limit Protocol"""

    def __init__(self, config: Any) -> None: ...

    def acquire(self, amount: float = 1) -> None:
        """Acquire an item from the rate limit. This method should block until a token is available"""

    def __enter__(self) -> SyncRateLimit:
        """Enter the context manager, acquiring resources if necessary

        This method should return an instance of SyncRateLimit

        Returns:
            An instance of the rate limit context manager
        """
        return self

    def __exit__(self, exc_type: type[BaseException], exc_val: BaseException, exc_tb: TracebackType) -> None:
        """Exit the context manager, releasing any resources if necessary

        Args:
            exc_type: The type of the exception raised, if any
            exc_val: The value of the exception raised, if any
            exc_tb: The traceback object, if any
        """


class AsyncRateLimit(Protocol):
    """Asynchronous Rate Limit Protocol"""

    def __init__(self, config: Any, max_concurrent: int | None = None) -> None: ...

    async def acquire(self, amount: float = 1) -> None:
        """Acquire an item from the rate limit. This method should block until a token is available"""

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
