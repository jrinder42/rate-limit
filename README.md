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
| LLM-Token                   | Yes  |  Yes  |

> [!NOTE]  
> Implementations will be single-threaded, blocking requests (or the equivalent) with burst capabilities. With asyncio, we use non-blocking cooperative multitasking, not preemptive multi-threading

## Development

Setup `uv`-based virtual environment

```shell
# Install uv
# for a mac or linux
brew install uv
# OPTIONAL: or
curl -LsSf https://astral.sh/uv/install.sh | sh

# python version are automatically downloaded as needed or: uv python install 3.12
uv venv rate --python 3.12


# to activate the virtual environment
source .venv/bin/activate

# to deactivate the virtual environment
deactivate
```

Create lock file + requirements.txt

```shell
# after pyproject.toml is created
uv lock

uv export -o requirements.txt --quiet
```

Upgrade dependencies

```shell
# can use sync or lock
uv sync --upgrade

or 

# to upgrade a specific package
uv lock --upgrade-package requests
```

## Usage

> [!IMPORTANT]
> These are special use cases. The general use cases are in the `examples/` folder

### LLM Token-Based Rate Limiting

> [!NOTE]
> This decorator assumes that the user will pass any necessary params. If you want to make these optional, see `limitor/__init__.py`

```python
import random
import time
from typing import Callable

from limitor.base import SyncRateLimit
from limitor.configs import BucketConfig
from limitor.leaky_bucket.core import SyncLeakyBucket


def rate_limit(capacity: int = 10, seconds: float = 1, bucket_cls: type[SyncRateLimit] = SyncLeakyBucket) -> Callable:
    bucket = bucket_cls(BucketConfig(capacity=capacity, seconds=seconds))

    def decorator(func):
        def wrapper(*args, **kwargs):
            amount = kwargs.get("amount", 1)
            bucket.acquire(amount=amount)
            return func(*args, **kwargs)
        return wrapper

    return decorator

# limit of 100,000 tokens per second

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

### With User-Specific Rate Limits + Cache

```python
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
