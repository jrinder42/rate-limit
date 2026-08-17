import asyncio
from typing import Any

import pytest

from limitor import async_rate_limit
from limitor.base import AsyncRateLimit
from limitor.configs import BucketConfig
from limitor.extra.leaky_bucket.core import AsyncLeakyBucket as AsyncLeakyBucketExtra
from limitor.generic_cell_rate.core import (
    AsyncLeakyBucketGCRA,
    AsyncVirtualSchedulingGCRA,
)
from limitor.leaky_bucket.core import AsyncLeakyBucket
from limitor.token_bucket.core import AsyncTokenBucket


# parametrized fixture: any test that accepts `bucket_cls_capacity` will be run once per class
@pytest.fixture(params=[AsyncLeakyBucket, AsyncTokenBucket, AsyncLeakyBucketExtra])
def bucket_cls_capacity(
    request: pytest.FixtureRequest, bucket_config: BucketConfig
) -> Any:
    """Fixture that provides bucket instances with capacity=2, seconds=0.2 for capacity tests"""
    return request.param(bucket_config)  # like AsyncLeakyBucket(BucketConfig(...))


# parametrized fixture: any test that accepts `bucket_cls` will be run once per class
@pytest.fixture(
    params=[
        AsyncLeakyBucket,
        AsyncTokenBucket,
        AsyncLeakyBucketGCRA,
        AsyncVirtualSchedulingGCRA,
        AsyncLeakyBucketExtra,
    ]
)
def bucket_cls(request: pytest.FixtureRequest, bucket_config: BucketConfig) -> Any:
    """Fixture that provides bucket instances with capacity=2, seconds=0.2 for general tests"""
    return request.param(bucket_config)  # like AsyncLeakyBucket(BucketConfig(...))


@pytest.mark.parametrize(
    "bucket_cls",
    [
        AsyncLeakyBucket,
        AsyncTokenBucket,
        AsyncLeakyBucketGCRA,
        AsyncVirtualSchedulingGCRA,
    ],
)
def test_initialization_default(bucket_cls: type[AsyncLeakyBucket]) -> None:
    """Test bucket initialization with default config"""
    default_bucket = bucket_cls()

    assert default_bucket.capacity == 10
    assert default_bucket.seconds == 1
    assert isinstance(default_bucket._lock, asyncio.Lock)  # pylint: disable=protected-access
    assert default_bucket.max_concurrent is None


# Capacity tests
# note: this should really be a private method and not called directly


@pytest.mark.asyncio
class TestCapacityInfo:
    """Tests for the `capacity_info` method of async bucket implementations"""

    async def test_capacity_amount_exceeds(
        self, bucket_cls_capacity: AsyncRateLimit
    ) -> None:
        """Test capacity_info when requested amount exceeds capacity"""
        cap_info = bucket_cls_capacity.capacity_info(amount=3)  # type: ignore
        assert not cap_info.has_capacity
        assert cap_info.needed_capacity == 1

    async def test_capacity_amount_good(
        self, bucket_cls_capacity: AsyncRateLimit
    ) -> None:
        """Test capacity_info when requested amount is within capacity"""
        cap_info = bucket_cls_capacity.capacity_info(amount=2)  # type: ignore
        assert cap_info.has_capacity
        assert cap_info.needed_capacity == 0

        cap_info = bucket_cls_capacity.capacity_info(amount=1)  # type: ignore
        assert cap_info.has_capacity
        assert cap_info.needed_capacity == -1


# Timeout validation


@pytest.mark.asyncio
class TestTimeoutValidation:
    """Tests for the timeout behavior of async bucket implementations"""

    async def test_async_timeout_error(
        self, bucket_cls: AsyncRateLimit, asyncio_sleep_calls: list[float]
    ) -> None:
        """Test that acquire raises TimeoutError when timeout is exceeded"""
        # fill the bucket so the next acquire will need to wait
        await bucket_cls.acquire(1)
        await bucket_cls.acquire(1)

        # test timeout path: set a very small timeout to trigger TimeoutError
        with pytest.raises(TimeoutError):
            await bucket_cls.acquire(1, timeout=0.001)  # 0.1 > 0.001

        # the spy may have recorded a sleep call for the waiting logic
        assert len(asyncio_sleep_calls) == 1

    async def test_async_timeout_good(
        self, bucket_cls: AsyncRateLimit, asyncio_sleep_calls: list[float]
    ) -> None:
        """Test that acquire succeeds when timeout is sufficient"""
        # fill the bucket so the next acquire will need to wait
        await bucket_cls.acquire(1)
        await bucket_cls.acquire(1)

        await bucket_cls.acquire(1, timeout=0.2)

        # the spy may have recorded a sleep call for the waiting logic
        assert len(asyncio_sleep_calls) == 1


