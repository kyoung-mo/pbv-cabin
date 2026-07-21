# ecu-rear-cargo — Rear_Zone_ECU (STM32F446, FreeRTOS)

뒷좌석 좌/우 존 ECU. **FreeRTOS(CMSIS-RTOS v2)** 로 리클라인 서보 2축 + 슬라이드 스텝 2축을 제어하고,
INA226 앤티핀치와 슬라이드 위치 피드백을 담당한다. DBC상 노드명은 `Rear_Zone_ECU`.

## 정본 / 디렉토리
```
ecu-rear-cargo/
├── firmware/slide4/   ★ 정본 (STM32F446RE)
│   └── Core/Src/  can.c  slide.c  servo.c  ina226.c  main.c  model_car_net.c …
├── firmware/slide2/   (legacy) 초기 슬라이드 버전
├── firmware/slide3/   (legacy)
└── fw_slide4/         (legacy) slide4의 분기 벤치 사본 — 서보 방향반전·CAN 오토복구 실험,
                        앤티핀치는 사실상 무력화(임계 60000mA). 정본 아님.
```

## 하드웨어
- **STM32F446RE** · CAN 500kbps · 11bit
- 리클라인: **SG90 서보 ×2**(TIM2 CH1/CH2, 0–180°, 부팅 90°)
- 슬라이드: **NEMA17 리드스크류 + TMC2208 ×2**(STEP/DIR/EN, 1/2 마이크로스텝, 396.8 step/mm, 0–100mm)

## 태스크 (CMSIS-v2)
- **Motion**(High) — CAN RX 큐 드레인 → 디스패치 → slide/servo/pinch 서비스
- **Status**(Normal) — `send_status()` 100ms 주기
- defaultTask(idle 스텁)

## CAN 인터페이스
| 방향 | ID | 메시지 | 처리 |
|---|---|---|---|
| RX | `0x120` | Rear_Left_Seat_Cmd | RL 리클라인 + 슬라이드(센티넬 254 호밍/255 재영점/253 홀드) |
| RX | `0x121` | Rear_Right_Seat_Cmd | RR 상동 (+ Cargo_Lamp_Status — GPIO 미배선) |
| RX | `0x010` | SafeAbort | Stop_Flag=1 → 슬라이드 E-stop(서보는 계속) |
| TX | `0x220` | Rear_Left_Seat_Status | 현재 리클라인 + Pinch + **슬라이드 위치(0–100mm / 0xFF=원점 미확정)** |
| TX | `0x221` | Rear_Right_Seat_Status | 상동 |

## 특징
- **앤티핀치(활성)**: INA226 듀얼(0x40/0x41), 임계 **460mA**·3샘플 디바운스 → 리클라인 서보 **15° 후퇴** + Pinch 비트.
- **호밍**: 센서리스 하드스톱(센티넬 254). 부팅 자동호밍은 `SLIDE_HOMING=0`으로 꺼둠(현재 위치 0 가정).
- **슬라이드 위치**: 개루프 스텝카운트(엔코더 아님)를 0–100mm로 보고.
- **동시구동 인터록 제거(2026-07-05)** → 두 리니어 직렬화 책임은 슈퍼바이저로 이관.
- 미구현: Heartbeat(0x050) 감시, GearStatus 게이팅(수신·미사용), IWDG.

## 빌드
```
STM32CubeIDE: ecu-rear-cargo/firmware/slide4 import → Build → Flash
```
