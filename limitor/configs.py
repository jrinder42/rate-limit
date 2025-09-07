"""Configuration for Rate Limiter implementations"""

from dataclasses import dataclass


@dataclass
class BucketConfig:
    """Configuration for any Rate Limiter"""

    capacity: float = 10
    """Maximum number of items the bucket can hold i.e. number of requests that can be processed at once"""

    seconds: float = 1
    """Up to `capacity` acquisitions are allowed within this time period in a burst"""

    def __post_init__(self) -> None:
        """Validate the configuration parameters"""
        leak_rate_per_sec = self.capacity / self.seconds  # can also be thought of as fill_rate_per_sec
        if leak_rate_per_sec <= 0:
            raise ValueError("leak_rate_per_sec must be positive and non-zero")

        if self.capacity < 1:
            raise ValueError("capacity must be at least 1")
