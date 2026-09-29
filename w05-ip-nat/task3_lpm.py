#!/usr/bin/env python3
"""Week 5 · Task 3 — Make longest-prefix match fast.

Textbook §4.3.3.

`LinearTable` is correct and it is what you probably wrote in Task 1: keep the
prefixes in a list, check every one, remember the longest that matched. On six
entries that is fine. A real router holds close to a million, and it has to
answer while the packet is still in the buffer.

Beat it:

    python3 bench.py
    python3 bench.py --yours

Correctness first: `bench.py` checks every one of your answers against the
linear table. A fast router that forwards to the wrong next hop is not a
router, it is an outage.
"""


class LinearTable:
    """Correct, and slow in the obvious way."""

    def __init__(self):
        self.entries = []                     # (prefix_len, network, next_hop)

    def add(self, network, prefix_len, next_hop):
        self.entries.append((prefix_len, network, next_hop))

    def lookup(self, address):
        best = None
        for plen, net, hop in self.entries:
            mask = (0xFFFFFFFF << (32 - plen)) & 0xFFFFFFFF
            if address & mask == net and (best is None or plen > best[0]):
                best = (plen, hop)
        return best[1] if best else None


class YourTable:
    """Your table. Same three methods, same answers, fewer comparisons.

    Addresses and networks are plain 32-bit ints here - no strings, no parsing,
    so that the benchmark measures your lookup and nothing else.

    Two directions worth knowing about before you pick one:

      * group by prefix length. There are only 33 possible lengths, and you can
        ask them in an order that lets you stop early.
      * walk the address one bit at a time. Each bit takes you to at most one
        child, so the work is bounded by the address width, not by the table size.

    The second is what hardware does. The first is easier and often enough.
    Say which you chose and what it cost you in memory.

    Chosen: group by prefix length. One dict per length that is actually in
    use, keyed by network. A lookup masks the address once per length,
    longest first, and stops at the first hit - at most 33 dict probes,
    in practice only the handful of lengths the table holds (7 here).
    Memory: one dict entry per route plus a sorted list of lengths.
    """

    def __init__(self):
        self.by_len = {}                      # prefix_len -> {network: next_hop}
        self.probes = []                      # [(mask, dict)] longest first

    def add(self, network, prefix_len, next_hop):
        bucket = self.by_len.get(prefix_len)
        if bucket is None:
            bucket = self.by_len[prefix_len] = {}
            self.probes = [((0xFFFFFFFF << (32 - p)) & 0xFFFFFFFF, self.by_len[p])
                           for p in sorted(self.by_len, reverse=True)]
        bucket[network] = next_hop

    def lookup(self, address):
        for mask, bucket in self.probes:
            hop = bucket.get(address & mask)
            if hop is not None:
                return hop
        return None
