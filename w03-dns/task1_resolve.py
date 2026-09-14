#!/usr/bin/env python3
"""Week 3 · Task 1 — Build your own iterative resolver.

Textbook §2.4.2 - §2.4.3.

    python3 task1_resolve.py www.korea.ac.kr
    python3 task1_resolve.py --verify        # check yourself against dig
"""
import argparse, socket, struct, random, sys

ROOT_SERVERS = [
    "198.41.0.4",       # a.root-servers.net
    "199.9.14.201",     # b.root-servers.net
    "192.33.4.12",      # c.root-servers.net
]

VERIFY_NAMES = [
    ("www.korea.ac.kr", "stable"),
    ("dns.google", "stable"),
    ("en.wikipedia.org", "stable"),
    ("www.stanford.edu", "stable"),
    ("www.microsoft.com", "cdn"),
]

# ----------------------------------------------------------------- DNS wire


def _encode_name(name):
    out = b''
    for label in name.rstrip('.').split('.'):
        enc = label.encode('ascii')
        out += bytes([len(enc)]) + enc
    return out + b'\x00'


def _decode_name(data, offset):
    """Return (name_string, new_offset). Handles pointer compression."""
    labels = []
    jumped = False
    final_offset = None

    while offset < len(data):
        b = data[offset]
        if b == 0:
            if not jumped:
                final_offset = offset + 1
            break
        elif (b & 0xC0) == 0xC0:           # pointer
            if offset + 1 >= len(data):
                break
            ptr = ((b & 0x3F) << 8) | data[offset + 1]
            if not jumped:
                final_offset = offset + 2
            jumped = True
            offset = ptr
        else:
            label_len = b
            offset += 1
            if offset + label_len > len(data):
                break
            labels.append(data[offset:offset + label_len].decode('ascii', errors='replace'))
            offset += label_len

    if final_offset is None:
        final_offset = offset + 1
    return '.'.join(labels), final_offset


def _parse_rr(data, offset):
    name, offset = _decode_name(data, offset)
    if offset + 10 > len(data):
        raise ValueError("truncated RR")
    rtype, _rclass, ttl, rdlen = struct.unpack('>HHIH', data[offset:offset + 10])
    offset += 10
    rdata_start = offset
    offset += rdlen

    rdata = None
    if rtype == 1 and rdlen == 4:               # A
        rdata = '.'.join(str(b) for b in data[rdata_start:rdata_start + 4])
    elif rtype in (2, 5):                       # NS, CNAME
        rdata, _ = _decode_name(data, rdata_start)

    return {'name': name.lower(), 'type': rtype, 'ttl': ttl, 'rdata': rdata}, offset


def _parse_response(data):
    if len(data) < 12:
        return None
    txid, flags, qdcount, ancount, nscount, arcount = struct.unpack('>HHHHHH', data[:12])
    res = {
        'txid': txid, 'flags': flags, 'rcode': flags & 0xF,
        'answers': [], 'authority': [], 'additional': [],
    }
    offset = 12
    for _ in range(qdcount):
        _, offset = _decode_name(data, offset)
        offset += 4
    for lst, count in [(res['answers'], ancount),
                       (res['authority'], nscount),
                       (res['additional'], arcount)]:
        for _ in range(count):
            try:
                rr, offset = _parse_rr(data, offset)
                lst.append(rr)
            except Exception:
                break
    return res


