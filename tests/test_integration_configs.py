import pytest

from limitor.configs import BucketConfig


def test_bucket_config_initialization() -> None:
    """Test that BucketConfig initializes correctly with given parameters"""
    config = BucketConfig(capacity=5, seconds=10)
    assert config.capacity == 5
    assert config.seconds == 10


def test_bucket_config_defaults() -> None:
    """Test that BucketConfig uses default values when parameters are not provided"""
    config = BucketConfig()
    assert config.capacity == 10
    assert config.seconds == 1


@pytest.mark.parametrize(
    ("capacity", "seconds", "expected_message"),
    [(-1, 10, "capacity must be at least 1"), (5, 0, "seconds must be positive and non-zero")],
)
def test_bucket_config_invalid_parameters(capacity: float, seconds: float, expected_message: str) -> None:
    """Test that BucketConfig raises ValueError for invalid parameters"""
    with pytest.raises(ValueError, match=expected_message):
        BucketConfig(capacity=capacity, seconds=seconds)
