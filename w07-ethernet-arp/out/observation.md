# Week 7 Observations

## Task 1 · A Learning Switch

- A frame must never go back out of the port it arrived on because the sending station is definitionally reachable through that port — returning the frame would loop it back to the sender and consume bandwidth without making progress toward the destination.
- A switch floods when the destination is unknown because it does not know which port leads to it, yet still has to deliver the frame; a router drops unknowns because IP routing guarantees that every routable destination has an explicit entry — if none exists the packet is truly undeliverable, whereas at layer 2 "unknown" just means "not yet learned."
- Using a time-based age rather than an explicit "station departed" signal means the table holds stale entries for up to AGE_SECONDS after a device moves or powers off; "more direct" would be a mobility signal (802.11 reassociation, gratuitous ARP) but those require cooperation from the station, which a pure switch cannot assume.

## Task 2 · Watch ARP Happen

- The first entry to come back after clearing is the default gateway (192.168.1.1), because every frame destined outside the local subnet is handed to the gateway first — the very next IP packet triggers an ARP request for it before any other host.
- A server on the other side of the world does not appear in the ARP table because ARP operates at layer 2 and only resolves MAC addresses for hosts on the same local subnet; traffic to remote IP addresses goes to the gateway, whose MAC is cached, not the server's.
- The ARP request carries destination MAC ff:ff:ff:ff:ff:ff (broadcast), meaning every station on the segment must receive and inspect it; the reply carries the requester's unicast MAC, so only the original asker receives the answer — a question everyone hears, an answer only one machine needs.

## Task 3 · A Switch That Runs Out of Room

- Eviction policy: LFU (least-frequently-used); each table entry tracks a hit count incremented on every source or destination match. Admission control: when the table is full, a new source is admitted only if its total-appearances counter (_seen) exceeds the LFU entry's in-table count; first-time senders are declined. Together these cut wasted deliveries by 50% (→ strong) versus the baseline's FIFO with no admission control.
- Declining admission made the largest single improvement: without it LRU alone cut 32%; adding the frequency gate pushed the cut to 50%. The gain comes from preventing rare senders from evicting entries for stations that carry most of the traffic in the Zipf-distributed trace.
- R6 — attack (MAC flooding / CAM table overflow): an attacker sends frames with a large number of forged source MACs, each unique, filling the table with useless entries. Once full, every new real frame gets flooded to all ports, making the switch behave like a hub and exposing all traffic to the attacker's port. One countermeasure: rate-limit learning (max N new entries per second per port), or limit the number of MACs learned per port so a single attacker port cannot exhaust the whole table.
