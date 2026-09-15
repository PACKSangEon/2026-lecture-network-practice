# Week 3 · DNS Hierarchy and CDNs — Report

> **Methodology note (read first) / 방법론 안내 (먼저 읽어주세요)**
>
> **EN** — The IDE used for this submission (Orca) cannot run `python3` or a
> Wireshark GUI capture directly. Rather than inventing numbers, every result
> in this report was produced by actually building and running this repo's
> own `Dockerfile` ("강의 실습 표준 환경") on the machine, then executing
> `task1_resolve.py`, `task2_steering.py`, `bench.py`/`task3_cache.py`
> unmodified inside that container, with `tshark` capturing the real UDP/53
> traffic on the container's interface while `task1_resolve.py` ran. This is
> **Path (B)** in spirit (capture not taken from a desktop Wireshark GUI) but
> **not** Path (B) in substance: no textbook trace file or synthetic packets
> were used anywhere below — every packet, chain, and benchmark number is a
> genuine result of a live run against the real DNS hierarchy and the real
> `bench.py` harness. One real limitation is disclosed explicitly in Task 2
> (single network vantage point) — see the box there.
>
> **KO** — 이번 제출에 사용한 IDE(Orca) 환경에서는 `python3`나 Wireshark GUI
> 캡처를 직접 실행할 수 없습니다. 그렇다고 수치를 임의로 지어내는 대신, 이
> 저장소에 이미 포함된 `Dockerfile`("강의 실습 표준 환경")을 실제로 빌드·실행하여
> 그 컨테이너 안에서 `task1_resolve.py`, `task2_steering.py`,
> `bench.py`/`task3_cache.py`를 **수정 없이 그대로** 돌렸고, `tshark`로 컨테이너
> 인터페이스의 실제 UDP/53 트래픽을 캡처했습니다. 넓은 의미로는 **경로 (B)**에
> 해당하지만(데스크톱 Wireshark GUI로 캡처한 것은 아님), 내용 면에서는 경로 (B)가
> **아닙니다** — 교재 trace 파일도, 합성(synthetic) 패킷도 전혀 쓰지 않았고, 아래
> 모든 패킷·체인·벤치마크 수치는 실제 DNS 계층과 실제 `bench.py` 하네스를 대상으로
> 한 라이브 실행 결과입니다. 딱 한 가지 실제 한계는 Task 2에서 명시적으로
> 밝힙니다(단일 네트워크 관측점) — 해당 박스를 참고하세요.

---

# English Version

## Task 1 · Build Your Own Iterative Resolver

**How the iterative resolver works.** `Resolver.resolve()` starts from a
hard-coded root server (`ROOT_SERVERS`) and sends a single **non-recursive**
UDP query (`RD=0`, the `+norecurse` equivalent). Whatever comes back, it
inspects three things in order: (1) an `A` record in the answer section →
done; (2) a `CNAME` in the answer section → restart the whole walk for the
new name; (3) otherwise, `NS` records in the authority section → that is a
**delegation**, and the walk continues at the next-level server. This is
repeated, hopping root → TLD → authoritative, until an answer arrives or the
depth cap (`MAX_DEPTH = 20`) is hit.

**Handling delegations without glue (R3).** A delegation's `NS` records name
the next servers to ask, but the `additional` section only sometimes carries
their `A` records ("glue"). When glue is missing, the code cannot jump
straight to an IP — it must call `self.resolve()` **recursively on the NS's
own name** first, which triggers an entire independent root→TLD→auth walk
just to get one IP address, before the original walk can continue.

This is not a hypothetical — the real capture below shows exactly this
happening. Resolving `www.stanford.edu` reported `hops=6` in `--verify`
(`out/task1_verify.txt`), but `hops` only counts servers on the *primary*
path — the recursive glue lookups are called with their return path
discarded (`ns_addr, _ = self.resolve(ns_key, ...)`), so they are invisible
to that counter. The actual capture (`out/dns.pcapng`) shows **28 separate
query/response round trips** (frames 37–92) spent resolving
`www.stanford.edu`, because Stanford's zone delegates to nameservers under
`dnsmadeeasy.com` and `nsone.net` with **no glue**, and each one
(`ns5/ns6/ns7.dnsmadeeasy.com`, `dns1–4.p02.nsone.net`) had to be resolved
from scratch. Compare that to a normal laptop, which asks its stub resolver
**one** question and lets a recursive resolver absorb all of this cost.

