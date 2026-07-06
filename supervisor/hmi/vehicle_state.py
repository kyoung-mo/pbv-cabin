"""VehicleState — 차량 HMI의 단일 상태 객체 (single source of truth).

스텝2: 실제 can0 양방향 연동.
  · 입력(슬라이더/모드/적용/기어) → 안전 인터록 통과 시에만 CanHub 로 encode→send.
  · 디지털 트윈의 "현재 recline 포즈"는 로컬 트윈이 아니라 **수신한 Seat_Status**로만
    갱신한다(onSeatStatus). 더미 ECU(또는 실물 ECU)가 보내는 Curr_*_Recline 을 따라간다.
      └ 회전(앞 Curr_*_Rotate)은 실시간 closed-loop. 슬라이드(뒤 Curr_*_Slide)는 이동 중
        상태 기아로 '완료 후 1회' 실측이 와서, open-loop 트윈을 그 시점에 실측으로 스냅한다.
  · QML은 이 객체의 Property에 binding으로만 그리며, 입력은 @Slot setter만 호출한다.
  · CanHub 가 None(셀프테스트/CAN 미연결)이면 송신부는 콘솔 출력으로 폴백한다.
"""

import time

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

# 기어 → CAN GearStatus(0x070) Gear 값 인코딩. 슬라이더 위치(GEARS: R-P-D)와는 별개인 CAN 전송 값.
#   ECU 합의는 D=1(전진)/R=2(후진)이었으나, 실제 Drive_ECU 가 회전 방향을 반대로 구현해
#   D=1→후진, R=2→전진으로 동작한다. 펌웨어를 안 고치고 supervisor 에서 보정하기 위해
#   D/R 코드를 맞바꿔 쏜다 → D=전진, R=후진. (P=0 중립은 그대로.)
GEAR_CAN_VALUE = {"P": 0, "D": 2, "R": 1}

# 주행(DRIVE) 모드 식별자 — 기어 D/R 진입을 허용하는 유일한 모드
DRIVE_MODE = "주행"

# "적용" 트윈 — current(3D 실제 위치)가 target(목표)까지 가는 시간/틱 간격(ms)
TWEEN_DURATION_MS = 1200
TWEEN_INTERVAL_MS = 16

# 대기(AMBIENT) 진입 — 이 시간(ms) 동안 "입력"이 없으면 대기 모드로. (기어 조작은 입력 제외)
IDLE_TIMEOUT_MS = 10000

# ── 뒷좌석 슬라이드 호밍/센티넬 (리어 ECU slide4 정본 기준) ──────────────────────
#   slide4 는 부팅 호밍이 꺼져 있어(SLIDE_HOMING=0) 전원 시 놓인 위치를 그냥 0으로 간주한다.
#   → 절대위치(0~100mm)를 쓰기 전에 반드시 254(호밍)로 물리 원점을 잡아야 한다(이게 없으면
#     "리니어가 엉뚱하게 움직인다"는 증상이 난다).
#   254=호밍(오른쪽 끝=운전석쪽으로 밀어 그 위치를 0), 255=재영점(현재 위치를 0으로, 이동 없음).
#   253(HOLD)은 slide4 미구현이라 supervisor 는 쓰지 않는다 — 슬라이드를 '유지'하려면 현재
#     절대위치를 그대로 재전송한다(target==현재 → ECU 가 안 움직임). 그래서 리클라인만 바꿔도
#     슬라이드는 (호밍만 돼 있으면) 안 움직인다.
SLIDE_HOME_CMD = 254
SLIDE_REZERO_CMD = 255
# 뒷좌석 슬라이드 '상태' 센티넬(명령이 아니라 수신 Curr_*_Slide 값).
#   리어 ECU(slide.c:302 slide_report_pos_mm)는 원점 확정(homed) 전에는 실제 위치 대신
#   255(0xFF)를 보고한다 → 255 = 원점 미확정(호밍 필요), 0~100 = 실측 위치(mm).
#   DBC range 가 [0|100]이어도 cantools decode 는 클램프를 안 해 255 가 그대로 들어온다.
SLIDE_POS_UNKNOWN = 255
REAR_SEATS = ("rear_left", "rear_right")
# 원점 정렬은 사용자 확인 스텝으로 진행한다(자동 완료판정 X):
#   왼쪽 정렬(자동 시작) → [확인] → 오른쪽 정렬 → [확인] → 주행 자세 원복.
#   호밍이 ~2분 걸리고 방향(오른쪽 끝=앞쪽)도 눈으로 봐야 하므로, 사람이 보고 단계를 넘긴다.

