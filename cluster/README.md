# cluster — 감시노드 검증용 시뮬레이터 (테스트 하네스)

감시노드(`Monitor_Node`) 개발을 위한 **검증용 슈퍼바이저 흉내 스크립트**. 실제 감시노드 펌웨어가
아니라, 장차 STM32로 만들 감시노드가 하트비트/세이프어보트를 제대로 처리하는지 확인하기 위한
CAN 테스트 하네스다.

> ⚠️ 이 디렉토리는 **실장 노드가 아니다.** DBC상 `Monitor_Node`는 인터페이스만 정의돼 있고,
> 감시노드 펌웨어는 미구현(후속 과제). `supervision.py`는 그 감시노드를 시험하기 위한 도구다.

## `supervision.py` 역할
- **Heartbeat(0x050)** 100ms 주기 송신 — 슈퍼바이저 생존 신호를 흉내 낸다.
- **Heartbeat_Ack(0x060)** 수신 확인 — 감시노드가 응답하는지 검증.
- **SafeAbort(0x010)** 수신 시 경보 출력 — 감시노드가 비상정지를 발동하는지 확인.

## 실차 시나리오 재현 옵션
```bash
python3 supervision.py                      # 정상 하트비트 송신
python3 supervision.py --freeze             # Alive Counter 고정 (Alive Stuck 시나리오)
python3 supervision.py --silent             # 하트비트 미송신 (Timeout 시나리오)
python3 supervision.py --interface can0 --period 0.1
```
사전 준비: `pip3 install python-can` · `sudo ip link set can0 up type can bitrate 500000`

## 참고
- 실제 배포에서는 슈퍼바이저(`supervisor/hmi/can_hub.py`)가 Heartbeat(0x050)를 상시 송신한다.
  본 시뮬레이터는 감시노드 단독 검증 시에만 사용한다(동시에 켜면 하트비트 소스가 겹친다).
