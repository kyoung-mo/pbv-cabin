"""wheel_input — 레이싱휠(D-INPUT) → Drive_Cmd/GearStatus 주기 송신 + HMI 화면 즉각 반영.

레이싱휠을 **D-INPUT 모드**로 두면 페달이 단일 아날로그 축으로 살아난다(X-INPUT 에서는
버튼으로 뭉개졌다). jstest(js0)로 최종 확정한 매핑을 그대로 따른다:

  [확정 매핑 — js0 인덱스]
    · 조향   = Axis 0,  -32767~32767 (왼쪽 음수 / 오른쪽 양수)
    · 페달   = Axis 1 단일축: 안 밟으면 0, 엑셀=음수(0~-32767), 브레이크=양수(0~+32767)
    · 기어업 = Button 5 (모멘터리)
    · 기어다운 = Button 4 (모멘터리)

  이 매핑은 supervisor/handle/ 의 검증 코드(wheel_can_sender.py·handle.py·drive_game.py)와
  동일하다 — axis0=조향, axis1=페달(음수=엑셀/양수=브레이크). 부호·스케일을 거기에 맞췄다:
    · 조향 :  steering = int(axis0 * 127)  (wheel_can_sender 와 동일, DBC 8bit signed → ±127 포화)
    · 페달 :  pedal<0 → accel=|pedal|*100 / pedal>0 → brake=pedal*100
    · RPM  :  Target_Velocity = accel% * 3, 최대 300 (wheel_can_sender 와 동일)

  ※ 라이브러리: pygame.joystick 유지. 이 휠(0e8f Steering Wheel Controller)은 D-INPUT 에서
    pygame 으로도 페달이 **연속 축(axis1)** 으로 잡힌다(4 axes / 13 buttons). 시작 시 probe 가
    축/버튼 개수와 인덱스 유효성을 검증하고(없으면 에러로 중단), 어느 축/버튼이 무엇인지 로그로
    찍는다. pygame 의 ABS 정렬이 js0 와 동일해 인덱스가 그대로 일치한다.

  [송신 규칙]
    · drive ECU 는 Drive_Cmd 가 300ms 끊기면 비상정지 → 값 불변이어도 50ms 마다 무조건 송신.
    · 주행-가능 인터록(기어 D/R)일 때만 조향/엑셀/브레이크 실제 값 송신, P 면 중립(0,0,0).
    · 화면 반영(wheelInput 시그널)은 인터록과 무관하게 항상 emit.
    · 기어는 휠 패들 엣지를 잡아 gearShift(±1) 시그널로 GUI 스레드에 넘긴다. 실제 기어 상태는
      VehicleState 가 단일 소유(터치 슬라이더와 동일 경로) → GearStatus(0x070) 송신·슬라이더
      동기까지 한곳에서 처리된다(두 입력이 같은 상태를 갱신).
"""

import os
import statistics
import threading
import time
from collections import deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")   # pygame 만 영향(Qt 와 무관) — 디스플레이 불요
import pygame                                         # noqa: E402

from PySide6.QtCore import QObject, Signal            # noqa: E402


# ── 확정 매핑 인덱스 (js0 = pygame 동일) ─────────────────────────────────────
STEER_AXIS = 0           # 조향축
PEDAL_AXIS = 1           # 페달 단일축 (음수=엑셀 / 양수=브레이크)
BTN_GEAR_UP = 5          # 기어 업 패들 (R→P→D)
BTN_GEAR_DOWN = 4        # 기어 다운 패들 (D→P→R)

# ── 스케일/데드밴드 (handle/ 검증 코드와 동일) ───────────────────────────────
STEER_SCALE = 127        # int(axis0 * 127) — DBC Steering_Angle 8bit signed(±127 포화)
STEER_DEADBAND_DEG = 3   # |조향각| < 3° → 0
PEDAL_RAW_FULL = 32767   # 페달 풀스케일(절대값) — jstest 범위
PEDAL_DEADBAND = 1500.0 / PEDAL_RAW_FULL   # ±1500 raw → ±0.0458 (pygame -1..1)
RPM_PER_PCT = 3          # accel% → RPM (wheel_can_sender: target_rpm = accel*3)
RPM_MAX = 300            # Target_Velocity 상한(RPM)

SEND_PERIOD = 0.05       # 50ms (≪ 300ms estop) — 값 불변에도 브로드캐스트

# 페달 평활: median(5) + EMA(0.2) + 슬루레이트 제한
PEDAL_MEDIAN_WIN = 5
PEDAL_EMA_ALPHA = 0.20
PEDAL_SLEW = 0.18        # tick(50ms) 당 최대 변화(-1..1 단위) — 급변 방지
# 조향 평활(가벼운): median(3) + EMA(0.4) — 반응성 우선
STEER_MEDIAN_WIN = 3
STEER_EMA_ALPHA = 0.40

