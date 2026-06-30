"""VehicleState — 차량 HMI의 단일 상태 객체 (single source of truth).

이 단계(스텝1)에서는 실제 CAN 송신을 하지 않는다.
모든 "CAN으로 보낼 자리"는 print()로 무엇을 보낼지만 콘솔에 출력한다.
QML은 이 객체의 Property에 binding으로만 그리며, 입력은 @Slot setter만 호출한다.
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

# 기어 슬라이드 인덱스: 아래(0)=R, 중앙(1)=P, 위(2)=D
GEARS = ("R", "P", "D")

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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gear = "P"
        self._cabin_mode = ""                  # 아직 미선택
        self._right_panel_screen = "MODE_SELECT"
        self._selected_seat = "driver"
        # 좌석별 각도값 (재진입해도 유지되도록 여기에만 저장).
        # 각 축은 target(목표) / current(3D가 실제로 가 있는 값) 두 개로 분리한다.
        #   · 슬라이더는 target 만 바꾼다(즉시 움직이지 않음).
        #   · "적용"을 누르면 current 가 target 까지 부드럽게 보간된다.
        #   · 3D 캐빈은 current 에 바인딩한다.
        #   recline: 0~180 (90=직립/정상착좌, 180=완전 뒤로 눕기, 0=앞으로 폴딩)
        #   axis2  : 앞좌석=회전 0~180, 뒷좌석=슬라이드 0~100
        def _axes(recline, axis2):
            return {
                "recline": {"target": recline, "current": recline},
                "axis2":   {"target": axis2,   "current": axis2},
            }
        # 앞좌석 axis2=회전(기본 0=정면). 뒷좌석 axis2=슬라이드(기본 30=여유 있는 정상
        # 착좌 위치; 0으로 당기면 앞쪽 최대 full-space, 100이면 뒤쪽 최대).
        self._seat_values = {
            "driver":     _axes(90, 0),
            "passenger":  _axes(90, 0),
            "rear_left":  _axes(90, 30),
            "rear_right": _axes(90, 30),
        }

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
        # 인터록: D/R로 변경은 "주행 모드 AND 현재 기어 P"일 때만 허용.
        # (한 칸 이동 규칙상 D/R로 가는 출발점은 항상 P이므로 모드만 확인하면 충분)
        if target in ("D", "R") and self._cabin_mode != DRIVE_MODE:
            print("BLOCKED: 주행 모드가 아니라 기어 변경 불가")
            self.gearChanged.emit()  # 슬라이더를 P로 되돌림
            return
        self._gear = target
        print(f"GEAR: {self._gear}")
        self.gearChanged.emit()

    @Slot()
    def gearBlockedNotice(self):
        """잠긴 기어 슬라이드를 눌렀을 때 QML이 호출 — 사유만 출력."""
        print("BLOCKED: 주행 모드가 아니라 기어 변경 불가")

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
    def toggleCarArea(self):
        """왼쪽 차량 영역 클릭:
        MODE_SELECT ↔ SEAT_OVERVIEW 토글, SEAT_DETAIL이면 MODE_SELECT로."""
        self._register_activity()
        if self._right_panel_screen == "MODE_SELECT":
            self._set_screen("SEAT_OVERVIEW")
        else:
            self._set_screen("MODE_SELECT")

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
    def _get_seat_moving(self):
        moving = {seat: False for seat in SEAT_LABELS}
        for (seat, _axis) in self._tweens:
            moving[seat] = True
        return moving

    seatMoving = Property("QVariantMap", _get_seat_moving, notify=seatMovingChanged)

    # --- "적용" — 여기서 CAN 송신(현재는 print) + current를 target까지 트윈 ---
    @Slot()
    def applyRecline(self):
        self._register_activity()
        self._commit_axis(self._selected_seat, "recline")

    @Slot()
    def applyAxis2(self):
        self._register_activity()
        self._commit_axis(self._selected_seat, "axis2")

    def _commit_axis(self, seat, axis):
        """target 확정(= CAN 송신 자리, SEAT_CMD print) + current→target 트윈 시작."""
        target = self._seat_values[seat][axis]["target"]
        if axis == "recline":
            print(f"SEAT_CMD: {SEAT_LABELS[seat]} 리클라인={target}")
        else:
            name = "회전" if seat in FRONT_SEATS else "슬라이드"
            print(f"SEAT_CMD: {SEAT_LABELS[seat]} {name}={target}")
        self._start_tween(seat, axis)

    def _apply_mode_preset(self, mode):
        """모드 프리셋 값으로 4개 좌석 target 세팅 후 즉시 적용(트윈). 미포함 좌석/축은 유지."""
        preset = MODE_PRESETS.get(mode)
        if not preset:
            return
        for seat, axes in preset.items():
            for axis, value in axes.items():
                self._seat_values[seat][axis]["target"] = int(value)
                self._commit_axis(seat, axis)
        self.seatValuesChanged.emit()   # SEAT_DETAIL 슬라이더/dirty 즉시 갱신

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
        self.seatValuesChanged.emit()
