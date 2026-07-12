# CAN 기반 가변 실내 PBV(Purpose Built Vehicle)
# 🥇 최종 프로젝트 경진대회 대상

> RPi5(PySide6/QtQuick3D 메인 제어기) + STM32 존 ECU ×3 + CAN Bus(500kbps) 기반
> 터치 HMI·레이싱휠 입력 → 결정적 안전 인터록 → 존 ECU 분산 액추에이션으로
> 좌석 8축 재배치 + 2륜 차동 드라이브-바이-와이어
> Intel Edge AI SW Academy 9기 4차 최종 프로젝트 (2026.06~07) · 팀 풀악셀(5인)

---

## 🔧 Tech Stack

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![C](https://img.shields.io/badge/C-FreeRTOS%20-A8B9CC?logo=c&logoColor=black)
![Raspberry Pi 5](https://img.shields.io/badge/Raspberry%20Pi%205-Main%20Controller-A22846?logo=raspberrypi&logoColor=white)
![STM32F103](https://img.shields.io/badge/STM32F103-Front%20Zone-03234B?logo=stmicroelectronics&logoColor=white)
![STM32F446](https://img.shields.io/badge/STM32F446-Rear%20/%20Drive-03234B?logo=stmicroelectronics&logoColor=white)
![FreeRTOS](https://img.shields.io/badge/FreeRTOS-CMSIS%20v1%2Fv2-8CC84B)

![PySide6](https://img.shields.io/badge/PySide6-Qt6-41CD52?logo=qt&logoColor=white)
![QtQuick3D](https://img.shields.io/badge/QtQuick3D-Digital%20Twin-41CD52?logo=qt&logoColor=white)
![CAN](https://img.shields.io/badge/CAN%20Bus-500kbps%2011bit-FF6F00)
![Vector CANdb++](https://img.shields.io/badge/Vector-CANdb%2B%2B-E2001A)
![cantools](https://img.shields.io/badge/cantools-DBC%20codec-0A7BBB)
![MCP2515](https://img.shields.io/badge/MCP2515-SocketCAN-555555)
![pygame](https://img.shields.io/badge/pygame-USB--HID%20Wheel-6495ED)
![TMC2208](https://img.shields.io/badge/TMC2208-NEMA17%20Slide-00979D)
![INA226](https://img.shields.io/badge/INA226-Anti--pinch-FFA000)

---

## 💡 Motivation

자율주행·PBV(Purpose Built Vehicle) 시대의 실내는 더 이상 고정된 좌석 배열이 아니다.
주행·회의·휴식 같은 목적에 따라 실내 공간이 실시간으로 재구성되어야 하고,
그 재구성은 **운전자·탑승자·주행 상태가 뒤섞인 채로** 안전하게 일어나야 한다.

여기서 핵심 문제의식은 하나다.

👉 **어떤 입력도 액추에이터를 곧바로 제어하지 못한다. 모든 입력은 "요청"이며,
결정적(deterministic) 안전 인터록을 통과해야만 비로소 CAN 명령이 된다.**

터치 HMI에서 누른 좌석 프리셋, 레이싱휠에서 밟은 페달, 패들로 넣은 기어 —
이 모두는 메인 제어기의 인터록(기어 P에서만 모드 전이 / 주행 중 좌석 이동 금지 /
D↔R은 P 경유 / 뒷좌석 리니어 동시구동 금지)을 거쳐야만 존 ECU로 나간다.
입력과 액추에이션 사이에 **결정적 안전 계층을 물리적으로 끼워 넣는 것**이 이 프로젝트의 설계 축이다.

> 본 프로젝트는 카메라·AI 인지 기능 대신, **분산 존 ECU · 기능안전 지향 설계 ·
> 실차 CAN 네트워크 · 드라이브-바이-와이어 아키텍처**에 집중한다.
> "감지"가 아니라 "요청 → 인터록 → 액추에이션"의 단방향 풀스택을 실장하는 것이 목표다.

---

## 📌 Key Features

- **분산 존(zone) CAN 아키텍처** — 메인 제어기(RPi5) 1 + 존 ECU 3(프론트/리어/구동)을 CAN 500kbps·11bit로 묶어 좌석 8축 + 2륜 차동 주행을 분산 제어. 정본 DBC 14메시지(Vector CANdb++), 각 ECU는 cantools 생성 C 코덱(`model_car_net.c/.h`) 공유.
- **결정적 안전 인터록** — 모든 입력은 메인 제어기 `VehicleState`의 인터록을 통과해야 CAN 명령이 된다. 기어=P에서만 모드 전이 / 주행(D·R) 중 좌석 액추에이터 금지 / D↔R은 P 경유 / 뒷좌석 리니어 직렬화(동시구동 금지) / SafeAbort(0x010) 전 노드 비상정지.
- **드라이브-바이-와이어** — 아우라 레이싱휠(USB-HID, pygame) → 조향/페달/패들 → `Drive_Cmd`(0x100) 50ms 주기 송신. 구동 ECU는 명령 300ms 손실 시 숏브레이크 자동 정지, 기어 로컬 게이팅(P=정지/D=전진/R=후진).
- **실시간 3D 디지털 트윈** — QtQuick3D로 X-ray 캐빈 3D 모델을 실시간 렌더. 좌석 현재포즈(리클라인/회전/슬라이드)를 상태 피드백으로 추종, 레이싱휠 조향각을 앞바퀴에 연동.
- **앤티핀치(anti-pinch)** — 리어 존은 INA226 전류감시(170mA 임계·3샘플 디바운스)로 리클라인 서보 끼임 감지 시 15° 후퇴 + Pinch 비트 보고. (프론트 존은 알고리즘 실장, 현재 측정전용 모드 — 아래 §핵심 기능 참조.)

---

## 🏗️ Architecture

<img width="1602" height="1049" alt="image" src="https://github.com/user-attachments/assets/4b9e6fe5-eb80-42ec-9585-615cd88ca8ba" />


| 노드 | 보드 | 역할 | 설계 원칙 |
|---|---|---|---|
| **메인 제어기 (Central_Supervisor)** | Raspberry Pi 5 + MCP2515(SPI, SocketCAN) | 터치 HMI(PySide6/QML) · 3D 디지털 트윈(QtQuick3D) · 레이싱휠 HID · 결정적 안전 인터록 · CAN encode/송수신(cantools) | 입력은 전부 "요청". 인터록을 통과한 것만 CAN 명령으로 나간다(단방향). |
| **Front_Zone_ECU** | STM32F103CBTx (베어메탈 슈퍼루프) | 운전석·조수석 리클라인(SG90 ×2) + 회전(28BYJ-48+ULN2003 ×2) · 좌석 상태 피드백(0x210/0x211) · SafeAbort 수신 | 논블로킹 협조 스케줄링. Cmd 체크섬 검증, 상태 100ms 주기 송신. |
| **Rear_Zone_ECU** | STM32F446RE (FreeRTOS CMSIS-v2) | 뒷좌석 좌/우 리클라인(SG90 ×2) + 슬라이드(NEMA17 리드스크류+TMC2208 ×2) · INA226 앤티핀치 · 슬라이드 위치 피드백 · SafeAbort 수신 | Motion(High)/Status(Normal) 태스크 분리. 동시구동 인터록은 메인 제어기로 이관. |
| **Drive_ECU** | STM32F446RE (FreeRTOS CMSIS-v1) | 2륜 차동 주행(JGB37-520 ×2 + L298N) · 조향 믹싱 · 기어 로컬 게이팅 · Drive_Cmd 300ms 손실 정지 · 엔코더 속도 보고 | Drive 명령이 끊기면 결정적으로 정지(페일세이프). 기어 P/미지 = 로컬 주행금지. |
| *Monitor_Node* | *(미실장)* | *레이싱휠·세이프티가드 신호 수신 / Heartbeat 감시 → SafeAbort 발동* | *DBC상 정의만 존재. 펌웨어는 후속 과제(§핵심 기능 참조).* |

---

## 📡 CAN 네트워크 설계

정본 DBC: `supervisor/dbc/model_car_net.dbc` (Vector CANdb++, **14메시지**) · 500 kbps · 11bit 표준 ID
메인 제어기는 cantools로 이 DBC를 로드해 encode/decode, 각 ECU는 동일 DBC에서 생성한 C 코덱을 공유한다(단일 소스 오브 트루스).

**ID 대역 체계** — CAN은 ID가 낮을수록 버스 중재(arbitration)에서 우선순위가 높다.
이를 이용해 안전·시스템 메시지에 최상위 대역(`0x0xx`)을 배정하고, 명령/상태를 방향별로 대역 분리했다.

| ID 대역 | 용도 | 소속 메시지 |
|---|---|---|
| `0x0xx` | **안전 · 시스템 관리** (최우선 중재) | `SafeAbort`(0x010) · `Heartbeat`(0x050) · `Heartbeat_Ack`(0x060) · `GearStatus`(0x070) |
| `0x1xx` | **메인 제어기 → 존 ECU** (명령) | `Drive_Cmd`(0x100) · 좌석 Cmd 4종(0x110·0x111 프론트 / 0x120·0x121 리어) |
| `0x2xx` | **존 ECU → 메인 제어기** (상태 보고) | `Drive_Status`(0x200) · 좌석 Status 4종(0x210·0x211 프론트 / 0x220·0x221 리어) |

**대역별 요점**
- `0x0xx` — `SafeAbort`는 3개 존 ECU + 메인 제어기 전 노드가 수신·래치하며, 해제는 메인 제어기가 `Stop_Flag=0` 프레임으로 송신. `Heartbeat`(0x050)는 메인 제어기가 100ms 주기 상시 송신. `GearStatus`(0x070)는 전 ECU 브로드캐스트로, 구동 ECU가 로컬 게이팅에 사용.
- `0x1xx` — `Drive_Cmd`는 레이싱휠 입력을 50ms 주기로 무조건 송신(구동 ECU의 300ms 손실정지 페일세이프와 짝). 좌석 Cmd는 인터록 통과분만 송신되며, `Driver_Seat_Cmd`(0x110)는 Rolling Counter + 체크섬 검증 포함.
- `0x2xx` — 각 존 ECU가 100ms 주기로 현재포즈·Pinch 비트·주행 상태(엔코더 실측 속도)를 보고. 메인 제어기는 이를 3D 디지털 트윈 추종에 사용.

> **미실장 정직 표기**: `Heartbeat_Ack`(0x060)와 Monitor_Node는 CAN 인터페이스(DBC) 정의만 존재하며 감시노드 펌웨어는 후속 과제. `SafeAbort` 발동(`Stop_Flag=1`) 자동 주입 주체도 후속 과제(수신·해제는 구현 완료). `Cargo_Lamp_Status` 신호(0x121)는 DBC에 존재하나 램프 GPIO 미배선. `Drive_Status`의 모터 전류는 스텁(0).

---

## ⚙️ 핵심 기능

**결정적 안전 인터록 체계 (메인 제어기 `vehicle_state.py`)**
- 모든 입력(터치 모드/좌석 슬라이더/기어/레이싱휠)은 단일 상태 객체 `VehicleState`를 통과한다. 인터록을 통과하지 못한 요청은 CAN으로 나가지 않는다(단방향: 입력 → 인터록 → encode → send).
- **모드 전이**: 기어=P(주행 모드)일 때만 허용. 주행/후진(D·R) 중에는 모드 변경 차단.
- **기어 전이**: D/R 진입은 주행 모드에서만 허용, D↔R은 반드시 P 경유(단일 `_apply_gear` 경로에서 슬라이더·휠 패들 공유).
- **좌석 액추에이터**: 기어 D/R 중에는 좌석 Cmd 송신 거부(`_seat_cmd_approved`).
- **뒷좌석 리니어 직렬화**: 두 슬라이드 동시구동 절대 금지 → 메인 제어기가 큐(`_slide_queue`)로 한 축씩 순차 구동. (펌웨어 레벨 인터록은 2026-07-05 제거하고 이 직렬화로 이관.)
- **SafeAbort(0x010)**: 수신 시 전체화면 적색 경보. 해제는 `Stop_Flag=0`(00 01 01) 프레임 송신으로 각 노드 래치 해제.

**레이싱휠 HID 파이프라인 (`wheel_input.py` + `can_hub.py`)**
- 아우라 레이싱휠 USB-HID를 pygame으로 폴링. **P4X(Generic X-Box pad, axes=6) 모드 필수** — 다른 모드면 조향=axis0/페달=axis1/패들=btn4·5 매핑이 어긋나 경고 후 폴백.
- 조향 axis0 → `Steering_Angle`(±127, 8bit signed 포화, 데드밴드 3°), 페달 axis1 단일축(음수=엑셀→RPM, 양수=브레이크→%), 패들 btn5/btn4 → 기어 업/다운(상승엣지 디바운스).
- 값 변화가 없어도 `Drive_Cmd`를 **50ms 주기로 무조건 브로드캐스트**(구동 ECU 300ms 손실정지보다 짧게) → 전용 스레드에서 GUI 지터와 무관하게 송신.

**실시간 3D 디지털 트윈 (QtQuick3D)**
- X-ray 캐빈 3D 모델(`Sports Car.glb`)을 실시간 렌더. 4좌석의 리클라인/회전/슬라이드 현재포즈를 CAN 상태 피드백으로 추종.
- 앞좌석 회전은 `Curr_*_Rotate` closed-loop 추종, 뒷좌석 슬라이드는 이동 중 open-loop 트윈 + 완료 시 `Curr_*_Slide` 실측 스냅.
- 레이싱휠 조향각을 앞바퀴 3D에 연동, ACTIVE↔AMBIENT(대기) UI 전환 + 무입력 타이머.

**존 ECU별 제어**
- *Front(F103, 베어메탈)*: 논블로킹 슈퍼루프. 리클라인 SG90 ×2(TIM2 PWM, 500–2500µs=0–180°) + 회전 28BYJ-48 ×2(ULN2003 8상 하프스텝, 2048스텝=180°). `Driver_Seat_Cmd` 체크섬(8bit 합) 검증, 상태 100ms 송신. SafeAbort 수신 시 전 축 정지.
- *Rear(F446, FreeRTOS v2)*: Motion(High)/Status(Normal)/idle 3태스크. 리클라인 SG90 ×2 + 슬라이드 NEMA17+TMC2208 ×2(1/2 마이크로스텝, 396.8 step/mm, 0–100mm). 센서리스 하드스톱 호밍(센티넬 254), 슬라이드 위치 개루프 스텝카운트를 0–100mm(미확정 시 0xFF)로 보고.
- *Drive(F446, FreeRTOS v1)*: DriveTask(High, 10ms)/CanTxTask(Normal, 10ms). 조향 차동 믹싱(`v_steer = angle×0.5`, 좌=base+steer/우=base−steer), L298N TIM1 PWM 2채널. **속도는 TIM2/TIM3 쿼드러처 엔코더 실측 RPM을 `Current_Velocity`로 보고(모니터링)하되, 듀티 계산 자체는 PID 없는 개루프 차동**. 기어 로컬 게이팅(P/미지=정지). `Drive_Cmd` 300ms 손실 시 4핀 HIGH 숏브레이크.

**앤티핀치(anti-pinch)**
- *Rear(활성)*: INA226 듀얼(I2C 0x40/0x41, 션트 100mΩ)로 리클라인 서보 전류 감시. 임계 **170mA**(3샘플 디바운스, 20ms 폴링) 초과 시 `servo_pinch_relief()`가 **15° 후퇴** + 목표 덮어써 정지, `*_Pinch_Detected` 비트 보고. (보호 대상은 리클라인 서보, 슬라이드는 전류감시 없음.)
- *Front(측정전용)*: INA226 듀얼 + 이중임계 알고리즘(운전석 soft 0.11A/hard 0.85A, 조수석 soft 0.03A/hard 0.70A)이 **실장되어 있으나 `PINCH_MEASURE_ONLY_MODE=1`로 컴파일** — 감지는 하되 래치/정지가 비활성이라 실동작에서 액추에이터를 멈추지 않는다(Pinch 비트 항상 0). **활성 정지 로직은 후속 과제.**

**기능안전 지향 설계 — 구현 현황(정직 구분)**
- ✅ **구현**: SafeAbort(0x010) 전 노드 비상정지 수신 + 메인 제어기 해제 송신 / 구동 ECU Drive_Cmd 300ms 손실정지 / 리어 앤티핀치 활성 / 결정적 인터록·직렬화 / Heartbeat(0x050) 메인 제어기 상시 송신.
- ⏳ **설계·CAN 인터페이스(DBC) 정의 완료, 구현은 후속 과제**: 감시노드(Monitor_Node) 펌웨어 / Heartbeat 감시·응답(0x060) 및 ECU측 하트비트 손실 페일세이프 / SafeAbort 발동(Stop_Flag=1) 자동 주입 / IWDG 워치독(3 ECU 전부 미사용) / 프론트 앤티핀치 활성화 / 프론트·리어 링크(명령손실) 페일세이프 / 좌석 상태 FSM enum / 좌석 과전류 E-stop CAN 배선.

> ⚠️ 본 프로젝트는 **기능안전 지향 설계 패턴**을 실장·검증하는 것을 목표로 하며,
> 기능안전 표준(ISO 26262 등) "인증"을 주장하지 않는다.

---

## 📁 프로젝트 구조

```
pbv-cabin/
├── supervisor/                 # RPi5 메인 제어기 (Python)
│   ├── dbc/model_car_net.dbc   #   ★ 정본 DBC (14메시지, Vector CANdb++)
│   ├── hmi/
│   │   ├── main.py             #   PySide6 엔트리 — CanHub/VehicleState/WheelInput 결선
│   │   ├── vehicle_state.py    #   ★ 단일 상태 객체 — 입력→인터록→CAN, 상태→트윈
│   │   ├── can_hub.py          #   can0 송수신 허브(cantools) + Heartbeat/SafeAbort
│   │   ├── wheel_input.py      #   레이싱휠 USB-HID(pygame) → Drive_Cmd 50ms
│   │   ├── qml/                #   HMI + QtQuick3D 디지털 트윈
│   │   │   ├── Main.qml  Cabin3D.qml  Seat3D.qml  SteeringWheel.qml
│   │   │   ├── ModeSelect.qml  SeatDetail.qml  SeatOverview.qml  GearSlider.qml …
│   │   ├── assets/models/      #   X-ray 캐빈 GLB
│   │   └── tools/              #   dummy_ecu.py(ECU 없이 트윈 검증) · 에셋 생성
│   └── handle/                 #   레이싱휠 실험 스크립트(drive_game/handle …)
│
├── ecu-front/                  # Front_Zone_ECU — STM32F103, 베어메탈
│   └── Src/  can.c  front_seat_app.c  servo.c  step.c  pinchdetect.c  main.c
│
├── ecu-rear-cargo/            # Rear_Zone_ECU — STM32F446, FreeRTOS CMSIS-v2
│   └── firmware/slide4/       #   ★ 정본 (slide2/slide3 = legacy)
│       └── Core/Src/  can.c  slide.c  servo.c  ina226.c  main.c  model_car_net.c
│
├── ecu-drive/                 # Drive_ECU — STM32F446, FreeRTOS CMSIS-v1
│   ├── PowerTrain_F446_freeRTOS/   #   ★ 정본
│   │   └── Core/Src/  main.c  freertos.c  model_car_net.c
│   └── PowerTrain_F446/            #   (legacy) 베어메탈 구현
│
├── cluster/supervision.py     # 감시노드 검증용 메인 제어기 흉내 시뮬레이터(테스트 하네스)
├── fw_slide4/                 # (legacy) 리어 정본의 분기 벤치 사본
├── interface/                 # FSM·인터록매트릭스 문서 placeholder
└── docs/                      # 설계 문서·배선도
```

---

## 🚀 빠른 시작

**메인 제어기 (RPi5)**
```bash
# MCP2515 SocketCAN 인터페이스 기동
sudo ip link set can0 up type can bitrate 500000
# 메인 제어기 앱 (PySide6 + QtQuick3D)
cd supervisor/hmi && python3 main.py
#   HMI_WINDOWED=1 ...   창모드(원격/검증)
#   HMI_NOCAN=1 ...      CAN/휠 없이 화면만
#   python3 tools/dummy_ecu.py   # 실 ECU 없이 좌석 트윈 검증
```

**Front_Zone_ECU (STM32F103)**
```
STM32CubeIDE: ecu-front import → Build → Flash (ST-Link)
```

**Rear_Zone_ECU (STM32F446, 정본 slide4)**
```
STM32CubeIDE: ecu-rear-cargo/firmware/slide4 import → Build → Flash
```

**Drive_ECU (STM32F446, 정본 freeRTOS)**
```
STM32CubeIDE: ecu-drive/PowerTrain_F446_freeRTOS import → Build → Flash
```

---

## 🛠️ 개발 환경

| 항목 | 내용 |
|---|---|
| 메인 제어기 | Raspberry Pi 5, Python 3.13, PySide6/Qt6(QtQuick3D), python-can + cantools, MCP2515(SPI) SocketCAN |
| 입력 장치 | 아우라 레이싱휠(USB-HID, pygame, P4X 모드), 터치 디스플레이 |
| Front Zone ECU | STM32F103CBTx (베어메탈 슈퍼루프), STM32CubeIDE, SG90 ×2 + 28BYJ-48/ULN2003 ×2 |
| Rear Zone ECU | STM32F446RE (FreeRTOS CMSIS-v2), SG90 ×2 + NEMA17/TMC2208 ×2, INA226 ×2 |
| Drive ECU | STM32F446RE (FreeRTOS CMSIS-v1), JGB37-520 ×2 + L298N, 쿼드러처 엔코더 |
| 차량 네트워크 | CAN Bus 500 kbps · 11bit 표준 ID, DBC(Vector CANdb++) 14메시지 |

---

## 👥 팀 풀악셀 (5인)

| 노드 / 디렉토리 | 담당 | 역할 |
|---|---|---|
| 총괄 · `supervisor/` | **구영모**(팀장) | 프로젝트 총괄, 메인 제어기·HMI·3D 트윈, CAN/DBC·인터록 설계, HW 디버깅 |
| `cluster/` | 인수민 | 3D 모델링 · 감시노드 트랙 · 하트비트/세이프어보트 검증 하네스 |
| `ecu-front/` | 김현주 | 프론트 존 ECU(앞좌석 2축, 앤티핀치) · 하드웨어 제작 |
| `ecu-rear-cargo/` | 김준기 | 리어 존 ECU(뒷좌석 슬라이드·리클라인 4축, 앤티핀치) |
| `ecu-drive/` | 안해성 | 구동 ECU(2륜 차동 주행·페달 2축) · CAN DBC 정의 |

---

## 🎯 산출물

- **4노드 분산 CAN 프로토타입** — 메인 제어기 1 + 존 ECU 3(F103 베어메탈 / F446 FreeRTOS ×2)이 CAN 500kbps로 실동작.
- **좌석 8축 재배치** — 앞 4축(리클라인·회전 ×2) + 뒤 4축(리클라인·슬라이드 ×2), 4모드 프리셋(주행/회의/Full-space/휴식).
- **정본 DBC 14메시지 · ID 대역 설계** — 0x0xx 안전/0x1xx 명령/0x2xx 상태로 대역 분리(낮은 ID=높은 중재 우선순위), cantools 코덱을 메인 제어기·ECU가 공유(단일 소스 오브 트루스). 구현/계약정의 상태를 정직 명시.
- **드라이브-바이-와이어** — 레이싱휠 `Drive_Cmd` 50ms 주기 → 구동 ECU 2륜 차동 + 조향 믹싱, **300ms 명령손실 페일세이프**, 기어 로컬 게이팅.
- **결정적 안전 인터록** — 모드/기어/좌석/직렬화/SafeAbort 인터록을 메인 제어기 단일 상태 객체에 집약.
- **앤티핀치** — 리어 INA226 **170mA 임계 · 15° 후퇴** 활성, 프론트 이중임계 알고리즘 실장(측정전용).
- **실시간 3D 디지털 트윈** — QtQuick3D X-ray 캐빈, 좌석 포즈·조향 CAN 피드백 연동.
- **베어메탈·FreeRTOS 이중 구현 보존** — 구동 ECU의 legacy 베어메탈, 리어 초기 슬라이드 버전(slide2/3) 트리 보존.

---

*A2 스케일 무하중 모형. 본 프로젝트는 인증된 기능안전이 아니라 기능안전 지향 설계 패턴의 실증입니다.*
