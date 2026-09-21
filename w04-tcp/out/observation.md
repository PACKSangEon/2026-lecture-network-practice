# Week 4 Observations

## Task 1 · Reliable Delivery (Stop-and-Wait)

- **Protocol choice**: stop-and-wait를 선택했다. 채널이 손실·중복·재배열을 동시에 일으키기 때문에 슬라이딩 윈도우보다 "한 번에 하나" 모델이 시퀀스 번호 경계 오염 없이 구현하기 쉬웠다.
- **Packet overhead**: 2,000 바이트(250 패킷) 전달에 채널은 약 300~325회 전송을 수행했다 — 최솟값 대비 약 1.3배로, 10% 손실과 중복·재배열에 의한 재전송 비용이다.
- **What broke first**: 손실(loss)이 가장 먼저 문제가 됐다. ACK가 유실되면 송신자가 무한 대기해 교착이 발생했고, 명시적 타임아웃(20 스텝)을 추가해 해결했다.

## Task 2 · Measure Your Own Link

- **Initial sequence numbers**: SYN·SYN-ACK의 ISN이 모두 0이 아닌 임의값이다. 이는 이전 연결의 지연 패킷이 현재 연결을 오염시키는 "old duplicate segment" 문제를 방지하기 위한 것이다(§3.5).
- **Scaled window vs actual limit**: 광고 수신 윈도우는 스케일링 후 수 MB에 달하지만 실제 병목은 RTT 기반 혼잡 윈도우(cwnd)였다 — 핸드셰이크 시간(7.1 ms)이 슬로우 스타트 수렴 속도를 결정하므로 RTT가 짧아야 초반 처리량이 높아진다(§3.7 B5 메커니즘).
- **Two-network medians**: campus-wifi 중앙값 260 Mbps / spread 42%, tethering 260 Mbps / spread 12%로 두 링크는 사실상 동일 인터페이스다. spread 차이는 campus-wifi 5회 측정 중 한 번(163 Mbps)에 TCP가 ssthresh를 낮게 추정한 결과이며, 이것이 RTT와 throughput이 독립적이지 않음을 보여 준다.

## Task 3 · Beat the Fixed Window

- **R5 — why FixedWindow is the worst sender**: goodput은 가장 높지만 큐를 항상 꽉 채워(avg queue 8.8) 다른 흐름에 지연을 강요하고, 37% 손실로 링크 용량의 37%를 재전송 쓰레기로 낭비한다. 혼잡 신호를 무시하는 발신자가 많아지면 네트워크는 1986년 10월처럼 붕괴한다.
- **Window convergence**: YourControl의 윈도우는 ssthresh=20(BDP)에서 CA로 진입 후 ~30(BDP+queue 상한)에서 손실이 나면 floor=19로 복귀하며 평균 23~24에 수렴한다. 이 값은 링크를 100% 활용하면서 꼬리 드롭을 최소화하는 BDP+α 균형점이다.
- **Goodput vs queue trade-off**: backoff floor를 10→19로 완만하게 올렸을 때 goodput은 88%→98%로 증가했지만 avg queue가 3.3→4.9로 상한(5.0)에 근접했다. 더 올리면 R4(queue ≤ 5.0)를 위반하므로 19가 허용 범위 내 최댓값이다.
