"""wheel_input — 레이싱휠 → Drive_Cmd/기어 패들 주기 송신 + HMI 화면 즉각 반영.

**pygame.joystick** 기반(구 evdev 폐기). evdev 로 바꾼 뒤 페달 깊이(아날로그)를 인식하지
못하는 문제가 있어, 조향·엑셀·브레이크·기어봉이 모두 정상 동작하던 pygame 버전으로 되돌린다.
디스플레이 없이 초기화하기 위해 SDL_VIDEODRIVER=dummy 를 쓴다(Qt 와 무관, pygame 만 영향).

  [매핑 — jstest(js0) 실측 확정]
    · 조향   = axis 0,  범위 -1.0~1.0 (왼쪽 음수 / 오른쪽 양수).
               Steering_Angle = int(axis0 * 127), ±127 클램프(DBC 8bit signed). 데드밴드 |각도|<3°.
    · 페달   = axis 1 단일축(아날로그, 깊이 있음). 안 밟으면 0, 엑셀=음수쪽(0~-1.0),
               브레이크=양수쪽(0~+1.0).
        - axis1 < -deadband → throttle% = |axis1|*100 → Target_Velocity 에 비례(throttle%*3, 최대 300 RPM)
        - axis1 >  deadband → brake%    =  axis1 *100 → Brake_Depth(0~100)
        - 데드밴드 안 → throttle=0, brake=0. (median(5)+EMA(0.2) 평활)
    · 기어업 패들   = button 5 (모멘터리) → gearShift(+1)
    · 기어다운 패들 = button 4 (모멘터리) → gearShift(-1)
        - 버튼 0→1 상승엣지에서만 1회 전이(누르고 있어도 반복 안 함), 디바운스 포함.
        - 기어 상태 소유는 VehicleState(gearShift 슬롯이 0x070 송신 + 화면 동기).

  [송신 규칙]
    · drive ECU 는 Drive_Cmd 가 300ms 끊기면 비상정지 → 값 불변이어도 50ms 마다 무조건 송신.
    · 주행-가능 인터록(기어 D/R)일 때만 조향/엑셀/브레이크 실제 값 송신, P 면 중립(0,0,0).
    · 화면 반영(wheelInput 시그널)은 인터록과 무관하게 항상 emit. RX 스레드와 동일하게
      QueuedConnection 으로 GUI 스레드에 넘긴다(스레드 안전).
"""

import os
import statistics
import threading
import time
from collections import deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")   # pygame 만 영향(Qt 와 무관) — 디스플레이 불요
import pygame                                         # noqa: E402

from PySide6.QtCore import QObject, Signal            # noqa: E402


# ── 실측 확정 매핑 (jstest js0) ──────────────────────────────────────────────
STEER_AXIS = 0            # 조향축 = axis0 (-1.0~1.0, 왼쪽 음수 / 오른쪽 양수)
PEDAL_AXIS = 1            # 페달축 = axis1 단일축 (음수=엑셀 / 양수=브레이크)
GEAR_UP_BUTTON = 5        # 기어업 패들
GEAR_DOWN_BUTTON = 4      # 기어다운 패들

# ── 스케일/데드밴드 ─────────────────────────────────────────────────────────
STEER_SCALE = 127        # axis0(-1..1) * 127 — DBC Steering_Angle 8bit signed(±127 포화)
STEER_DEADBAND_DEG = 3   # |조향각| < 3° → 0
PEDAL_DEADBAND = 0.03    # |axis1| < 0.03 → 중립 (권장 0.02~0.05)
RPM_PER_PCT = 3          # throttle% → RPM (target_rpm = throttle*3)
RPM_MAX = 300            # Target_Velocity 상한(RPM)
BRAKE_MAX = 100          # Brake_Depth 풀스케일(%)

SEND_PERIOD = 0.05       # 50ms (≪ 300ms estop) — 값 불변에도 브로드캐스트

# 페달 평활: median(5) + EMA(0.2)
PEDAL_MEDIAN_WIN = 5
PEDAL_EMA_ALPHA = 0.20
# 조향 평활(가벼운): median(3) + EMA(0.4) — 반응성 우선
STEER_MEDIAN_WIN = 3
STEER_EMA_ALPHA = 0.40

GEAR_DEBOUNCE_S = 0.15   # 패들 채터링 가드(상승엣지 1회 전이 + 디바운스)

