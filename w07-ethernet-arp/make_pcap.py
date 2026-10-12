import struct, os

def make_pcapng():
    shb_body = struct.pack('<IHHq', 0x1A2B3C4D, 1, 0, -1)
    shb_len = 12 + len(shb_body)
    shb = struct.pack('<II', 0x0A0D0D0A, shb_len) + shb_body + struct.pack('<I', shb_len)

    idb_body = struct.pack('<HHI', 1, 0, 65535)
    idb_len = 12 + len(idb_body)
    idb = struct.pack('<II', 1, idb_len) + idb_body + struct.pack('<I', idb_len)

    def make_arp_pkt(dst_mac, src_mac, oper, sha, spa, tha, tpa):
        eth = dst_mac + src_mac + b'\x08\x06'
        arp_hdr = struct.pack('!HHBBH', 1, 0x0800, 6, 4, oper)
        return eth + arp_hdr + sha + spa + tha + tpa

    def make_epb(pkt):
        pad = (4 - len(pkt) % 4) % 4
        body = struct.pack('<IIIII', 0, 0, 0, len(pkt), len(pkt)) + pkt + b'\x00' * pad
        blen = 12 + len(body)
        return struct.pack('<II', 6, blen) + body + struct.pack('<I', blen)

    mac1  = bytes.fromhex('001122334455')
    mac2  = bytes.fromhex('00aabbccddee')
    bcast = b'\xff' * 6
    zeros = b'\x00' * 6
    ip1   = bytes([192, 168, 1, 1])
    ip2   = bytes([192, 168, 1, 2])

    req = make_arp_pkt(bcast, mac1, 1, mac1, ip1, zeros, ip2)
    rep = make_arp_pkt(mac1,  mac2, 2, mac2, ip2, mac1, ip1)
    return shb + idb + make_epb(req) + make_epb(rep)

os.makedirs('out', exist_ok=True)
data = make_pcapng()
with open('out/arp.pcapng', 'wb') as f:
    f.write(data)
print(f'Generated out/arp.pcapng ({len(data)} bytes)')
