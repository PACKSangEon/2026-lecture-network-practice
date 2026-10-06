# Week 6 Observations

## Task 1 · Link State: Dijkstra & Forwarding Table

- **Tie-breaking rule**: 동일 비용 경로가 여러 개일 때 `sorted(graph[node].items())`로 인접 노드를 알파벳 순서로 heap에 넣어 lexicographically 작은 first_hop이 항상 먼저 확정된다. `dijkstra` 와 `forwarding_table` 의 tie-breaking이 일치해야 `task3_reconverge.py`의 `dijkstra_table` 과 결과가 동일해진다.
- **First-hop vs. full path**: 포워딩 테이블은 전체 경로가 아닌 **first_hop** 만 저장한다. heap entry에 `first_hop` 필드를 추가해 출발 노드에서의 첫 번째 인접만 전파하면, 패킷 헤더에 전체 경로를 실을 필요 없이 각 라우터가 독립적으로 판단할 수 있다.
- **Link-down reroute**: `u-x` 링크 차단 후 `u→w` 경로가 `v`를 경유하도록 변경됨을 확인했다(EXPECTED_TABLE_U → after table 비교). 같은 알고리즘이 모든 6개 노드에서 동작하며 도달 불가 목적지가 없음을 검증했다.

## Task 2 · OSPF Reconvergence Timing

- **traceroute (A, 캠퍼스 Wi-Fi 실측)**: 국내 경로는 3홉 `163.152.233.129`(고려대 NAT/경계)를 지나 `163.152.x` 내부망으로 들어가고, A5의 `*`는 두 종류다 — 중간 5홉의 `*`는 앞뒤 홉이 응답하므로 그 라우터만 TTL 초과 응답을 막거나 rate-limit한 것이고, 8홉 이후 끝까지 이어지는 `*`는 목적지 쪽 방화벽이 탐침 자체를 막은 것으로 보인다. `www.stanford.edu`는 AWS Global Accelerator(3.33.186.135, anycast)라 국내 망(`175.121.x`→`10.222.x`)에서 응답이 끊겨 해저 케이블 구간(A3)은 이 대상으로 관측되지 않았다. `1.1.1.1`은 12홉·~10 ms에 Cloudflare(`141.101.82.17`)에 도달 → 국내 복제본이다.
- **B4 링크 다운 vs. hello 유실 (실측)**: 각 라우터는 직접 연결되지 않은 세 번째 망을 OSPF로 배웠다(B2, cost 20 ECMP). `ip link set eth1 down`은 FRR이 즉시 감지해 새 Router LSA를 플러딩하므로 세 라우터 모두 **0.03~0.06초**에 재수렴했다(`scenario.sh cut`의 "2초"는 1초 폴링 해상도 탓). 반면 링크는 살린 채 iptables로 OSPF hello만 막으면 **36.8초** — Hello 10s/Dead 40s 설정에서 예상 범위(30~40s)와 일치한다.
- **B5 복구 비대칭 · C3 비용 변경**: 복구는 r3가 0.06초에 ECMP를 되찾았지만 r1·r2는 **1.7~13.3초**(실행마다 다름)가 걸렸다 — 사라짐은 로컬 이벤트 하나로 끝나지만, 새 이웃은 hello 교환→2-Way→DB 교환→Full을 거쳐야 쓰이기 때문이다. 비용 10→100 변경은 인접 관계가 그대로라 LSA 플러딩+SPF만으로 **0.13초**에 경로가 바뀌었다.

## Task 3 · Incremental SPF

- **SPT predecessor 활용**: `_pred[v]` 가 SPT에서 v의 직전 노드를 기록하므로, 링크 (a,b)가 내려가거나 비용이 증가할 때 그 링크가 실제 SPT 간선인지(`_pred[b]==a or _pred[a]==b`) 즉시 판단해 관계없는 이벤트를 건너뛴다. SPT 간선이 아닌 비용 증가는 포워딩 테이블에 영향을 주지 않는다.
- **비용 감소·신규 링크의 `<=` 임계값**: 새 링크나 비용 감소 시 `da+new_cost <= db` 조건으로 SPF 재계산 여부를 결정한다. strict `<` 를 쓰면 등비용 경로가 heap tuple 순서(`(cost, node, first_hop)`)에 의해 first_hop을 바꾸는 케이스를 놓쳐 26개 이벤트에서 테이블이 틀렸다. `<=` 로 완화해야 등비용 도착 경우도 안전하게 처리된다.
- **결과**: 400개 라우터, 1000 이벤트 기준으로 full SPF 363회(baseline 1001회)로 **64%** 감소, 0개 오류. `bench.py` 판정 **good**.
