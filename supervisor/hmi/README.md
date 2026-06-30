# supervisor/hmi — 터치 HMI (스텝1: 화면/입력 골격)

PySide6 + QML 차량 HMI의 UI 골격. **이 단계는 CAN 통신을 하지 않는다.**
모든 "CAN으로 보낼 자리"는 실제 전송 대신 `print()`로 무엇을 보낼지만 콘솔에 출력한다.
디자인은 색깔 박스 + 글자 placeholder.

## 구조

```
main.py            엔트리포인트. VehicleState를 QML 전역(vehicleState)으로 노출
vehicle_state.py   단일 상태 객체(QObject). 모든 상태를 Property+Signal로, 입력은 @Slot로
qml/
  Main.qml         풀스크린 가로, 좌우 2분할(왼쪽 차량 40% / 오른쪽 패널 60%)
  LeftCar.qml      회색 CAR 박스(전체 클릭=화면 토글) + 기어 텍스트
  GearSlider.qml   세로 기어 슬라이드 (위=D / 중앙=P / 아래=R, 한 칸씩만)
  RightPanel.qml   right_panel_screen에 따라 3화면 전환(Loader)
  ModeSelect.qml   2x2 모드 박스 (주행/회의/Full-space/휴식)
  SeatOverview.qml 2x2 좌석 배치 (좌상 운전석 / 우상 조수석 / 좌하·우하 뒷좌석)
  SeatDetail.qml   선택 좌석 + 슬라이더 2개 (리클라인 + 회전/슬라이드)
```

상태는 `VehicleState` 한 곳에만 있고, QML은 binding으로만 그린다(수동 재draw 없음).

## 의존성 설치 (Raspberry Pi OS 64bit / Debian, aarch64)

pip는 externally-managed라 막히므로 **apt**로 설치한다(QML 런타임 모듈은 시스템에 이미 있음):

```bash
sudo apt install -y python3-pyside6.qtquick python3-pyside6.qtqml python3-pyside6.qtquickcontrols2
```

## 실행

```bash
cd supervisor/hmi
python3 main.py                 # 풀스크린 (실차/타깃 디스플레이)
HMI_WINDOWED=1 python3 main.py  # 창모드 (원격 X11 등 검증 편의)
```

- 종료: **Esc** 키
- 화면 없이 QML 문법만 확인: `HMI_SELFTEST=1 QT_QPA_PLATFORM=offscreen python3 main.py`

## 콘솔 출력 (print로 대체된 CAN 송신 자리)

| 동작 | 출력 |
|---|---|
| 기어 변경 | `GEAR: D` / `GEAR: P` / `GEAR: R` (점프 시 `GEAR: 거부 ...`) |
| 모드 선택 | `MODE: 회의 선택 → 좌석 프리셋 전송 예정` |
| 슬라이더 조절 | `SEAT_CMD: 운전석 리클라인=120` / `SEAT_CMD: 뒷좌석(좌) 슬라이드=55` |

## 스텝2 — 실제 can0 양방향 연동 (구현 완료)

이 노드는 DBC 상 **Central_Supervisor**. 인터페이스 이름은 `can_hub.py`의 `CAN_IFACE="can0"`
상수 하나로 빼 두었다(교체 시 한 줄). DBC 는 `supervisor/dbc/model_car_net.dbc` 를 cantools
로 로드해 encode/decode 한다(임시 메시지 정의 없음, .h/.c 는 ECU 펌웨어용이라 미사용).

```
can_hub.py      DBC 로드 + can0 버스. 송신 헬퍼(좌석/Drive/Gear) + RX 스레드 → Qt Signal.
                Driver_Seat_Cmd 의 Rolling_Counter(0~15 순환) + Checksum(XOR of byte0..2) 채움.
wheel_input.py  레이싱휠(pygame.joystick) → Drive_Cmd 50ms 주기 송신 + 화면 즉각 반영.
                조향=axis0(±130°,데드밴드3°) / 페달=axis1 단일축(음수=엑셀,양수=브레이크).
tools/dummy_ecu.py  STM32 전 자체 검증용 더미 존 ECU. 좌석 Cmd→*_Seat_Status 응답.
```