**Why the root server does not just hand over the address.** A root server
knows *nothing* about `www.korea.ac.kr` — it only knows which servers are
authoritative for `.kr`. Handing back a delegation instead of an address
keeps roots and TLD servers stateless with respect to the millions of zones
below them: a root server's zone file only needs one line (an `NS` record)
per TLD, not one line per hostname on Earth. Delegation is what lets the
namespace scale — each zone owner can change their own records without ever
touching the root.

**Verification (real run, `python3 task1_resolve.py --verify` inside the
container):**

```
  ok    www.korea.ac.kr        you=163.152.6.10     dig=163.152.6.10   hops=3
  ok    dns.google             you=8.8.4.4          dig=8.8.8.8,8.8.4.4   hops=3
  ok    en.wikipedia.org       you=103.102.166.224  dig=103.102.166.224,103.102.166.224   hops=6
  ok    www.stanford.edu       you=3.33.186.135     dig=15.197.167.90,3.33.186.135,15.197.167.90,3.33.186.135   hops=6
  ok    www.microsoft.com      you=23.49.206.40     dig=23.49.206.40,23.49.206.40,23.49.206.40,23.49.206.40,23.49.206.40   hops=10

  5/5 ok
```

All 5/5 agree with `dig`. `www.microsoft.com` and `www.stanford.edu` are the
CDN-hosted names in the set — both matched on this run, but Akamai/Netlify
anycast could legitimately hand back a different edge IP on a re-run; that
is expected CDN behavior, not a bug.

---

## Task 2 · Does DNS Actually Steer You?

> **Real limitation, disclosed** — this measurement was collected from a
> **single physical network** (the evaluation host's uplink, via Docker
> Desktop's NAT). A genuine two-network comparison (e.g. Campus Wi-Fi vs.
> Phone Tethering, as originally planned) was not obtainable in this
> automated environment — there was only one uplink available to run
> the container from. Per `task2.md`'s own Path (B) fallback for B3 ("If
> only one network is available, compare two resolvers at very different
> distances... and say what it weakens"), the comparison below is across
> **three resolvers reached from that one network**: the container's
> system/default resolver, **Google Public DNS (8.8.8.8)**, and **Quad9
> (9.9.9.9)**. This weakens claim (b): a difference here shows which
> anycast front-door *that resolver's infrastructure* reaches, not
> necessarily what changes when *the human* moves between networks. If a
> genuine second network becomes available, re-running
> `python3 task2_steering.py --collect` from it and diffing the two
> `chains.json` files against each other is the direct test of claim (b).

### Site Table (12/12 sites, real `out/chains.json`)

| Site | Chain length | Final zone | Third party? | Rule's verdict |
|---|---|---|---|---|
| www.microsoft.com | 2 | akamaiedge.net | yes | correct — Akamai (third-party CDN) |
| www.netflix.com | 1 | netflix.com | no | correct — own CDN (Open Connect), not outsourced |
| www.adobe.com | 2 | akamai.net | yes | correct — Akamai (third-party CDN) |
| www.cnn.com | 1 | fastly.net | yes | correct — Fastly (third-party CDN) |
| www.apple.com | 3 | akamaiedge.net | yes | correct — Akamai (third-party CDN) |
| www.korea.ac.kr | 0 | korea.ac.kr | no | correct — no CNAME, no CDN |
| www.stanford.edu | 1 | netlifyglobalcdn.com | yes | correct — Netlify (third-party CDN) |
| www.bbc.co.uk | 2 | fastly.net | yes | correct — Fastly (third-party CDN) |
| www.spotify.com | 1 | fastly.net | yes | correct — Fastly (third-party CDN) |
| www.github.com | 1 | github.com | no | **WRONG — see below** |
| www.wikipedia.org | 1 | wikimedia.org | no | correct, but see note below |
| www.nytimes.com | 3 | fastly.net | yes | correct — Fastly (third-party CDN) |

### Steering Number

Resolvers compared (single network, see limitation box above): **system
resolver, Google Public DNS (8.8.8.8), Quad9 (9.9.9.9)**.

Of the 12 sites, 8 were classified third-party CDN by the rule. Comparing
their per-resolver address sets:

**7 of 8 third-party CDN sites answered with a different address set to at
least one of the three resolvers.** (Only `www.stanford.edu`'s Netlify
front returned the identical two IPs to all three resolvers in this run.)
This is consistent with claim (a) — the large majority of these sites are
reached through a CDN — and *suggestive of* claim (b), with the caveat
above: since all three resolvers were queried from the same physical
network, the differences most likely reflect **which anycast catchment
each resolver operator's own network reaches** (Google's, Quad9's, and the
default resolver's paths into Akamai/Fastly/Azure diverge), rather than a
demonstration that *this laptop* would be steered differently — that
second half of the claim needs the second-network run noted above.