GEAR_DEBOUNCE_S = 0.06   # 패들 채터링 가드(>1 tick). 한 번 누름=1전이는 '릴리스 후 상승엣지'
                         # 조건이 보장하므로, 디바운스는 1-tick 글리치만 막을 만큼만 짧게 둔다.
PROBE_WINDOW_S = 0.6     # 시작 시 축/버튼 관찰 로그 윈도우


class _Filter:
    """median(win) → EMA(alpha) → slew-rate 제한. 축 하나당 하나씩."""

    def __init__(self, win, alpha, slew=None):
        self._buf = deque(maxlen=win)
        self._alpha = alpha
        self._slew = slew
        self._ema = 0.0
        self._out = 0.0

    def reset(self):
        self._buf.clear()
        self._ema = 0.0
        self._out = 0.0

    def push(self, x):
        self._buf.append(x)
        med = statistics.median(self._buf)
        self._ema = self._alpha * med + (1.0 - self._alpha) * self._ema
        if self._slew is None:
            self._out = self._ema
        else:
            delta = self._ema - self._out
            if delta > self._slew:
                delta = self._slew
            elif delta < -self._slew:
                delta = -self._slew
            self._out += delta
        return self._out


class WheelInput(QObject):
    # 휠 스레드 → GUI 스레드 (QueuedConnection): (조향각°, throttle%, brake%)
    wheelInput = Signal(int, int, int)
    # 휠 패들 기어 변속 엣지 → GUI 스레드: +1=업(R→P→D), -1=다운(D→P→R)
    gearShift = Signal(int)

    def __init__(self, can_hub, drive_enabled_cb, parent=None):
        super().__init__(parent)
        self._can = can_hub
        self._enabled = drive_enabled_cb        # () -> bool (기어 D/R)
        self._running = False
        self._thread = None

        self._pedal_filter = _Filter(PEDAL_MEDIAN_WIN, PEDAL_EMA_ALPHA, PEDAL_SLEW)
        self._steer_filter = _Filter(STEER_MEDIAN_WIN, STEER_EMA_ALPHA)

        # 패들 엣지 검출 상태
        self._prev_up = 0
        self._prev_down = 0
        self._last_shift = 0.0

        self._js = self._open()
        self._probe()

    # ── 휠 오픈 ────────────────────────────────────────────────────────
    @staticmethod
    def _open():
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            raise RuntimeError(
                "레이싱휠(joystick)을 찾지 못함 — D-INPUT 모드/USB 연결 확인 "
                "(/dev/input/js0 = Steering Wheel Controller)")
        js = pygame.joystick.Joystick(0)
        js.init()
        return js

    # ── probe: 매핑 자동 검증 + 로그 ───────────────────────────────────
    def _probe(self):
        """시작 시 1회: 축/버튼 개수·인덱스 유효성 검증(없으면 에러), 관찰값 로그.

        확정 매핑(axis0=조향, axis1=페달, btn5=업, btn4=다운)을 그대로 쓰되,
        라이브러리 인덱스가 실제로 존재하는지 확인한다. PROBE_WINDOW_S 동안 축을
        관찰해 페달축이 '연속값(축)' 인지(고정/이산 아님) 범위를 함께 찍는다.
        """
        name = self._js.get_name().strip()
        n_ax = self._js.get_numaxes()
        n_btn = self._js.get_numbuttons()
        print(f"WHEEL PROBE: '{name}'  axes={n_ax} buttons={n_btn} "
              f"hats={self._js.get_numhats()}")

        # 인덱스 유효성 — 하나라도 범위를 벗어나면 매핑이 깨진 것 → 중단(에러)
        need_ax = {"조향(steer)": STEER_AXIS, "페달(pedal)": PEDAL_AXIS}
        need_btn = {"기어업(up)": BTN_GEAR_UP, "기어다운(down)": BTN_GEAR_DOWN}
        for label, idx in need_ax.items():
            if idx >= n_ax:
                raise RuntimeError(
                    f"probe 실패: {label}=axis{idx} 가 없음(axes={n_ax}). "
                    "D-INPUT 모드인지/올바른 디바이스인지 확인")
        for label, idx in need_btn.items():
            if idx >= n_btn:
                raise RuntimeError(
                    f"probe 실패: {label}=button{idx} 가 없음(buttons={n_btn})")

        # 관찰 윈도우 — 페달축이 연속 축으로 잡히는지(이산/고정 아님) 범위 로그
        lo = [9.9] * n_ax
        hi = [-9.9] * n_ax
        t_end = time.monotonic() + PROBE_WINDOW_S
        samples = 0
        while time.monotonic() < t_end:
            pygame.event.pump()
            for i in range(n_ax):
                v = self._js.get_axis(i)
                lo[i] = min(lo[i], v)
                hi[i] = max(hi[i], v)
            samples += 1
            time.sleep(0.01)

        def rng(i):
            return f"axis{i}=[{lo[i]:+.3f},{hi[i]:+.3f}]"
        print("WHEEL PROBE: 관찰범위 " + "  ".join(rng(i) for i in range(n_ax)))
        print(f"WHEEL MAP: 조향=axis{STEER_AXIS}(×{STEER_SCALE}) "
              f"페달=axis{PEDAL_AXIS}(음수=엑셀/양수=브레이크) "
              f"기어업=btn{BTN_GEAR_UP} 기어다운=btn{BTN_GEAR_DOWN}")
        # 페달축은 실수 축으로 노출됨(연속). 시작 시엔 보통 정지(≈0)라 범위가 좁다 —
        # 실측 연속성은 ⑤ 재검증(페달을 밟아 candump 비례 확인)에서 최종 확인한다.
        print("WHEEL: probe OK — 페달은 연속 축으로 노출됨(밟으면 비례값). 준비 완료")

    # ── 시작 ──────────────────────────────────────────────────────────
    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="wheel-drive",
                                        daemon=True)
        self._thread.start()

    # ── 매핑 ───────────────────────────────────────────────────────────
    def _steering_deg(self, axis0):
        """axis0(-1..1) → 조향각(도). median→EMA 평활 후 ×127, |deg|<3 데드밴드."""
        med = self._steer_filter.push(axis0)
        deg = med * STEER_SCALE
        if abs(deg) < STEER_DEADBAND_DEG:
            return 0
        return int(round(deg))

    def _pedal(self, axis1):
        """axis1 단일축 → (throttle%, brake%). 음수=엑셀 / 양수=브레이크.

        median(5)+EMA(0.2)+슬루레이트로 평활한 뒤 데드밴드 적용. 풀스케일(|1.0|)에서 100%.
        """
        val = self._pedal_filter.push(axis1)
        if val < -PEDAL_DEADBAND:
            throttle = min(100, int(round(abs(val) * 100)))
            return throttle, 0
        if val > PEDAL_DEADBAND:
            brake = min(100, int(round(val * 100)))
            return 0, brake
        return 0, 0

    def _handle_paddles(self, now):
        """Button5(업)/Button4(다운) 0→1 엣지 → gearShift(±1). 디바운스 포함."""
        try:
            up = self._js.get_button(BTN_GEAR_UP)
            down = self._js.get_button(BTN_GEAR_DOWN)
        except Exception:
            up, down = 0, 0
        # 누르고 있어도 1회만: 0→1 상승엣지에서만 + 디바운스 윈도우
        if now - self._last_shift >= GEAR_DEBOUNCE_S:
            if up and not self._prev_up:
                self.gearShift.emit(+1)        # R→P→D
                self._last_shift = now
            elif down and not self._prev_down:
                self.gearShift.emit(-1)        # D→P→R
                self._last_shift = now
        self._prev_up = up
        self._prev_down = down

    # ── 50ms 루프: 읽기 → 패들 → 화면 emit(항상) → CAN 송신(인터록 게이트) ──
    def _loop(self):
        nxt = time.monotonic()
        last_screen = None
        while self._running:
            nxt += SEND_PERIOD
            now = time.monotonic()
            try:
                pygame.event.pump()
                axis0 = self._js.get_axis(STEER_AXIS)
                axis1 = self._js.get_axis(PEDAL_AXIS)
            except Exception:
                axis0, axis1 = 0.0, 0.0

            # 기어 패들 엣지(화면/CAN 동기는 VehicleState 가 단일 처리)
            self._handle_paddles(now)

            steer = self._steering_deg(axis0)
            throttle, brake = self._pedal(axis1)

            # ── 화면 반영: 인터록과 무관하게 항상 (변할 때만 emit) ──
            screen = (steer, throttle, brake)
            if screen != last_screen:
                last_screen = screen
                self.wheelInput.emit(steer, throttle, brake)

            # ── CAN 송신: 주행-가능(D/R)일 때만 실제 값, 아니면 중립 ──
            if self._enabled():
                tx_steer = steer
                tx_rpm = min(RPM_MAX, throttle * RPM_PER_PCT)   # accel% → RPM
                tx_brake = brake
            else:
                tx_steer, tx_rpm, tx_brake = 0, 0, 0
                self._pedal_filter.reset()     # 주행 진입 시 깨끗한 상태로
                self._steer_filter.reset()
            try:
                # tx_rpm → Target_Velocity, tx_brake → Brake_Depth, tx_steer → Steering_Angle
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
