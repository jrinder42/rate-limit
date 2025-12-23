import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from limitor import async_rate_limit
from limitor.base import AsyncRateLimit
from limitor.configs import BucketConfig, Capacity
from limitor.extra.leaky_bucket.core import AsyncLeakyBucket as AsyncLeakyBucketExtra
from limitor.generic_cell_rate.core import (
    AsyncLeakyBucketGCRA,
    AsyncVirtualSchedulingGCRA,
)
from limitor.leaky_bucket.core import AsyncLeakyBucket
from limitor.token_bucket.core import AsyncTokenBucket


# parametrized fixture: any test that accepts `bucket_cls` will be run once per class
@pytest.fixture(
    params=[AsyncLeakyBucket, AsyncTokenBucket, AsyncLeakyBucketGCRA, AsyncVirtualSchedulingGCRA, AsyncLeakyBucketExtra]
)
def bucket_cls(request: pytest.FixtureRequest, bucket_config: BucketConfig) -> Any:
    """Fixture that provides bucket instances with capacity=2, seconds=0.2 for general tests"""
    return request.param(bucket_config)  # like AsyncLeakyBucket(BucketConfig(...))


@pytest.mark.asyncio
class TestAmountValidation:
    """Tests for amount validation in async bucket implementations"""

    @pytest.mark.parametrize("bucket_cls", [AsyncLeakyBucket, AsyncTokenBucket])
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("time.monotonic", side_effect=[0, 0, 0, 0, 0.1])
    async def test_acquire_amount_single_sleep_non_grca(
        self,
        mocked_monotonic: MagicMock,
        mocked_sleep: AsyncMock,
        bucket_config: BucketConfig,
        bucket_cls: type[AsyncRateLimit],
    ) -> None:
        """Test if a single request performs correctly"""
        bucket = bucket_cls(bucket_config=bucket_config)

        for _ in range(3):
            await bucket.acquire(1)

        assert mocked_monotonic.call_count == 5
        assert mocked_sleep.call_count == 1
        mocked_sleep.assert_called_once_with(pytest.approx(0.1, abs=1e-2))

    @pytest.mark.parametrize("bucket_cls", [AsyncLeakyBucketGCRA, AsyncVirtualSchedulingGCRA])
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("time.monotonic", side_effect=[0, 0, 0])
    async def test_acquire_amount_single_sleep_grca(
        self,
        mocked_monotonic: MagicMock,
        mocked_sleep: AsyncMock,
        bucket_config: BucketConfig,
        bucket_cls: type[AsyncRateLimit],
    ) -> None:
        """Test if a single request performs correctly"""
        bucket = bucket_cls(bucket_config=bucket_config)

        for _ in range(3):
            await bucket.acquire(1)

        assert mocked_monotonic.call_count == 3
        assert mocked_sleep.call_count == 1
        mocked_sleep.assert_called_once_with(pytest.approx(0.1, abs=1e-2))

    @pytest.mark.parametrize("bucket_cls", [AsyncLeakyBucket, AsyncTokenBucket])
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("time.monotonic")
    async def test_acquire_amount_multiple_same(
        self,
        mocked_monotonic: MagicMock,
        mocked_sleep: AsyncMock,
        bucket_config: BucketConfig,
        bucket_cls: type[AsyncRateLimit],
    ) -> None:
        """Test if multiple requests of the same amount perform correctly"""
        bucket = bucket_cls(bucket_config=bucket_config)

        with patch.object(bucket, "capacity_info") as mocked_capacity_info:
            mocked_capacity_info.side_effect = [
                Capacity(has_capacity=True, needed_capacity=-1),  # needed = 0 + 1 - 2 = -1 (outer)
                Capacity(has_capacity=True, needed_capacity=0),  # needed = 1 + 1 - 2 = 0 (outer)
                Capacity(
                    has_capacity=False, needed_capacity=1
                ),  # needed = 2 + 1 - 2 = 1 (outer) --> wait = 1 / (2 / 0.2) = 0.1s
                Capacity(has_capacity=True, needed_capacity=0),  # needed = 1 + 1 - 2 = 0 (inner)
                Capacity(
                    has_capacity=False, needed_capacity=1
                ),  # needed = 2 + 1 - 2 = 1 (outer) --> wait = 1 / (2 / 0.2) = 0.1s
                Capacity(has_capacity=True, needed_capacity=0),  # needed = 1 + 1 - 2 = 0 (inner)
                Capacity(
                    has_capacity=False, needed_capacity=1
                ),  # needed = 2 + 1 - 2 = 1 (outer) --> wait = 1 / (2 / 0.2) = 0.1s
                Capacity(has_capacity=True, needed_capacity=0),  # needed = 1 + 1 - 2 = 0 (inner)
                Capacity(
                    has_capacity=False, needed_capacity=1
                ),  # needed = 2 + 1 - 2 = 1 (outer) --> wait = 1 / (2 / 0.2) = 0.1s
                Capacity(has_capacity=True, needed_capacity=0),  # needed = 1 + 1 - 2 = 0 (inner)
            ]

            value_list = []
            for value in range(6):
                await bucket.acquire(1)
                value_list.append(value + 1)

            # this is b/c we are bypassing the _leak method, so this is from the constructor
            assert mocked_monotonic.call_count == 1

            assert mocked_sleep.call_count == 4
            mocked_sleep.assert_has_calls(
                [
                    call(pytest.approx(0.1, abs=1e-2)),
                    call(pytest.approx(0.1, abs=1e-2)),
                    call(pytest.approx(0.1, abs=1e-2)),
                    call(pytest.approx(0.1, abs=1e-2)),
                ],
                any_order=False,
            )
            assert value_list == [1, 2, 3, 4, 5, 6]  # assert order is correct

    @pytest.mark.parametrize("bucket_cls", [AsyncLeakyBucket, AsyncTokenBucket])
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("time.monotonic")
    async def test_acquire_amount_variable_amount_multiple(
        self,
        mocked_monotonic: MagicMock,
        mocked_sleep: AsyncMock,
        bucket_config: BucketConfig,
        bucket_cls: type[AsyncRateLimit],
    ) -> None:
        """Test if multiple requests of variable amounts perform correctly"""
        bucket = bucket_cls(bucket_config=bucket_config)

        with patch.object(bucket, "capacity_info") as mocked_capacity_info:
            mocked_capacity_info.side_effect = [
                Capacity(has_capacity=True, needed_capacity=-1),  # needed = 0 + 1 - 2 = -1 (outer)
                Capacity(
                    has_capacity=False, needed_capacity=1
                ),  # needed = 1 + 2 - 2 = 1 (outer) --> wait = 1 / (2 / 0.2) = 0.1s
                Capacity(has_capacity=True, needed_capacity=0),  # needed = 0 + 2 - 2 = 0 (inner)
                Capacity(
                    has_capacity=False, needed_capacity=1
                ),  # needed = 2 + 1 - 2 = 1 (outer) --> wait = 1 / (2 / 0.2) = 0.1s
                Capacity(has_capacity=True, needed_capacity=0),  # needed = 1 + 1 - 2 = 0 (inner)
                Capacity(
                    has_capacity=False, needed_capacity=1
                ),  # needed = 1 + 2 - 2 = 1 (outer) --> wait = 1 / (2 / 0.2) = 0.1s
                Capacity(has_capacity=True, needed_capacity=0),  # needed = 0 + 2 - 2 = 0 (inner)
                Capacity(
                    has_capacity=False, needed_capacity=1
                ),  # needed = 2 + 1 - 2 = 1 (outer) --> wait = 1 / (2 / 0.2) = 0.1s
                Capacity(has_capacity=True, needed_capacity=0),  # needed = 1 + 1 - 2 = 0 (inner)
                Capacity(
                    has_capacity=False, needed_capacity=1
                ),  # needed = 1 + 2 - 2 = 1 (outer) --> wait = 1 / (2 / 0.2) = 0.1s
                Capacity(has_capacity=True, needed_capacity=0),  # needed = 0 + 2 - 2 = 0 (inner)
            ]

            value_list = []
            for value in range(6):
                await bucket.acquire(1 if value % 2 == 0 else 2)  # [1, 2, 1, 2, 1, 2]
                value_list.append(1 if value % 2 == 0 else 2)

            # this is b/c we are bypassing the _leak method, so this is from the constructor
            assert mocked_monotonic.call_count == 1

            assert mocked_sleep.call_count == 5
            mocked_sleep.assert_has_calls(
                [
                    call(pytest.approx(0.1, abs=1e-2)),
                    call(pytest.approx(0.1, abs=1e-2)),
                    call(pytest.approx(0.1, abs=1e-2)),
                    call(pytest.approx(0.1, abs=1e-2)),
                    call(pytest.approx(0.1, abs=1e-2)),
                ],
                any_order=False,
            )
            assert value_list == [1, 2, 1, 2, 1, 2]  # assert order is correct