@pytest.mark.asyncio
class TestAmountValidation:
    """Tests for the amount validation of async bucket implementations"""

    async def test_acquire_rejects_amount_greater_than_capacity(
        self, bucket_cls: AsyncRateLimit
    ) -> None:
        """Verify that requesting more than the configured capacity raises ValueError"""
        with pytest.raises(
            ValueError, match=r"Cannot acquire more than the bucket's capacity: 2"
        ):
            await bucket_cls.acquire(3)

    async def test_acquire_rejects_amount_less_than_zero(
        self, bucket_cls: AsyncRateLimit
    ) -> None:
        """Verify that requesting less than zero raises ValueError"""
        with pytest.raises(
            ValueError, match=r"Cannot acquire less than 0 amount with amount: -1"
        ):
            await bucket_cls.acquire(-1)

    async def test_acquire_amount_single(
        self, bucket_cls: AsyncRateLimit, asyncio_sleep_calls: list[float]
    ) -> None:
        """Test if a single request performs correctly"""
        await bucket_cls.acquire(1)

        assert len(asyncio_sleep_calls) == 0  # first acquire should not sleep

    async def test_acquire_amount_multiple_same(
        self, bucket_cls: AsyncRateLimit, asyncio_sleep_calls: list[float]
    ) -> None:
        """Test if multiple requests of the same amount perform correctly"""
        value_list = []
        for value in range(6):
            await bucket_cls.acquire(1)
            value_list.append(value + 1)

        assert (
            len(asyncio_sleep_calls) >= 4
        )  # possibility of some extra sleeps depending on OS timing
        assert value_list == [1, 2, 3, 4, 5, 6]

    async def test_acquire_variable_amount_multiple(
        self, bucket_cls: AsyncRateLimit, asyncio_sleep_calls: list[float]
    ) -> None:
        """Test if multiple requests of variable amounts perform correctly"""
        value_list = []
        for value in range(6):
            await bucket_cls.acquire(1 if value % 2 == 0 else 2)
            value_list.append(1 if value % 2 == 0 else 2)

        assert len(asyncio_sleep_calls) >= 5
        assert value_list == [1, 2, 1, 2, 1, 2]  # assert order is correct


# Test the more complicated cases involving the rate_limit decorator and context manager


@pytest.mark.asyncio
async def test_rate_limit_decorator_default_usage() -> None:
    """Test usage of @async_rate_limit without parentheses"""

    @async_rate_limit
    async def dummy(x: int) -> int:
        return x + 2

    assert await dummy(3) == 5


# decorator tests
@pytest.mark.parametrize(
    "bucket_cls",
    [
        AsyncLeakyBucket,
        AsyncTokenBucket,
        AsyncLeakyBucketGCRA,
        AsyncVirtualSchedulingGCRA,
    ],
)
@pytest.mark.asyncio
async def test_decorator_calls_acquire(
    bucket_cls: type[AsyncRateLimit], asyncio_sleep_calls: list[float]
) -> None:
    """Test that the async_rate_limit decorator calls acquire on the bucket"""

    @async_rate_limit(capacity=2, seconds=0.2, bucket_cls=bucket_cls)
    async def something(x: int) -> int:
        return x + 1

    value_list = []
    for value in range(6):
        value_list.append(await something(value))  # amount defaults to 1

    assert len(asyncio_sleep_calls) >= 4
    assert value_list == [1, 2, 3, 4, 5, 6]  # assert order is correct


# context manager tests
@pytest.mark.asyncio
async def test_context_manager_calls_acquire(
    bucket_cls: AsyncRateLimit, asyncio_sleep_calls: list[float]
) -> None:
    """Context manager should call `acquire` on enter and return self"""
    value_list = []
    for value in range(6):
        async with bucket_cls:
            value_list.append(
                value + 1
            )  # just acquire and release, amount defaults to 1

    assert len(asyncio_sleep_calls) >= 4
    assert value_list == [1, 2, 3, 4, 5, 6]  # assert order is correct


