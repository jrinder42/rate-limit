from typing import Any

import pytest

from limitor import rate_limit
from limitor.base import SyncRateLimit
from limitor.configs import BucketConfig
from limitor.generic_cell_rate.core import (
    SyncLeakyBucketGCRA,
    SyncVirtualSchedulingGCRA,
)
from limitor.leaky_bucket.core import SyncLeakyBucket
from limitor.token_bucket.core import SyncTokenBucket


# parametrized fixture: any test that accepts `bucket_cls_capacity` will be run once per class
@pytest.fixture(params=[SyncLeakyBucket, SyncTokenBucket])
def bucket_cls_capacity(request: pytest.FixtureRequest, bucket_config: BucketConfig) -> Any:
    """Fixture that provides bucket instances with capacity=2, seconds=0.2 for capacity tests"""
    return request.param(bucket_config)  # like AsyncLeakyBucket(BucketConfig(...))


# parametrized fixture: any test that accepts `bucket_cls` will be run once per class
@pytest.fixture(params=[SyncLeakyBucket, SyncTokenBucket, SyncLeakyBucketGCRA, SyncVirtualSchedulingGCRA])
def bucket_cls(request: pytest.FixtureRequest, bucket_config: BucketConfig) -> Any:
    """Fixture that provides bucket instances with capacity=2, seconds=0.2 for general tests"""
    return request.param(bucket_config)  # like AsyncLeakyBucket(BucketConfig(...))


@pytest.mark.parametrize(
    "bucket_cls", [SyncLeakyBucket, SyncTokenBucket, SyncLeakyBucketGCRA, SyncVirtualSchedulingGCRA]
)
def test_initialization_default(bucket_cls: type[SyncLeakyBucket]) -> None:
    """Test bucket initialization with default config"""
    default_bucket = bucket_cls()

    assert default_bucket.capacity == 10
    assert default_bucket.seconds == 1


# Capacity tests
# note: this should really be a private method and not called directly


class TestCapacityInfo:
    """Tests for the `capacity_info` method of sync bucket implementations"""

    def test_capacity_amount_exceeds(self, bucket_cls_capacity: SyncRateLimit) -> None:
        """Test capacity_info when requested amount exceeds capacity"""
        cap_info = bucket_cls_capacity.capacity_info(amount=3)  # type: ignore
        assert not cap_info.has_capacity
        assert cap_info.needed_capacity == 1

    def test_capacity_amount_good(self, bucket_cls_capacity: SyncRateLimit) -> None:
        """Test capacity_info when requested amount is within capacity"""
        cap_info = bucket_cls_capacity.capacity_info(amount=2)  # type: ignore
        assert cap_info.has_capacity
        assert cap_info.needed_capacity == 0

        cap_info = bucket_cls_capacity.capacity_info(amount=1)  # type: ignore
        assert cap_info.has_capacity
        assert cap_info.needed_capacity == -1


# Validate amount


class TestAmountValidation:
    """Tests for the amount validation behavior of sync bucket implementations"""

    def test_acquire_rejects_amount_greater_than_capacity(self, bucket_cls: SyncRateLimit) -> None:
        """Verify that requesting more than the configured capacity raises ValueError"""
        with pytest.raises(ValueError, match=r"Cannot acquire more than the bucket's capacity: 2"):
            bucket_cls.acquire(3)

    def test_acquire_rejects_amount_less_than_zero(self, bucket_cls: SyncRateLimit) -> None:
        """Verify that requesting a negative amount raises ValueError"""
        with pytest.raises(ValueError, match=r"Cannot acquire less than 0 amount with amount: -1"):
            bucket_cls.acquire(-1)

    def test_acquire_amount_single(self, bucket_cls: SyncRateLimit, sleep_calls: list[float]) -> None:
        """Test if a single request performs correctly"""
        bucket_cls.acquire(1)

        assert len(sleep_calls) == 0  # first acquire should not sleep

    def test_acquire_amount_multiple_same(self, bucket_cls: SyncRateLimit, sleep_calls: list[float]) -> None:
        """Test multiple requests of the same amount perform correctly"""
        value_list = []
        for value in range(6):
            bucket_cls.acquire(1)
            value_list.append(value + 1)

        assert len(sleep_calls) >= 4  # possibility of some extra sleeps depending on OS timing
        assert value_list == [1, 2, 3, 4, 5, 6]

    def test_acquire_variable_amount_multiple(self, bucket_cls: SyncRateLimit, sleep_calls: list[float]) -> None:
        """Test multiple requests of variable amounts perform correctly"""
        value_list = []
        for value in range(6):
            bucket_cls.acquire(1 if value % 2 == 0 else 2)
            value_list.append(1 if value % 2 == 0 else 2)

        assert len(sleep_calls) >= 5
        assert value_list == [1, 2, 1, 2, 1, 2]  # assert order is correct


# Test the more complicated cases involving the rate_limit decorator and context manager


def test_rate_limit_decorator_default_usage() -> None:
    """Test usage of @rate_limit without parentheses"""

    @rate_limit
    def dummy(x: int) -> int:
        return x + 2

    assert dummy(3) == 5


# decorator tests
@pytest.mark.parametrize(
    "bucket_cls", [SyncLeakyBucket, SyncTokenBucket, SyncLeakyBucketGCRA, SyncVirtualSchedulingGCRA]
)
def test_decorator_calls_acquire(bucket_cls: type[SyncRateLimit], sleep_calls: list[float]) -> None:
    """Ensure the rate_limit decorator calls acquire on the bucket"""

    @rate_limit(capacity=2, seconds=0.2, bucket_cls=bucket_cls)
    def something(x: int) -> int:
        return x + 1

    value_list = []
    for value in range(6):
        value_list.append(something(value))  # amount defaults to 1

    assert len(sleep_calls) >= 4
    assert value_list == [1, 2, 3, 4, 5, 6]  # assert order is correct


# context manager tests
def test_context_manager_calls_acquire(bucket_cls: SyncRateLimit, sleep_calls: list[float]) -> None:
    """Ensure the context manager calls acquire on the bucket"""
    value_list = []
    for value in range(6):
        with bucket_cls:
            value_list.append(value + 1)  # just acquire and release, amount defaults to 1

    assert len(sleep_calls) >= 4
    assert value_list == [1, 2, 3, 4, 5, 6]  # assert order is correct
