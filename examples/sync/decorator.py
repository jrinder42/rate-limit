import time

from limitor import rate_limit


@rate_limit(capacity=2, seconds=2)
def something() -> None:
    """Prints a message"""
    print(f"This is a rate-limited function: {time.strftime('%X')}")


for _ in range(10):
    try:
        something()
    except Exception as error:  # pylint: disable=broad-exception-caught
        print(f"Rate limit exceeded: {error}")
