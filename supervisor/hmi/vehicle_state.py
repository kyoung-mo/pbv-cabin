"""VehicleState — 차량 HMI의 단일 상태 객체 (single source of truth).

스텝2: 실제 can0 양방향 연동.
  · 입력(슬라이더/모드/적용/기어) → 안전 인터록 통과 시에만 CanHub 로 encode→send.
  · 디지털 트윈의 "현재 recline 포즈"는 로컬 트윈이 아니라 **수신한 Seat_Status**로만
    갱신한다(onSeatStatus). 더미 ECU(또는 실물 ECU)가 보내는 Curr_*_Recline 을 따라간다.
      └ 단, 회전/슬라이드(axis2)는 DBC 에 Status 피드백이 없어 로컬 트윈으로 시각화한다.
  · QML은 이 객체의 Property에 binding으로만 그리며, 입력은 @Slot setter만 호출한다.
  · CanHub 가 None(셀프테스트/CAN 미연결)이면 송신부는 콘솔 출력으로 폴백한다.
"""

from PySide6.QtCore import QObject, Signal, Property, Slot, QTimer


# 좌석 식별자 → 한글 표시명
SEAT_LABELS = {
    "driver": "운전석",
    "passenger": "조수석",
    "rear_left": "뒷좌석(좌)",
    "rear_right": "뒷좌석(우)",
}

# 앞좌석(리클라인 + 회전) / 뒷좌석(리클라인 + 슬라이드) 구분
FRONT_SEATS = ("driver", "passenger")

# 기어 슬라이드 인덱스(UI 배치): 아래(0)=R, 중앙(1)=P, 위(2)=D
GEARS = ("R", "P", "D")

# 기어 → CAN GearStatus(0x070) Gear 값 인코딩. ECU 합의: R=0 / P=1(중립,기본) / D=2.
#   중립(P)=1 을 기준으로 위로 한 칸=D(2, 상한 클램프), 아래로=P(1)→R(0, 하한 클램프).
#   (GEARS 순서 R-P-D 의 인덱스와 동일 — 슬라이더 위치와 CAN 값이 같은 정렬이 된다.)
GEAR_CAN_VALUE = {"R": 0, "P": 1, "D": 2}

# 주행(DRIVE) 모드 식별자 — 기어 D/R 진입을 허용하는 유일한 모드
DRIVE_MODE = "주행"

# "적용" 트윈 — current(3D 실제 위치)가 target(목표)까지 가는 시간/틱 간격(ms)
TWEEN_DURATION_MS = 1200
TWEEN_INTERVAL_MS = 16

# 대기(AMBIENT) 진입 — 이 시간(ms) 동안 "입력"이 없으면 대기 모드로. (기어 조작은 입력 제외)
IDLE_TIMEOUT_MS = 10000

# ── 모드 프리셋 ──────────────────────────────────────────────────────────────
# 모드 타일을 누르면 아래 값으로 4개 좌석 target 을 세팅하고 즉시 "적용"(트윈)한다.
# 값만 바꿔 내일 조정 가능.
#   recline: 90=직립 / 0=앞으로 접어 평탄 / 150=뒤로 눕힘
#   axis2  : 앞좌석=회전(0=정면, 180=뒤로 돌아 마주봄), 뒷좌석=슬라이드(0=앞최대, 100=뒤최대)
#   좌석/축을 생략하면 그 좌석/축은 "그대로" 둔다(예: Full-space는 앞좌석 미포함).
MODE_PRESETS = {
    "주행": {                                          # 직립 주행 자세
        "driver":     {"recline": 90, "axis2": 0},
        "passenger":  {"recline": 90, "axis2": 0},
        "rear_left":  {"recline": 90, "axis2": 30},
        "rear_right": {"recline": 90, "axis2": 30},
    },
    "회의": {                                          # 앞좌석 뒤로 돌아 마주봄
        "driver":     {"recline": 90, "axis2": 180},
        "passenger":  {"recline": 90, "axis2": 180},
        "rear_left":  {"recline": 90, "axis2": 30},
        "rear_right": {"recline": 90, "axis2": 30},
    },
    "Full-space": {                                    # 뒷좌석 앞으로 최대 + 접어 평탄
        "driver":     {"recline": 90, "axis2": 0},     # 앞좌석도 직립/정면으로 초기화
        "passenger":  {"recline": 90, "axis2": 0},
        "rear_left":  {"recline": 0, "axis2": 0},
        "rear_right": {"recline": 0, "axis2": 0},
    },
    "휴식": {                                          # 뒷좌석 뒤로 최대 + 전 좌석 눕힘
        "driver":     {"recline": 150},
        "passenger":  {"recline": 150},
        "rear_left":  {"recline": 150, "axis2": 100},
        "rear_right": {"recline": 150, "axis2": 100},
    },
}


