import asyncio
import time

from limitor import async_rate_limit


@async_rate_limit(capacity=2, seconds=2)
async def something_async() -> None:
    """Prints a message"""
    print(f"This is a rate-limited function: {time.strftime('%X')}")


async def main() -> None:
    """Main function to run the async rate-limited function multiple times"""
    for _ in range(10):
        try:
            await something_async()
        except Exception as error:  # pylint: disable=broad-exception-caught
            print(f"Rate limit exceeded: {error}")


asyncio.run(main())