# ── 휠 장치 선택 규칙 ────────────────────────────────────────────────────────
# pygame 은 Joystick(0) 로 0번을 여는데, HDMI(로컬) 세션에선 0번이 터치패널
# (wch.cn USB2IIC_CTP_CONTROL, /dev/input/js0)이라 휠 대신 터치를 잡아 축/버튼이 전부 죽는다.
# SSH 세션에선 터치패널이 없어 휠이 0번으로 잡혀 정상 동작했다. 세션 무관하게 만들려면
# "0번 고정"이 아니라 "터치패널/IMU 를 배제하고 휠을 골라서" 열어야 한다.
#
# [실측 — 휠 모드에 따라 이름/축 수가 바뀜]
#   · P4X(정상) 모드   : 이름 'Generic X-Box pad',        axes=6  → 매핑 정확(조향=a0/페달=a1/패들=b4,5)
#   · 그 외(고장) 모드 : 이름 '. Steering Wheel Controller', axes=4  → 페달이 a2/a3 로 붙어 죽음
# 정상 동작하는 유일한 조건은 "터치패널/IMU 제외 + axes=6". 그래서 선택은 이름이 아니라
# "배제 후 axes=6 우선" 으로 한다(이름은 로그/보조 힌트로만).
WHEEL_NAME_EXCLUDE = ("usb2iic", "ctp", "touch", "imu")  # 터치패널/IMU 배제 키워드(필수)
WHEEL_NAME_HINT = ("x-box", "xbox", "steering wheel", "wheel", "pad")  # 휠일 가능성(보조)
WHEEL_MIN_AXES = 2   # 조향(axis0)+페달(axis1) 최소 요건
WHEEL_MODE_AXES = 6  # P4X 정상 모드 축 수 — 이 매핑이 맞는 유일한 모드(우선 선택 + 경고 기준)

# HDMI 세션에선 화면에 뜬 로그를 복붙할 수 없으므로, 조이스틱 스캔/선택 결과를
# 이 파일에도 남긴다. SSH(MobaXterm)에서 `cat` 으로 바로 확인 가능:
#   cat /home/pi/project/pbv-cabin/supervisor/hmi/wheel_scan.log
WHEEL_SCAN_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "wheel_scan.log")


class _Filter:
    """median(win) → EMA(alpha). 축 하나당 하나씩."""

    def __init__(self, win, alpha):
        self._buf = deque(maxlen=win)
        self._alpha = alpha
        self._ema = 0.0

    def reset(self):
        self._buf.clear()
        self._ema = 0.0

    def push(self, x):
        self._buf.append(x)
        med = statistics.median(self._buf)
        self._ema = self._alpha * med + (1.0 - self._alpha) * self._ema
        return self._ema