class VehicleState(QObject):
    # --- NOTIFY 시그널 ---
    gearChanged = Signal()
    cabinModeChanged = Signal()
    rightPanelScreenChanged = Signal()
    selectedSeatChanged = Signal()
    seatValuesChanged = Signal()  # 현재 선택 좌석의 각도값이 바뀜
    seatMovingChanged = Signal()  # 좌석의 이동(보간) 상태 집합이 바뀜
    uiModeChanged = Signal()      # 화면 상태(ACTIVE/AMBIENT) 전환
    pinchChanged = Signal()       # 좌석 끼임(Pinch_Detected) 집합이 바뀜
    driveStatusChanged = Signal() # Drive_Status(현재속도 등) 수신 반영
    wheelInputChanged = Signal()  # 레이싱휠 조향/페달 실시간 입력(화면 표시용)

    def __init__(self, can_hub=None, parent=None):
        super().__init__(parent)
        # CAN 송신 허브(없으면 콘솔 폴백). RX 시그널은 main 에서 onSeatStatus 등에 연결.
        self._can = can_hub
        self._gear = "P"
        # 시작 기본값: 주행 모드 + P(중립). (홈/대기 화면은 아래 _ui_mode=AMBIENT)
        #   주행이 기본이라 시작부터 기어 슬라이드가 열려 있다(gearLocked=False).
        #   좌석 기본 포즈가 이미 주행 프리셋과 같으므로 여기선 CAN 을 보내지 않는다.
        self._cabin_mode = DRIVE_MODE
        self._right_panel_screen = "MODE_SELECT"
        # 주행 모드 선택 후 "좌석 배치 완료 시 대기(홈)로 자동 이동" 대기 플래그.
        #   selectMode(주행)에서 켜고, 좌석 이동이 모두 끝나면 _check_drive_settle 이 끈다.
        self._drive_settle_pending = False
        self._selected_seat = "driver"
        # 좌석별 각도값 (재진입해도 유지되도록 여기에만 저장).
        # 각 축은 target(목표) / current(3D가 실제로 가 있는 값) 두 개로 분리한다.
        #   · 슬라이더는 target 만 바꾼다(즉시 움직이지 않음).
        #   · "적용"을 누르면 current 가 target 까지 부드럽게 보간된다.
        #   · 3D 캐빈은 current 에 바인딩한다.
        #   recline: 0~180 (90=직립/정상착좌, 180=완전 뒤로 눕기, 0=앞으로 폴딩)
        #   axis2  : 앞좌석=회전 0~180, 뒷좌석=슬라이드 0~100
        #   recline 은 "commanded"(마지막으로 CAN 송신한 목표)를 따로 둔다 — 트윈이 아니라
        #   수신 Status 로 current 가 commanded 까지 따라오는 동안을 "이동중"으로 본다.
        #   axis2 도 commanded 를 둔다: 앞좌석 회전은 이제 Curr_*_Rotate 피드백이 있어
        #   closed-loop(트윈X, status 추종) — 뒷좌석 슬라이드는 피드백이 없어 open-loop(트윈).
        def _axes(recline, axis2):
            return {
                "recline": {"target": recline, "current": recline,
                            "commanded": recline},
                "axis2":   {"target": axis2,   "current": axis2,
                            "commanded": axis2},
            }
        # 앞좌석 axis2=회전(기본 0=정면). 뒷좌석 axis2=슬라이드(기본 30=여유 있는 정상
        # 착좌 위치; 0으로 당기면 앞쪽 최대 full-space, 100이면 뒤쪽 최대).
        self._seat_values = {
            "driver":     _axes(90, 0),
            "passenger":  _axes(90, 0),
            "rear_left":  _axes(90, 30),
            "rear_right": _axes(90, 30),
        }

        # 좌석별 끼임 경고(Seat_Status.*_Pinch_Detected 수신 반영)
        self._pinch = {seat: False for seat in SEAT_LABELS}
        # Drive_Status 반영(현재 속도 RPM)
        self._current_velocity = 0.0
        # 레이싱휠 실시간 입력(화면 표시용) — 인터록과 무관하게 항상 갱신
        self._wheel_steer = 0      # 조향각(도, -130~130)
        self._wheel_throttle = 0   # 엑셀(%)
        self._wheel_brake = 0      # 브레이크(%)

        # 적용 트윈 엔진 — 단일 QTimer 로 여러 축(seat,axis)을 동시에 보간.
        self._tweens = {}   # (seat, axis) -> {"start", "target", "elapsed"}
        self._tween_timer = QTimer(self)
        self._tween_timer.setInterval(TWEEN_INTERVAL_MS)
        self._tween_timer.timeout.connect(self._on_tween_tick)

        # 화면 상태 + 무입력(앰비언트) 타이머. 기본 AMBIENT(켜면 바로 대기 화면).
        # 타이머는 ACTIVE 일 때만 의미가 있으므로 여기선 무장하지 않는다.
        # (차량 터치 → wakeFromAmbient → _register_activity 에서 타이머 시작)
        self._ui_mode = "AMBIENT"
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)        # start()마다 카운트다운 재시작
        self._idle_timer.timeout.connect(self._on_idle_timeout)

    # =====================================================================
    # gear
    # =====================================================================
    def _get_gear(self):
        return self._gear

    gear = Property(str, _get_gear, notify=gearChanged)

    def _get_gear_index(self):
        return GEARS.index(self._gear)

    gearIndex = Property(int, _get_gear_index, notify=gearChanged)

    @Slot(int)
    def requestGearIndex(self, idx):
        """기어 슬라이더에서 호출. 한 칸씩(인접)만 허용 — P를 건너뛰지 못한다."""
        idx = max(0, min(2, int(idx)))
        cur = GEARS.index(self._gear)
        if idx == cur:
            return
        if abs(idx - cur) != 1:
            # D↔R 직접 점프 거부. gearChanged를 쏘아 슬라이더를 원위치로 되돌린다.
            print(f"GEAR: 거부 ({self._gear}→{GEARS[idx]}, 한 칸씩만 이동 가능)")
            self.gearChanged.emit()
            return
        target = GEARS[idx]
        self._apply_gear(target, source="slider")

    def _apply_gear(self, target, *, source):
        """기어 상태를 target 으로 전이하고 GearStatus(0x070) 송신 + 화면 동기.

        슬라이더/휠 패들이 공유하는 단일 전이 경로. 인터록(D/R 진입은 주행 모드에서만)만
        검사하고, 실제 전이가 일어나면 매번 0x070 을 송신하고 gearChanged 를 쏜다.
        반환: 전이 성공 True / 거부·무변화 False.
        """
        if target == self._gear:
            return False
        # 인터록: D/R 진입은 주행 모드일 때만 허용. (P 로 복귀는 항상 허용)
        if target in ("D", "R") and self._cabin_mode != DRIVE_MODE:
            print(f"BLOCKED: 주행 모드가 아니라 기어 변경 불가 (src={source})")
            self.gearChanged.emit()  # 슬라이더를 현재 기어로 되돌림
            return False
        self._gear = target
        gear_idx = GEAR_CAN_VALUE[self._gear]     # CAN 인코딩(P=0/D=1/R=2), 슬라이더 인덱스와 별개
        print(f"GEAR: {self._gear}  → send GearStatus(0x070) Gear={gear_idx} (src={source})")
        # GearStatus 브로드캐스트(Drive/Front/Rear ECU 가 인터록 판단에 사용).
        if self._can:
            self._can.send_gear_status(gear_idx)
        self.gearChanged.emit()
        return True

    @Slot()
    def gearBlockedNotice(self):
        """잠긴 기어 슬라이드를 눌렀을 때 QML이 호출 — 사유만 출력."""
        print("BLOCKED: 주행 모드가 아니라 기어 변경 불가")

    @Slot(int)
    def onWheelGearShift(self, delta):
        """레이싱휠 패들(WheelInput.gearShift)에서 QueuedConnection 으로 호출 = GUI 스레드 안전.

        패들 press 엣지 1회 = 기어 한 칸 전이(GEARS 순서 R-P-D 를 따라 선형 이동, 경계 클램프).
          · 업(delta>0, btn5)  : R→P→D  (D 에서 더 눌러도 D 유지)
          · 다운(delta<0, btn4): D→P→R  (R 에서 더 눌러도 R 유지)
        터치 슬라이더와 동일한 _apply_gear 경로로 인터록·GearStatus(0x070) 송신·슬라이더 동기를
        한곳에서 처리(P=0/D=1/R=2 인코딩도 _apply_gear 가 담당).
        """
        step = 1 if int(delta) >= 0 else -1   # +1=업(R→P→D), -1=다운(D→P→R)
        try:
            i = GEARS.index(self._gear)
        except ValueError:
            i = GEARS.index("P")              # 현재 기어가 목록에 없으면 P 기준
        j = max(0, min(len(GEARS) - 1, i + step))   # 경계에서 클램프(끝단 넘어가지 않음)
        target = GEARS[j]
        if target == self._gear:
            print(f"WHEEL GEAR: paddle delta={delta} → 끝단({self._gear}) 유지")
            return
        print(f"WHEEL GEAR: paddle delta={delta} → {self._gear}→{target}")
        self._apply_gear(target, source="wheel")

    # --- 인터록 파생 상태 (QML이 binding으로 활성/비활성 판단) ---
    def _get_gear_locked(self):
        # 주행 모드가 아니면 기어 슬라이드를 P에 고정하고 잠근다.
        return self._cabin_mode != DRIVE_MODE

    gearLocked = Property(bool, _get_gear_locked, notify=cabinModeChanged)

    # =====================================================================
    # cabin_mode (MODE_SELECT 화면)
    # =====================================================================
    def _get_cabin_mode(self):
        return self._cabin_mode

    cabinMode = Property(str, _get_cabin_mode, notify=cabinModeChanged)

    @Slot(str)
    def selectMode(self, mode):
        self._register_activity()
        # 인터록: 주행/후진 중(기어 D/R)에는 모드 변경 불가.
        if self._gear in ("D", "R"):
            print("BLOCKED: 주행/후진 중이라 모드 변경 불가")
            return
        self._cabin_mode = mode
        print(f"MODE: {mode} 선택 → 좌석 프리셋 적용")
        self.cabinModeChanged.emit()
        # 모드 프리셋을 4개 좌석에 즉시 적용(target 세팅 + 트윈 시작 + SEAT_CMD print).
        self._apply_mode_preset(mode)
        # 주행 모드: 좌석이 전부 배치되면 대기(홈)로 자동 이동. (다른 모드는 현 화면 유지)
        #   이미 배치돼 있으면(움직임 없음) 즉시, 이동 중이면 배치 완료 시점에 이동한다.
        self._drive_settle_pending = (mode == DRIVE_MODE)
        self._check_drive_settle()

    @Slot()
    def modeBlockedNotice(self):
        """잠긴 모드 타일을 눌렀을 때 QML이 호출 — 사유만 출력."""
        self._register_activity()   # 잠겼어도 화면 터치는 입력 — 타이머 리셋
        print("BLOCKED: 주행/후진 중이라 모드 변경 불가")

    # --- 인터록 파생 상태 (QML이 binding으로 활성/비활성 판단) ---
    def _get_mode_locked(self):
        # 주행/후진 중(기어 D/R)이면 모드 타일을 잠근다. P로 돌아오면 해제.
        return self._gear in ("D", "R")

    modeLocked = Property(bool, _get_mode_locked, notify=gearChanged)

    # =====================================================================
    # right_panel_screen (오른쪽 패널 3화면 전환)
    # =====================================================================
    def _get_right_panel_screen(self):
        return self._right_panel_screen

    rightPanelScreen = Property(str, _get_right_panel_screen,
                                notify=rightPanelScreenChanged)

    def _set_screen(self, screen):
        if screen == self._right_panel_screen:
            return
        self._right_panel_screen = screen
        self.rightPanelScreenChanged.emit()

    @Slot()
    def cycleCarArea(self):
        """왼쪽 차량 3D 탭 — 한 번 누를 때마다 홈 → 모드 → 좌석 → 홈 순환.

          · 홈(AMBIENT)            → 모드(ACTIVE + MODE_SELECT)
          · 모드(MODE_SELECT)      → 좌석(ACTIVE + SEAT_OVERVIEW)
          · 좌석(SEAT_OVERVIEW/DETAIL) → 홈(AMBIENT)
        """
        if self._ui_mode == "AMBIENT":
            # 홈 → 모드 선택 (ACTIVE 복귀 + 무입력 타이머 시작)
            self._register_activity()
            self._set_screen("MODE_SELECT")
        elif self._right_panel_screen == "MODE_SELECT":
            # 모드 → 좌석 개요
            self._register_activity()
            self._set_screen("SEAT_OVERVIEW")
        else:
            # 좌석(개요/디테일) → 홈(대기). (타이머와 무관: 입력 아님)
            self._idle_timer.stop()
            self._set_ui_mode("AMBIENT")

    @Slot(str)
    def selectSeat(self, seat):
        """SEAT_OVERVIEW에서 좌석 클릭 → 선택 후 SEAT_DETAIL로."""
        self._register_activity()
        self._selected_seat = seat
        self.selectedSeatChanged.emit()
        self.seatValuesChanged.emit()  # 현재좌석 각도 Property 갱신
        self._set_screen("SEAT_DETAIL")

    @Slot()
    def backToOverview(self):
        self._register_activity()
        self._set_screen("SEAT_OVERVIEW")

    # =====================================================================
    # ui_mode (ACTIVE / AMBIENT) — 대기(앰비언트) 모드 + 무입력 타이머
    # =====================================================================
    #   · ACTIVE : 차량 3D + 오른쪽 패널(현재 화면), 정상 동작.
    #   · AMBIENT: 대기 화면(레이아웃은 다음 단계). 10초 무입력 + 기어 P 일 때 진입.
    #   · "입력"으로 치는 것: 화면/패널 터치, 슬라이더, 모드/좌석 선택, 적용 등.
    #     기어 조작(requestGearIndex)은 입력에서 제외 — 타이머도 안 깨우고, 대기도 안 깸.
    def _get_ui_mode(self):
        return self._ui_mode

    uiMode = Property(str, _get_ui_mode, notify=uiModeChanged)

    def _set_ui_mode(self, mode):
        if mode == self._ui_mode:
            return
        self._ui_mode = mode
        print(f"UI: {mode}")
        self.uiModeChanged.emit()

    def _register_activity(self):
        """기어를 제외한 '입력'마다 호출 — 무입력 타이머 리셋(+AMBIENT면 깨우기)."""
        # 사용자가 직접 조작하면 주행 모드 '자동 대기 이동'은 취소(원치 않는 홈 이동 방지).
        self._drive_settle_pending = False
        if self._ui_mode == "AMBIENT":
            self._set_ui_mode("ACTIVE")
        self._idle_timer.start(IDLE_TIMEOUT_MS)

    @Slot()
    def wakeFromAmbient(self):
        """AMBIENT에서 차량 화면 터치 → ACTIVE 복귀 + 타이머 재시작.
        (기어 조작은 이 경로를 안 써서 대기 유지. 레이아웃 전환은 다음 단계.)"""
        self._register_activity()

    # ── 하단 내비게이션 바 지름길 ──────────────────────────────────────
    @Slot()
    def goAmbient(self):
        """홈 버튼 — 대기(AMBIENT) 모드로 즉시 전환. (타이머와 무관: 입력 아님)"""
        self._idle_timer.stop()
        self._set_ui_mode("AMBIENT")

    @Slot()
    def goSeats(self):
        """좌석 버튼 — ACTIVE + 좌석 선택(SEAT_OVERVIEW). (입력 → 타이머 리셋)"""
        self._register_activity()          # AMBIENT면 ACTIVE 복귀 + 타이머 재시작
        self._set_screen("SEAT_OVERVIEW")

    @Slot()
    def goModes(self):
        """모드 버튼 — ACTIVE + 모드 선택(MODE_SELECT). (입력 → 타이머 리셋)"""
        self._register_activity()
        self._set_screen("MODE_SELECT")

    def _on_idle_timeout(self):
        """10초 무입력 경과. 기어 P 일 때만 AMBIENT 진입(주행/후진 중 대기 방지)."""
        if self._gear != "P":
            # 주행/후진 중 — 대기 미진입. 다음 기회를 위해 타이머만 재무장.
            self._idle_timer.start(IDLE_TIMEOUT_MS)
            return
        self._set_ui_mode("AMBIENT")

    # =====================================================================
    # selected_seat 및 현재좌석 파생 Property (SEAT_DETAIL이 binding으로 사용)
    # =====================================================================
    def _get_selected_seat(self):
        return self._selected_seat

    selectedSeat = Property(str, _get_selected_seat, notify=selectedSeatChanged)

    def _get_cur_seat_label(self):
        return SEAT_LABELS[self._selected_seat]

    curSeatLabel = Property(str, _get_cur_seat_label, notify=selectedSeatChanged)

    def _get_cur_is_front(self):
        return self._selected_seat in FRONT_SEATS

    curIsFront = Property(bool, _get_cur_is_front, notify=selectedSeatChanged)

    def _get_cur_axis2_name(self):
        return "회전" if self._selected_seat in FRONT_SEATS else "슬라이드"

    curAxis2Name = Property(str, _get_cur_axis2_name, notify=selectedSeatChanged)

    def _get_cur_axis2_max(self):
        return 180 if self._selected_seat in FRONT_SEATS else 100

    curAxis2Max = Property(int, _get_cur_axis2_max, notify=selectedSeatChanged)

    # 슬라이더가 바인딩하는 "목표값(target)" — 선택 좌석 기준.
    def _get_cur_recline_target(self):
        return self._seat_values[self._selected_seat]["recline"]["target"]

    curReclineTarget = Property(int, _get_cur_recline_target,
                                notify=seatValuesChanged)

    def _get_cur_axis2_target(self):
        return self._seat_values[self._selected_seat]["axis2"]["target"]

    curAxis2Target = Property(int, _get_cur_axis2_target,
                              notify=seatValuesChanged)

    # "적용" 버튼 활성/강조 판단 — 목표≠현재면 dirty(아직 적용 안 함).
    def _get_cur_recline_dirty(self):
        ax = self._seat_values[self._selected_seat]["recline"]
        return ax["target"] != ax["current"]

    curReclineDirty = Property(bool, _get_cur_recline_dirty,
                               notify=seatValuesChanged)

    def _get_cur_axis2_dirty(self):
        ax = self._seat_values[self._selected_seat]["axis2"]
        return ax["target"] != ax["current"]

    curAxis2Dirty = Property(bool, _get_cur_axis2_dirty,
                             notify=seatValuesChanged)

    # --- 3D 캐빈이 구독하는 좌석별 "현재값(current)" 전체 맵 ---
    # 각 Seat3D 가 seatPose["<seat>"].recline / .axis2 로 자기 값만 바인딩한다.
    # current = "적용" 후 보간된 실제 위치(= 3D가 따라가는 값, target 아님).
    def _get_seat_pose(self):
        return {
            seat: {
                "recline": ax["recline"]["current"],
                "axis2":   ax["axis2"]["current"],
            }
            for seat, ax in self._seat_values.items()
        }

    seatPose = Property("QVariantMap", _get_seat_pose, notify=seatValuesChanged)

    # --- 슬라이더 setter (목표값만 변경, 3D는 아직 움직이지 않음) ---
    @Slot(int)
    def setReclineTarget(self, value):
        self._register_activity()
        ax = self._seat_values[self._selected_seat]["recline"]
        value = int(value)
        if ax["target"] == value:
            return
        ax["target"] = value
        self.seatValuesChanged.emit()

    @Slot(int)
    def setAxis2Target(self, value):
        self._register_activity()
        ax = self._seat_values[self._selected_seat]["axis2"]
        value = int(value)
        if ax["target"] == value:
            return
        ax["target"] = value
        self.seatValuesChanged.emit()

    # --- 3D 캐빈이 구독하는 좌석별 "이동(보간) 중" 상태 맵 (목표 4: 시각 피드백) ---
    def _seat_moving_map(self):
        moving = {seat: False for seat in SEAT_LABELS}
        # 뒷좌석 슬라이드(open-loop) 로컬 트윈 진행 중
        for (seat, _axis) in self._tweens:
            moving[seat] = True
        # closed-loop 축: 송신한 commanded 까지 수신 current 가 아직 도달 못함 = 이동중
        #   recline(전 좌석) + 앞좌석 회전(axis2)
        for seat, ax in self._seat_values.items():
            if ax["recline"]["current"] != ax["recline"]["commanded"]:
                moving[seat] = True
            if self._axis2_closed_loop(seat) and \
                    ax["axis2"]["current"] != ax["axis2"]["commanded"]:
                moving[seat] = True
        return moving

    def _get_seat_moving(self):
        return self._seat_moving_map()

    seatMoving = Property("QVariantMap", _get_seat_moving, notify=seatMovingChanged)

    def _any_seat_moving(self):
        """좌석 중 하나라도 이동(보간) 중이면 True — 배치 완료 판정에 사용."""
        return any(self._seat_moving_map().values())

    def _check_drive_settle(self):
        """주행 모드 선택 후 좌석이 전부 배치되면 대기(홈, AMBIENT)로 자동 이동.

        selectMode(주행)에서 켠 _drive_settle_pending 을 조건으로, 좌석 이동이 모두
        끝난 순간(어떤 좌석도 이동 중이 아님) 한 번만 홈으로 넘어간다.
        좌석 이동 완료 시점마다(트윈 tick / Seat_Status 수신) 호출된다.
        """
        if not self._drive_settle_pending:
            return
        if self._any_seat_moving():
            return
        self._drive_settle_pending = False
        print("MODE(주행): 좌석 배치 완료 → 대기(홈) 자동 이동")
        self._idle_timer.stop()
        self._set_ui_mode("AMBIENT")

    # =====================================================================
    # CAN 수신 → 디지털 트윈 갱신 (RX 스레드에서 QueuedConnection 으로 호출됨 = GUI 스레드 안전)
    # =====================================================================
    @Slot(str, int, int, bool)
    def onSeatStatus(self, seat, recline, rotate, pinch):
        """*_Seat_Status 수신 → 디지털 트윈 현재포즈 + 끼임 경고를 GUI 에 반영.

        · recline           : 전 좌석 closed-loop — current ← Curr_*_Recline.
        · rotate(앞좌석만)  : closed-loop — axis2.current ← Curr_*_Rotate. (rotate<0=피드백 없음)
        · 뒷좌석 슬라이드    : 피드백 없음 → 여기서 건드리지 않음(open-loop 트윈 유지).

        ※ CanHub.seatStatusReceived 에 QueuedConnection 으로 연결 → 반드시 GUI 스레드 실행.
           RX 스레드가 직접 Property 를 건드리지 않는다(스레드 안전).
        """
        if seat not in self._seat_values:
            return
        changed = False
        r = self._seat_values[seat]["recline"]
        if r["current"] != recline:
            r["current"] = recline
            changed = True
        # 앞좌석 회전 closed-loop 반영(rotate>=0 일 때만; 뒷좌석은 -1)
        if rotate >= 0 and self._axis2_closed_loop(seat):
            a = self._seat_values[seat]["axis2"]
            if a["current"] != rotate:
                a["current"] = rotate
                changed = True
        if changed:
            self.seatValuesChanged.emit()   # 3D 트윈(seatPose)·dirty 갱신
            self.seatMovingChanged.emit()   # commanded 도달 여부(이동중) 갱신
        if self._pinch.get(seat) != bool(pinch):
            self._pinch[seat] = bool(pinch)
            if pinch:
                print(f"PINCH: {SEAT_LABELS[seat]} 끼임 감지!")
            self.pinchChanged.emit()
        # 주행 모드 좌석 배치 완료 시 홈 자동 이동(closed-loop 축이 commanded 에 도달한 시점).
        self._check_drive_settle()

    # --- 레이싱휠 → 화면 즉각 반영 (인터록과 무관, 항상) ---
    @Slot(int, int, int)
    def onWheelInput(self, steering_deg, throttle, brake):
        """휠 스레드(WheelInput.wheelInput)에서 QueuedConnection 으로 호출 = GUI 스레드 안전.

        문서 §5.2: 휠을 돌리면 인터록과 무관하게 HMI 조향 표시가 즉각 따라온다.
        """
        changed = False
        if self._wheel_steer != steering_deg:
            self._wheel_steer = steering_deg
            changed = True
        if self._wheel_throttle != throttle:
            self._wheel_throttle = throttle
            changed = True
        if self._wheel_brake != brake:
            self._wheel_brake = brake
            changed = True
        if changed:
            self.wheelInputChanged.emit()

    @Slot(float, int, int)
    def onDriveStatus(self, velocity_rpm, motor_mA, gear):
        """Drive_Status 수신: 현재 속도(RPM)를 HMI 에 반영(GEAR 옆 표시)."""
        if self._current_velocity != velocity_rpm:
            self._current_velocity = velocity_rpm
            self.driveStatusChanged.emit()

    # --- 끼임(Pinch) Property: QML 은 seatPinch[<seat>] 로 바인딩 ---
    def _get_seat_pinch(self):
        return dict(self._pinch)

    seatPinch = Property("QVariantMap", _get_seat_pinch, notify=pinchChanged)

    def _get_any_pinch(self):
        return any(self._pinch.values())

    anyPinch = Property(bool, _get_any_pinch, notify=pinchChanged)

    # --- Drive_Status: 현재 속도(RPM) ---
    def _get_current_velocity(self):
        return self._current_velocity

    currentVelocity = Property(float, _get_current_velocity,
                               notify=driveStatusChanged)

    # --- 레이싱휠 실시간 입력 Property (QML 조향 표시가 바인딩) ---
    def _get_wheel_steer(self):
        return self._wheel_steer

    wheelSteering = Property(int, _get_wheel_steer, notify=wheelInputChanged)

    def _get_wheel_throttle(self):
        return self._wheel_throttle

    wheelThrottle = Property(int, _get_wheel_throttle, notify=wheelInputChanged)

    def _get_wheel_brake(self):
        return self._wheel_brake

    wheelBrake = Property(int, _get_wheel_brake, notify=wheelInputChanged)

    # --- 휠 스레드가 읽는 주행-가능 인터록 (기어 D/R 진입은 DRIVE_MODE 에서만 허용됨) ---
    def drive_enabled(self):
        return self._gear in ("D", "R")

    # --- "적용" — 여기서 CAN 송신(현재는 print) + current를 target까지 트윈 ---
    @Slot()
    def applyRecline(self):
        self._register_activity()
        self._commit_axis(self._selected_seat, "recline")

    @Slot()
    def applyAxis2(self):
        self._register_activity()
        self._commit_axis(self._selected_seat, "axis2")

    # --- 안전 인터록: 좌석 Cmd 를 실제로 보내도 되는가 (단방향: 입력→인터록→CAN) ---
    def _seat_cmd_approved(self, seat):
        """주행/후진(기어 D/R) 중에는 좌석 액추에이터 명령 금지. reject 시 송신 안 함."""
        if self._gear in ("D", "R"):
            return False
        return True

    def _send_seat(self, seat):
        """선택 좌석의 현재 target(recline + axis2)을 *_Seat_Cmd 로 encode→can0 송신.

        좌석 Cmd 는 한 프레임에 두 축을 모두 싣는다(DBC 구조). CanHub.SEAT_CMD_DEF 가
        좌석키→메시지/시그널을 매핑한다. CAN 미연결 시 콘솔로 폴백.
        """
        recline = self._seat_values[seat]["recline"]["target"]
        axis2 = self._seat_values[seat]["axis2"]["target"]
        if self._can:
            self._can.send_seat_cmd(seat, recline, axis2)
        else:
            name = "회전" if seat in FRONT_SEATS else "슬라이드"
            print(f"[NO-CAN] SEAT_CMD {SEAT_LABELS[seat]} 리클라인={recline} {name}={axis2}")

    def _axis2_closed_loop(self, seat):
        """앞좌석 회전 = Curr_*_Rotate 피드백 있음(closed-loop). 뒷좌석 슬라이드 = 없음(open-loop)."""
        return seat in FRONT_SEATS

    def _mark_commit(self, seat, axis):
        """송신 후 트윈 시각화 처리. closed-loop 축은 commanded 만 갱신(status 추종),
        open-loop 축(뒷좌석 슬라이드)은 로컬 트윈 시작."""
        if axis == "recline" or self._axis2_closed_loop(seat):
            ax = self._seat_values[seat][axis]
            ax["commanded"] = ax["target"]      # status 도달 전까지 '이동중'
        else:
            self._start_tween(seat, axis)        # 뒷좌석 슬라이드: current==target 이면 no-op

    def _commit_axis(self, seat, axis):
        """적용: 인터록 통과 시 *_Seat_Cmd 송신. (reject 면 송신/이동 없음)

        좌석 Cmd 는 recline+axis2 를 한 프레임에 모두 싣는다.
        · recline         : 항상 closed-loop — 수신 Curr_*_Recline 로 current 갱신.
        · axis2(앞=회전)  : closed-loop — 수신 Curr_*_Rotate 로 current 갱신.
        · axis2(뒤=슬라이드): open-loop — 피드백 없어 로컬 트윈으로 시각화.
        """
        if not self._seat_cmd_approved(seat):
            print(f"BLOCKED(seat): 주행/후진 중 좌석 변경 거부 ({SEAT_LABELS[seat]})")
            return
        self._send_seat(seat)
        self._mark_commit(seat, axis)
        self.seatMovingChanged.emit()

    def _apply_mode_preset(self, mode):
        """모드 프리셋 값으로 4개 좌석 target 세팅 후 즉시 적용. 미포함 좌석/축은 유지."""
        preset = MODE_PRESETS.get(mode)
        if not preset:
            return
        for seat, axes in preset.items():
            for axis, value in axes.items():
                self._seat_values[seat][axis]["target"] = int(value)
            if not self._seat_cmd_approved(seat):
                continue
            # 좌석당 한 번만 송신(두 축 한 프레임). 두 축 모두 커밋 처리.
            self._send_seat(seat)
            self._mark_commit(seat, "recline")
            self._mark_commit(seat, "axis2")
        self.seatValuesChanged.emit()   # SEAT_DETAIL 슬라이더/dirty 즉시 갱신
        self.seatMovingChanged.emit()

    # =====================================================================
    # 적용 트윈 (current → target, 부드러운 ease-in-out)
    # =====================================================================
    def _start_tween(self, seat, axis):
        ax = self._seat_values[seat][axis]
        if ax["current"] == ax["target"]:
            return                      # 이미 목표 위치 — 할 일 없음
        # 진행 중이면 현재 위치에서 다시 시작(이어서 부드럽게).
        self._tweens[(seat, axis)] = {
            "start": ax["current"],
            "target": ax["target"],
            "elapsed": 0,
        }
        if not self._tween_timer.isActive():
            self._tween_timer.start()
        self.seatMovingChanged.emit()   # 이동중 표시 갱신

    @staticmethod
    def _ease_in_out(t):
        # cubic ease-in-out: 시작/끝이 부드럽다.
        if t < 0.5:
            return 4 * t * t * t
        f = -2 * t + 2
        return 1 - (f * f * f) / 2

    def _on_tween_tick(self):
        done = []
        for key, tw in self._tweens.items():
            tw["elapsed"] += TWEEN_INTERVAL_MS
            frac = min(1.0, tw["elapsed"] / TWEEN_DURATION_MS)
            seat, axis = key
            if frac >= 1.0:
                self._seat_values[seat][axis]["current"] = tw["target"]
                done.append(key)
            else:
                eased = self._ease_in_out(frac)
                val = tw["start"] + (tw["target"] - tw["start"]) * eased
                self._seat_values[seat][axis]["current"] = int(round(val))
        for key in done:
            del self._tweens[key]
        if not self._tweens:
            self._tween_timer.stop()
        if done:
            self.seatMovingChanged.emit()   # 도착한 좌석 이동중 표시 해제
            # 주행 모드 좌석 배치 완료(뒷좌석 슬라이드 트윈 종료) 시 홈 자동 이동.
            self._check_drive_settle()
        self.seatValuesChanged.emit()
