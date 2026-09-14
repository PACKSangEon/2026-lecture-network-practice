#!/usr/bin/env python3
"""Week 3 · Task 3 — Beat the baseline cache.

Textbook §2.4.2 (caching) and §2.4.3 (TTL).

    python3 bench.py                 # baseline only
    python3 bench.py --yours         # baseline vs. yours, side by side
"""
import time


class BaselineCache:
    """A DNS cache that somebody wrote in a hurry.

    It caches. It is not correct, and it is not fast. Both are your problem.
    """

    FIXED_LIFETIME = 60          # seconds we keep anything, regardless of TTL

    def __init__(self, upstream):
        self.upstream = upstream  # upstream(name) -> (address, ttl)
        self.entries = []         # list of [name, address, stored_at]

    def lookup(self, name, now):
        """Return an address for `name`, asking upstream only if we have to."""
        for entry in self.entries:                      # linear scan
            if entry[0] == name:
                if now - entry[2] < self.FIXED_LIFETIME:
                    return entry[1]
                self.entries.remove(entry)
                break
        address, ttl = self.upstream(name)
        self.entries.append([name, address, now])
        return address

    def stats(self):
        return {"entries": len(self.entries)}


class YourCache:
    """Correct TTL-respecting cache.

    Two bugs in BaselineCache:
    1. Performance: linear scan O(n) — a dict gives O(1) lookup.
    2. Correctness: FIXED_LIFETIME=60s ignores the actual TTL, so records with
       TTL < 60 are served stale, and records with TTL > 60 are evicted early.

    Fix: store (address, expiry_time) keyed by name. Serve from cache only
    while now < expiry_time; otherwise fetch fresh and update the expiry.
    """

    def __init__(self, upstream):
        self.upstream = upstream
        # name -> (address, expiry_time)
        self._cache = {}

    def lookup(self, name, now):
        entry = self._cache.get(name)
        if entry is not None:
            address, expiry = entry
            if now < expiry:                # still fresh
                return address
        # Cache miss or expired — fetch upstream
        address, ttl = self.upstream(name)
        self._cache[name] = (address, now + ttl)
        return address

    def stats(self):
        return {"entries": len(self._cache)}
