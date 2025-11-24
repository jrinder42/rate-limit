# Welcome to Limitor

This is a rate limiting library for Python that provides simple and efficient rate limiting mechanisms for your applications. 
Whether you're building APIs, web services, or any other system that requires rate limiting, Limitor has got you covered.

??? note "Algorithm Design"

    All algorithms default to traffic shaping patterns as opposed to traffic policing. 
    This means that transmitted pieces of data are not dropped and we wait until the request can be completed barring a timeout.

## Features

- Simple and intuitive API for defining rate limits
- Multiple rate limiting algorithms (Leaky Bucket, Token Bucket, etc.)
- Support for both synchronous and asynchronous operations
- Configurable burst handling
- Thread-safe implementations

### Bonus Features

- Built-in support for LLM token rate limiting
- Easy integration with caching systems
- Add user-specific rate limits


## Example Usage

LLM Token Rate Limiting

- System-wide rate limit of 100,000 tokens per second + simulate inputs of varying token amounts 

??? warning "decorator creation"

    This assumes all parameters need to be passed by the end-user. If you want to
    create a decorator with optional parameters, see `limitor/__init__.py` for an example.

=== "Synchronous"

    ```python
    import random
    import time
    from typing import Callable
    
    from limitor.base import SyncRateLimit
    from limitor.configs import BucketConfig
    from limitor.leaky_bucket.core import SyncLeakyBucket # (1)!
    
    
    def rate_limit(capacity: int = 10, seconds: float = 1, bucket_cls: type[SyncRateLimit] = SyncLeakyBucket) -> Callable:
        bucket = bucket_cls(BucketConfig(capacity=capacity, seconds=seconds))
    
        def decorator(func):
            def wrapper(*args, **kwargs):
                amount = kwargs.get("amount", 1)
                bucket.acquire(amount=amount)
                return func(*args, **kwargs)
            return wrapper
    
        return decorator
    
    @rate_limit(capacity=100_000, seconds=1)
    def process_request(amount=1):
        print(f"This is a rate-limited function: {time.strftime('%X')} - {amount} tokens")
    
    for _ in range(100):
        # generate random prompt tokens between 5,000 and 30,000 for 100 sample requests
        llm_prompt_tokens = random.randint(5_000, 30_000)
        try:
            process_request(amount=llm_prompt_tokens)
        except Exception as error:
            print(f"Rate limit exceeded: {error}")
    ```

    1. You can use any of the following synchronous classes here:
          - `SyncLeakyBucket`
          - `SyncTokenBucket`
          - `SyncVirtualSchedulingGCRA`
          - `SyncLeakyBucketGCRA`

=== "Asynchronous"

    ```python
    import random
    import time
    import asyncio
    from typing import Callable
    
    from limitor.base import AsyncRateLimit
    from limitor.configs import BucketConfig
    from limitor.leaky_bucket.core import AsyncLeakyBucket # (1)!
    
    
    def rate_limit(capacity: int = 10, seconds: float = 1, bucket_cls: type[AsyncRateLimit] = AsyncLeakyBucket) -> Callable:
        bucket = bucket_cls(BucketConfig(capacity=capacity, seconds=seconds))
    
        def decorator(func):
            async def wrapper(*args, **kwargs):
                amount = kwargs.get("amount", 1)
                await bucket.acquire(amount=amount)
                return await func(*args, **kwargs)
            return wrapper
    
        return decorator
    
    @rate_limit(capacity=100_000, seconds=1)
    async def process_request(amount=1):
        print(f"This is a rate-limited function: {time.strftime('%X')} - {amount} tokens")
    
    async def main():
        for _ in range(100):
            # generate random prompt tokens between 5,000 and 30,000 for 100 sample requests
            llm_prompt_tokens = random.randint(5_000, 30_000)
            try:
                await process_request(amount=llm_prompt_tokens)
            except Exception as error:
                print(f"Rate limit exceeded: {error}")
    
    asyncio.run(main())
    ```

    1. You can use any of the following asynchronous classes here:
          - `AsyncLeakyBucket`
          - `AsyncTokenBucket`
          - `AsyncVirtualSchedulingGCRA`
          - `AsyncLeakyBucketGCRA`

## References

- Linear Programming
    - [https://news.ycombinator.com/item?id=44393998](https://news.ycombinator.com/item?id=44393998)
      - [https://vivekn.dev/blog/rate-limit-diophantine](https://vivekn.dev/blog/rate-limit-diophantine)
- Async Rate Limiting
    - [https://asynciolimiter.readthedocs.io/en/latest/](https://asynciolimiter.readthedocs.io/en/latest/)
- Algorithms
    - [Leaky Bucket](https://en.wikipedia.org/wiki/Leaky_bucket)
        - Benefits: Smooth, predictable traffic at a constant rate, discarding the overflow
    - [Token Bucket](https://en.wikipedia.org/wiki/Token_bucket)
        - Benefits: Can be bursty with burst up to a limit, then at an average rate
    - [Generic Cell Rate Algorithm](https://en.wikipedia.org/wiki/Generic_cell_rate_algorithm)
        - Benefits: More precise control over traffic shaping and policing