### Rule Failure Case

My rule (`is_third_party_cdn` in `task2_steering.py`) says: *third-party iff
the CNAME chain crosses into a different eTLD+1 that is a member of a
known-CDN-provider allowlist.*

**It is wrong on `www.github.com`.** The real chain is
`www.github.com → github.com` — one CNAME hop, but it stays **inside**
GitHub's own `github.com` zone, so `final_etld1 == orig_etld1` and the rule
short-circuits to "not third party" before ever consulting the CDN
allowlist. In reality, `github.com` sits behind Fastly's anycast edge
network (a well-documented third-party CDN relationship) — the CDN is
invisible to a CNAME-chain rule precisely *because* GitHub's own DNS never
needs to point outside its own domain to reach it; the anycast routing does
the steering at the IP layer, not the DNS layer. This is a **false
negative**, and it is exactly the "some sites sit behind a CDN with no
`CNAME` at all (anycast)" case the assignment warns about — here it's not
"no CNAME at all" but a CNAME that never leaves home, which is the same
blind spot in a slightly sharper form.

*Secondary note:* `www.wikipedia.org → dyna.wikimedia.org` looks, on a naive
"do the last two labels match?" rule, like it **should** be flagged
third-party (`wikipedia.org` ≠ `wikimedia.org`). My rule gets this one right
only because `wikimedia.org` is absent from the CDN allowlist — the two
domains are the *same operator* (the Wikimedia Foundation runs its own
infrastructure, à la Netflix), not a third party. A cruder last-two-labels
rule would have failed here in the opposite direction (false positive); this
is the site the assignment's own warning ("a rule that just compares the
last two labels will be wrong on at least one site") is pointing at.

### Part A · Packet Analysis

Capture: `out/dns.pcapng` — 132 packets, taken with a `port 53` filter while
running `python3 task1_resolve.py www.korea.ac.kr` followed by
`python3 task1_resolve.py --verify`, inside the lab container (`tshark -i
eth0`). Frame numbers below are from that exact file (verifiable with
`tshark -r out/dns.pcapng`).

**Transaction ID match (A2)** — Frame **1** (query, `172.17.0.2 → 198.41.0.4`,
`dns.id = 0x5b8b`) and Frame **2** (response, `198.41.0.4 → 172.17.0.2`,
`dns.id = 0x5b8b`) — identical transaction ID on the wire, 75 bytes out /
383 bytes back.

**Delegation packet (A3)** — Frame **2**: a root server's (`198.41.0.4`)
response to `www.korea.ac.kr`. `dns.count.answers = 0`, `dns.count.auth_rr =
6` (six `NS` records for the `kr.` zone), `dns.count.add_rr = 10` (glue `A`
records). 383 bytes.

**Answer packet (A3)** — Frame **6**: `163.152.1.1` (Korea University's own
authoritative server) responding to the same name. `dns.count.answers = 1`
(one `A` record, `163.152.6.10`), authority/additional both 0. 91 bytes.
Same query name, same wire format as Frame 2 — only the populated section
differs, exactly as the task predicts.

**Largest response (A4)** — Frame **118**, **550 bytes**. It is a root
server's (`198.41.0.4`) delegation response for
`www.microsoft.com-c-3.edgekey.net`, referring the query down to the `.net`
gTLD: `dns.count.answers = 0`, `dns.count.auth_rr = 13` (all 13 `.net` TLD
`NS` records), `dns.count.add_rr = 11` (glue `A` records for most of them).
**Why it is large:** the packet isn't carrying more data per record — it is
carrying *far more records*: 24 resource records in one UDP datagram (13 NS
+ 11 glue A), versus a typical answer packet that carries exactly one. `.net`
happens to have an unusually large NS set (13, the maximum a root zone
lists for any TLD), so this delegation is close to the largest a *root*
response gets in this whole capture, even though it still fits in one UDP
datagram under EDNS0 (advertised buffer 4096B, no truncation flag set).

---

## Task 3 · Beat the Baseline Cache

Real run, `python3 bench.py --yours` inside the container (`out/bench.txt`):

```
  1000 queries over 60 simulated minutes, 20 ms per upstream round trip

  baseline   upstream   325   hit rate  67.5%   stale  266   sim time    6.5s
  yours      upstream   275   hit rate  72.5%   stale    0   sim time    5.5s

  0 stale, upstream +15% vs baseline  ->  good
```

