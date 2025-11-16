"""Configuration for Rate Limiter implementations"""

from dataclasses import dataclass
from typing import NamedTuple


@dataclass
class BucketConfig:
    """Configuration for any Rate Limiter"""

    capacity: float = 10
    """Maximum number of items the bucket can hold i.e. number of requests that can be processed at once"""

    seconds: float = 1
    """Up to `capacity` acquisitions are allowed within this time period in a burst"""

    def __post_init__(self) -> None:
        """Validate the configuration parameters"""
        if self.seconds <= 0:
            raise ValueError("seconds must be positive and non-zero")

        if self.capacity < 1:
            raise ValueError("capacity must be at least 1")


class Capacity(NamedTuple):
    """Information about the current capacity of the bucket"""

    has_capacity: bool
    """Indicates if the bucket has enough capacity to accommodate the requested amount"""

    needed_capacity: float
    """Amount of capacity needed to accommodate the request, if any"""
