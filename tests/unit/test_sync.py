from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from limitor import rate_limit
from limitor.base import SyncRateLimit
from limitor.configs import BucketConfig, Capacity
from limitor.generic_cell_rate.core import (
    SyncLeakyBucketGCRA,
    SyncVirtualSchedulingGCRA,
)
from limitor.leaky_bucket.core import SyncLeakyBucket
from limitor.token_bucket.core import SyncTokenBucket


# parametrized fixture: any test that accepts `bucket_cls` will be run once per class
@pytest.fixture(params=[SyncLeakyBucket, SyncTokenBucket, SyncLeakyBucketGCRA, SyncVirtualSchedulingGCRA])
def bucket_cls(request: pytest.FixtureRequest, bucket_config: BucketConfig) -> Any:
    """Fixture that provides bucket instances with capacity=2, seconds=0.2 for general tests"""
    return request.param(bucket_config)  # like AsyncLeakyBucket(BucketConfig(...))


# test amount
class TestAmountValidation:
    """Tests for amount validation in the `acquire` method of sync bucket implementations"""

    @patch("limitor.utils.validate_amount", side_effect=ValueError("Cannot acquire more than the bucket's capacity: 2"))
    def test_acquire_rejects_amount_greater_than_capacity(
        self, mocked_validate_amount: MagicMock, bucket_cls: SyncRateLimit
    ) -> None:
        """Verify that requesting more than the configured capacity raises ValueError"""
        with pytest.raises(ValueError, match=r"Cannot acquire more than the bucket's capacity: 2"):
            bucket_cls.acquire(3)  # any amount > 2 i.e. the capacity limit

        mocked_validate_amount.assert_not_called()

    @patch("limitor.utils.validate_amount", side_effect=ValueError("Cannot acquire less than 0 amount with amount: -1"))
    def test_acquire_rejects_amount_less_than_zero(
        self, mocked_validate_amount: MagicMock, bucket_cls: SyncRateLimit
    ) -> None:
        """Verify that requesting a negative amount raises ValueError"""
        with pytest.raises(ValueError, match=r"Cannot acquire less than 0 amount with amount: -1"):
            bucket_cls.acquire(-1)

        mocked_validate_amount.assert_not_called()

    @pytest.mark.parametrize("bucket_cls", [SyncLeakyBucket, SyncTokenBucket])
    @patch("time.sleep")
    @patch("time.monotonic", side_effect=[0, 0, 0, 0, 0.1])
    def test_acquire_amount_single_sleep_non_grca(
        self,
        mocked_monotonic: MagicMock,
        mocked_sleep: MagicMock,
        bucket_config: BucketConfig,
        bucket_cls: type[SyncRateLimit],
    ) -> None:
        """Test if a single request performs correctly

        Note:
            This is fine as it floating point error propagation has not occurred yet
        """
        bucket = bucket_cls(bucket_config=bucket_config)

        for _ in range(3):
            bucket.acquire(1)

        assert mocked_monotonic.call_count == 5
        assert mocked_sleep.call_count == 1
        mocked_sleep.assert_called_once_with(0.1)

    @pytest.mark.parametrize("bucket_cls", [SyncLeakyBucketGCRA, SyncVirtualSchedulingGCRA])
    @patch("time.sleep")
    @patch("time.monotonic", side_effect=[0, 0, 0])
    def test_acquire_amount_single_sleep_grca(
        self,
        mocked_monotonic: MagicMock,
        mocked_sleep: MagicMock,
        bucket_config: BucketConfig,
        bucket_cls: type[SyncRateLimit],
    ) -> None:
        """Test if a single request performs correctly

        Note:
            This is fine as it floating point error propagation has not occurred yet
        """
        bucket = bucket_cls(bucket_config=bucket_config)

        for _ in range(3):
            bucket.acquire(1)

        assert mocked_monotonic.call_count == 3
        assert mocked_sleep.call_count == 1
        mocked_sleep.assert_called_once_with(0.1)

    @pytest.mark.parametrize("bucket_cls", [SyncLeakyBucket, SyncTokenBucket])
    @patch("time.sleep")
    @patch("time.monotonic")
    def test_acquire_amount_multiple_same(
        self,
        mocked_monotonic: MagicMock,
        mocked_sleep: MagicMock,
        bucket_config: BucketConfig,
        bucket_cls: type[SyncRateLimit],
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
                bucket.acquire(1)
                value_list.append(value + 1)

            # this is b/c we are bypassing the _leak method, so this is from the constructor
            assert mocked_monotonic.call_count == 1

            assert mocked_sleep.call_count == 4
            mocked_sleep.assert_has_calls(
                [
                    call(pytest.approx(0.1, abs=1e-3)),
                    call(pytest.approx(0.1, abs=1e-3)),
                    call(pytest.approx(0.1, abs=1e-3)),
                    call(pytest.approx(0.1, abs=1e-3)),
                ],
                any_order=False,
            )
            assert value_list == [1, 2, 3, 4, 5, 6]  # assert order is correct

    @pytest.mark.parametrize("bucket_cls", [SyncLeakyBucket, SyncTokenBucket])
    @patch("time.sleep")
    @patch("time.monotonic")
    def test_acquire_amount_variable_amount_multiple(
        self,
        mocked_monotonic: MagicMock,
        mocked_sleep: MagicMock,
        bucket_config: BucketConfig,
        bucket_cls: type[SyncRateLimit],
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
                bucket.acquire(1 if value % 2 == 0 else 2)  # [1, 2, 1, 2, 1, 2]
                value_list.append(1 if value % 2 == 0 else 2)

            # this is b/c we are bypassing the _leak method, so this is from the constructor
            assert mocked_monotonic.call_count == 1

            assert mocked_sleep.call_count == 5
            mocked_sleep.assert_has_calls(
                [
                    call(pytest.approx(0.1, abs=1e-3)),
                    call(pytest.approx(0.1, abs=1e-3)),
                    call(pytest.approx(0.1, abs=1e-3)),
                    call(pytest.approx(0.1, abs=1e-3)),
                    call(pytest.approx(0.1, abs=1e-3)),
                ],
                any_order=False,
            )
            assert value_list == [1, 2, 1, 2, 1, 2]  # assert order is correct


def test_decorator_constructs_bucket_and_uses_context_manager_calls() -> None:
    """Decorator should construct bucket once and call context-manager methods

    Verify the synchronous `rate_limit` decorator constructs the bucket once
    at decoration time, and that the created bucket's context-manager methods
    are invoked on each wrapped-function call.
    """
    mocked_bucket = MagicMock(spec=SyncRateLimit)
    # __enter__ should return the bucket instance (or similar) when used as context manager
    mocked_bucket.__enter__.return_value = mocked_bucket
    mocked_bucket.__exit__.return_value = None

    # Factory/class used by the decorator; decorator will call this once at decoration
    mocked_cls = MagicMock(return_value=mocked_bucket)

    # technically is also a context manager
    @rate_limit(capacity=3, seconds=1, bucket_cls=mocked_cls)
    def dummy(x: int) -> int:
        return x + 2

    # The decorator should have constructed the bucket exactly once at definition time
    mocked_cls.assert_called_once()

    # No __enter__/__exit__ calls should have happened yet
    mocked_bucket.__enter__.assert_not_called()
    mocked_bucket.__exit__.assert_not_called()

    # Call the wrapped function and assert the context-manager methods ran once
    result = dummy(5)
    assert result == 7
    mocked_bucket.__enter__.assert_called_once()
    mocked_bucket.__exit__.assert_called_once()

    # Call again to ensure enter/exit are invoked on each call
    result2 = dummy(6)
    assert result2 == 8
    assert mocked_bucket.__enter__.call_count == 2
    assert mocked_bucket.__exit__.call_count == 2


def test_context_manager_calls_acquire_unit(bucket_cls: SyncRateLimit, monkeypatch: pytest.MonkeyPatch) -> None:
    """Context manager should call `acquire` on enter and return self

    Explicit unit test for the context manager behavior: patch the instance's
    `acquire` method and verify it's called each time the context manager is used.
    This mirrors the integration test but isolates the acquire behavior via mocking.
    """
    # Replace the acquire method with a mock side-effect that records the amounts
    recorded_amounts = []

    def _record(amount: float = 1) -> None:
        recorded_amounts.append(amount)

    mocked_acquire = MagicMock(side_effect=_record)
    monkeypatch.setattr(bucket_cls, "acquire", mocked_acquire)

    value_list = []
    for value in range(6):
        with bucket_cls:
            value_list.append(value + 1)

    # The context manager should call acquire once per 'with' usage
    assert mocked_acquire.call_count == 6

    # Ensure every call used the default amount==1 (via the side-effect recorder)
    assert recorded_amounts == [1, 1, 1, 1, 1, 1]

    # Assert our logic inside the 'with' executed as expected
    assert value_list == [1, 2, 3, 4, 5, 6]
