"""Configuration for Rate Limiter implementations"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, NamedTuple, TypeVar

T = TypeVar("T")


# TODO: need this here unfortunately due to circular imports with utils.py
def ensure_decimal_attrs(*attr_names: str) -> Callable[[type[T]], type[T]]:
    """Class decorator to ensure specified attributes are of type Decimal

    Args:
        *attr_names: Names of the attributes to ensure are of type Decimal

    Returns:
        A class decorator that enforces the specified attributes to be of type Decimal
    """

    def decorator(cls: type[T]) -> type[T]:
        """Decorator to modify the __post_init__ method of a dataclass to ensure specified attributes are Decimals

        Args:
            cls: The dataclass to decorate

        Returns:
            The decorated dataclass with modified __post_init__ method
        """
        orig_post = getattr(cls, "__post_init__", None)

        def __post_init__(self: object, *args: list[Any], **kwargs: dict[str, Any]) -> None:
            """Modified __post_init__ method to coerce specified attributes to Decimal

            Args:
                self: The dataclass to modify
                *args: Positional arguments
                **kwargs: Keyword arguments

            Raises:
                TypeError: If an attribute cannot be coerced to Decimal
            """
            for name in attr_names:
                val = getattr(self, name)
                if not isinstance(val, Decimal):
                    try:
                        setattr(self, name, Decimal(str(val)))
                    except Exception as exc:
                        raise TypeError(f"cannot coerce attribute {name!r} to Decimal: {exc}") from exc
            if orig_post:
                orig_post(self, *args, **kwargs)

        setattr(cls, "__post_init__", __post_init__)

        return cls

    return decorator


@ensure_decimal_attrs("capacity", "seconds")
@dataclass
class BucketConfig:
    """Configuration for any Rate Limiter"""

    capacity: Decimal = Decimal(10)
    """Maximum number of items the bucket can hold i.e. number of requests that can be processed at once"""

    seconds: Decimal = Decimal(1)
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

    needed_capacity: Decimal
    """Amount of capacity needed to accommodate the request, if any"""
