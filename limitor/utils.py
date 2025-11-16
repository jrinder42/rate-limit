from limitor.base import HasCapacity


def validate_amount(rate_limiter: HasCapacity, amount: float) -> None:
    """Validate the requested amount for acquire

    Args:
        rate_limiter: the rate limiter i.e. SyncLeakyBucket or AsyncTokenBucket
        amount: The amount of capacity to acquire

    Raises:
        ValueError: If the requested amount exceeds the bucket's capacity or is negative
    """
    if amount > rate_limiter.capacity:
        raise ValueError(f"Cannot acquire more than the bucket's capacity: {rate_limiter.capacity}")

    if amount < 0:
        raise ValueError(f"Cannot acquire less than 0 amount with amount: {amount}")
