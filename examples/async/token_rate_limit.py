import asyncio
import random
import time

from limitor import async_rate_limit
from limitor.configs import BucketConfig
from limitor.token_bucket.core import AsyncTokenBucket


# Rate limit: 10,000 tokens per second
@async_rate_limit(
    capacity=10_000,
    seconds=1,
    bucket_cls=AsyncTokenBucket,
    token_estimate=lambda prompt, **kw: len(prompt) * 4,  # Estimate prompt tokens
    token_reconcile=lambda response: response["usage"]["total_tokens"],  # Reconcile actual tokens
)
async def process_llm_request(prompt: str) -> dict:
    """Simulate rate limited async LLM request."""
    estimated = len(prompt) * 4
    actual = estimated + random.randint(10, 50)
    print(f"[{time.strftime('%X')}] Processed request: {estimated} estimated -> {actual} actual tokens")
    return {"content": "Response generated", "usage": {"total_tokens": actual}}


async def main() -> None:
    """Run async token rate limiter examples."""
    print("--- 1. Async Decorator with Token Estimation & Reconciliation ---")
    for _ in range(5):
        prompt_text = "sample prompt text " * random.randint(20, 60)
        await process_llm_request(prompt=prompt_text)

    print("\n--- 2. Async Parameterized Context Manager with Reconciliation ---")
    bucket = AsyncTokenBucket(BucketConfig(capacity=10_000, seconds=1))

    for _ in range(5):
        est_tokens = random.randint(500, 2000)
        async with bucket.acquire_ctx(amount=est_tokens):
            actual_tokens = est_tokens + random.randint(-50, 100)
            print(f"[{time.strftime('%X')}] Context manager: {est_tokens} est -> {actual_tokens} actual")
            await bucket.reconcile(actual=actual_tokens, estimated=est_tokens)


if __name__ == "__main__":
    asyncio.run(main())