`YourCache` fixes both `BaselineCache` bugs at once by keying on `name` in a
dict and storing an absolute `expiry_time = fetch_time + ttl` instead of a
flat 60-second `FIXED_LIFETIME`:

- **Correctness bug (the one worse than being slow):** `BaselineCache` kept
  everything for a fixed 60 s regardless of the record's real TTL. Anything
  with `TTL < 60` (e.g. `www.microsoft.com`, TTL 20s; `www.cnn.com`, TTL 30s;
  `www.netflix.com`, TTL 60s) got served **after** it had actually expired —
  266 of 1000 answers were stale. `YourCache` checks `now < expiry` using the
  record's own TTL, so it can never do this: **0 stale, confirmed**.
- **Performance bug:** `BaselineCache` also did a linear list scan per
  lookup and evicted long-lived records (TTL > 60s, e.g. the root server's
  86400s TTL) far too early, forcing needless re-fetches. `YourCache`'s dict
  lookup is O(1) and its expiry matches the real TTL, so long-lived records
  are kept exactly as long as they are valid — this alone accounts for most
  of the 325 → 275 drop in upstream calls.

### The Floor

**Claim: 275 upstream queries is the floor for this exact workload — the
smallest number of upstream queries *any* correct cache (zero stale) can
make — and `YourCache` already attains it.**

*Proof sketch.* Fix one name with TTL `T`. Every query for that name must be
served either (a) from a cache entry fetched at some time `s ≤ t` whose
window `[s, s+T)` still covers the query time `t`, or (b) by fetching again
right now. A correct cache is never allowed to serve past `s+T` (that would
be stale by definition), so:

1. **The first query for a name is a compulsory miss.** There are 10 distinct
   names in `FIXTURE`, so at least 10 fetches are unavoidable no matter what
   the cache does.
2. **After that, a fetch is forced exactly when a query for that name arrives
   at a time `t` past the current window's end** — no cache design can avoid
   this, because the window's length `T` is fixed by the authoritative
   record, not by the cache.