흐름:
- **입력→인터록→CAN**(단방향): "적용"/모드/슬라이더 → 안전 인터록(주행 중 좌석잠금) 통과 시에만
  해당 `*_Seat_Cmd` 송신. reject 면 송신 안 함.
- **수신→트윈**: RX 스레드가 `*_Seat_Status` decode → **Qt Signal(QueuedConnection)** 로 GUI
  스레드에 넘겨 갱신(스레드 안전). recline(전 좌석)·앞좌석 회전 = status closed-loop,
  뒷좌석 슬라이드 = 피드백 없어 로컬 트윈(open-loop). `*_Pinch_Detected` = 끼임 경고 표시.
- **휠→Drive_Cmd**: 기어 D/R 일 때만 실제 값, 아니면 중립(0). 값 불변에도 50ms 브로드캐스트
  (Drive ECU 가 300ms 끊기면 비상정지하므로). 화면 조향 표시는 인터록과 무관하게 항상 따라옴.

### 실행 (자체 검증)

```bash
cd supervisor/hmi
python3 tools/dummy_ecu.py        # ① 터미널 A: 더미 ECU (STM32 대용)
python3 main.py                   # ② 터미널 B: HMI
candump -ta can0                  # ③ 터미널 C: 버스 관찰(또는 PC cangaroo)
```

좌석 조작 시 `*_Seat_Cmd`(0x110~0x121)가 나가고 Driver 의 Rolling_Counter 가 증가, 더미가
보낸 `*_Seat_Status` 로 3D 트윈 현재포즈가 따라 움직인다. 휠을 돌리면(기어 D/R) Drive_Cmd(0x100)
의 Steering_Angle 이 같이 변한다. 실물 ECU 가 붙으면 `dummy_ecu.py` 만 끄면 그대로 동작한다.

> 참고: `Drive_Cmd.Steering_Angle` 은 DBC 상 8bit signed(선언 ±135)라 물리적으로 ±127 까지만
> 인코딩된다 — 휠 풀스케일 ±130° 의 끝단은 ±127 로 포화한다. CAN/휠 없이 화면만 보려면
> `HMI_NOCAN=1 python3 main.py`.

## 에셋 라이선스 — 모드 타일 배경 사진 (CC0 / Public Domain)

`assets/modes/*.png` — 모두 **CC0 또는 퍼블릭 도메인**만 사용. Openverse(api.openverse.org, `license=cc0,pdm` 필터)로 검색·검증해 받았고, 타일 크기에 맞춰 560×420으로 다운샘플함. 원본 출처(landing)에서 라이선스 재확인 가능.

| 모드 | 파일 | 제목 | 제작자 | 라이선스 | 출처(provider) | 원본 페이지 |
|---|---|---|---|---|---|---|
| 주행 | `drive.png` | Open highway road desert Arizona | (미상) | CC0 1.0 (Public Domain Dedication) | rawpixel | https://www.rawpixel.com/image/3292687/free-photo-image-asphalt-cc0-creative-commons |
| 회의 | `meeting.png` | conference room table chairs | (미상) | CC0 1.0 (Public Domain Dedication) | rawpixel | https://www.rawpixel.com/image/3337630/free-photo-image-boardroom-conference-office-background |
| Full-space | `fullspace.png` | Dodge Grand Caravan (RT) with 4x8 foot plywood inside (뒷좌석 접은 트렁크 적재공간) | CZmarlin — Christopher Ziemnowicz | CC0 1.0 (Public Domain Dedication) | wikimedia | https://commons.wikimedia.org/w/index.php?curid=157179039 |
| 휴식 | `rest.png` | Milky Way and starry night sky | naturenps | Public Domain Mark 1.0 | flickr | https://www.flickr.com/photos/130826934@N07/26972689115 |

> 라이선스가 CC0/PD가 아닌 이미지는 사용하지 않음. 교체 시에도 동일 기준 유지.
