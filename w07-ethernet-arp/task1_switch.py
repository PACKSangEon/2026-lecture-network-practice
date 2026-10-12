#!/usr/bin/env python3
"""Week 7 · Task 1 — Build a learning switch.

Textbook §6.4.3 (link-layer switches, self-learning) and §6.4.1 (MAC addresses).

A switch is handed a frame and has to decide which ports to send it out of.
Nobody configures it. It works out the map by **watching where frames come
from**, which is the whole idea of self-learning, and it is about thirty lines.

The thirty lines are not the hard part. The hard part is what it does when it
does not know, and what happens to the things it learned when a machine moves.

    python3 task1_switch.py --verify
"""
import argparse


class Switch:
    """A self-learning Ethernet switch.

    `ports` is how many it has, numbered from 0.

    handle(frame, in_port) -> list of ports to forward out of, in ascending order

    A frame is (src_mac, dst_mac, time). Time is in seconds and it only moves
    forward; you need it for aging.
    """

    BROADCAST = "ff:ff:ff:ff:ff:ff"
    AGE_SECONDS = 300

    def __init__(self, ports):
        self.ports = ports
        self._table = {}   # mac -> (port, timestamp)
        self._now = 0.0

    def handle(self, frame, in_port):
        """Learn from the source, then decide where the frame goes.

        The rules, in the order they matter:

          1. learn: the source MAC is reachable through `in_port`, as of now
          2. never send a frame back out of the port it arrived on
          3. broadcast destination -> every other port
          4. known destination -> that one port only
          5. unknown destination -> every other port ("flooding")

        Rule 5 is why a switch works at all before it has learned anything, and
        it is also what Task 3 is about.
        """
        src, dst, now = frame
        self._now = now
        # Rule 1: learn source MAC with current timestamp
        self._table[src] = (in_port, now)
        other = [p for p in range(self.ports) if p != in_port]
        # Rule 3: broadcast floods everywhere except back
        if dst == self.BROADCAST:
            return other
        # Rule 4: known, non-aged destination -> direct forward
        if dst in self._table:
            out_port, ts = self._table[dst]
            if now - ts < self.AGE_SECONDS:
                return [] if out_port == in_port else [out_port]
        # Rule 5: unknown or aged-out destination -> flood
        return other

    def table(self):
        """{mac: port} as currently learned. Aged-out entries must be gone."""
        return {m: p for m, (p, t) in self._table.items()
                if self._now - t < self.AGE_SECONDS}


# ------------------------------------------------------------------- harness
A, B, C = "00:00:00:00:00:0a", "00:00:00:00:00:0b", "00:00:00:00:00:0c"
BC = Switch.BROADCAST


def verify():
    fails = 0

    def check(label, got, want):
        nonlocal fails
        ok = got == want
        print(f"  {'ok  ' if ok else 'FAIL'}  {label:<46} {got}"
              + ("" if ok else f"   want {want}"))
        fails += not ok

    try:
        s = Switch(4)
    except NotImplementedError:
        print("  Switch is still a stub"); return 1

    # A talks to B. Nobody knows B yet, so it floods - but not back to port 0.
    check("unknown destination floods",
          s.handle((A, B, 0.0), 0), [1, 2, 3])
    # Now B answers from port 2. The switch has seen A, so it forwards precisely.
    check("known destination is not flooded",
          s.handle((B, A, 1.0), 2), [0])
    check("learned both",
          s.table(), {A: 0, B: 2})
    # Broadcast always goes everywhere except back.
    check("broadcast floods",
          s.handle((A, BC, 2.0), 0), [1, 2, 3])
    # A frame for yourself must not come back out of the port it came in on.
    check("never back out the arrival port",
          s.handle((C, A, 3.0), 0), [])
    # B moves to port 3. The switch must believe the new evidence.
    check("station moved, table follows",
          (s.handle((B, A, 4.0), 3), s.table()[B]), ([0], 3))
    # Nothing heard from A for longer than AGE_SECONDS - it must be forgotten.
    s.handle((C, BC, 400.0), 1)
    check("aged-out entry is gone", A in s.table(), False)

    print(f"\n  {'all ok' if not fails else str(fails) + ' failed'}")
    return 1 if fails else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--verify", action="store_true")
    a = p.parse_args()
    raise SystemExit(verify() if a.verify else p.print_help())
