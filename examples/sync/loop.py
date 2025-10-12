import time
from datetime import datetime

from limitor.configs import BucketConfig
from limitor.generic_cell_rate.core import (
    SyncLeakyBucketGCRA,
)
from limitor.leaky_bucket.core import SyncLeakyBucket

print("Leaky Bucket Algorithm\n")

# 4 requests per 2 seconds and a 4 second burst capacity
config = BucketConfig(capacity=4, seconds=2)
sync_bucket = SyncLeakyBucket(config)
for i in range(10):
    sync_bucket.acquire(1)
    print(f"Acquired 1 unit using context manager: {sync_bucket._bucket_level}")
    print(f"Current level {i} sent at {time.strftime('%X')}")

"""
this is optional, you do not have to leak at the end
it is illustrative of how the leaky bucket algorithm works i.e. leaks
"""
print("Waiting for bucket to leak...")
time.sleep(1)  # check how much leaks out of the bucket in 1 second
sync_bucket._leak()  # update the bucket level after waiting
print(f"Current level after waiting 1 second: {sync_bucket._bucket_level}")

print("\nGeneric Cell Rate Algorithm\n")

# 10 requests per 5 seconds and a 10 second burst capacity
config = BucketConfig(capacity=10, seconds=5)
sync_bucket = SyncLeakyBucketGCRA(config)  # can swap with SyncVirtualSchedulingGCRA
for i in range(12):
    if i % 2 == 0:
        sync_bucket.acquire(1)
    else:
        sync_bucket.acquire(2)
    print(f"Current level {i + 1} sent at {datetime.now().strftime('%X.%f')}")