@pytest.mark.asyncio
class TestAsyncFeatures:
    """Tests for async-specific features in async bucket implementations"""

    @patch("asyncio.wait_for", new_callable=AsyncMock)
    async def test_acquire_uses_timeout_success(self, mocked_wait_for: AsyncMock, bucket_cls: AsyncRateLimit) -> None:
        """Test that acquire uses asyncio.wait_for when timeout is provided"""
        await bucket_cls.acquire(amount=1, timeout=5.0)

        assert mocked_wait_for.call_count == 1
        args, kwargs = mocked_wait_for.call_args
        assert kwargs["timeout"] == 5.0

        # Close the coroutine to avoid warnings since we're mocking wait_for
        args[0].close()

    @patch("asyncio.wait_for", side_effect=asyncio.TimeoutError)
    async def test_acquire_timeout_raises_error(self, mocked_wait_for: MagicMock, bucket_cls: AsyncRateLimit) -> None:
        """Test that acquire raises TimeoutError when asyncio.wait_for times out"""
        with pytest.raises(TimeoutError) as exc_info:
            await bucket_cls.acquire(amount=1, timeout=0.1)

        assert "Acquire timed out" in str(exc_info.value)
        assert mocked_wait_for.call_count == 1

        # Close the coroutine to avoid warnings
        args, _ = mocked_wait_for.call_args
        args[0].close()

    @pytest.mark.parametrize(
        "bucket_cls", [AsyncLeakyBucket, AsyncTokenBucket, AsyncLeakyBucketGCRA, AsyncVirtualSchedulingGCRA]
    )
    @patch("asyncio.Semaphore")
    async def test_acquire_uses_semaphore_when_max_concurrent_set(
        self, mocked_sem_cls: MagicMock, bucket_config: BucketConfig, bucket_cls: type[AsyncRateLimit]
    ) -> None:
        """Test that acquire initializes and uses a Semaphore when max_concurrent is set"""
        bucket = bucket_cls(bucket_config=bucket_config, max_concurrent=5)

        mock_sem_instance = MagicMock()
        mock_sem_instance.__aenter__ = AsyncMock()
        mock_sem_instance.__aexit__ = AsyncMock()

        # We mock _acquire_logic to isolate the semaphore testing
        mocked_sem_cls.return_value = mock_sem_instance
        with patch.object(bucket, "_acquire_logic", new_callable=AsyncMock) as mock_logic:
            await bucket.acquire(amount=1)

            # Check Semaphore instantiation
            mocked_sem_cls.assert_called_with(5)

            # Check Semaphore usage
            mock_sem_instance.__aenter__.assert_called_once()
            mock_sem_instance.__aexit__.assert_called_once()

            # Check logic was called inside
            mock_logic.assert_called_once_with(1)

    @pytest.mark.parametrize("bucket_cls", [AsyncLeakyBucket, AsyncTokenBucket])
    @patch("time.monotonic", return_value=0)
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_acquire_logic_uses_lock_non_gcra(
        self,
        mocked_sleep: AsyncMock,
        mocked_monotonic: MagicMock,
        bucket_config: BucketConfig,
        bucket_cls: type[AsyncRateLimit],
    ) -> None:
        """Test that _acquire_logic (and thus acquire) uses the instance lock"""
        bucket = bucket_cls(bucket_config=bucket_config)

        # Replace the instance lock with a mock
        mocked_lock = MagicMock()
        mocked_lock.__aenter__ = AsyncMock()
        mocked_lock.__aexit__ = AsyncMock()
        bucket._lock = mocked_lock  # type: ignore

        # Patch asyncio.sleep to avoid actual waiting
        with patch.object(
            bucket,
            "capacity_info",
            side_effect=[
                Capacity(has_capacity=False, needed_capacity=0.1),
                Capacity(has_capacity=True, needed_capacity=0),
            ],
        ):
            await bucket.acquire(amount=1)

        mocked_lock.__aenter__.assert_called_once()
        mocked_lock.__aexit__.assert_called_once()
        mocked_sleep.assert_called_once()
        mocked_monotonic.assert_called_once()

    @pytest.mark.parametrize("bucket_cls", [AsyncLeakyBucketGCRA, AsyncVirtualSchedulingGCRA])
    @patch("time.monotonic", return_value=0)
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_acquire_logic_uses_lock_gcra(
        self,
        mocked_sleep: AsyncMock,
        mocked_monotonic: MagicMock,
        bucket_config: BucketConfig,
        bucket_cls: type[AsyncRateLimit],
    ) -> None:
        """Test that _acquire_logic (and thus acquire) uses the instance lock"""
        bucket = bucket_cls(bucket_config=bucket_config)

        # Replace the instance lock with a mock
        mock_locked = MagicMock()
        mock_locked.__aenter__ = AsyncMock()
        mock_locked.__aexit__ = AsyncMock()
        bucket._lock = mock_locked  # type: ignore

        # Patch asyncio.sleep to avoid actual waiting
        # Patch time.monotonic to ensure deterministic behavior for GCRA

        await bucket.acquire(amount=1)

        mock_locked.__aenter__.assert_called_once()
        mock_locked.__aexit__.assert_called_once()
        mocked_monotonic.assert_called_once()
        mocked_sleep.assert_not_called()

    @patch("asyncio.get_event_loop")
    @patch("asyncio.Queue.put", new_callable=AsyncMock)
    @patch("limitor.extra.leaky_bucket.core.AsyncLeakyBucket._worker", return_value=AsyncMock())
    async def test_extra_leaky_bucket_worker_lifecycle(
        self, mocked_worker: MagicMock, mocked_queue_put: AsyncMock, mocked_loop: AsyncMock, bucket_config: BucketConfig
    ) -> None:
        """Test the lifecycle of the worker task in AsyncLeakyBucketExtra"""
        bucket = AsyncLeakyBucketExtra(bucket_config)
        assert bucket._worker_task is None

        # We need to mock queue.put and future to avoid actual execution

        # Use a real future but resolve it immediately
        loop = asyncio.get_running_loop()
        real_future = loop.create_future()
        real_future.set_result(True)
        mocked_loop.return_value.create_future.return_value = real_future

        await bucket.acquire(1)
        assert bucket._worker_task is not None

        await bucket.shutdown()
        mocked_queue_put.assert_called_with(None)

        # Cleanup the created task if it was actually created
        if bucket._worker_task:
            bucket._worker_task.cancel()
            try:
                await bucket._worker_task
            except asyncio.CancelledError:
                pass

        mocked_worker.assert_called_once()


