import time
from typing import Dict, Tuple
from dataclasses import dataclass


@dataclass
class Bucket:
    capacity: float
    tokens: float
    rate: float  # tokens per second
    last_refill: float


class RateLimiter:
    """
    Implements a Token Bucket algorithm for rate limiting.
    Manages multiple independent buckets identified by a key (scope).
    """

    def __init__(self):
        self._buckets: Dict[str, Bucket] = {}

    def update_bucket(self, key: str, rate: float, capacity: float = None):
        """
        Updates or creates a bucket configuration.
        
        Args:
            key: Unique identifier for the bucket.
            rate: Tokens per second.
            capacity: Max tokens. Defaults to rate (i.e., 1 second worth of tokens).
        """
        if capacity is None:
            capacity = rate

        now = time.time()
        
        if key not in self._buckets:
            # Initialize full
            self._buckets[key] = Bucket(
                capacity=capacity,
                tokens=capacity,
                rate=rate,
                last_refill=now
            )
        else:
            # Update existing parameters, keeping current level (clamped)
            b = self._buckets[key]
            # Refill first to be fair
            self._refill(b, now)
            b.rate = rate
            b.capacity = capacity
            b.tokens = min(b.tokens, b.capacity)

    def try_acquire(self, key: str, cost: float = 1.0) -> float:
        """
        Attempts to acquire tokens from the bucket.

        Returns:
            0.0 if successful.
            >0.0 if failed, representing the seconds to wait until enough tokens are available.
        """
        bucket = self._buckets.get(key)
        if not bucket:
            # No limit defined for this key implies infinite tokens
            return 0.0

        now = time.time()
        self._refill(bucket, now)

        if bucket.tokens >= cost:
            bucket.tokens -= cost
            return 0.0
        else:
            # Calculate time to wait
            missing = cost - bucket.tokens
            if bucket.rate <= 0:
                return float("inf") # Should not happen in normal config
            return missing / bucket.rate

    def _refill(self, bucket: Bucket, now: float):
        elapsed = now - bucket.last_refill
        if elapsed > 0:
            added = elapsed * bucket.rate
            bucket.tokens = min(bucket.capacity, bucket.tokens + added)
            bucket.last_refill = now