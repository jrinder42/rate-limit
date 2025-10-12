import time
from datetime import datetime

from limitor.configs import BucketConfig
from limitor.generic_cell_rate.core import (
    SyncLeakyBucketGCRA,
)
from limitor.leaky_bucket.core import SyncLeakyBucket
from limitor.token_bucket.core import SyncTokenBucket

print("Leaky Bucket Algorithm\n")

# 4 requests per 2 seconds and a 4 second burst capacity
config = BucketConfig(capacity=4, seconds=2)
context_sync = SyncLeakyBucket(config)  # use the same config as above
for _ in range(10):
    with context_sync as thing:
        print(f"Acquired 1 unit using context manager: {thing._bucket_level}")
        print(f"Current level {_} sent at {time.strftime('%X')}")

"""
this is optional, you do not have to leak at the end
it is illustrative of how the leaky bucket algorithm works i.e. leaks
"""
print("Waiting for bucket to leak...")
# wait 1 second to let the bucket leak: should lower level from 4 --> 2
# our leak rate is 4 per 2 seconds aka 2 per second; hence, after 1 second, we should have 2 left in the bucket
time.sleep(1)
context_sync._leak()  # update the bucket level after waiting -- just to illustrate the leak
print(f"Current level after waiting 1 second: {context_sync._bucket_level}")

print("\nToken Bucket Algorithm\n")

# 4 requests per 2 seconds and a 4 second burst capacity
config = BucketConfig(capacity=4, seconds=2)
context_sync = SyncTokenBucket(config)  # use the same config as above
for _ in range(10):
    with context_sync as thing:
        print(f"Acquired 1 unit using context manager: {thing._bucket_level}")
        print(f"Current level {_} sent at {time.strftime('%X')}")


# wait 1 second to let the bucket leak: should lower level from 4 --> 2
# our leak rate is 4 per 2 seconds aka 2 per second; hence, after 1 second, we should have 2 left in the bucket
time.sleep(1)
context_sync._fill()  # update the bucket level after waiting -- just to illustrate the leak
print(f"Current level after waiting 1 second: {context_sync._bucket_level}")

print("\nGeneric Cell Rate Algorithm\n")

# 3 requests per 1.5 seconds and a 3 second burst capacity
config = BucketConfig(capacity=3, seconds=1.5)
context_sync = SyncLeakyBucketGCRA(config)  # can swap with SyncVirtualSchedulingGCRA
for _ in range(12):
    with context_sync as thing:
        print(f"Current level {_} sent at {datetime.now().strftime('%X.%f')}")
