from typing import Any

import pytest

from limitor import async_rate_limit
from limitor.base import AsyncRateLimit
from limitor.configs import BucketConfig
from limitor.generic_cell_rate.core import (
    AsyncLeakyBucketGCRA,
    AsyncVirtualSchedulingGCRA,
)
from limitor.leaky_bucket.core import AsyncLeakyBucket
from limitor.token_bucket.core import AsyncTokenBucket


# parametrized fixture: any test that accepts `bucket_cls_capacity` will be run once per class
@pytest.fixture(params=[AsyncLeakyBucket, AsyncTokenBucket])
def bucket_cls_capacity(request: pytest.FixtureRequest, bucket_config: BucketConfig) -> Any:
    """Fixture that provides bucket instances with capacity=2, seconds=0.2 for capacity tests"""
    return request.param(bucket_config)  # like AsyncLeakyBucket(BucketConfig(...))


# parametrized fixture: any test that accepts `bucket_cls` will be run once per class
@pytest.fixture(params=[AsyncLeakyBucket, AsyncTokenBucket, AsyncLeakyBucketGCRA, AsyncVirtualSchedulingGCRA])
def bucket_cls(request: pytest.FixtureRequest, bucket_config: BucketConfig) -> Any:
    """Fixture that provides bucket instances with capacity=2, seconds=0.2 for general tests"""
    return request.param(bucket_config)  # like AsyncLeakyBucket(BucketConfig(...))


# Capacity tests
# note: this should really be a private method and not called directly


class TestCapacityInfo:
    """Tests for the `capacity_info` method of async bucket implementations"""

    @pytest.mark.asyncio
    async def test_capacity_amount_exceeds(self, bucket_cls_capacity: AsyncRateLimit) -> None:
        """Test capacity_info when requested amount exceeds capacity"""
        cap_info = bucket_cls_capacity.capacity_info(amount=3)  # type: ignore
        assert not cap_info.has_capacity
        assert cap_info.needed_capacity == 1

    @pytest.mark.asyncio
    async def test_capacity_amount_good(self, bucket_cls_capacity: AsyncRateLimit) -> None:
        """Test capacity_info when requested amount is within capacity"""
        cap_info = bucket_cls_capacity.capacity_info(amount=2)  # type: ignore
        assert cap_info.has_capacity
        assert cap_info.needed_capacity == 0

        cap_info = bucket_cls_capacity.capacity_info(amount=1)  # type: ignore
        assert cap_info.has_capacity
        assert cap_info.needed_capacity == -1


# Timeout validation


class TestTimeoutValidation:
    """Tests for the timeout behavior of async bucket implementations"""

    @pytest.mark.asyncio
    async def test_async_timeout_error(self, bucket_cls: AsyncRateLimit, asyncio_sleep_calls: list[float]) -> None:
        """Test that acquire raises TimeoutError when timeout is exceeded"""
        # fill the bucket so the next acquire will need to wait
        await bucket_cls.acquire(1)
        await bucket_cls.acquire(1)

        # test timeout path: set a very small timeout to trigger TimeoutError
        with pytest.raises(TimeoutError):
            await bucket_cls.acquire(1, timeout=0.001)  # 0.1 > 0.001

        # the spy may have recorded a sleep call for the waiting logic
        assert len(asyncio_sleep_calls) == 1

    @pytest.mark.asyncio
    async def test_async_timeout_good(self, bucket_cls: AsyncRateLimit, asyncio_sleep_calls: list[float]) -> None:
        """Test that acquire succeeds when timeout is sufficient"""
        # fill the bucket so the next acquire will need to wait
        await bucket_cls.acquire(1)
        await bucket_cls.acquire(1)

        await bucket_cls.acquire(1, timeout=0.2)

        # the spy may have recorded a sleep call for the waiting logic
        assert len(asyncio_sleep_calls) == 1