# 뒷좌석 슬라이드 실측 이동 속도 ≈ 3mm/s(slide4 STEP_MIN_US=800, 가속 포함). 트윈(3D) 시간을
#   이 값으로 잡으면 ① 3D 가 실물과 동기 ② rear_left 슬라이드가 '진짜로' 끝난 뒤에야 rear_right
#   가 나가서 **두 리니어 액추에이터가 동시에 움직이지 않는다**(하드웨어 제약: 양쪽 동시 구동 금지).
#   실측보다 살짝 느리게(보수적) 잡아 겹침을 확실히 막는다.
SLIDE_MS_PER_MM = 450       # ≈2.2mm/s (실측 ~3mm/s 보다 느리게 = 안전여유)
SLIDE_MOVE_MARGIN_MS = 800  # 가속/정지 여유(고정)

# ── 뒷좌석 슬라이드 직렬화(두 리니어 동시 구동 절대 금지) ────────────────────────
#   시간 추정만으로는 실물(부하로 느려짐)에서 겹칠 수 있어, 실제 ECU 상태로 완료를 판정한다.
#   이동 중엔 리어 상태(0x220/0x221) 송신이 끊기고(MotionTask tight-loop 가 StatusTask 기아),
#   완료되면 재개된다 → 명령 후 가드 시간 지난 뒤 처음 들어온 리어 상태 = 완료. 타이머는 폴백.
SLIDE_DONE_GUARD_MS = 700      # 명령 직후 이 시간 내 리어 상태는 '이동 시작 전 잔여'로 무시
SLIDE_MOVE_TIMEOUT_MS = 70000  # 폴백: 최악 풀스트로크(~50s, 부하 시) + 여유. 상태 못 잡을 때만

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
    estopChanged = Signal()       # 좌석 과전류 긴급정지 상태 집합이 바뀜
    homingChanged = Signal()      # 뒷좌석 슬라이드 호밍(원점 정렬) 진행 상태가 바뀜
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
        # 뒷좌석 슬라이드 직렬화 상태(두 리니어 동시 구동 금지).
        #   _slide_busy : 현재 구동 중인 좌석('rear_left'/'rear_right') 또는 None.
        #   _slide_queue: 구동 대기 좌석 목록. busy 가 완료되면 큐에서 다음을 시작.
        #   완료 판정 = 리어 상태 재개(정확) + 데드라인 타임아웃(폴백).
        self._slide_busy = None
        self._slide_queue = []
        self._slide_started = 0.0     # busy 명령 시각(ms) — 상태재개 가드용
        self._slide_deadline = 0.0    # busy 타임아웃 시각(ms)
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
        # 좌석별 과전류 긴급정지(각 좌석 과전류 센서 → 긴급정지). CAN 수신 방식 미정 →
        #   지금은 setSeatEstop(seat, on) 슬롯으로만 세팅(테스트/후속 CAN 배선 훅).
        self._estop = {seat: False for seat in SEAT_LABELS}
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

        # 뒷좌석 슬라이드 원점(호밍) 상태 — 사용자 확인 스텝 시퀀스.
        #   _rear_homed: 축별 물리 원점 확정 여부.
        #   _home_seq  : "" (없음) / "left" (왼쪽 정렬 중) / "right" (오른쪽 정렬 중).
        #                확인 버튼(confirmHomingStep)으로 다음 단계 진행.
        self._rear_homed = {seat: False for seat in REAR_SEATS}
        self._home_seq = ""
        # 원점 정렬 후 주행 자세 원복이 끝나면 모드 선택 화면으로 넘어가기 위한 플래그.
        self._post_home_to_modes = False
        # 뒷좌석 슬라이드 직렬화 완료 폴백 타이머(상태 재개를 못 잡을 때만 사용).
        self._slide_timer = QTimer(self)
        self._slide_timer.setInterval(200)
        self._slide_timer.timeout.connect(self._slide_poll)

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
        # 인터록: 원점 정렬(호밍) 중에는 모드 변경 불가(명령 겹침 방지).
        if self._home_seq:
            print("BLOCKED: 원점 정렬 중이라 모드 변경 불가")
            return
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
        """기어를 제외한 '입력'마다 호출 — AMBIENT면 깨우기.

        10초 무입력 자동 홈(AMBIENT) 전환은 비활성화됨(사용자 요청): 좌석 이동 도중 홈으로
        튀는 것을 막기 위해 무입력 타이머를 더 이상 무장하지 않는다. 홈 전환은 홈 버튼 등 수동만.
        """
        # 사용자가 직접 조작하면 주행 모드 '자동 대기 이동'은 취소(원치 않는 홈 이동 방지).
        self._drive_settle_pending = False
        if self._ui_mode == "AMBIENT":
            self._set_ui_mode("ACTIVE")

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
        """(비활성) 10초 무입력 자동 홈(AMBIENT) 전환 — 사용자 요청으로 끔.

        무입력 타이머를 더 이상 시작하지 않으므로 호출되지 않는다. 되살리려면
        _register_activity 에서 self._idle_timer.start(IDLE_TIMEOUT_MS) 를 복구하고
        아래 본문을 원래대로 되돌리면 된다.
        """
        return

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
        # 뒷좌석 슬라이드 원점 정렬 진행 중인 축(왼쪽/오른쪽 순차)
        if self._home_seq == "left":
            moving["rear_left"] = True
        elif self._home_seq == "right":
            moving["rear_right"] = True
        # 뒷좌석 슬라이드 직렬화: 구동 중 + 대기 중인 좌석
        if self._slide_busy:
            moving[self._slide_busy] = True
        for seat in self._slide_queue:
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
    @Slot(str, int, int, bool, int)
    def onSeatStatus(self, seat, recline, rotate, pinch, slide=-1):
        """*_Seat_Status 수신 → 디지털 트윈 현재포즈 + 끼임 경고를 GUI 에 반영.

        · recline           : 전 좌석 closed-loop — current ← Curr_*_Recline.
        · rotate(앞좌석만)  : closed-loop — axis2.current ← Curr_*_Rotate. (rotate<0=피드백 없음)
        · 뒷좌석 슬라이드    : Curr_*_Slide 피드백(0~100mm / 255=원점 미확정). 이동 완료 후
          재개되는 상태 프레임에서 실측값으로 axis2 트윈을 스냅(_apply_rear_slide_feedback).
          (slide<0 = 앞좌석/피드백 없음.)

        ※ CanHub.seatStatusReceived 에 QueuedConnection 으로 연결 → 반드시 GUI 스레드 실행.
           RX 스레드가 직접 Property 를 건드리지 않는다(스레드 안전).
        """
        if seat not in self._seat_values:
            return
        # 뒷좌석 슬라이드 직렬화 완료 판정: 구동 중엔 리어 상태가 끊겼다 완료 시 재개된다.
        #   가드 시간 지난 뒤 처음 들어온 리어(0x220/0x221) 상태 = 현재 슬라이드 완료 → 다음 시작.
        if self._slide_busy is not None and seat in REAR_SEATS:
            if time.monotonic() * 1000.0 - self._slide_started >= SLIDE_DONE_GUARD_MS:
                self._finish_rear_slide("상태재개")
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
        # 뒷좌석 슬라이드 위치 피드백(closed-loop 스냅) — 255=미확정 / 0~100=실측 mm.
        if seat in REAR_SEATS and slide >= 0:
            if self._apply_rear_slide_feedback(seat, slide):
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
        self._check_post_home()   # 원점 정렬 후 원복 완료 시 모드 선택 화면으로

    def _apply_rear_slide_feedback(self, seat, slide):
        """뒷좌석 Curr_*_Slide 수신 처리. 반환: 트윈(current)이 실제로 바뀌었으면 True.

        펌웨어는 이동 중엔 상태를 못 보내고(MotionTask 기아) 완료 후 재개하며 그 프레임에
        '도착 위치'를 싣는다 — 그래서 여기 오는 slide 는 사실상 '정지한 실측 위치'다.
          · 255(SLIDE_POS_UNKNOWN) = 원점 미확정 → homed 해제, 위치는 무시(스냅 안 함).
          · 0~100 = 실측 mm → homed 확정 + axis2.current 를 실측으로 스냅(open-loop 추정 보정).

        스냅은 current 만 한다(옵션 A): 사용자가 슬라이더로 둔 target 은 유지한다. 과부하로
        목표에 못 미쳐 멈추면 target≠current 라 'dirty(적용 필요)'가 떠 '덜 갔음'을 그대로 알린다.
        """
        # 원점 정렬 시퀀스 중엔 호밍 로직(_mark_home_done)이 트윈을 직접 관리 → 스냅은 비켜준다.
        if self._home_seq:
            return False
        if slide == SLIDE_POS_UNKNOWN:
            # 원점 미확정 통보(부팅~호밍 전). 위치값 아님 → 트윈 건드리지 않음.
            if self._rear_homed.get(seat):
                self._rear_homed[seat] = False
            return False
        # 0~100 실측 위치 = 원점 확정된 상태.
        self._rear_homed[seat] = True
        # 구동 시작 직후 가드 내 프레임은 '이동 시작 전 잔여 위치'일 수 있어 스냅 보류
        #   (완료판정과 동일 가드 — 실제 도착 프레임은 가드 이후에 재개된다).
        if self._slide_busy == seat and \
                time.monotonic() * 1000.0 - self._slide_started < SLIDE_DONE_GUARD_MS:
            return False
        ax = self._seat_values[seat]["axis2"]
        if ax["current"] == slide:
            return False   # 유휴 중 동일 위치 반복 수신 — 무변화
        # 진행 중이던 open-loop 트윈이 있으면 취소(실측이 진실).
        self._tweens.pop((seat, "axis2"), None)
        ax["current"] = int(slide)
        return True

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

    def _get_pinch_prompt(self):
        """끼임(과전류) 오버레이 안내문 — 현재 끼인 좌석 이름 + 해제 방법."""
        seats = [SEAT_LABELS[s] for s, on in self._pinch.items() if on]
        if not seats:
            return ""
        return (f"{', '.join(seats)} 좌석에서 과도한 힘(과전류)이 감지됐습니다.\n"
                "장애물을 치운 뒤 [확인]을 누르면 해제됩니다.")

    pinchPrompt = Property(str, _get_pinch_prompt, notify=pinchChanged)

    @Slot(str)
    def resolvePinch(self, seat=""):
        """끼임(과전류) 확인/해제: 끼인 좌석에 현재 target 을 재송신해 펌웨어 끼임 래치를 푼다.

        slide4(main.c)는 새 *_Seat_Cmd 를 받으면 '끼임 해소'로 보고 pinch 래치를 해제한다.
        (과전류 = 끼임 — 별개 상태가 아님.) 장애물이 남아 있으면 다음 상태프레임에서 다시
        끼임으로 잡히므로(정상 재래치), 확인은 사실상 '재시도 + 경고 해제'다.
        seat="" 이면 현재 끼인 좌석 전체를 해제한다(오버레이 확인 버튼 경로).
        슬라이드 target 은 그대로라 재송신해도 리니어는 안 움직인다(래치만 풀림).
        """
        targets = [seat] if seat else [s for s, on in self._pinch.items() if on]
        changed = False
        for s in targets:
            if s not in self._pinch:
                continue
            if self._can and s in self._seat_values:
                self._send_seat(s)          # 새 명령 = 펌웨어 끼임 래치 해제
            if self._pinch.get(s):
                self._pinch[s] = False
                changed = True
                print(f"PINCH: {SEAT_LABELS[s]} 끼임 확인/해제 명령 전송")
        if changed:
            self.pinchChanged.emit()

    # --- 과전류 긴급정지(E-stop) Property/훅: QML 은 seatEstop[<seat>] 로 바인딩 ---
    #   과전류 → 해당 좌석 긴급정지 시 3D 좌석이 빨강~핑크로 깜빡인다(Seat3D.estop).
    #   CAN 수신 방식이 정해지면 그 디코드 지점에서 setSeatEstop(seat, on) 을 호출하면 된다.
    #   (예: onSeatStatus 에 과전류 비트 추가, 또는 SafeAbort Source_Id 매핑 등.)
    def _get_seat_estop(self):
        return dict(self._estop)

    seatEstop = Property("QVariantMap", _get_seat_estop, notify=estopChanged)

    def _get_any_estop(self):
        return any(self._estop.values())

    anyEstop = Property(bool, _get_any_estop, notify=estopChanged)

    @Slot(str, bool)
    def setSeatEstop(self, seat, on):
        """좌석 과전류 긴급정지 상태 세팅 훅(후속 CAN 배선/테스트에서 호출).

        seat: SEAT_LABELS 키('driver'/'passenger'/'rear_left'/'rear_right').
        """
        if seat not in self._estop:
            return
        if self._estop[seat] != bool(on):
            self._estop[seat] = bool(on)
            if on:
                print(f"E-STOP: {SEAT_LABELS[seat]} 과전류 긴급정지!")
            self.estopChanged.emit()

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

    def _send_seat(self, seat, slide_override=None):
        """선택 좌석의 현재 target(recline + axis2)을 *_Seat_Cmd 로 encode→can0 송신.

        좌석 Cmd 는 한 프레임에 두 축을 모두 싣는다(DBC 구조). CanHub.SEAT_CMD_DEF 가
        좌석키→메시지/시그널을 매핑한다. CAN 미연결 시 콘솔로 폴백.

        slide_override(뒷좌석 전용): 254=호밍/255=재영점 같은 raw 슬라이드 센티넬.
          can_hub 가 인코딩 후 슬라이드 바이트를 직접 덮어써 보낸다(DBC 무변경). byte0=리클라인
          target 은 그대로 실려 호밍/재영점 프레임에서도 서보가 0°로 튀지 않는다
          (slide4 규칙: recline 은 매 프레임 항상 적용).
        """
        recline = self._seat_values[seat]["recline"]["target"]
        axis2 = self._seat_values[seat]["axis2"]["target"]
        if self._can:
            self._can.send_seat_cmd(seat, recline, axis2, slide_raw=slide_override)
        else:
            name = "회전" if seat in FRONT_SEATS else "슬라이드"
            shown = slide_override if slide_override is not None else axis2
            print(f"[NO-CAN] SEAT_CMD {SEAT_LABELS[seat]} 리클라인={recline} {name}={shown}")

    def _axis2_closed_loop(self, seat):
        """앞좌석 회전 = Curr_*_Rotate 실시간 closed-loop. 뒷좌석 슬라이드 = 이동 중엔 open-loop
        트윈이고, Curr_*_Slide 는 '완료 후 1회'만 와 별도 경로(_apply_rear_slide_feedback)로
        스냅한다 → 실시간 추종이 아니므로 여기선 앞좌석만 True."""
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
        if self._home_seq:
            print(f"BLOCKED(seat): 원점 정렬 중 좌석 변경 거부 ({SEAT_LABELS[seat]})")
            return
        if not self._seat_cmd_approved(seat):
            print(f"BLOCKED(seat): 주행/후진 중 좌석 변경 거부 ({SEAT_LABELS[seat]})")
            return
        # 뒷좌석 슬라이드 이동은 직렬화 큐로만(두 리니어 동시 구동 금지).
        if axis == "axis2" and seat in REAR_SEATS:
            self._enqueue_rear_slide(seat)
        else:
            self._send_seat(seat)
            self._mark_commit(seat, axis)
        self.seatMovingChanged.emit()

    def _apply_seat_cmd(self, seat):
        """좌석 1개의 현재 target 을 인터록 통과 시 송신 + 커밋(두 축 한 프레임)."""
        if not self._seat_cmd_approved(seat):
            return
        self._send_seat(seat)
        self._mark_commit(seat, "recline")
        self._mark_commit(seat, "axis2")

    # =====================================================================
    # 뒷좌석 슬라이드 직렬화 — 두 리니어 액추에이터 동시 구동 절대 금지.
    #   한 슬라이드가 구동 중이면 다른 슬라이드는 큐에서 대기하고, 완료(리어 상태 재개 감지
    #   또는 타임아웃)된 뒤에야 시작한다. 모드 변경/원복/수동 적용 모두 이 경로로만 슬라이드를 움직인다.
    # =====================================================================
    def _enqueue_rear_slide(self, seat):
        """뒷좌석 슬라이드 이동을 직렬화 큐에 넣는다(비어 있으면 즉시 시작)."""
        if seat == self._slide_busy or seat in self._slide_queue:
            return
        self._slide_queue.append(seat)
        self._pump_rear_slide()

    def _pump_rear_slide(self):
        """구동 중인 슬라이드가 없으면 큐에서 다음 좌석을 꺼내 시작."""
        if self._slide_busy is not None:
            return
        if not self._slide_queue:
            self._slide_timer.stop()
            return
        self._start_rear_slide(self._slide_queue.pop(0))

    def _start_rear_slide(self, seat):
        """뒷좌석 1개의 슬라이드 프레임(리클라인+슬라이드)을 실제 송신하고 busy 로 잠근다."""
        self._slide_busy = seat
        now = time.monotonic() * 1000.0
        self._slide_started = now
        self._slide_deadline = now + SLIDE_MOVE_TIMEOUT_MS
        self._send_seat(seat)                # recline + slide 한 프레임
        self._mark_commit(seat, "recline")   # 리클라인(closed-loop) commanded
        self._mark_commit(seat, "axis2")     # 슬라이드(open-loop) 3D 트윈 시작
        print(f"SLIDE: {SEAT_LABELS[seat]} 슬라이드 구동 시작(직렬화)")
        if not self._slide_timer.isActive():
            self._slide_timer.start()
        self.seatMovingChanged.emit()

    def _finish_rear_slide(self, reason):
        """현재 슬라이드 완료 → 다음 대기 좌석 시작(직렬). 완료 콜백들도 갱신."""
        seat = self._slide_busy
        if seat is None:
            return
        self._slide_busy = None
        print(f"SLIDE: {SEAT_LABELS[seat]} 슬라이드 완료({reason})")
        self.seatMovingChanged.emit()
        self._pump_rear_slide()          # 대기 중이면 다음 슬라이드 시작
        self._check_drive_settle()
        self._check_post_home()

    def _slide_poll(self):
        """폴백: 리어 상태 재개를 못 잡아도 데드라인 지나면 완료로 간주(직렬 멈춤 방지)."""
        if self._slide_busy is None:
            self._slide_timer.stop()
            return
        if time.monotonic() * 1000.0 >= self._slide_deadline:
            self._finish_rear_slide("타임아웃")

    # =====================================================================
    # 뒷좌석 슬라이드 호밍(원점 정렬) — slide4 는 부팅 호밍이 꺼져 있어 필수.
    #   사용자 확인 스텝: 왼쪽 정렬 → [확인] → 오른쪽 정렬 → [확인] → 주행 자세 원복.
    #   진행 중엔 homingActive=True → QML 오버레이가 화면을 잠그고 확인 버튼만 노출한다.
    # =====================================================================
    def _get_homing_active(self):
        return self._home_seq != ""

    homingActive = Property(bool, _get_homing_active, notify=homingChanged)

    def _get_homing_prompt(self):
        if self._home_seq == "left":
            return ("① 왼쪽 뒷좌석 슬라이드가 운전석 쪽 끝으로 이동합니다.\n"
                    "끝에 붙어 멈추면 아래 버튼을 누르세요 — 그 위치가 원점(0)이 됩니다.")
        if self._home_seq == "right":
            return ("② 오른쪽 뒷좌석 슬라이드가 운전석 쪽 끝으로 이동합니다.\n"
                    "끝에 붙어 멈추면 아래 버튼을 누르세요 — 그 위치가 원점(0)이 됩니다.")
        return ""

    homingPrompt = Property(str, _get_homing_prompt, notify=homingChanged)

    def _get_homing_confirm_text(self):
        if self._home_seq == "left":
            return "왼쪽 여기가 원점 · 오른쪽 진행 →"
        if self._home_seq == "right":
            return "오른쪽 여기가 원점 · 주행 자세로 →"
        return ""

    homingConfirmText = Property(str, _get_homing_confirm_text, notify=homingChanged)

    @Slot()
    def initFrontSeats(self):
        """앞좌석 초기 자세를 메인 제어기(supervisor)가 능동 송신: 리클라인 90° / 회전 0°.

        부팅 시 1회 호출(main.py). 앞좌석 ECU 가 자체 원점(0/0)에 있어도 supervisor 가
        목표 자세를 0x110(운전석)·0x111(조수석)로 쏴 실제 시트를 초기 위치로 맞춘다.
        운전석은 CanHub 가 Rolling_Counter/Checksum 을 채워 보낸다(체크섬 OK 여야 동작).
        주행/후진(D/R) 중에는 좌석 액추에이터 명령 금지라 스킵.
        """
        if self._gear in ("D", "R"):
            print("BLOCKED(front-init): 주행/후진 중 앞좌석 초기화 불가")
            return
        for seat in FRONT_SEATS:
            v = self._seat_values[seat]
            v["recline"]["target"] = v["recline"]["current"] = v["recline"]["commanded"] = 90
            v["axis2"]["target"] = v["axis2"]["current"] = v["axis2"]["commanded"] = 0
            self._send_seat(seat)
        print("INIT: 앞좌석 초기화 송신 — 리클라인 90° / 회전 0° (운전석 0x110 · 조수석 0x111)")

    @Slot()
    def homeRearSlides(self):
        """원점 정렬 시퀀스 시작(왼쪽부터). 앱 시작 자동 + '원점 잡기' 버튼에서 호출.

        · 주행/후진(D/R) 중 거부. · CAN 미연결(콘솔)이면 즉시 homed 처리하고 스킵.
        · 이후 진행은 confirmHomingStep(확인 버튼)이 담당한다(왼쪽→오른쪽→원복).
        """
        if self._gear in ("D", "R"):
            print("BLOCKED(home): 주행/후진 중 원점 정렬 불가")
            return
        if self._home_seq != "":
            return   # 이미 진행 중
        if self._can is None:
            for seat in REAR_SEATS:
                self._rear_homed[seat] = True
            print("HOME: CAN 없음 — 원점 정렬 건너뜀(콘솔 모드)")
            return
        self._rear_homed = {seat: False for seat in REAR_SEATS}
        self._home_seq = "left"
        self._send_seat("rear_left", slide_override=SLIDE_HOME_CMD)
        print("HOME: ① 왼쪽 뒷좌석 원점 정렬 시작(254) — 완료되면 확인 버튼")
        self.homingChanged.emit()
        self.seatMovingChanged.emit()

    def _mark_home_done(self, seat):
        """해당 좌석 원점 확정: 슬라이드 0(원점)으로 트윈 값도 맞춘다."""
        self._rear_homed[seat] = True
        ax = self._seat_values[seat]["axis2"]
        ax["current"] = 0
        ax["commanded"] = 0
        ax["target"] = 0

    @Slot()
    def confirmHomingStep(self):
        """오버레이 확인 버튼: 지금 끝에 붙어 멈춘 위치를 255(재영점)로 '여기가 0' 확정.

        255(REZERO)는 slide4 에서 '현재 위치=0 선언 + 진행 중이던 호밍(오버드라이브) 즉시 취소'다.
        그래서 확인을 누르는 순간 진동(오버드라이브 갈림)이 멈추고 원점이 그 자리에 고정된다.
          left  → 왼쪽 재영점 후 오른쪽을 끝으로 이동(254) 시작.
          right → 오른쪽 재영점 후 주행 자세로 원복(왼쪽 30 → 오른쪽 30 순차) → 모드 선택 화면.
        """
        if self._home_seq == "left":
            self._send_seat("rear_left", slide_override=SLIDE_REZERO_CMD)  # 여기가 0
            self._mark_home_done("rear_left")
            self._home_seq = "right"
            self._send_seat("rear_right", slide_override=SLIDE_HOME_CMD)   # 오른쪽 끝으로 이동
            print("HOME: 왼쪽 재영점(255) → ② 오른쪽 끝으로 이동 시작(254)")
            self.homingChanged.emit()
            self.seatValuesChanged.emit()
            self.seatMovingChanged.emit()
        elif self._home_seq == "right":
            self._send_seat("rear_right", slide_override=SLIDE_REZERO_CMD)  # 여기가 0
            self._mark_home_done("rear_right")
            self._home_seq = ""
            print("HOME: 오른쪽 재영점(255) → ③ 주행 자세로 원복")
            self.homingChanged.emit()
            self.seatValuesChanged.emit()
            self.seatMovingChanged.emit()
            self._restore_drive_pose()

    def _restore_drive_pose(self):
        """원점 정렬 완료 후 주행 자세로 원복(주행 프리셋을 4좌석에 적용).

        원점이 잡혀 있어 절대위치(뒷좌석 슬라이드 30mm 등)가 정확하게 나간다.
        뒷좌석 슬라이드는 왼쪽 30 → (완료) → 오른쪽 30 순차(두 리니어 동시 구동 금지).
        모든 좌석이 자리잡으면(_check_post_home) 모드 선택 화면으로 넘어간다.
        """
        self._cabin_mode = DRIVE_MODE
        self.cabinModeChanged.emit()
        self._post_home_to_modes = True
        self._apply_mode_preset(DRIVE_MODE)
        print("HOME: 주행 자세 원복(슬라이드 30) 순차 이동 시작 → 완료 시 모드 선택 화면")
        self._check_post_home()   # 이동이 없으면(이미 30) 즉시 넘어가도록

    def _check_post_home(self):
        """주행 자세 원복이 끝나면(호밍/보류/이동 전부 종료) 모드 선택 화면으로 전환."""
        if not self._post_home_to_modes:
            return
        if self._home_seq:
            return
        if self._any_seat_moving():
            return
        self._post_home_to_modes = False
        print("HOME: 주행 자세 원복 완료 → 모드 선택 화면")
        self._set_ui_mode("ACTIVE")
        self._set_screen("MODE_SELECT")

    def _apply_mode_preset(self, mode):
        """모드 프리셋 값으로 4개 좌석 target 세팅 후 적용. 미포함 좌석/축은 유지.

        뒷좌석 슬라이드는 "왼쪽 먼저 → 왼쪽 완료 후 오른쪽" 순서로 움직인다.
          · 먼저 모든 좌석 target 을 세팅한다.
          · 앞좌석 + rear_left 는 즉시 적용(송신/트윈 시작).
          · rear_right 는 rear_left 슬라이드 트윈이 진행 중이면 미뤄뒀다가
            그 트윈이 끝나는 순간(_on_tween_tick) 적용한다. (트윈이 없으면 즉시 적용)
        """
        preset = MODE_PRESETS.get(mode)
        if not preset:
            return
        # 1) 모든 좌석 target 먼저 세팅 (SEAT_DETAIL 슬라이더/dirty 즉시 반영용).
        for seat, axes in preset.items():
            for axis, value in axes.items():
                self._seat_values[seat][axis]["target"] = int(value)
        # 2) 앞좌석(회전/리클라인 — 동시 구동 제약 없음)은 즉시 적용.
        for seat in ("driver", "passenger"):
            if seat in preset:
                self._apply_seat_cmd(seat)
        # 3) 뒷좌석 슬라이드는 직렬화 큐로만(두 리니어 동시 구동 금지). 한쪽 완료 후 다른 쪽 시작.
        #    리클라인도 같은 프레임에 실려 나가므로 여기서 함께 처리된다.
        for seat in ("rear_left", "rear_right"):
            if seat in preset and self._seat_cmd_approved(seat):
                self._enqueue_rear_slide(seat)
        self.seatValuesChanged.emit()   # SEAT_DETAIL 슬라이더/dirty 즉시 갱신
        self.seatMovingChanged.emit()

    # =====================================================================
    # 적용 트윈 (current → target, 부드러운 ease-in-out)
    # =====================================================================
    def _start_tween(self, seat, axis):
        ax = self._seat_values[seat][axis]
        if ax["current"] == ax["target"]:
            return                      # 이미 목표 위치 — 할 일 없음
        # 뒷좌석 슬라이드(open-loop)는 실제 이동 시간(거리×속도)에 맞춰 트윈 시간을 잡는다.
        #   → rear_left 트윈이 실물 완료 시점에 끝나므로, 그때서야 나가는 rear_right 와 겹치지 않는다
        #     (두 리니어 동시 구동 금지). 그 외 축은 기존 기본 트윈 시간.
        if axis == "axis2" and seat in REAR_SEATS:
            dist = abs(ax["target"] - ax["current"])
            duration = int(dist * SLIDE_MS_PER_MM + SLIDE_MOVE_MARGIN_MS)
        else:
            duration = TWEEN_DURATION_MS
        # 진행 중이면 현재 위치에서 다시 시작(이어서 부드럽게).
        self._tweens[(seat, axis)] = {
            "start": ax["current"],
            "target": ax["target"],
            "elapsed": 0,
            "duration": max(1, duration),
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
            frac = min(1.0, tw["elapsed"] / tw["duration"])
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
            self._check_post_home()          # 원점 정렬 후 원복 완료 시 모드 선택 화면으로
        self.seatValuesChanged.emit()
