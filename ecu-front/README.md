# ecu-front — Front_Zone_ECU (STM32F103, 베어메탈)

앞좌석(운전석·조수석) 존 ECU. **베어메탈 슈퍼루프**(FreeRTOS 미사용)로 리클라인·회전 2축씩,
합 4축을 논블로킹 협조 스케줄링으로 제어한다. DBC상 노드명은 `Front_Zone_ECU`.

## 하드웨어
- **STM32F103CBTx** · 트랜시버로 CAN 500kbps · 11bit 표준 ID
- 리클라인: **SG90 서보 ×2** — TIM2 CH1/CH2 PWM(50Hz, 500–2500µs = 0–180°), 소프트 램프
- 회전: **28BYJ-48 스텝 ×2 + ULN2003** — 8상 하프스텝, 2048스텝 = 180°(홈센서 없음, 전원 시 0 가정)

## CAN 인터페이스
| 방향 | ID | 메시지 | 처리 |
|---|---|---|---|
| RX | `0x110` | Driver_Seat_Cmd | 리클라인+회전 목표. **Checksum(8bit 합) 검증**, Rolling_Counter는 파싱만 |
| RX | `0x111` | Passenger_Seat_Cmd | 리클라인+회전 목표 |
| RX | `0x070` | GearStatus | **저장만** 함(로컬 게이팅 없음) |
| RX | `0x010` | SafeAbort | Stop_Flag=1 → 전 축 정지 + 래치, =0 → 해제 |
| TX | `0x210` | Driver_Seat_Status | 현재 리클라인/회전 + Pinch 비트, **100ms 주기** |
| TX | `0x211` | Passenger_Seat_Status | 상동 |

## 앤티핀치 (INA226)
- INA226 듀얼(I2C 0x40/0x41)로 서보 전류 감시, 좌석별 이중임계(soft 이동평균 / hard 순간) 알고리즘 실장.
- ⚠️ 현재 **`PINCH_MEASURE_ONLY_MODE=1`(측정전용)** 로 컴파일 — 감지는 하되 래치/정지가 컴파일 제외라
  실동작에서 액추에이터를 멈추지 않는다(Pinch 비트 항상 0). **활성 정지 로직은 후속 과제.**

## 구조 / 미구현
```
ecu-front/  Inc/  Src/(can.c front_seat_app.c servo.c step.c pinchdetect.c main.c)  Startup/
```
- 미구현: FreeRTOS, IWDG 워치독, 명령손실 타임아웃(끊겨도 마지막 위치 홀드), 프론트 앤티핀치 활성화.

## 빌드
```
STM32CubeIDE: ecu-front import → Build → Flash (ST-Link)
```