@pytest.mark.asyncio
async def test_decorator_constructs_bucket_and_uses_context_manager_calls() -> None:
    """Decorator should construct bucket once and use context manager calls

    Verify the async `async_rate_limit` decorator constructs the bucket once
    at decoration time, and that the created bucket's context-manager methods
    are invoked on each wrapped-function call.
    """
    mocked_bucket = MagicMock(spec=AsyncRateLimit)
    # __aenter__ should return the bucket instance (or similar) when used as context manager
    mocked_bucket.__aenter__ = AsyncMock(return_value=mocked_bucket)
    mocked_bucket.__aexit__ = AsyncMock(return_value=None)

    # Factory/class used by the decorator; decorator will call this once at decoration
    mocked_cls = MagicMock(return_value=mocked_bucket)

    # technically is also a context manager
    @async_rate_limit(capacity=3, seconds=1, bucket_cls=mocked_cls)
    async def dummy(x: int) -> int:
        return x + 2

    # The decorator should have constructed the bucket exactly once at definition time
    mocked_cls.assert_called_once()

    # No __aenter__/__aexit__ calls should have happened yet
    mocked_bucket.__aenter__.assert_not_called()
    mocked_bucket.__aexit__.assert_not_called()

    # Call the wrapped function and assert the context-manager methods ran once
    result = await dummy(5)
    assert result == 7
    mocked_bucket.__aenter__.assert_called_once()
    mocked_bucket.__aexit__.assert_called_once()

    # Call again to ensure enter/exit are invoked on each call
    result2 = await dummy(6)
    assert result2 == 8
    assert mocked_bucket.__aenter__.call_count == 2
    assert mocked_bucket.__aexit__.call_count == 2


@pytest.mark.asyncio
async def test_context_manager_calls_acquire_unit(bucket_cls: AsyncRateLimit, monkeypatch: pytest.MonkeyPatch) -> None:
    """Context manager should call `acquire` on the bucket

    Explicit unit test for the context manager behavior: patch the instance's
    `acquire` method and verify it's called each time the context manager is used.
    This mirrors the integration test but isolates the acquire behavior via mocking.
    """
    # Replace the acquire method with a mock side-effect that records the amounts
    recorded_amounts = []

    async def _record(amount: float = 1) -> None:
        recorded_amounts.append(amount)

    mocked_acquire = AsyncMock(side_effect=_record)
    monkeypatch.setattr(bucket_cls, "acquire", mocked_acquire)

    value_list = []
    for value in range(6):
        async with bucket_cls:
            value_list.append(value + 1)

    # The context manager should call acquire once per 'with' usage
    assert mocked_acquire.call_count == 6

    # Ensure every call used the default amount==1 (via the side-effect recorder)
    assert recorded_amounts == [1, 1, 1, 1, 1, 1]

    # Assert our logic inside the 'with' executed as expected
    assert value_list == [1, 2, 3, 4, 5, 6]