@pytest.mark.asyncio
class TestReconcileOverestimate:
    """Tests for reconcile refund behavior (actual < estimated) per bucket type"""

    async def test_token_bucket_refunds(self, bucket_config: BucketConfig) -> None:
        """Token bucket refund adds back to _bucket_level"""
        tb = AsyncTokenBucket(bucket_config=bucket_config)
        tb._bucket_level = 0.5
        await tb.reconcile(actual=2, estimated=3)
        assert tb._bucket_level > 0.5

    async def test_leaky_bucket_refunds(self, bucket_config: BucketConfig) -> None:
        """Leaky bucket refund subtracts from _bucket_level"""
        lb = AsyncLeakyBucket(bucket_config=bucket_config)
        lb._bucket_level = 1.5
        await lb.reconcile(actual=1, estimated=2)
        assert lb._bucket_level < 1.5

    async def test_gcra_vs_refunds_when_acquired(
        self, bucket_config: BucketConfig
    ) -> None:
        """GCRA virtual-scheduling refund pulls TAT backward after an acquire"""
        gcra_vs = AsyncVirtualSchedulingGCRA(bucket_config=bucket_config)
        await gcra_vs.acquire(1)
        prev_tat = gcra_vs._tat
        await gcra_vs.reconcile(actual=0.5, estimated=1.0)
        assert gcra_vs._tat is not None
        assert prev_tat is not None
        assert gcra_vs._tat < prev_tat

    async def test_gcra_vs_refunds_when_not_acquired(
        self, bucket_config: BucketConfig
    ) -> None:
        """GCRA virtual-scheduling refund preserves None _tat when never acquired"""
        gcra_vs = AsyncVirtualSchedulingGCRA(bucket_config=bucket_config)
        await gcra_vs.reconcile(actual=0.5, estimated=1.0)
        assert gcra_vs._tat is None

    async def test_gcra_lb_refunds_when_acquired(
        self, bucket_config: BucketConfig
    ) -> None:
        """GCRA leaky-bucket refund reduces _bucket_level after an acquire"""
        gcra_lb = AsyncLeakyBucketGCRA(bucket_config=bucket_config)
        await gcra_lb.acquire(1)
        await gcra_lb.reconcile(actual=0.5, estimated=1.0)
        assert gcra_lb._bucket_level < 1.0

    async def test_gcra_lb_refunds_when_not_acquired(
        self, bucket_config: BucketConfig
    ) -> None:
        """GCRA leaky-bucket refund preserves state when never acquired"""
        gcra_lb = AsyncLeakyBucketGCRA(bucket_config=bucket_config)
        await gcra_lb.reconcile(actual=0.5, estimated=1.0)
        assert gcra_lb._last_leak is None
        assert gcra_lb._bucket_level == 0.0

    async def test_extra_leaky_bucket_refunds(
        self, bucket_config: BucketConfig
    ) -> None:
        """Extra leaky bucket refund subtracts from _bucket_level"""
        lb_extra = AsyncLeakyBucketExtra(bucket_config=bucket_config)
        lb_extra._bucket_level = 1.5
        await lb_extra.reconcile(actual=1, estimated=2)
        assert lb_extra._bucket_level < 1.5


@pytest.mark.asyncio
async def test_async_decorator_token_estimate_and_reconcile() -> None:
    """Test async decorator with token_estimate and token_reconcile hooks"""

    @async_rate_limit(
        capacity=100,
        seconds=1,
        bucket_cls=AsyncTokenBucket,
        token_estimate=lambda prompt, **kw: len(prompt) * 2,
        token_reconcile=lambda res: res["tokens"],
    )
    async def call_llm(prompt: str):
        return {"content": "ok", "tokens": len(prompt) * 3}

    res = await call_llm("hello")
    assert res == {"content": "ok", "tokens": 15}


@pytest.mark.asyncio
async def test_async_decorator_token_estimate_only() -> None:
    """Test async decorator with token_estimate only (no token_reconcile)"""

    @async_rate_limit(
        capacity=100,
        seconds=1,
        bucket_cls=AsyncTokenBucket,
        token_estimate=lambda prompt, **kw: len(prompt) * 2,
    )
    async def call_llm(prompt: str):
        return f"result: {prompt}"

    res = await call_llm("hello")
    assert res == "result: hello"


@pytest.mark.asyncio
async def test_shutdown_without_starting_worker(bucket_config: BucketConfig) -> None:
    """Shutdown should be a no-op if the worker was never started"""
    bucket = AsyncLeakyBucketExtra(bucket_config)
    # worker should not be started at construction time
    assert bucket._worker_task is None  # pylint: disable=protected-access

    # calling shutdown in an async context should not raise
    await bucket.shutdown()

    # still not started
    assert bucket._worker_task is None  # pylint: disable=protected-access

    # idempotent: calling shutdown again should still be fine
    await bucket.shutdown()
