# Week 3 · Observations

---

## English Version

### Task 1

- The root server did not hand back the address because it has no idea what
  `www.korea.ac.kr` is — it only tracks which servers are authoritative for
  `.kr`. Returning a delegation (an `NS` referral) instead of an address
  keeps root and TLD zone files at "one line per zone" size, not "one line
  per hostname on the internet." Delegation is the mechanism that lets the
  namespace scale to billions of names without the root ever changing.
- When a delegation arrived without glue, I had to call `resolve()`
  recursively on the nameserver's own name — a full independent
  root→TLD→authoritative walk just to turn one `NS` name into one IP. The
  real cost showed up in the packet capture, not in the reported hop count:
  resolving `www.stanford.edu` reported `hops=6`, but the actual capture
  (`out/dns.pcapng`, frames 37–92) shows **28 separate query/response round
  trips**, because Stanford delegates to `dnsmadeeasy.com` and `nsone.net`
  nameservers with no glue at all, and each one had to be resolved from
  scratch. The `hops` counter undercounts this because the recursive
  sub-resolution's path is discarded (`ns_addr, _ = self.resolve(...)`).
- For a normal name (`www.korea.ac.kr`) I ended up asking **3** servers
  (root, `.kr`, `korea.ac.kr`'s own authoritative). For a name with
  glue-less NS delegations (`www.stanford.edu`) the real wire cost was
  **28** round trips. My laptop's stub resolver normally asks its recursive
  resolver **1** question and never sees any of this — the recursive
  resolver absorbs (and caches) all of it.

### Task 2

- The one-sentence difference, from the capture rather than the slide: a
  **delegation** response has `dns.count.answers = 0` and the servers to ask
  next sitting in the *authority* section as `NS` records (frame 2, root →
  `kr.`); an **answer** response has the actual `A` record sitting in the
  *answer* section instead (frame 6, `163.152.1.1` → `163.152.6.10`) — same
  DNS message format end to end, only which section got filled in differs.
- My third-party rule (CNAME chain crosses into a known-CDN eTLD+1) is wrong
  on `www.github.com`: the real chain (`www.github.com → github.com`) never
  leaves GitHub's own zone, so the rule reports "not third party" even
  though `github.com` is documented to sit behind Fastly's anycast edge.
  The CDN relationship is invisible to a CNAME-chain rule specifically
  because the steering happens at the IP/anycast layer, not in DNS.
- The steering number: **7 of 8** third-party CDN sites answered with a
  different address set to at least one of the three resolvers compared
  (system, 8.8.8.8, 9.9.9.9). This supports claim (a) strongly (8/12 sites
  are CDN-fronted) and is *suggestive* of claim (b), but not a clean proof
  of it — all three resolvers were queried from one physical network in
  this run, so the differences most likely show which anycast catchment
  each resolver operator's own infrastructure reaches, not what changes
  when the human moves networks. A genuine two-network run (not available
  in this automated environment — see `report.md`'s methodology note) is
  the real test of claim (b).

### Task 3

- Two separate things were wrong with `BaselineCache`, and they share a root
  cause (ignoring the record's real TTL in favor of one hard-coded
  `FIXED_LIFETIME = 60`): **(1) correctness** — records with `TTL < 60`
  (e.g. `www.microsoft.com`, TTL 20s) kept being served after they had
  actually expired, which is how 266/1000 answers ended up stale; **(2)
  performance** — records with `TTL > 60` (e.g. `www.korea.ac.kr`, TTL 3600s,
  or the root-servers entry at 86400s) were evicted long before they needed
  to be, forcing wasted re-fetches. The record the baseline handles worst is
  `www.microsoft.com` (TTL 20s, and the heaviest-weighted name under the
  Zipf query distribution): it churns fastest relative to the fixed 60s
  window, so it racks up the most stale hits of any single name.
- The floor: **275 upstream queries**, for this exact 1000-query / seed-246
  / one-hour workload, and `YourCache` already reaches it. Reasoning: (a)
  each of the 10 distinct fixture names forces at least one compulsory
  first fetch — 10 unavoidable calls; (b) beyond that, a correct cache is
  forced to re-fetch a name exactly when a query for it arrives after the
  previous fetch's `[fetch_time, fetch_time+ttl)` window has closed — this
  is dictated purely by the query timestamps and the record's own TTL, not
  by cache cleverness; (c) among all valid choices of when to perform a
  forced fetch, fetching at the exact moment it becomes necessary (never
  earlier) maximizes how far the resulting window reaches into the future,
  so it can only reduce or match — never increase — the number of later
  forced fetches. That "wait as long as possible, then fetch" policy is
  exactly what `YourCache.lookup()` does, so its measured 275 is provably
  optimal, not just empirically good — you cannot go lower without handing
  out a stale answer.

---

## 한국어 번역판

### Task 1

- 루트 서버가 주소를 곧바로 주지 않은 이유는 `www.korea.ac.kr`이 무엇인지
  전혀 모르기 때문입니다 — `.kr`을 누가 담당하는지만 알 뿐입니다. 주소
  대신 위임(NS 안내)을 돌려주는 방식 덕분에 root와 TLD 존 파일은 "존
  하나당 한 줄" 크기를 유지하지, "인터넷의 모든 호스트네임마다 한 줄"이
  되지 않습니다. 위임은 root를 전혀 바꾸지 않고도 네임스페이스가 수십억
  개의 이름으로 확장되게 해주는 메커니즘입니다.
- glue 없이 위임이 왔을 때는 네임서버 이름 자체에 대해 `resolve()`를
  재귀 호출해야 했습니다 — `NS` 이름 하나를 IP 하나로 바꾸려고 완전히
  독립적인 root→TLD→authoritative 탐색을 한 번 더 도는 것입니다. 실제
  비용은 보고된 hop 수가 아니라 패킷 캡처에서 드러났습니다:
  `www.stanford.edu` 해석은 `hops=6`으로 찍혔지만, 실제 캡처
  (`out/dns.pcapng`, 프레임 37~92)를 보면 **28번의 독립적인 질의/응답
  왕복**이 있었습니다. 스탠퍼드가 `dnsmadeeasy.com`과 `nsone.net`
  네임서버로 위임하는데 glue가 전혀 없어서, 각각을 처음부터 다시
  풀어야 했기 때문입니다. `hops` 카운터가 이를 과소 집계하는 이유는
  재귀적 하위 조회의 경로가 버려지기 때문입니다
  (`ns_addr, _ = self.resolve(...)`).
- 평범한 이름(`www.korea.ac.kr`)에서는 서버 **3**곳(root, `.kr`,
  `korea.ac.kr`의 authoritative)에 물었습니다. glue 없는 NS 위임이 있는
  이름(`www.stanford.edu`)에서는 실제 통신 비용이 **28**번의 왕복이었습니다.
  평소 제 노트북의 스텁 리졸버는 재귀 리졸버에게 **질문 1번**만 던지고 이
  모든 과정을 전혀 보지 않습니다 — 재귀 리졸버가 이 비용을 전부 흡수하고
  캐싱합니다.

### Task 2

- 슬라이드가 아니라 캡처에서 확인한 한 문장 차이: **위임(delegation)**
  응답은 `dns.count.answers = 0`이고 다음에 물어볼 서버가 *authority*
  섹션에 `NS` 레코드로 들어있습니다(프레임 2, root → `kr.`). **응답(answer)**
  은 실제 `A` 레코드가 *answer* 섹션에 들어있습니다(프레임 6,
  `163.152.1.1` → `163.152.6.10`) — 처음부터 끝까지 같은 DNS 메시지
  포맷이며, 어느 섹션이 채워졌는지만 다릅니다.
- 제 서드파티 규칙(CNAME 체인이 알려진 CDN eTLD+1로 넘어가는지)은
  `www.github.com`에서 틀립니다: 실제 체인(`www.github.com → github.com`)이
  GitHub 자신의 존을 벗어나지 않으므로, `github.com`이 Fastly의 anycast
  엣지 뒤에 있다는 것이 알려져 있음에도 규칙은 "서드파티 아님"으로
  판정합니다. 유도가 DNS가 아니라 IP/anycast 계층에서 일어나기 때문에
  CDN 관계가 CNAME 체인 규칙에는 보이지 않는 것입니다.
- Steering number: 비교한 세 리졸버(시스템, 8.8.8.8, 9.9.9.9) 중
  최소 하나에게 다른 주소 집합으로 응답한 서드파티 CDN 사이트가
  **8개 중 7개**였습니다. 이는 주장 (a)를 강하게 뒷받침하지만(12개 중
  8개가 CDN 앞단), 주장 (b)에 대해서는 *시사*는 하되 깔끔한 증명은
  아닙니다 — 이번 실행에서는 세 리졸버 모두 하나의 물리 네트워크에서
  질의했으므로, 여기서 보이는 차이는 사람이 네트워크를 옮길 때 무엇이
  바뀌는지가 아니라 각 리졸버 운영사의 인프라가 어느 anycast 권역에
  닿는지를 보여줄 가능성이 큽니다. 진짜 두 네트워크 측정(이 자동화된
  환경에서는 얻을 수 없었음 — `report.md`의 방법론 안내 참고)이 주장
  (b)의 진짜 검증입니다.

### Task 3

- `BaselineCache`에는 서로 다른 두 가지 문제가 있었고, 둘 다 같은
  근본 원인(레코드의 실제 TTL을 무시하고 고정된
  `FIXED_LIFETIME = 60`을 쓴 것)에서 나옵니다: **(1) 정확성** —
  `TTL < 60`인 레코드(예: `www.microsoft.com`, TTL 20초)가 실제로 만료된
  뒤에도 계속 서빙되어, 1000개 중 266개 응답이 stale이 되었습니다.
  **(2) 성능** — `TTL > 60`인 레코드(예: `www.korea.ac.kr`, TTL 3600초,
  혹은 root-servers 항목의 86400초)는 필요 이상으로 일찍 폐기되어
  불필요한 재조회를 유발했습니다. 베이스라인이 가장 못 다루는 레코드는
  `www.microsoft.com`입니다(TTL 20초이면서 Zipf 질의 분포에서 가장 비중이
  큰 이름) — 고정된 60초 창에 비해 가장 빠르게 회전하므로, 단일 이름
  기준으로 stale 적중이 가장 많이 쌓입니다.
- The Floor: 이 정확한 1000개 질의·시드 246·1시간 워크로드에서 이론상
  최소값은 **275번의 upstream 요청**이며, `YourCache`가 이미 이 값에
  도달했습니다. 근거: (a) fixture의 서로 다른 이름 10개 각각이 최소 한
  번의 필연적인 첫 조회를 강제하므로 — 피할 수 없는 10번의 호출; (b) 그
  이후로는, 어떤 이름에 대한 질의가 이전 조회의 `[fetch_time,
  fetch_time+ttl)` 구간이 끝난 뒤에 도착하는 순간 재조회가 강제됩니다 —
  이는 순전히 질의 시각과 레코드 자체의 TTL이 정하는 것이지, 캐시가
  얼마나 영리한지와는 무관합니다; (c) 강제된 조회를 언제 수행할지의
  모든 유효한 선택지 중, 필요해지는 바로 그 순간에(절대 더 일찍이 아니라)
  조회하면 결과 구간이 미래로 뻗는 범위가 최대화되므로, 이후 강제되는
  조회 횟수를 줄이거나 최소한 같게 만들 뿐 늘리지 않습니다. "최대한
  기다렸다가 조회한다"는 이 정책이 정확히 `YourCache.lookup()`이 하는
  일이므로, 실측된 275라는 값은 경험적으로 좋은 수준이 아니라 증명 가능한
  최적치입니다 — stale 응답을 내주지 않고서는 이보다 더 낮출 수 없습니다.
