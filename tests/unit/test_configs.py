from unittest.mock import MagicMock, patch

import pytest

from limitor.configs import BucketConfig


@patch.object(BucketConfig, "__post_init__", side_effect=ValueError("capacity must be at least 1"))
def test_bucket_config_invalid_capacity(mocked_post: MagicMock) -> None:
    """Unit test: constructor reacts to invalid capacity by propagating ValueError from validator."""
    with pytest.raises(ValueError, match="capacity must be at least 1"):
        BucketConfig(capacity=-1, seconds=10)

    mocked_post.assert_called_once()


@patch.object(BucketConfig, "__post_init__", side_effect=ValueError("seconds must be positive and non-zero"))
def test_bucket_config_invalid_seconds(mocked_post: MagicMock) -> None:
    """Unit test: constructor reacts to invalid seconds by propagating ValueError from validator."""
    with pytest.raises(ValueError, match="seconds must be positive and non-zero"):
        BucketConfig(capacity=5, seconds=0)

    mocked_post.assert_called_once()
