#!/usr/bin/env python3
"""Week 7 · Task 3 — A switch that runs out of room.

Textbook §6.4.3.

A switch does not have room for every station on the network. Its forwarding
table sits in a fixed amount of fast memory, and when that fills, something has
to go. Whatever goes gets **flooded** the next time anyone sends to it - out of
every port, to every station that did not ask for it.

`NaiveSwitch` handles a full table the simplest way: throw out whichever entry
has been there longest. That is a perfectly reasonable first idea and it is
close to the worst thing you can do with this traffic.

    python3 bench.py
    python3 bench.py --yours

Correctness first: every frame whose destination is reachable must still reach
it. A switch that floods less because it delivers less is not a switch.
"""
from collections import OrderedDict


class NaiveSwitch:
    """Correct. Evicts the oldest entry, which is not the least useful one."""

    BROADCAST = "ff:ff:ff:ff:ff:ff"

    def __init__(self, ports, capacity):
        self.ports = ports
        self.capacity = capacity
        self.table = OrderedDict()                 # mac -> port, insertion order

    def handle(self, frame, in_port):
        src, dst, now = frame
        if src not in self.table and len(self.table) >= self.capacity:
            self.table.popitem(last=False)         # throw out the oldest arrival
        self.table[src] = in_port

        if dst == self.BROADCAST or dst not in self.table:
            return [p for p in range(self.ports) if p != in_port]
        out = self.table[dst]
        return [] if out == in_port else [out]


class YourSwitch:
    """LFU eviction + frequency-based admission control.

    Two improvements over NaiveSwitch:
      1. Evict the least-frequently-used (LFU) entry, not FIFO. Hot stations
         accumulate high counts and are never displaced by rarely-seen ones.
      2. Decline new admissions when the table is full unless the newcomer
         has been seen (_seen counter) more times than the LFU entry has
         been active inside the table. This filters one-shot senders that
         would only evict a well-established entry.

    _seen is a plain dict (not part of self.table); only self.table is
    capacity-bounded.
    """

    BROADCAST = "ff:ff:ff:ff:ff:ff"

    def __init__(self, ports, capacity):
        self.ports = ports
        self.capacity = capacity
        self.table = {}   # mac -> (port, hit_count_while_in_table)
        self._seen = {}   # mac -> total times seen as source (admission counter)

    def handle(self, frame, in_port):
        src, dst, now = frame
        self._seen[src] = self._seen.get(src, 0) + 1

        if src in self.table:
            port, cnt = self.table[src]
            self.table[src] = (in_port, cnt + 1)
        elif len(self.table) < self.capacity:
            self.table[src] = (in_port, 1)
        else:
            # Find least-frequently-used entry
            lfu_mac = min(self.table, key=lambda m: self.table[m][1])
            lfu_cnt = self.table[lfu_mac][1]
            if self._seen[src] > lfu_cnt:
                # Newcomer has proven itself more active; evict LFU
                del self.table[lfu_mac]
                self.table[src] = (in_port, self._seen[src])
            # else: decline — LFU entry is still more active than this newcomer

        if dst == self.BROADCAST or dst not in self.table:
            return [p for p in range(self.ports) if p != in_port]
        port, cnt = self.table[dst]
        self.table[dst] = (port, cnt + 1)
        return [] if port == in_port else [port]
