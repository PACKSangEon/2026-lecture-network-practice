#!/usr/bin/env python3
"""Week 4 · Task 1 — Build reliable delivery on top of an unreliable channel.

Textbook §3.4 (reliable data transfer) and §3.5 (TCP's sequence numbers).

`UnreliableChannel` below loses packets, reorders them, duplicates them, and
delays them. It is the network as §3.4 models it. Your job is to move a file
across it and have the bytes arrive intact and in order.

That is the whole of TCP's reliability story with the congestion control taken
out, and it is worth building once by hand before you ever trust a socket again.

    python3 task1_rdt.py --verify
"""
import argparse, hashlib, random

PAYLOAD = 8            # bytes per packet - small, so you see the sequencing


class UnreliableChannel:
    """Loses 10%, duplicates 3%, reorders, and delays. Deterministic by seed.

    You may not make it nicer. You may not read its internals. It is the only
    way your sender can reach your receiver.
    """

    def __init__(self, seed=246, loss=0.10, dup=0.03, reorder=0.10):
        self.rng = random.Random(seed)
        self.loss, self.dup, self.reorder = loss, dup, reorder
        self.wire = []          # packets in flight, in no particular order
        self.stats = {"sent": 0, "lost": 0, "duplicated": 0, "delivered": 0}

    def send(self, packet):
        """Hand a packet to the network. It may never come out."""
        self.stats["sent"] += 1
        if self.rng.random() < self.loss:
            self.stats["lost"] += 1
            return
        copies = 2 if self.rng.random() < self.dup else 1
        self.stats["duplicated"] += copies - 1
        for _ in range(copies):
            if self.rng.random() < self.reorder and self.wire:
                self.wire.insert(self.rng.randrange(len(self.wire)), packet)
            else:
                self.wire.append(packet)

    def receive(self):
        """Take the next packet out, or None if the network has nothing."""
        if not self.wire:
            return None
        self.stats["delivered"] += 1
        return self.wire.pop(0)


class Sender:
    """Stop-and-wait sender.

    Sends one chunk at a time, waits for matching ACK, retransmits on timeout.
    Chosen over sliding window: simpler duplicate/reorder handling with no
    out-of-order buffer needed on either side.
    """

    TIMEOUT = 20  # steps before retransmit

    def __init__(self, data_channel, ack_channel, data):
        self._data_ch = data_channel
        self._ack_ch = ack_channel
        self._chunks = [data[i:i + PAYLOAD] for i in range(0, len(data), PAYLOAD)]
        self._num_chunks = len(self._chunks)
        self._next = 0          # next seq to deliver
        self._step = 0
        self._last_tx = -(self.TIMEOUT)  # forces immediate send on first step

    def _transmit(self):
        self._data_ch.send((self._next, self._chunks[self._next]))
        self._last_tx = self._step

    def step(self):
        """Do one unit of work. Return False when you believe you are done."""
        self._step += 1

        # Drain one ACK and advance if it matches current seq
        pkt = self._ack_ch.receive()
        if pkt is not None and pkt == self._next:
            self._next += 1
            self._last_tx = -(self.TIMEOUT)  # trigger immediate send of next

        if self._next >= self._num_chunks:
            return False

        if self._step - self._last_tx >= self.TIMEOUT:
            self._transmit()

        return True


class Receiver:
    """Your receiver. Hands back the reassembled bytes via `.data()`."""

    def __init__(self, data_channel, ack_channel):
        self._data_ch = data_channel
        self._ack_ch = ack_channel
        self._expected = 0
        self._buf = b""

    def step(self):
        pkt = self._data_ch.receive()
        if pkt is None:
            return
        seq, payload = pkt
        if seq == self._expected:
            # In-order: accept and advance
            self._buf += payload
            self._expected += 1
            self._ack_ch.send(seq)
        elif seq < self._expected:
            # Duplicate: re-ACK so sender doesn't time out waiting
            self._ack_ch.send(seq)
        # seq > expected: out-of-order in stop-and-wait, ignore;
        # sender will retransmit the missing one after timeout

    def data(self):
        """The bytes reassembled so far."""
        return self._buf


# ------------------------------------------------------------------- harness
def verify(seed=246, size=2000, max_steps=200_000):
    original = bytes(random.Random(seed).getrandbits(8) for _ in range(size))
    up, down = UnreliableChannel(seed), UnreliableChannel(seed + 1)

    # Data goes out over `up`, ACKs come back over `down`. Both are unreliable.
    sender = Sender(up, down, original)
    receiver = Receiver(up, down)

    for _ in range(max_steps):
        alive = sender.step()
        receiver.step()
        if not alive and len(receiver.data() or b"") >= size:
            break

    got = receiver.data() or b""
    ok = hashlib.sha256(got).hexdigest() == hashlib.sha256(original).hexdigest()
    print(f"  bytes    sent {size}   received {len(got)}")
    print(f"  channel  {up.stats}")
    print(f"  result   {'IDENTICAL' if ok else 'CORRUPTED OR INCOMPLETE'}")
    return 0 if ok else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--verify", action="store_true")
    p.add_argument("--seed", type=int, default=246)
    a = p.parse_args()
    raise SystemExit(verify(a.seed) if a.verify else p.print_help())
