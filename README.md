# Rate Limiting Algorithms

> [!IMPORTANT]
> This is just for my own knowledge. Please do not use this if you stumble upon it.

## Algorithms

| Algorithms                  | Sync | Async |
|:----------------------------|:----:|:-----:|
| Leaky Bucket                | Yes  |  Yes  |
| Token Bucket                | Yes  |  TBD  |
| Generic Cell Rate Algorithm | Yes  |  TBD  |
| LLM-Token                   | TBD  |  TBD  |

> [!NOTE]  
> Implementations will be single-threaded, blocking requests (or the equivalent) with burst capabilities. With asyncio, we use non-blocking cooperative multitasking, not preemptive multi-threading

> [!NOTE]
> All algorithms default to traffic shaping patterns as opposed to traffic policing. This means that transmitted pieces of data are not dropped and we wait until the request can be completed barring a timeout.

## Development

Setup `uv`-based virtual environment

```shell
# Install uv
# for a mac or linux
brew install uv
# OPTIONAL: or
curl -LsSf https://astral.sh/uv/install.sh | sh

# python version are automatically downloaded as needed or: uv python install 3.12
uv venv financials --python 3.12


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

## Generating Docs

**Enable GitHub Pages**

1. On GitHub go to “Settings” -> “Pages”.

2. In the “Source” section, choose “Deploy from a branch” in the dropdown menu.

3. In the “Branch” section choose “gh-pages” and “/root” in the dropdown menus and click save.

You should now be able to verify the pages deployment in the Actions list.



## Usage

TODO: cleanup

> [!NOTE]
> All of the below algorithms should produce identical results with identical parameters

### Leaky Bucket

Synchronous

```python
# no context manager, use directly

import time

from limitor.leaky_bucket import LeakyBucketConfig, SyncLeakyBucket

# 4 requests per 2 seconds and a 4 second burst capacity
config = LeakyBucketConfig(capacity=4, seconds=2)
sync_bucket = SyncLeakyBucket(config)
for i in range(7):
    sync_bucket.acquire(1)
    print(f"Current level: {sync_bucket._bucket_level}")
    time.sleep(0.3)  # Simulate some work being done

print("Waiting for bucket to leak...")
time.sleep(1)  # check how much leaks out of the bucket in 1 second
sync_bucket._leak()  # update the bucket level after waiting
print(f"Current level after leaking: {sync_bucket._bucket_level}")
```

```python
# context manager

import time

from limitor.leaky_bucket import LeakyBucketConfig, SyncLeakyBucket

# 4 requests per 2 seconds and a 4 second burst capacity
config = LeakyBucketConfig(capacity=4, seconds=2)
context_sync = SyncLeakyBucket(config)  # use the same config as above
for _ in range(10):
    with context_sync as thing:
        print(f"Acquired 1 unit using context manager: {thing._bucket_level}")
        print(f"Current level {_} sent at {time.strftime('%X')}")
        time.sleep(0.3)  # simulate some work being done
print("Exited context manager.", context_sync._bucket_level)
# wait 1 second to let the bucket leak: should lower level from 4 --> 2
# our leak rate is 4 per 2 seconds aka 2 per second; hence, after 1 second, we should have 2 left in the bucket
time.sleep(1)
context_sync._leak()  # update the bucket level after waiting -- just to illustrate the leak
print(f"Current level after waiting 1 second: {context_sync._bucket_level}")
```

### Token Bucket

Synchronous - similar to the above examples

```python
# context manager

import time

from limitor.leaky_bucket import SyncTokenBucket, TokenBucketConfig

# 4 requests per 2 seconds and a 4 second burst capacity
config = TokenBucketConfig(capacity=4, seconds=2)
context_sync = SyncTokenBucket(config)  # use the same config as above
for _ in range(10):
    with context_sync as thing:
        print(f"Acquired 1 unit using context manager: {thing._bucket_level}")
        print(f"Current level {_} sent at {time.strftime('%X')}")
        # time.sleep(0.3)  # simulate some work being done
print("Exited context manager.", context_sync._bucket_level)
# wait 1 second to let the bucket leak: should lower level from 4 --> 2
# our leak rate is 4 per 2 seconds aka 2 per second; hence, after 1 second, we should have 2 left in the bucket
time.sleep(1)
context_sync._fill()  # update the bucket level after waiting -- just to illustrate the leak
print(f"Current level after waiting 1 second: {context_sync._bucket_level}")

