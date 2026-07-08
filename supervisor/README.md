# supervisor — Central_Supervisor 노드 (RPi5)

가변 실내 PBV의 **중앙 슈퍼바이저**. 터치 HMI·레이싱휠 입력을 받아 **결정적 안전 인터록**을
통과한 요청만 CAN 명령으로 인코딩해 존 ECU 3개로 내보내고, ECU 상태 피드백으로 3D 디지털 트윈을
갱신한다. DBC상 노드명은 `Central_Supervisor`.

> 설계 축: **입력(요청) → 결정적 안전 인터록 → CAN 액추에이션** 단방향. 어떤 입력도 인터록을
> 통과하지 않으면 CAN으로 나가지 못한다.

## 하드웨어 / 런타임
- Raspberry Pi 5 + **MCP2515(SPI) — SocketCAN `can0`**, CAN 500kbps · 11bit 표준 ID
- Python 3.13 / PySide6(Qt6) + QtQuick3D / python-can + **cantools**(DBC 코덱) / pygame(레이싱휠)

## 디렉토리
```
supervisor/
├── dbc/model_car_net.dbc   ★ 정본 DBC (14메시지, Vector CANdb++) — 전 노드 단일 소스
├── hmi/
│   ├── main.py             PySide6 엔트리 — CanHub / VehicleState / WheelInput 결선
│   ├── vehicle_state.py    ★ 단일 상태 객체 — 입력→인터록→CAN, 상태→3D 트윈
│   ├── can_hub.py          can0 송수신 허브(cantools) + Heartbeat/SafeAbort
│   ├── wheel_input.py      레이싱휠 USB-HID(pygame) → Drive_Cmd 50ms 주기 송신
│   ├── qml/                HMI + QtQuick3D 디지털 트윈 (Main/Cabin3D/Seat3D/SteeringWheel …)
│   ├── assets/             3D 모델(GLB)·차체/좌석/모드 이미지
│   └── tools/              dummy_ecu.py(실 ECU 없이 트윈 검증) · 에셋 생성 스크립트
└── handle/                 레이싱휠 실험 스크립트(drive_game / handle / wheel_can_sender)
```

## 핵심 동작
- **결정적 안전 인터록 (`vehicle_state.py`)** — 기어=P(주행 모드)에서만 모드 전이 / 주행(D·R) 중 좌석
  액추에이터 명령 거부 / D↔R은 P 경유 / 뒷좌석 두 슬라이드 **직렬화**(동시구동 금지, `_slide_queue`).
- **CAN 허브 (`can_hub.py`)** — 송신은 Lock 직렬화, 수신은 전용 RX 스레드 → Qt Signal(QueuedConnection).
  `Heartbeat`(0x050) 전용 스레드 100ms 상시 송신, `SafeAbort`(0x010) 수신 시 전체화면 경보 + 해제 프레임 송신.
- **레이싱휠 파이프라인 (`wheel_input.py`)** — **P4X(Generic X-Box pad, axes=6) 모드 필수**.
  조향 axis0 / 페달 axis1(엑셀·브레이크) / 패들 btn4·5(기어). `Drive_Cmd`(0x100) 50ms 무조건 브로드캐스트.
- **3D 디지털 트윈 (QtQuick3D)** — X-ray 캐빈 실시간 렌더. 좌석 리클라인/회전/슬라이드 현재포즈를
  상태 피드백으로 추종, 레이싱휠 조향각을 앞바퀴에 연동. ACTIVE↔AMBIENT UI 전환.

## 실행
```bash
sudo ip link set can0 up type can bitrate 500000     # MCP2515 SocketCAN 기동
cd supervisor/hmi && python3 main.py
#   HMI_WINDOWED=1 …  창모드(원격/검증)   HMI_NOCAN=1 …  CAN/휠 없이 화면만
#   python3 tools/dummy_ecu.py            # 실 ECU 없이 좌석 트윈 검증
```
