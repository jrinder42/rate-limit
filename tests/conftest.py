import pytest

from limitor.configs import BucketConfig


@pytest.fixture
def bucket_config() -> BucketConfig:
    """Fixture that provides a BucketConfig with capacity=2, seconds=0.2 for tests"""
    return BucketConfig(capacity=2, seconds=0.2)
