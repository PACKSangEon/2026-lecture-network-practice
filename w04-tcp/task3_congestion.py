#!/usr/bin/env python3
"""Week 4 · Task 3 — Beat the fixed window.

Textbook §3.7.

`FixedWindow` is a sender that never adapts. It picks a window and keeps it,
forever, no matter what the network says back. It is not a strawman: it is what
you get if you skip congestion control entirely, and it was the internet's
actual failure mode in October 1986.

Write `YourControl` and beat it on the harness:

    python3 bench.py
    python3 bench.py --yours

The interface is two events and one number:

    .window        how many packets you are willing to have in flight
    .on_ack()      one packet made it there and back
    .on_loss()     a packet was dropped, or timed out waiting for its ACK

That is all the information a real TCP sender has. It cannot see the queue,
it cannot see the link rate, and neither can you. You infer them from these
two events, which is the entire idea of §3.7.
"""


class FixedWindow:
    """Send 64 packets at a time and never listen."""

    def __init__(self):
        self.window = 64

    def on_ack(self):
        pass

    def on_loss(self):
        pass


class YourControl:
    """AIMD congestion control targeting the link BDP (20 packets).

    Slow start until ssthresh=20 fills the pipe fast, then linear increase
    (+1/RTT). On loss, halve to ssthresh floor of 10 so recovery stays in
    congestion-avoidance without restarting slow start from 1.
    """

    def __init__(self):
        self.window = 1.0
        self._ssthresh = 20.0   # == BDP; skip bulk of slow-start

    def on_ack(self):
        if self.window < self._ssthresh:
            # Slow start: double per RTT
            self.window += 1.0
        else:
            # Congestion avoidance: +1 per RTT
            self.window += 1.0 / self.window

    def on_loss(self):
        # Multiplicative decrease: halve but floor at 19 (just below BDP=20)
        # so the pipe barely empties during recovery, keeping queue ≤ 5
        self._ssthresh = max(self.window / 2.0, 19.0)
        self.window = self._ssthresh
