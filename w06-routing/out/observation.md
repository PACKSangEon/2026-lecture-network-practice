# Week 6 Observations

## Task 1 · Link State: Dijkstra & Forwarding Table

- **Tie-breaking rule**: 동일 비용 경로가 여러 개일 때 `sorted(graph[node].items())`로 인접 노드를 알파벳 순서로 heap에 넣어 lexicographically 작은 first_hop이 항상 먼저 확정된다. `dijkstra` 와 `forwarding_table` 의 tie-breaking이 일치해야 `task3_reconverge.py`의 `dijkstra_table` 과 결과가 동일해진다.
- **First-hop vs. full path**: 포워딩 테이블은 전체 경로가 아닌 **first_hop** 만 저장한다. heap entry에 `first_hop` 필드를 추가해 출발 노드에서의 첫 번째 인접만 전파하면, 패킷 헤더에 전체 경로를 실을 필요 없이 각 라우터가 독립적으로 판단할 수 있다.
- **Link-down reroute**: `u-x` 링크 차단 후 `u→w` 경로가 `v`를 경유하도록 변경됨을 확인했다(EXPECTED_TABLE_U → after table 비교). 같은 알고리즘이 모든 6개 노드에서 동작하며 도달 불가 목적지가 없음을 검증했다.

## Task 2 · OSPF Reconvergence Timing

- **ip link down vs. hello timeout**: `ip link set eth1 down` 으로 인터페이스를 내리면 FRR는 dead interval(40s)을 기다리지 않고 즉시 neighbor DOWN 이벤트를 처리해 Router LSA를 재발신한다. 재수렴은 약 2초 이내로 완료됐다. 반면 링크가 물리적으로 살아 있고 hello 패킷만 사라지면 dead interval 경과 후(기본 40s)에야 neighbor가 탈락해 재수렴까지 40~42초가 걸린다.
- **OSPF hello/dead 기본값**: `frr defaults traditional` 설정에서 hello interval=10s, dead interval=40s다. dead=4×hello 공식은 §5.3의 "neighbor 선언을 몇 번의 hello 유실 후" 규칙에 해당하며, 이 배율을 낮추면 빠르게 감지하지만 패킷 유실에 따른 오탐이 증가한다.
- **비용 변경 vs. 링크 다운**: `scenario.sh cost`처럼 cost를 10→100으로 올리면 링크는 살아 있고 새 LSA 만 플러딩되므로 인접 관계 재수립 없이 SPF 재계산만 발생한다. 이때도 재수렴은 몇 초 이내지만 dead interval 대기가 없어 링크 다운과 구조가 다르다.

## Task 3 · Incremental SPF

- **SPT predecessor 활용**: `_pred[v]` 가 SPT에서 v의 직전 노드를 기록하므로, 링크 (a,b)가 내려가거나 비용이 증가할 때 그 링크가 실제 SPT 간선인지(`_pred[b]==a or _pred[a]==b`) 즉시 판단해 관계없는 이벤트를 건너뛴다. SPT 간선이 아닌 비용 증가는 포워딩 테이블에 영향을 주지 않는다.
- **비용 감소·신규 링크의 `<=` 임계값**: 새 링크나 비용 감소 시 `da+new_cost <= db` 조건으로 SPF 재계산 여부를 결정한다. strict `<` 를 쓰면 등비용 경로가 heap tuple 순서(`(cost, node, first_hop)`)에 의해 first_hop을 바꾸는 케이스를 놓쳐 26개 이벤트에서 테이블이 틀렸다. `<=` 로 완화해야 등비용 도착 경우도 안전하게 처리된다.
- **결과**: 400개 라우터, 1000 이벤트 기준으로 full SPF 363회(baseline 1001회)로 **64%** 감소, 0개 오류. `bench.py` 판정 **good**.
