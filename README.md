# Rate Limiting Algorithms

[![PyPI Version][pypi-image]][pypi-url]
[![Build Status][build-image]][build-url]
[![Documentation Status][doc-image]][doc-url]
[![Code Coverage][coverage-image]][coverage-url]
[![PyPI - Python Version][version-image]][pypi-url]


<!-- Badges -->

[pypi-image]: https://img.shields.io/pypi/v/limitor
[pypi-url]: https://pypi.org/project/limitor
[build-image]: https://github.com/jrinder42/rate-limit/actions/workflows/ci.yml/badge.svg
[build-url]: https://github.com/jrinder42/rate-limit/actions/workflows/ci.yml
[doc-image]: https://img.shields.io/badge/docs-link-blue
[doc-url]: https://jrinder42.github.io/rate-limit/
[coverage-image]: https://codecov.io/gh/jrinder42/rate-limit/graph/badge.svg
[coverage-url]: https://codecov.io/gh/jrinder42/rate-limit
[version-image]: https://img.shields.io/pypi/pyversions/limitor

This project adheres to [Semantic Versioning](https://semver.org/)

## Algorithms

| Algorithms                  | Sync | Async |
|:----------------------------|:----:|:-----:|
| Leaky Bucket                | Yes  |  Yes  |
| Token Bucket                | Yes  |  Yes  |
| Generic Cell Rate Algorithm | Yes  |  Yes  |
| LLM Token-based             | Yes  |  Yes  |

> [!NOTE]  
> Implementations will be single-threaded, blocking requests (or the equivalent) with burst capabilities. With asyncio, we use non-blocking cooperative multitasking, not preemptive multi-threading

## Development

### Project Specific

Install `uv` (mac / linux)

```
just install-uv
```

Install dependencies

```
just develop
```

Reset environment

```
just reset-env
```

### Project Agnostic

Setup `uv`-based virtual environment

```shell
# Install uv
# for a mac or linux
brew install uv
# OPTIONAL: or
curl -LsSf https://astral.sh/uv/install.sh | sh

# python version are automatically downloaded as needed or: uv python install 3.12
uv venv --python 3.12


# to activate the virtual environment
source .venv/bin/activate

# to deactivate the virtual environment
deactivate
```

## Usage

> [!IMPORTANT]
> These are special use cases. The general use cases are in the `examples/` folder

### Token & Variable-Amount Rate Limiting (LLM TPM, Batch Sizes)

`limitor` natively supports variable-capacity and LLM token-based rate limiting via decorators and context managers using `acquire_ctx()`, `reconcile()`, and optional `token_estimate` / `token_reconcile` decorator hooks.

#### 1. Dynamic Token Estimation with Decorators (LLM Prompt Tokens)

```python
import random
import time
from limitor import rate_limit
from limitor.token_bucket.core import SyncTokenBucket

# Rate limit of 100,000 tokens per second
@rate_limit(
    capacity=100_000,
    seconds=1,
    bucket_cls=SyncTokenBucket,
    token_estimate=lambda prompt, **kw: len(prompt) * 4,  # Estimate tokens from prompt
)
def generate_response(prompt: str):
    print(f"[{time.strftime('%X')}] Generating response for prompt ({len(prompt)*4} tokens)")
    return f"Response to: {prompt}"

for i in range(10):
    sample_prompt = "x" * random.randint(1_000, 5_000)
    generate_response(sample_prompt)
```

#### 2. Full LLM Prompt Estimation + Response Token Reconciliation

When working with LLM APIs, you can estimate prompt tokens before the request and reconcile with the exact total tokens reported in the API response:

```python
from limitor import rate_limit
from limitor.token_bucket.core import SyncTokenBucket

# Automatically debit excess tokens or refund unused tokens
@rate_limit(
    capacity=50_000,
    seconds=60,
    bucket_cls=SyncTokenBucket,
    token_estimate=lambda prompt, **kw: len(prompt) // 4,
    token_reconcile=lambda response: response["usage"]["total_tokens"],
)
def query_llm(prompt: str):
    # Simulated API call returning usage metadata
    return {"content": "Hello!", "usage": {"total_tokens": 120}}
```

#### 3. Variable Tokens with Context Managers (`acquire_ctx` & `reconcile`)

```python
from limitor.configs import BucketConfig
from limitor.token_bucket.core import SyncTokenBucket

bucket = SyncTokenBucket(BucketConfig(capacity=100_000, seconds=60))

estimated_tokens = 500

# Acquire custom amount via context manager and reconcile actual usage
with bucket.acquire_ctx(amount=estimated_tokens):
    # response = client.chat.completions.create(...)
    actual_tokens = 450  # e.g. response.usage.total_tokens
    bucket.reconcile(actual=actual_tokens, estimated=estimated_tokens)
```

### With User-Specific Rate Limits + Cache

```python
from functools import wraps
import time
from typing import Optional

from cachetools import LRUCache, TTLCache

from limitor.base import SyncRateLimit
from limitor.configs import BucketConfig
from limitor.leaky_bucket.core import (
    AsyncLeakyBucket,
    SyncLeakyBucket,
)


def _get_user_cache(max_users, ttl):
    if ttl is not None:
        return TTLCache(maxsize=max_users, ttl=ttl)
    return LRUCache(maxsize=max_users)

def rate_limit_per_user(capacity=10, seconds=1, max_users=1000, ttl=None, bucket_cls: type[SyncRateLimit] = SyncLeakyBucket):
    buckets = _get_user_cache(max_users, ttl)
    global_bucket = bucket_cls(BucketConfig(capacity=capacity, seconds=seconds))

    def decorator(func):
        # optional use_id. if not set, it will default to a regular global rate limiter
        # if user_id is not set, this means the max_users / ttl parameters will be ignored
        @wraps(func)
        def wrapper(*args, user_id=None, **kwargs):
            if user_id is None:
                bucket = global_bucket
            else:
                if user_id not in buckets:
                    buckets[user_id] = bucket_cls(BucketConfig(capacity=capacity, seconds=seconds))
                bucket = buckets[user_id]
            with bucket:
                return func(user_id, *args, **kwargs)

        return wrapper

    return decorator

@rate_limit_per_user(capacity=2, seconds=1, max_users=3, ttl=600)  # TTLCache: 10 min/user
def something_user(user_id):
    print(f"User {user_id} called at {time.strftime('%X')}")

for _ in range(20):
    try:
        x = 1 if _ % 2 == 0 else 0
        something_user(user_id=x)
    except Exception as error:
        print(f"Rate limit exceeded: {error}")
```