time.sleep(1)
context_sync._fill()
print(f"Current level after waiting 1 second: {context_sync._bucket_level}")
```

### Generic Cell Rate Algorithm

> [!NOTE]
> Can be either the virtual scheduling algorithm or the continuous leaky bucket algorithm

```python
# context manager

from datetime import datetime

from limitor.generic_cell_rate import (
    GCRAConfig,
    SyncLeakyBucketGCRA,
    SyncVirtualSchedulingGCRA,
)

# 3 requests per 1.5 seconds and a 3 second burst capacity
config = GCRAConfig(capacity=3, seconds=1.5)
context_sync = SyncLeakyBucketGCRA(config)  # can swap with VirtualSchedulingGCRA
for _ in range(12):
    with context_sync as thing:
        print(f"Current level {_} sent at {datetime.now().strftime('%X.%f')}")
```

```python
# no context manager, use directly

from datetime import datetime

from limitor.generic_cell_rate import (
    GCRAConfig,
    SyncLeakyBucketGCRA,
    SyncVirtualSchedulingGCRA,
)

# 10 requests per 5 seconds and a 10 second burst capacity
config = GCRAConfig(capacity=10, seconds=5)
sync_bucket = SyncLeakyBucketGCRA(config)  # can swap with SyncVirtualSchedulingGCRA
for i in range(12):
    if i % 2 == 0:
        sync_bucket.acquire(1)
    else:
        sync_bucket.acquire(2)
    print(f"Current level {i + 1} sent at {datetime.now().strftime('%X.%f')}")
```

## Async Rate Limiting

### Leaky Bucket

```python
import asyncio
import time

from limitor.leaky_bucket import AsyncLeakyBucket, LeakynBucketConfig


async def main():
    bucket = AsyncLeakyBucket(LeakyBucketConfig(capacity=2, seconds=2))
    for i in range(10):
        await bucket.acquire()
        print(f"Request {i + 1} allowed at {time.strftime('%X')}")


asyncio.run(main())
```

uneven requests

```python
import asyncio
import time

from limitor.leaky_bucket import AsyncLeakyBucket, LeakynBucketConfig


async def request(bucket, amount, idx):
    await bucket.acquire(amount)
    print(f"Request {idx} (amount={amount}) allowed at {time.strftime('%X')}")


async def main():
    bucket = AsyncLeakyBucket(LeakyBucketConfig(capacity=3, seconds=3), max_concurrent=5)
    amounts = [1, 3, 2, 1, 2, 3, 1]
    tasks = [
        asyncio.create_task(request(bucket, amt, i))
        for i, amt in enumerate(amounts, 1)
    ]
    await asyncio.gather(*tasks)


asyncio.run(main())
```

## Async HTTP Requests

```python
import asyncio
import random
import time

import httpx

from limitor.extra.leaky_bucket.core import AsyncLeakyBucket, LeakyBucketConfig


async def fetch_url(bucket, client, url, idx, timeout):
    try:
        await bucket.acquire(timeout=timeout)
        response = await client.get(url, timeout=timeout)
        text = response.text
        print(f"Request {idx} succeeded: {len(text)} bytes at {time.strftime('%X')}")
    except asyncio.TimeoutError:
        print(f"Request {idx} timed out by rate limiter at {time.strftime('%X')}")
    except Exception as e:
        print(f"Request {idx} failed: {e}")


async def main():
    bucket = AsyncLeakyBucket(LeakyBucketConfig(capacity=2, seconds=2))
    urls = [
        "https://example.com",
        "https://httpbin.org/get",
        "https://httpbin.org/delay/1",
        "https://httpbin.org/delay/2",
        "https://example.com",
        "https://httpbin.org/get"
    ]
    async with httpx.AsyncClient() as client:
        tasks = [
            fetch_url(bucket, client, url, idx, random.uniform(0.5, 2.5))
            for idx, url in enumerate(urls, 1)
        ]
        await asyncio.gather(*tasks)
    await bucket.shutdownß()

    
asyncio.run(main())
```