def _udp_query(server, name, qtype=1, timeout=3.0):
    """Non-recursive UDP DNS query. Returns parsed response or None."""
    txid = random.randint(1, 65535)
    # RD=0: we do not want the server to recurse for us
    pkt = struct.pack('>HHHHHH', txid, 0x0000, 1, 0, 0, 0)
    pkt += _encode_name(name) + struct.pack('>HH', qtype, 1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(pkt, (server, 53))
        data, _ = sock.recvfrom(8192)
        resp = _parse_response(data)
        if resp and resp['txid'] == txid:
            return resp
    except Exception:
        pass
    finally:
        sock.close()
    return None


# ----------------------------------------------------------------- Resolver


class Resolver:
    """Iterative resolver: walks root -> TLD -> authoritative without recursion."""

    MAX_DEPTH = 20

    def resolve(self, name, _depth=0):
        """Return (address, path) where path is the list of servers queried."""
        if _depth >= self.MAX_DEPTH:
            raise Exception(f"depth cap reached resolving {name!r}")

        name = name.lower().rstrip('.')
        servers = list(ROOT_SERVERS)
        path = []

        for _hop in range(self.MAX_DEPTH):
            progress = False
            for srv in servers:
                resp = _udp_query(srv, name)
                if resp is None:
                    continue                     # R4: server did not answer, try next

                # CNAME in answer section? (R5)
                for rr in resp['answers']:
                    if rr['type'] == 5 and rr['rdata']:
                        path.append(srv)
                        cname = rr['rdata'].lower().rstrip('.')
                        addr, cpath = self.resolve(cname, _depth + 1)
                        return addr, path + cpath

                # A record in answer section?
                for rr in resp['answers']:
                    if rr['type'] == 1 and rr['rdata']:
                        path.append(srv)
                        return rr['rdata'], path

                # Delegation in authority section?
                ns_names = [rr['rdata'] for rr in resp['authority']
                            if rr['type'] == 2 and rr['rdata']]
                if not ns_names:
                    continue

                # Collect glue A records from additional section
                glue = {}
                for rr in resp['additional']:
                    if rr['type'] == 1 and rr['rdata']:
                        glue[rr['name'].lower().rstrip('.')] = rr['rdata']

                # Resolve each NS to an IP (R3: handle missing glue)
                next_servers = []
                for ns in ns_names[:6]:
                    ns_key = ns.lower().rstrip('.')
                    if ns_key in glue:
                        next_servers.append(glue[ns_key])
                    else:
                        # No glue — resolve the NS name independently (R3)
                        try:
                            ns_addr, _ = self.resolve(ns_key, _depth + 1)
                            next_servers.append(ns_addr)
                        except Exception:
                            pass

                if next_servers:
                    path.append(srv)
                    servers = next_servers
                    progress = True
                    break

            if not progress:
                raise Exception(f"could not make progress resolving {name!r}")

        raise Exception(f"hop limit exceeded for {name!r}")


# ------------------------------------------------------------------ harness
def dig_answer(name):
    """What the system resolver says, for comparison."""
    import subprocess
    out = subprocess.run(["dig", "+short", name, "A"],
                         capture_output=True, text=True).stdout
    return [l for l in out.split() if l and l[0].isdigit()]


def verify():
    r, failures = Resolver(), 0
    for name, kind in VERIFY_NAMES:
        try:
            addr, path = r.resolve(name)
        except NotImplementedError:
            print("Nothing implemented yet - write Resolver.resolve first.")
            return 1
        except Exception as e:
            print(f"  FAIL  {name:<22} your resolver raised {e!r}")
            failures += 1
            continue
        expected = dig_answer(name)
        if addr in expected:
            note = ""
        elif kind == "cdn":
            note = "  <- differs, but this name is CDN-hosted. Explain it."
        else:
            note = "  <- should have matched"
            failures += 1
        print(f"  {'FAIL' if note.endswith('matched') else 'ok  '}  {name:<22} "
              f"you={addr:<16} dig={','.join(expected) or '-'}   "
              f"hops={len(path)}{note}")
    print(f"\n  {len(VERIFY_NAMES) - failures}/{len(VERIFY_NAMES)} ok")
    return 1 if failures else 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("name", nargs="?", default="www.korea.ac.kr")
    p.add_argument("--verify", action="store_true")
    a = p.parse_args()

    if a.verify:
        sys.exit(verify())

    addr, path = Resolver().resolve(a.name)
    for i, server in enumerate(path, 1):
        print(f"  {i}. asked {server}")
    print(f"\n  {a.name} -> {addr}")


if __name__ == "__main__":
    main()
