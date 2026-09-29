#!/usr/bin/env python3
"""Week 5 · Task 1 — Subnets and longest-prefix match.

Textbook §4.3.2 (IPv4 addressing, CIDR) and §4.3.3 (forwarding).

Two things a router does with every packet: work out which prefixes the
destination falls inside, and pick the longest one. The second is the whole
of "longest prefix match", and it is the reason the internet's routing table
can hold a million entries and still be answerable.

You build both, from integers up. No `ipaddress` module - that library is
exactly the thing you are supposed to understand this week.

    python3 task1_forward.py --verify
"""
import argparse


def _ip_to_int(text):
    parts = text.strip().split(".")
    if len(parts) != 4:
        raise ValueError(f"not a dotted quad: {text!r}")
    value = 0
    for p in parts:
        if not p.isdigit() or int(p) > 255:
            raise ValueError(f"bad octet {p!r} in {text!r}")
        value = (value << 8) | int(p)
    return value


def _int_to_ip(value):
    return ".".join(str((value >> s) & 0xFF) for s in (24, 16, 8, 0))


def _mask(plen):
    return (0xFFFFFFFF << (32 - plen)) & 0xFFFFFFFF


def parse_cidr(cidr):
    """'163.152.6.0/24' -> (network as int, prefix length).

    Requirements: reject a prefix length outside 0-32, and reject an address
    whose host bits are set when they should not be (163.152.6.5/24 is a
    common way to write a host, but it is not a network).
    """
    addr, sep, plen_text = cidr.strip().partition("/")
    if not sep or not plen_text.isdigit():
        raise ValueError(f"missing prefix length: {cidr!r}")
    plen = int(plen_text)
    if not 0 <= plen <= 32:
        raise ValueError(f"prefix length out of range 0-32: {cidr!r}")
    net = _ip_to_int(addr)
    if net & ~_mask(plen) & 0xFFFFFFFF:
        raise ValueError(f"host bits set - {cidr!r} is a host, not a network")
    return net, plen


def network_range(cidr):
    """'163.152.6.0/24' -> (first usable, last usable, broadcast) as strings.

    Careful at the edges. /31 and /32 do not have a usable host range in the
    ordinary sense - decide what you return and say so in observation.md.

    /31 (RFC 3021 point-to-point): both addresses are usable, no broadcast -> None.
    /32: the single address is the only host, no broadcast -> None.
    """
    net, plen = parse_cidr(cidr)
    last = net | (~_mask(plen) & 0xFFFFFFFF)
    if plen == 32:
        return _int_to_ip(net), _int_to_ip(net), None
    if plen == 31:
        return _int_to_ip(net), _int_to_ip(last), None
    return _int_to_ip(net + 1), _int_to_ip(last - 1), _int_to_ip(last)


class ForwardingTable:
    """Longest-prefix-match forwarding.

    add(cidr, next_hop)  ·  lookup(address) -> next_hop or None

    The default route 0.0.0.0/0 matches everything and is the shortest prefix,
    so it must lose to any other match. If two entries have the same prefix
    length, the table is malformed - say what you do.

    Same (network, length) added twice: the later add replaces the earlier
    one, like a route update - one prefix never holds two next hops.
    """

    def __init__(self):
        self.routes = {}                      # (network, prefix_len) -> next_hop

    def add(self, cidr, next_hop):
        self.routes[parse_cidr(cidr)] = next_hop

    def lookup(self, address):
        addr = _ip_to_int(address)
        best_len, best_hop = -1, None
        for (net, plen), hop in self.routes.items():
            if addr & _mask(plen) == net and plen > best_len:
                best_len, best_hop = plen, hop
        return best_hop


# ------------------------------------------------------------------- harness
RANGE_CASES = [
    ("192.168.0.0/24",  "192.168.0.1",   "192.168.0.254",  "192.168.0.255"),
    ("10.0.0.0/8",      "10.0.0.1",      "10.255.255.254", "10.255.255.255"),
    ("172.16.32.0/20",  "172.16.32.1",   "172.16.47.254",  "172.16.47.255"),
    ("203.0.113.64/26", "203.0.113.65",  "203.0.113.126",  "203.0.113.127"),
]

TABLE = [
    ("0.0.0.0/0",       "default-gw"),
    ("10.0.0.0/8",      "campus"),
    ("10.20.0.0/16",    "eng-building"),
    ("10.20.30.0/24",   "lab-floor"),
    ("10.20.30.64/26",  "lab-rack-2"),
    ("192.168.1.0/24",  "home"),
]

LOOKUP_CASES = [
    ("10.20.30.70",   "lab-rack-2"),     # inside all four 10.x entries
    ("10.20.30.10",   "lab-floor"),
    ("10.20.99.1",    "eng-building"),
    ("10.99.0.1",     "campus"),
    ("8.8.8.8",       "default-gw"),
    ("192.168.1.77",  "home"),
]


def verify():
    fails = 0
    for cidr, first, last, bcast in RANGE_CASES:
        try:
            got = network_range(cidr)
        except NotImplementedError:
            print("  network_range is still a stub"); return 1
        except Exception as e:
            print(f"  FAIL  {cidr:<18} raised {e!r}"); fails += 1; continue
        ok = tuple(got) == (first, last, bcast)
        print(f"  {'ok  ' if ok else 'FAIL'}  {cidr:<18} {got}")
        fails += not ok

    t = ForwardingTable()
    try:
        for cidr, hop in TABLE:
            t.add(cidr, hop)
    except NotImplementedError:
        print("  ForwardingTable is still a stub"); return 1

    for addr, expect in LOOKUP_CASES:
        got = t.lookup(addr)
        ok = got == expect
        print(f"  {'ok  ' if ok else 'FAIL'}  {addr:<16} -> {got}  (want {expect})")
        fails += not ok

    print(f"\n  {len(RANGE_CASES) + len(LOOKUP_CASES) - fails}"
          f"/{len(RANGE_CASES) + len(LOOKUP_CASES)} ok")
    return 1 if fails else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--verify", action="store_true")
    a = p.parse_args()
    raise SystemExit(verify() if a.verify else p.print_help())
