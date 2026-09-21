# Week 4 Observations

## Task 1 · Reliable Delivery (Stop-and-Wait)

Stop-and-wait 프로토콜을 선택했다. 채널이 중복(dup)과 재배열(reorder)을 동시에 일으키기 때문에, 슬라이딩 윈도우를 쓰면 수신 측 버퍼에서 시퀀스 번호 경계가 꼬이기 쉬워 stop-and-wait의 단순한 "한 번에 하나" 모델이 더 안전하다고 판단했다. 2000바이트(250 패킷)를 전달하기 위해 채널은 약 280~330번 전송을 수행했으며(최소 250 대비 약 1.2~1.3배), 그 오버헤드는 10% 손실과 재정렬·중복에 의한 재전송 비용이다. 가장 먼저 문제가 된 것은 손실(loss)이었다 — ACK 손실 시 송신자가 타임아웃 전까지 무한 대기하는 상황이 초기 구현에서 발생했고, 타임아웃을 명시하여 해결했다.

## Task 2 · Measure Your Own Link

측정은 WSL(Windows Subsystem for Linux)에서 동일 물리 네트워크를 "campus-wifi"와 "tethering" 두 라벨로 진행했으며 실제로는 같은 링크여서 두 중앙값이 260 Mbps 전후로 거의 일치한다. 핸드셰이크 시간(7.1 ms vs 7.2 ms)은 같은 Cloudflare 서버까지의 RTT를 반영하며, 이 RTT가 TCP 슬로우 스타트 수렴 속도를 결정해 초기 1~2 RTT 동안 처리량을 제한한다(§3.7의 핸드셰이크-처리량 의존성). campus-wifi 측정의 spread(42%)가 tethering(12%)보다 큰 이유는 campus-wifi 쪽 5회 측정 중 한 번(163 Mbps)에 TCP 혼잡 제어가 ssthresh를 낮게 추정한 결과로 보인다.

측정에 사용한 초기 시퀀스 번호(ISN)는 양 단말이 서로 다른 임의값을 선택하므로 0이 아니다. 이는 이전 연결의 패킷이 뒤늦게 도착해 현재 연결을 오염시키는 "old duplicate segment" 문제를 막기 위한 것이며(§3.5), 수신 윈도우 스케일링 후 광고 윈도우는 수 MB에 달하지만 실제 병목은 서버까지의 RTT 기반 혼잡 윈도우(cwnd)였다.

## Task 3 · Beat the Fixed Window

FixedWindow(W=64)는 goodput이 가장 높지만 최악의 발신자다. 큐를 항상 꽉 채워(avg queue 8.8) 다른 흐름의 지연을 늘리고, 37% 손실로 전체 링크 대역폭의 37%를 재전송 쓰레기로 낭비하기 때문이다. 혼잡 신호를 무시하는 발신자가 많아지면 네트워크는 1986년 10월처럼 붕괴한다.

YourControl의 윈도우는 ssthresh=20(BDP)에서 CA에 진입 후 30(BDP+queue 용량)까지 선형 증가하다 손실 시 floor=19로 복귀하며, 평균적으로 약 23~24에 수렴한다. 이 값은 BDP(20)에 평균 큐 점유(~4)를 더한 것으로 링크를 100% 활용하면서도 꼬리 드롭을 최소화하는 균형점이다. backoff를 완만하게(floor=19) 했을 때 goodput은 98%로 증가했지만 avg queue가 4.9로 상한(5.0)에 근접했다 — 더 완만하게 하면 queue 제한을 넘겨 R4를 위반할 수 있다.
