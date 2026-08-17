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

### LLM Token Rate Limiting

`limitor` provides native support for variable-capacity and LLM token-based rate limiting via decorators and context managers using `acquire_ctx()`, `reconcile()`, and optional `token_estimate` / `token_reconcile` decorator hooks.

=== "Synchronous"

    #### Decorator with Estimation & Reconciliation

    ```python
    import random
    import time
    from limitor import rate_limit
    from limitor.token_bucket.core import SyncTokenBucket # (1)!

    # Rate limit of 100,000 tokens per second
    @rate_limit(
        capacity=100_000,
        seconds=1,
        bucket_cls=SyncTokenBucket,
        token_estimate=lambda prompt, **kw: len(prompt) * 4,  # Estimate prompt tokens
        token_reconcile=lambda response: response["usage"]["total_tokens"],  # Reconcile actual usage
    )
    def query_llm(prompt: str):
        # Simulated API call returning usage metadata
        print(f"[{time.strftime('%X')}] Generating response for {len(prompt)*4} estimated tokens")
        return {"content": "Response", "usage": {"total_tokens": len(prompt) * 4 + 20}}

    for _ in range(10):
        prompt = "x" * random.randint(1_000, 5_000)
        try:
            query_llm(prompt)
        except Exception as error:
            print(f"Rate limit exceeded: {error}")
    ```

    1. You can use any of the following synchronous classes here:
          - `SyncLeakyBucket`
          - `SyncTokenBucket`
          - `SyncVirtualSchedulingGCRA`
          - `SyncLeakyBucketGCRA`

    #### Parameterized Context Manager

    ```python
    from limitor.configs import BucketConfig
    from limitor.token_bucket.core import SyncTokenBucket

    bucket = SyncTokenBucket(BucketConfig(capacity=100_000, seconds=60))
    estimated_tokens = 500

    with bucket.acquire_ctx(amount=estimated_tokens):
        # response = client.chat.completions.create(...)
        actual_tokens = 480
        bucket.reconcile(actual=actual_tokens, estimated=estimated_tokens)
    ```

=== "Asynchronous"

    #### Decorator with Estimation & Reconciliation

    ```python
    import asyncio
    import random
    import time
    from limitor import async_rate_limit
    from limitor.token_bucket.core import AsyncTokenBucket # (1)!

    # Rate limit of 100,000 tokens per second
    @async_rate_limit(
        capacity=100_000,
        seconds=1,
        bucket_cls=AsyncTokenBucket,
        token_estimate=lambda prompt, **kw: len(prompt) * 4,  # Estimate prompt tokens
        token_reconcile=lambda response: response["usage"]["total_tokens"],  # Reconcile actual usage
    )
    async def query_llm(prompt: str):
        # Simulated async API call returning usage metadata
        print(f"[{time.strftime('%X')}] Generating response for {len(prompt)*4} estimated tokens")
        return {"content": "Response", "usage": {"total_tokens": len(prompt) * 4 + 20}}

    async def main():
        for _ in range(10):
            prompt = "x" * random.randint(1_000, 5_000)
            try:
                await query_llm(prompt)
            except Exception as error:
                print(f"Rate limit exceeded: {error}")

    asyncio.run(main())
    ```

    1. You can use any of the following asynchronous classes here:
          - `AsyncLeakyBucket`
          - `AsyncTokenBucket`
          - `AsyncVirtualSchedulingGCRA`
          - `AsyncLeakyBucketGCRA`

    #### Parameterized Context Manager

    ```python
    import asyncio
    from limitor.configs import BucketConfig
    from limitor.token_bucket.core import AsyncTokenBucket

    async def main():
        bucket = AsyncTokenBucket(BucketConfig(capacity=100_000, seconds=60))
        estimated_tokens = 500

        async with bucket.acquire_ctx(amount=estimated_tokens):
            # response = await client.chat.completions.create(...)
            actual_tokens = 480
            await bucket.reconcile(actual=actual_tokens, estimated=estimated_tokens)

    asyncio.run(main())
    ```

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