class TestAmountValidation:
    """Tests for the amount validation of async bucket implementations"""

    @pytest.mark.asyncio
    async def test_acquire_rejects_amount_greater_than_capacity(self, bucket_cls: AsyncRateLimit) -> None:
        """Verify that requesting more than the configured capacity raises ValueError"""
        with pytest.raises(ValueError, match=r"Cannot acquire more than the bucket's capacity: 2"):
            await bucket_cls.acquire(3)

    @pytest.mark.asyncio
    async def test_acquire_rejects_amount_less_than_zero(self, bucket_cls: AsyncRateLimit) -> None:
        """Verify that requesting less than zero raises ValueError"""
        with pytest.raises(ValueError, match=r"Cannot acquire less than 0 amount with amount: -1"):
            await bucket_cls.acquire(-1)

    @pytest.mark.asyncio
    async def test_acquire_amount_single(self, bucket_cls: AsyncRateLimit, asyncio_sleep_calls: list[float]) -> None:
        """Test if a single request performs correctly"""
        await bucket_cls.acquire(1)

        assert len(asyncio_sleep_calls) == 0  # first acquire should not sleep

    @pytest.mark.asyncio
    async def test_acquire_amount_multiple_same(
        self, bucket_cls: AsyncRateLimit, asyncio_sleep_calls: list[float]
    ) -> None:
        """Test if multiple requests of the same amount perform correctly"""
        for _ in range(6):
            await bucket_cls.acquire(1)

        assert all(call == pytest.approx(0.2 / 2, abs=0.01) for call in asyncio_sleep_calls)
        assert len(asyncio_sleep_calls) == 4

    @pytest.mark.asyncio
    async def test_acquire_variable_amount_multiple(
        self, bucket_cls: AsyncRateLimit, asyncio_sleep_calls: list[float]
    ) -> None:
        """Test if multiple requests of variable amounts perform correctly"""
        value_list = []
        for value in range(6):
            await bucket_cls.acquire(1 if value % 2 == 0 else 2)
            value_list.append(1 if value % 2 == 0 else 2)

        assert all(
            call == pytest.approx(0.2 / 2, abs=0.01) for idx, call in enumerate(asyncio_sleep_calls) if idx in [0, 1, 3]
        )
        assert all(
            call == pytest.approx(0.2 / 2 * 2, abs=0.01)
            for idx, call in enumerate(asyncio_sleep_calls)
            if idx in [2, 4]
        )
        assert len(asyncio_sleep_calls) == 5
        assert value_list == [1, 2, 1, 2, 1, 2]  # assert order is correct


# Test the more complicated cases involving the rate_limit decorator and context manager


# decorator tests
@pytest.mark.parametrize(
    "bucket_cls", [AsyncLeakyBucket, AsyncTokenBucket, AsyncLeakyBucketGCRA, AsyncVirtualSchedulingGCRA]
)
@pytest.mark.asyncio
async def test_decorator_calls_acquire(bucket_cls: type[AsyncRateLimit], asyncio_sleep_calls: list[float]) -> None:
    """Test that the async_rate_limit decorator calls acquire on the bucket"""

    @async_rate_limit(capacity=2, seconds=0.2, bucket_cls=bucket_cls)
    async def something(x: int) -> int:
        return x + 1

    value_list = []
    for value in range(6):
        value_list.append(await something(value))  # amount defaults to 1

    assert all(call == pytest.approx(0.2 / 2, abs=0.01) for call in asyncio_sleep_calls)
    assert len(asyncio_sleep_calls) == 4
    assert value_list == [1, 2, 3, 4, 5, 6]  # assert order is correct


# context manager tests
@pytest.mark.asyncio
async def test_context_manager_calls_acquire(bucket_cls: AsyncRateLimit, asyncio_sleep_calls: list[float]) -> None:
    """Context manager should call `acquire` on enter and return self"""
    value_list = []
    for value in range(6):
        async with bucket_cls:
            value_list.append(value + 1)  # just acquire and release, amount defaults to 1

    assert all(call == pytest.approx(0.2 / 2, abs=0.01) for call in asyncio_sleep_calls)
    assert len(asyncio_sleep_calls) == 4
    assert value_list == [1, 2, 3, 4, 5, 6]  # assert order is correct