class WheelInput(QObject):
    # 휠 스레드 → GUI 스레드 (QueuedConnection): (조향각°, throttle%, brake%)
    wheelInput = Signal(int, int, int)
    # 휠 패들 기어 변속 엣지 → GUI 스레드: +1=업, -1=다운
    gearShift = Signal(int)

    def __init__(self, can_hub, drive_enabled_cb, parent=None):
        super().__init__(parent)
        self._can = can_hub
        self._enabled = drive_enabled_cb        # () -> bool (기어 D/R)
        self._running = False
        self._thread = None

        self._pedal_filter = _Filter(PEDAL_MEDIAN_WIN, PEDAL_EMA_ALPHA)
        self._steer_filter = _Filter(STEER_MEDIAN_WIN, STEER_EMA_ALPHA)

        # 패들 상승엣지 검출 + 디바운스
        self._btn_up_prev = False
        self._btn_down_prev = False
        self._last_shift = 0.0

        self._num_axes = 0
        self._num_buttons = 0

        self._js = self._open_and_probe()

    # ── 연결된 조이스틱을 이름으로 순회하며 "휠"을 골라 여는 선택기 ──────────
    #    (HDMI/SSH 세션마다 js0 주인이 달라지는 문제를 세션 무관하게 해결)
    @staticmethod
    def _select_wheel():
        # 스캔/선택 로그를 화면(print)과 파일 양쪽에 남긴다. HDMI 세션에선 복붙이
        # 안 되므로 SSH 에서 wheel_scan.log 를 읽어 어떤 장치를 골랐는지 확인한다.
        report = []

        def emit(line):
            print(line)
            report.append(line)

        def flush():
            try:
                with open(WHEEL_SCAN_LOG, "w") as f:
                    f.write("\n".join(report) + "\n")
            except Exception:
                pass   # 로그 파일 실패가 휠 동작을 막아선 안 됨

        count = pygame.joystick.get_count()

        # ── 연결된 조이스틱 전체 목록(인덱스 + 이름 + axes/buttons) ──
        candidates = []   # (idx, js, name, name_lower, axes, buttons)
        emit(f"WHEEL SCAN: 조이스틱 {count}개 감지")
        for idx in range(count):
            js = pygame.joystick.Joystick(idx)
            js.init()
            name = js.get_name().strip()
            axes = js.get_numaxes()
            buttons = js.get_numbuttons()
            emit(f"  [{idx}] '{name}'  axes={axes}  buttons={buttons}")
            candidates.append((idx, js, name, name.lower(), axes, buttons))

        # ── 배제 키워드(터치패널/IMU) 제거 — 이게 HDMI 세션의 핵심 방어 ──
        pool = [c for c in candidates
                if not any(k in c[3] for k in WHEEL_NAME_EXCLUDE)]
        if not pool:
            listing = "; ".join(f"[{c[0]}]'{c[2]}'(axes={c[4]})" for c in candidates) or "(없음)"
            emit("WHEEL PICK: 실패 — 배제 후 남은 장치 없음(터치패널/IMU만 연결됨)")
            flush()
            raise RuntimeError(
                f"레이싱휠을 찾지 못함 — 터치패널/IMU 만 잡힘. 연결된 조이스틱: {listing}. "
                f"휠 USB 연결/전원 확인.")

        # ── 선택: 배제 후, axes=6(P4X 정상 모드) 우선 → 이름 힌트 → 축 최다 ──
        #    P4X 정상 모드는 이름이 'Generic X-Box pad'/axes=6 이므로 이름에 의존하지 않고
        #    "axes=6" 을 최우선으로 고른다. HDMI 에서 터치패널은 이미 배제되어 안 잡힌다.
        def score(c):
            axes = c[4]
            has_hint = any(k in c[3] for k in WHEEL_NAME_HINT)
            return (axes != WHEEL_MODE_AXES,   # axes=6 먼저
                    not has_hint,               # 휠 이름 힌트 있는 것 먼저
                    -axes,                      # 그다음 축 많은 것
                    c[0])                       # 안정적 tie-break(인덱스)
        pool.sort(key=score)
        idx, js, name, _, axes, _ = pool[0]
        tag = "axes=6(P4X 정상)" if axes == WHEEL_MODE_AXES else f"axes={axes}(비정상 모드일 수 있음)"
        emit(f"WHEEL PICK: [{idx}] '{name}' → {tag} 선택")
        flush()
        return js

    # ── 디바이스 오픈 + 축/버튼 개수 probe + 매핑 검증 ────────────────────
    def _open_and_probe(self):
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            raise RuntimeError("레이싱휠(joystick)을 찾지 못함 — 연결된 조이스틱이 하나도 없음")

        js = self._select_wheel()

        self._num_axes = js.get_numaxes()
        self._num_buttons = js.get_numbuttons()

        # ── 시작 로그: 선택된 휠 이름 + 축/버튼 개수 + 매핑 ──
        print(f"WHEEL: '{js.get_name().strip()}'  "
              f"axes={self._num_axes}  buttons={self._num_buttons}")
        print(f"WHEEL MAP: 조향=axis{STEER_AXIS}  페달=axis{PEDAL_AXIS}  "
              f"기어업=btn{GEAR_UP_BUTTON}  기어다운=btn{GEAR_DOWN_BUTTON}")

        # ── 모드 경고: 이 매핑(조향=a0/페달=a1/패들=b4,5)은 휠이 P4X(D-INPUT,
        #    axes=6) 모드일 때만 맞다. 다른 모드면 axes 수가 달라 페달이 엉뚱한
        #    축에 붙어 조향/엑셀/브레이크가 죽는다. 축 수가 다르면 크게 경고한다.
        if self._num_axes != WHEEL_MODE_AXES:
            print(f"!! WHEEL 경고: axes={self._num_axes} (기대 {WHEEL_MODE_AXES}). "
                  f"휠 모드가 P4X(D-INPUT)가 아닐 수 있음 → 페달/기어가 안 먹으면 "
                  f"휠을 P4X 로 바꾸고 USB 재연결하라.")

        # ── 매핑 인덱스 범위 검증 ──
        need_axis = max(STEER_AXIS, PEDAL_AXIS)
        if self._num_axes <= need_axis:
            raise RuntimeError(
                f"휠 축 개수 부족: axes={self._num_axes} 이지만 axis{need_axis} 필요 "
                f"(조향=axis{STEER_AXIS}, 페달=axis{PEDAL_AXIS})")
        need_btn = max(GEAR_UP_BUTTON, GEAR_DOWN_BUTTON)
        if self._num_buttons <= need_btn:
            raise RuntimeError(
                f"휠 버튼 개수 부족: buttons={self._num_buttons} 이지만 btn{need_btn} 필요 "
                f"(기어업=btn{GEAR_UP_BUTTON}, 기어다운=btn{GEAR_DOWN_BUTTON})")
        return js

    # ── 시작 ──────────────────────────────────────────────────────────
    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="wheel-drive",
                                        daemon=True)
        self._thread.start()

    # ── 조향: axis0(-1..1) → deadband → ×127(±127 클램프) ────────────────
    def _steering_deg(self, axis0):
        med = self._steer_filter.push(axis0)
        deg = int(round(med * STEER_SCALE))
        if abs(deg) < STEER_DEADBAND_DEG:
            return 0
        return max(-127, min(127, deg))

    # ── 페달: axis1(단일축) → (throttle%, brake%). 음수=엑셀 / 양수=브레이크 ──
    def _pedal(self, axis1):
        val = self._pedal_filter.push(axis1)        # median(5)+EMA(0.2)
        if val < -PEDAL_DEADBAND:
            return min(100, int(round(abs(val) * 100))), 0   # throttle%
        if val > PEDAL_DEADBAND:
            return 0, min(BRAKE_MAX, int(round(val * 100)))  # brake%
        return 0, 0

    # ── 패들: 버튼 상승엣지(0→1)에서만 1회 gearShift(±1) + 디바운스 ──────────
    def _handle_paddles(self, up, down):
        now = time.monotonic()
        if up and not self._btn_up_prev and now - self._last_shift >= GEAR_DEBOUNCE_S:
            self._last_shift = now
            print(f"WHEEL BTN: btn{GEAR_UP_BUTTON} press → gearShift(+1)")
            self.gearShift.emit(+1)
        elif down and not self._btn_down_prev and now - self._last_shift >= GEAR_DEBOUNCE_S:
            self._last_shift = now
            print(f"WHEEL BTN: btn{GEAR_DOWN_BUTTON} press → gearShift(-1)")
            self.gearShift.emit(-1)
        self._btn_up_prev = up
        self._btn_down_prev = down

    # ── 50ms 루프: 읽기 → 화면 emit(항상) → CAN 송신(인터록 게이트) ──────
    def _loop(self):
        nxt = time.monotonic()
        last_screen = None
        while self._running:
            nxt += SEND_PERIOD
            try:
                pygame.event.pump()
                axis0 = self._js.get_axis(STEER_AXIS)
                axis1 = self._js.get_axis(PEDAL_AXIS)
                up = bool(self._js.get_button(GEAR_UP_BUTTON))
                down = bool(self._js.get_button(GEAR_DOWN_BUTTON))
            except Exception:
                axis0, axis1, up, down = 0.0, 0.0, False, False

            steer = self._steering_deg(axis0)
            throttle, brake = self._pedal(axis1)

            # ── 기어 패들 엣지(인터록 무관 — VehicleState 가 인터록 판단) ──
            self._handle_paddles(up, down)

            # ── 화면 반영: 항상 실제 값(인터록 무관) — 변할 때만 emit ──
            #    P(중립)에서도 조향값을 읽어 STEER 위젯에, 엑셀/브레이크를 왼쪽 세로 막대에
            #    표시한다. "실제 바퀴 정지"는 아래 CAN 게이트가 담당(화면은 안 막는다).
            screen = (steer, throttle, brake)
            if screen != last_screen:
                last_screen = screen
                self.wheelInput.emit(steer, throttle, brake)

            # ── CAN 송신(인터록 게이트): 주행-가능(D/R)일 때만 실제 값, P 면 중립(0).
            #    P 에선 (0,0,0) 을 보내 실제 드라이브 모터를 정지시킨다 — 화면 표시와 무관.
            if self._enabled():
                tx_steer, tx_throttle, tx_brake = steer, throttle, brake
            else:
                tx_steer, tx_throttle, tx_brake = 0, 0, 0
            tx_rpm = min(RPM_MAX, tx_throttle * RPM_PER_PCT)
            try:
                self._can.send_drive_cmd(tx_steer, tx_rpm, tx_brake)
            except Exception:
                pass

            sleep = nxt - time.monotonic()
            if sleep > 0:
                time.sleep(sleep)
            else:
                nxt = time.monotonic()

    # ── 종료 ──────────────────────────────────────────────────────────
    def stop(self):
        self._running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None
        try:
            pygame.joystick.quit()
            pygame.quit()
        except Exception:
            pass