3. **Fetching later is strictly at least as good as fetching earlier.** For
   any forced fetch, choosing `s = t` (fetch at the exact moment forced,
   never speculatively earlier) maximizes the window's reach `s + T` into
   the future, which can only reduce or match the number of *subsequent*
   forced fetches — never increase it. So the greedy "fetch only when the
   current entry doesn't cover `now`, and fetch exactly at `now`" policy is
   optimal for every name, independently (upstream calls for different names
   don't interact).

`YourCache.lookup()` is exactly this policy: it serves whenever
`now < expiry`, and otherwise fetches immediately and sets
`expiry = now + ttl`. It never fetches early and never serves stale, so by
the argument above **no correct cache can beat what it does — its measured
275 upstream calls is not just "good", it is the floor**, for this
1000-query, seed-246, one-hour workload.

---

# 한국어 번역판

## Task 1 · 나만의 반복 리졸버 구축

**반복 리졸버 동작 방식.** `Resolver.resolve()`는 하드코딩된 루트 서버
(`ROOT_SERVERS`)에서 시작해 **재귀를 요청하지 않는(RD=0, `+norecurse`에
해당)** UDP 질의를 한 번 보냅니다. 응답을 받으면 순서대로 세 가지를 확인합니다:
(1) Answer 섹션에 `A` 레코드가 있으면 → 완료, (2) Answer 섹션에 `CNAME`이
있으면 → 새 이름으로 전체 탐색을 재시작, (3) 그 외에는 Authority 섹션의 `NS`
레코드를 확인 → 이것이 **위임(delegation)**이며, 다음 단계 서버로 탐색을
이어갑니다. 이 과정을 root → TLD → authoritative 순으로 반복하며, 답이 나오거나
깊이 상한(`MAX_DEPTH = 20`)에 도달할 때까지 계속합니다.

**Glue 없이 위임이 오는 경우 처리 (R3).** 위임 응답의 `NS` 레코드는 다음에
물어볼 서버의 "이름"만 알려주며, `additional` 섹션에 그 서버의 `A` 레코드
("glue")가 함께 올 때도 있고 없을 때도 있습니다. glue가 없으면 곧바로 IP로
넘어갈 수 없으므로, 코드는 **그 네임서버 이름 자체를 다시 `self.resolve()`로
재귀 호출**해야 합니다 — IP 주소 하나를 얻으려고 root→TLD→authoritative 전체
탐색을 독립적으로 한 번 더 도는 셈입니다.

이것은 가설이 아니라 실제 캡처에서 그대로 확인됩니다. `www.stanford.edu`를
해석했을 때 `--verify` 결과(`out/task1_verify.txt`)에는 `hops=6`으로
찍혔지만, 이 `hops`는 *주(main) 경로*의 서버 수만 세는 값입니다 — glue가 없어
재귀적으로 조회한 하위 경로는 반환값이 버려지도록 짜여 있어(`ns_addr, _ =
self.resolve(ns_key, ...)`) 카운터에 잡히지 않습니다. 실제 캡처
(`out/dns.pcapng`)를 보면 `www.stanford.edu`를 해석하는 데 **실제로는 28번의
독립적인 질의/응답 왕복**(프레임 37~92)이 쓰였습니다. 스탠퍼드의 존이
`dnsmadeeasy.com`과 `nsone.net` 산하 네임서버로 위임되는데 **glue가 전혀
없어서**, `ns5/ns6/ns7.dnsmadeeasy.com`, `dns1~4.p02.nsone.net` 하나하나를
처음부터 다시 풀어야 했기 때문입니다. 일반적인 내 노트북은 스텁 리졸버에게
**질문 한 번**만 던지고 이 모든 비용을 재귀 리졸버가 대신 흡수한다는 점과
대조됩니다.

**루트 서버가 곧바로 주소를 주지 않는 이유.** 루트 서버는 `www.korea.ac.kr`에
대해 *아무것도* 모릅니다 — `.kr`을 담당하는 서버가 누구인지만 알 뿐입니다.
주소 대신 위임을 돌려주는 방식 덕분에 root와 TLD 서버는 그 아래 수백만
개의 존에 대해 상태를 갖지 않아도 됩니다 — 루트 존 파일은 TLD당 한 줄(`NS`
레코드)이면 되지, 지구상 모든 호스트네임마다 한 줄이 필요한 게 아닙니다.
위임 구조 덕분에 네임스페이스가 확장 가능해지며, 각 존의 소유자는 root를
전혀 건드리지 않고도 자신의 레코드를 바꿀 수 있습니다.

**검증 결과 (컨테이너 내부에서 실제 실행한
`python3 task1_resolve.py --verify`):**

```
  ok    www.korea.ac.kr        you=163.152.6.10     dig=163.152.6.10   hops=3
  ok    dns.google             you=8.8.4.4          dig=8.8.8.8,8.8.4.4   hops=3
  ok    en.wikipedia.org       you=103.102.166.224  dig=103.102.166.224,103.102.166.224   hops=6
  ok    www.stanford.edu       you=3.33.186.135     dig=15.197.167.90,3.33.186.135,15.197.167.90,3.33.186.135   hops=6
  ok    www.microsoft.com      you=23.49.206.40     dig=23.49.206.40,23.49.206.40,23.49.206.40,23.49.206.40,23.49.206.40   hops=10

  5/5 ok
```

5/5 모두 `dig`와 일치했습니다. `www.microsoft.com`과 `www.stanford.edu`는
목록 중 CDN 호스팅 이름인데, 이번 실행에서는 일치했지만 Akamai/Netlify
anycast 특성상 재실행 시 다른 엣지 IP를 돌려줄 수 있습니다 — 이는 버그가
아니라 CDN에서 예상되는 정상 동작입니다.

---

## Task 2 · DNS는 정말로 사용자를 유도(steering)하는가?

> **실제 한계 사항 (투명하게 공개)** — 이 측정은 **단일 물리 네트워크**
> (평가용 호스트의 업링크, Docker Desktop NAT 경유)에서 수집했습니다. 원래
> 계획했던 진짜 두 네트워크 비교(예: 교내 Wi-Fi vs 폰 테더링)는 이 자동화된
> 환경에서는 얻을 수 없었습니다 — 컨테이너를 실행할 업링크가 하나뿐이었기
> 때문입니다. `task2.md`가 B3에 대해 스스로 제시한 경로 (B) 대안("네트워크가
> 하나뿐이면, 거리 차이가 큰 두 리졸버를 비교하고 그것이 결론을 어떻게
> 약화시키는지 밝혀라")에 따라, 아래 비교는 **같은 네트워크에서 도달한 세
> 리졸버** 간 비교입니다: 컨테이너의 시스템(기본) 리졸버, **Google Public DNS
> (8.8.8.8)**, **Quad9 (9.9.9.9)**. 이는 주장 (b)를 약화시킵니다 — 여기서
> 보이는 차이는 *그 리졸버의 인프라가 어느 anycast 관문에 닿는지*를
> 보여줄 뿐, *사람이 네트워크를 옮겼을 때* 무엇이 달라지는지를 보여주는 것은
> 아닙니다. 만약 실제 두 번째 네트워크를 쓸 수 있게 되면, 그곳에서
> `python3 task2_steering.py --collect`를 다시 돌려 두 `chains.json`을
> 서로 비교하는 것이 주장 (b)를 직접 검증하는 방법입니다.

### 사이트 표 (12개 전수, 실제 `out/chains.json`)

| 사이트 | 체인 길이 | 최종 존 | 서드파티? | 규칙 판정 |
|---|---|---|---|---|
| www.microsoft.com | 2 | akamaiedge.net | yes | 정답 — Akamai(서드파티 CDN) |
| www.netflix.com | 1 | netflix.com | no | 정답 — 자체 CDN(Open Connect), 외주 아님 |
| www.adobe.com | 2 | akamai.net | yes | 정답 — Akamai(서드파티 CDN) |
| www.cnn.com | 1 | fastly.net | yes | 정답 — Fastly(서드파티 CDN) |
| www.apple.com | 3 | akamaiedge.net | yes | 정답 — Akamai(서드파티 CDN) |
| www.korea.ac.kr | 0 | korea.ac.kr | no | 정답 — CNAME 없음, CDN도 없음 |
| www.stanford.edu | 1 | netlifyglobalcdn.com | yes | 정답 — Netlify(서드파티 CDN) |
| www.bbc.co.uk | 2 | fastly.net | yes | 정답 — Fastly(서드파티 CDN) |
| www.spotify.com | 1 | fastly.net | yes | 정답 — Fastly(서드파티 CDN) |
| www.github.com | 1 | github.com | no | **오답 — 아래 참고** |
| www.wikipedia.org | 1 | wikimedia.org | no | 정답이지만 아래 참고 |
| www.nytimes.com | 3 | fastly.net | yes | 정답 — Fastly(서드파티 CDN) |

### Steering Number (유도 지표)

비교한 리졸버(단일 네트워크, 위 한계 사항 참고): **시스템 리졸버, Google
Public DNS(8.8.8.8), Quad9(9.9.9.9)**.

12개 사이트 중 규칙이 서드파티 CDN으로 분류한 사이트는 8개였습니다. 이
8개의 리졸버별 주소 집합을 비교하면:

**서드파티 CDN 사이트 8개 중 7개가 세 리졸버 중 최소 하나에게 다른 주소
집합으로 응답했습니다.** (이번 실행에서 `www.stanford.edu`의 Netlify만
세 리졸버 모두에게 동일한 두 개의 IP를 돌려주었습니다.) 이는 주장 (a) —
이 사이트들 대다수가 CDN을 통해 서비스된다 — 와 부합하며, 주장 (b)를
*시사*는 하지만 위에서 밝힌 단서가 붙습니다: 세 리졸버 모두 같은 물리
네트워크에서 질의했기 때문에, 여기서 보이는 차이는 대부분 **각 리졸버
운영사의 네트워크가 어느 anycast 권역에 닿는지**(Google, Quad9, 기본
리졸버가 Akamai/Fastly/Azure로 들어가는 경로가 서로 다름)를 반영할 뿐,
"이 노트북 자체가 다른 곳으로 유도된다"는 것을 보여주지는 않습니다 — 그
후자를 보이려면 위에서 언급한 두 번째 네트워크 측정이 필요합니다.

### 규칙이 틀린 사례

제 규칙(`task2_steering.py`의 `is_third_party_cdn`)은: *CNAME 체인이 알려진
CDN 사업자 목록에 속한, 원래 사이트와 다른 eTLD+1로 넘어가면 서드파티다*
입니다.

**`www.github.com`에서 틀립니다.** 실제 체인은
`www.github.com → github.com`으로 CNAME이 한 번 있지만, GitHub 자신의
`github.com` 존 **안에 머뭅니다**. 그래서 `final_etld1 == orig_etld1`이
되어 CDN 목록을 확인하기도 전에 규칙이 "서드파티 아님"으로 조기 판정합니다.
실제로는 `github.com`이 Fastly의 anycast 엣지 네트워크 뒤에 있는 것으로
잘 알려져 있습니다(문서화된 서드파티 CDN 관계) — 이 CDN은 CNAME 체인 규칙에
보이지 않는데, 그 이유는 바로 GitHub의 DNS가 자기 도메인 밖을 가리킬 필요가
전혀 없이도 CDN에 도달하기 때문입니다. anycast 라우팅이 DNS 계층이 아니라
IP 계층에서 유도를 수행하는 것입니다. 이는 **위양성이 아니라 위음성**이며,
과제가 경고한 "CNAME이 전혀 없는 anycast CDN" 사례의 변형입니다 — 여기서는
"CNAME이 전혀 없는" 것이 아니라 "집 밖으로 나가지 않는 CNAME"이라는, 같은
사각지대의 좀 더 미묘한 형태입니다.

*추가로:* `www.wikipedia.org → dyna.wikimedia.org`는 "마지막 두 라벨만
비교하는" 단순한 규칙으로 보면 서드파티로 잘못 판정되기 **쉬운**
사례입니다(`wikipedia.org` ≠ `wikimedia.org`). 제 규칙이 이걸 맞히는
이유는 오직 `wikimedia.org`가 CDN 목록에 없기 때문입니다 — 이 두 도메인은
사실 *같은 운영 주체*(Wikimedia 재단이 Netflix처럼 자체 인프라를 운영)이지
서드파티가 아닙니다. 더 단순한 "마지막 두 라벨" 규칙이었다면 여기서
반대 방향(위양성)으로 실패했을 것입니다 — 과제가 언급한 "마지막 두 라벨만
비교하는 규칙은 목록의 최소 한 사이트에서 틀린다"는 경고가 가리키는 사이트가
바로 이것입니다.

### Part A · 패킷 분석

캡처 파일: `out/dns.pcapng` — 실습용 컨테이너 안에서 `tshark -i eth0`으로
`port 53` 필터를 걸고, `python3 task1_resolve.py www.korea.ac.kr`에 이어
`python3 task1_resolve.py --verify`를 실행하며 캡처한 132개 패킷. 아래
프레임 번호는 이 파일 그대로이며 `tshark -r out/dns.pcapng`로 검증
가능합니다.

**Transaction ID 일치 (A2)** — 프레임 **1**(질의, `172.17.0.2 → 198.41.0.4`,
`dns.id = 0x5b8b`)과 프레임 **2**(응답, `198.41.0.4 → 172.17.0.2`,
`dns.id = 0x5b8b`) — 트랜잭션 ID가 그대로 일치합니다. 나갈 때 75바이트,
돌아올 때 383바이트.

**위임(Delegation) 패킷 (A3)** — 프레임 **2**: 루트 서버(`198.41.0.4`)가
`www.korea.ac.kr`에 대해 응답. `dns.count.answers = 0`,
`dns.count.auth_rr = 6`(`kr.` 존에 대한 NS 레코드 6개),
`dns.count.add_rr = 10`(glue A 레코드). 383바이트.

**응답(Answer) 패킷 (A3)** — 프레임 **6**: `163.152.1.1`(고려대학교 자체
authoritative 서버)이 같은 이름에 응답. `dns.count.answers = 1`(A 레코드
1개, `163.152.6.10`), authority/additional 모두 0. 91바이트. 같은 질의
이름, 프레임 2와 완전히 같은 와이어 포맷 — 채워진 섹션만 다릅니다. 과제가
예고한 그대로입니다.

**가장 큰 응답 (A4)** — 프레임 **118**, **550바이트**. 루트 서버
(`198.41.0.4`)가 `www.microsoft.com-c-3.edgekey.net`에 대해 `.net` gTLD로
위임하는 응답입니다: `dns.count.answers = 0`, `dns.count.auth_rr = 13`
(`.net`의 NS 레코드 13개 전부), `dns.count.add_rr = 11`(그중 대부분의 glue
A 레코드). **커진 이유:** 레코드 하나당 데이터가 많아서가 아니라, 레코드
**개수 자체**가 훨씬 많기 때문입니다 — 보통의 답변 패킷이 레코드 1개를
담는 것과 달리, 이 패킷은 UDP 데이터그램 하나에 24개(NS 13 + glue A 11)를
담고 있습니다. `.net`은 루트가 어느 TLD에 대해서든 나열하는 NS 개수 중
최대치인 13개를 갖고 있어서, 이번 캡처 전체에서 루트 응답 중 가장 큰
축에 속하면서도 EDNS0(광고된 버퍼 4096바이트, truncation 플래그 없음)
덕분에 UDP 패킷 하나에 여전히 들어갑니다.

---

## Task 3 · 베이스라인 캐시 이기기

실제 실행 결과, 컨테이너 안에서 `python3 bench.py --yours` (`out/bench.txt`):

```
  1000 queries over 60 simulated minutes, 20 ms per upstream round trip

  baseline   upstream   325   hit rate  67.5%   stale  266   sim time    6.5s
  yours      upstream   275   hit rate  72.5%   stale    0   sim time    5.5s

  0 stale, upstream +15% vs baseline  ->  good
```

`YourCache`는 이름(`name`)을 키로 하는 딕셔너리에, 고정된 60초
(`FIXED_LIFETIME`) 대신 절대 만료 시각 `expiry_time = fetch_time + ttl`을
저장함으로써 `BaselineCache`의 두 버그를 한 번에 고칩니다.

- **정확성 버그 (느린 것보다 더 나쁜 문제):** `BaselineCache`는 실제 TTL과
  무관하게 무조건 60초간 보관했습니다. `TTL < 60`인 레코드(예:
  `www.microsoft.com` TTL 20초, `www.cnn.com` TTL 30초,
  `www.netflix.com` TTL 60초)는 실제로 만료된 **이후에도** 그대로
  서빙되어, 1000개 중 266개 응답이 만료된 값이었습니다. `YourCache`는
  레코드 고유의 TTL을 이용해 `now < expiry`를 확인하므로 이런 일이 절대
  일어날 수 없습니다: **stale 0건, 확인됨**.
- **성능 버그:** `BaselineCache`는 조회마다 리스트를 선형 탐색했고, TTL이
  긴 레코드(예: 루트 서버의 86400초 TTL)를 너무 일찍 폐기해 불필요한
  재조회를 유발했습니다. `YourCache`의 딕셔너리 조회는 O(1)이고 만료
  시각이 실제 TTL과 일치하므로, 오래 유효한 레코드는 유효한 만큼만
  보관됩니다 — upstream 호출이 325 → 275로 줄어든 주된 이유입니다.

### The Floor (이론상 최소 Upstream 요청 수)

**주장: 이 워크로드에서 이론상 최소 upstream 요청 수는 275건이며 —
정답(stale 0)을 유지하는 그 어떤 캐시도 이보다 적게 갈 수 없고 —
`YourCache`는 이미 이 하한에 도달했습니다.**

*증명 개요.* TTL이 `T`인 이름 하나를 고정합시다. 그 이름에 대한 모든
질의는 (a) 어떤 시각 `s ≤ t`에 가져온 캐시 항목의 유효 구간 `[s, s+T)`가
질의 시각 `t`를 여전히 덮고 있어서 캐시로 응답하거나, (b) 지금 다시
가져와야 합니다. 정답인 캐시는 `s+T`를 넘겨서 응답할 수 없으므로(그러면
정의상 stale입니다):

1. **이름마다 첫 질의는 필연적인 미스입니다.** `FIXTURE`에는 서로 다른
   이름이 10개 있으므로, 캐시가 무엇을 하든 최소 10번의 조회는 피할 수
   없습니다.
2. **그 이후로는, 어떤 이름에 대한 질의가 현재 구간이 끝난 뒤의 시각
   `t`에 도착하는 순간 조회가 강제됩니다** — 구간 길이 `T`는 캐시가
   아니라 authoritative 레코드가 정하므로, 어떤 캐시 설계로도 이를 피할
   수 없습니다.
3. **더 늦게 가져오는 것이 더 일찍 가져오는 것보다 항상 같거나 낫습니다.**
   강제된 조회가 있을 때, `s = t`(선제적으로 더 일찍이 아니라, 강제된
   바로 그 순간에 조회)를 선택하면 구간이 미래로 뻗는 범위 `s + T`가
   최대화되어, 이후 강제되는 조회 횟수를 줄이거나 최소한 같게 만들 뿐
   늘리는 일은 없습니다. 따라서 "현재 항목이 `now`를 덮지 못할 때만,
   그리고 정확히 `now`에 조회한다"는 탐욕적 정책이 이름별로 독립적으로
   최적입니다(서로 다른 이름의 upstream 호출은 서로 영향을 주지 않습니다).

`YourCache.lookup()`은 정확히 이 정책입니다: `now < expiry`이면 캐시로
응답하고, 아니면 즉시 조회해 `expiry = now + ttl`로 갱신합니다. 절대
선제적으로 조회하지 않고 절대 stale을 서빙하지 않으므로, 위 논증에 따라
**어떤 정답 캐시도 이보다 나을 수 없습니다 — 실측된 275번의 upstream
호출은 단순히 "좋은" 수준이 아니라, 이 1000개 질의·시드 246·1시간
워크로드에 대한 이론상 하한(the floor) 그 자체입니다.**
