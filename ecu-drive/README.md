# ecu-drive — Drive_ECU (STM32F446, FreeRTOS)

구동(파워트레인) 존 ECU. **FreeRTOS(CMSIS-RTOS v1)** 로 2륜 차동 주행과 조향 믹싱을 담당하고,
레이싱휠 `Drive_Cmd`를 받아 바퀴를 구동한다. DBC상 노드명은 `Drive_ECU`.

## 정본 / 디렉토리
```
ecu-drive/
├── PowerTrain_F446_freeRTOS/   ★ 정본 (STM32F446RE, FreeRTOS)
│   └── Core/Src/  main.c  freertos.c  model_car_net.c …
└── PowerTrain_F446/            (legacy) 베어메탈 초기 구현
```

## 하드웨어
- **STM32F446RE** · CAN 500kbps · 11bit
- 구동: **JGB37-520 ×2 + L298N** — TIM1 PWM 2채널(period 999), 방향 GPIO 4핀
- 피드백: **쿼드러처 엔코더 ×2**(TIM2/TIM3, PPR 1320) — 실측 RPM 계산

## 태스크 (CMSIS-v1)
- **DriveTask**(High, 10ms) — 명령 해석 · 조향 믹싱 · 듀티 램프 · 페일세이프
- **CanTxTask**(Normal, 10ms) — Drive_Status 주기 송신

## CAN 인터페이스
| 방향 | ID | 메시지 | 처리 |
|---|---|---|---|
| RX | `0x100` | Drive_Cmd | Target_Velocity / Steering_Angle / Brake_Depth |
| RX | `0x070` | GearStatus | **로컬 게이팅** — P(=0)/미지=정지, D=전진, R=후진 |
| RX | `0x010` | SafeAbort | Stop_Flag=1 → 숏브레이크 정지 |
| TX | `0x200` | Drive_Status | 속도=**엔코더 실측 RPM**, 전류=스텁(0), 기어=에코 |

## 특징
- **명령손실 페일세이프**: `Drive_Cmd`가 **~300ms** 끊기면 4핀 HIGH 숏브레이크로 결정적 정지.
- **조향**: 별도 조향축 없이 차동 믹싱(`v_steer = angle × 0.5`, 좌=base+steer / 우=base−steer, 음수 클램프).
- **개루프 차동**: 엔코더 RPM은 상태로 보고(모니터링)하되 듀티 계산에는 되먹이지 않음(PID 없음).
- 미구현: Heartbeat(0x050) 감시(수신 스캐폴딩만 존재), IWDG.

## 빌드
```
STM32CubeIDE: ecu-drive/PowerTrain_F446_freeRTOS import → Build → Flash
```
