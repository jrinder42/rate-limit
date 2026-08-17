import random
import time

from limitor import rate_limit
from limitor.configs import BucketConfig
from limitor.token_bucket.core import SyncTokenBucket

print("--- 1. Decorator with Token Estimation & Reconciliation ---")


# Rate limit: 10,000 tokens per second
@rate_limit(
    capacity=10_000,
    seconds=1,
    bucket_cls=SyncTokenBucket,
    token_estimate=lambda prompt, **kw: len(prompt) * 4,  # Estimate prompt tokens
    token_reconcile=lambda response: response["usage"]["total_tokens"],  # Reconcile actual tokens
)
def process_llm_request(prompt: str) -> dict:
    """Simulate rate limited LLM request."""
    estimated = len(prompt) * 4
    actual = estimated + random.randint(10, 50)  # Completion tokens
    print(f"[{time.strftime('%X')}] Processed request: {estimated} estimated -> {actual} actual tokens")
    return {"content": "Response generated", "usage": {"total_tokens": actual}}


for i in range(5):
    prompt_text = "sample prompt text " * random.randint(20, 60)
    process_llm_request(prompt=prompt_text)


print("\n--- 2. Parameterized Context Manager with Reconciliation ---")

bucket = SyncTokenBucket(BucketConfig(capacity=10_000, seconds=1))

for i in range(5):
    est_tokens = random.randint(500, 2000)
    with bucket.acquire_ctx(amount=est_tokens):
        actual_tokens = est_tokens + random.randint(-50, 100)
        print(f"[{time.strftime('%X')}] Context manager: {est_tokens} est -> {actual_tokens} actual")
        bucket.reconcile(actual=actual_tokens, estimated=est_tokens)
