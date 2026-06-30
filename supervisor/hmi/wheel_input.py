"""wheel_input — 레이싱휠 → Drive_Cmd 주기 송신 + HMI 화면 즉각 반영 (스텝3).

축 매핑은 수민(handle/ wheel_can_sender.py·handle.py·drive_game.py)이 라즈베리파이
실물 휠로 **실측·검증한 값**을 그대로 따른다. (해당 reference 파일이 이 워킹트리에는
없어 직접 읽지는 못했고, 검증된 매핑 사양에 1:1로 맞춰 구현했다.) 입력 라이브러리도
reference 와 동일하게 **pygame.joystick** 을 쓴다 — evdev 의 ABS 코드 순서와 pygame 의
축 인덱스 순서가 다를 수 있어, "axis0/axis1" 을 정확히 같게 맞추려면 pygame 이 안전하다.

[검증된 매핑]
  · 조향 = axis0 (★ axis1 아님). 값 -1.0~1.0 → deg = axis0 * MAX_STEERING_ANGLE(130).
        데드밴드: |deg| < 3 이면 0. (DBC Steering_Angle 은 8bit signed → 물리적으로 ±127
        까지만 인코딩 가능. 130 스케일은 곡선을 reference 와 맞추되 끝단은 ±127 로 포화된다.)
  · 페달 = axis1 단일 축 (X-INPUT 에서 엑셀/브레이크가 한 축에 합쳐짐).
        axis1 < -0.02 → throttle = |axis1|*100, brake = 0   (→ Target_Velocity)
        axis1 >  0.02 → throttle = 0,           brake = axis1*100 (→ Brake_Depth)
        -0.02~0.02    → throttle 0, brake 0 (중립)

[송신 규칙]
  · drive ECU 는 Drive_Cmd 가 300ms 끊기면 비상정지(Short Brake)한다 → 값이 안 변해도
    50ms 마다 무조건 브로드캐스트(중립이라도). 0x100 송신 주체는 이 프로세스 하나뿐.
  · 주행-가능 인터록(기어 D 또는 R)일 때만 실제 값 송신, 아니면 CAN 으로는 중립(0,0,0).
  · 화면 반영(wheelInput 시그널)은 인터록과 무관하게 항상 emit — 휠을 돌리면 P 에서도
    HMI 조향 표시가 즉각 따라온다(문서 §5.2). RX 스레드와 동일하게 QueuedConnection 으로
    GUI 스레드에 넘긴다(스레드 안전).
"""

import os
import statistics
import threading
import time
from collections import deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")   # pygame 만 영향(Qt 와 무관) — 디스플레이 불요
import pygame                                         # noqa: E402

from PySide6.QtCore import QObject, Signal            # noqa: E402


# ── 검증된 축/스케일 상수 (reference 와 동일) ────────────────────────────────
STEER_AXIS = 0            # 조향축 = axis0
PEDAL_AXIS = 1            # 페달축 = axis1 (엑셀/브레이크 합쳐진 단일 축)
MAX_STEERING_ANGLE = 130 # 조향 풀스케일(도). DBC ±135 선언이나 8bit 라 실제 ±127 포화.
STEER_DEADBAND_DEG = 3   # |조향각| < 3° → 0
PEDAL_DEADBAND = 0.02    # |axis1| < 0.02 → 중립
THROTTLE_MAX = 100       # throttle/ brake 풀스케일(%) — Target_Velocity/Brake_Depth 로 직결
BRAKE_MAX = 100

SEND_PERIOD = 0.05       # 50ms (≪ 300ms estop) — 값 불변에도 브로드캐스트
MEDIAN_WIN = 3           # 스파이크 제거(정상상태 출력은 불변)
EMA_ALPHA = 0.40         # 반응성 우선(즉각 반영) + 약한 평활


class WheelInput(QObject):
    # 휠 스레드 → GUI 스레드 (QueuedConnection): (조향각°, throttle%, brake%)
    wheelInput = Signal(int, int, int)

    def __init__(self, can_hub, drive_enabled_cb, parent=None):
        super().__init__(parent)
        self._can = can_hub
        self._enabled = drive_enabled_cb        # () -> bool (기어 D/R)
        self._running = False
        self._thread = None

        self._median = deque(maxlen=MEDIAN_WIN)
        self._ema = 0.0

        self._js = self._open()

    @staticmethod
    def _open():
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            raise RuntimeError("레이싱휠(joystick)을 찾지 못함")
        js = pygame.joystick.Joystick(0)
        js.init()
        return js

    # ── 시작 ──────────────────────────────────────────────────────────
    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="wheel-drive",
                                        daemon=True)
        self._thread.start()
        print(f"WHEEL: {self._js.get_name().strip()} "
              f"조향=axis{STEER_AXIS} 페달=axis{PEDAL_AXIS} 풀스케일=±{MAX_STEERING_ANGLE}°")

    # ── 매핑 (검증된 값) ──────────────────────────────────────────────
    def _steering_deg(self, axis0):
        """axis0(-1..1) → 조향각(도). median→EMA 평활 후 130 스케일, |deg|<3 데드밴드."""
        self._median.append(axis0)
        med = statistics.median(self._median)
        self._ema = EMA_ALPHA * med + (1.0 - EMA_ALPHA) * self._ema
        deg = self._ema * MAX_STEERING_ANGLE
        if abs(deg) < STEER_DEADBAND_DEG:
            return 0
        return int(round(deg))

    @staticmethod
    def _pedal(axis1):
        """axis1 단일 축 → (throttle%, brake%). 음수=엑셀 / 양수=브레이크."""
        if axis1 < -PEDAL_DEADBAND:
            return int(round(abs(axis1) * THROTTLE_MAX)), 0
        if axis1 > PEDAL_DEADBAND:
            return 0, int(round(axis1 * BRAKE_MAX))
        return 0, 0

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
            except Exception:
                axis0, axis1 = 0.0, 0.0

            steer = self._steering_deg(axis0)
            throttle, brake = self._pedal(axis1)

            # ── 화면 반영: 인터록과 무관하게 항상 (변할 때만 emit) ──
            screen = (steer, throttle, brake)
            if screen != last_screen:
                last_screen = screen
                self.wheelInput.emit(steer, throttle, brake)

            # ── CAN 송신: 주행-가능일 때만 실제 값, 아니면 중립 ──
            if self._enabled():
                tx_steer, tx_throttle, tx_brake = steer, throttle, brake
            else:
                tx_steer, tx_throttle, tx_brake = 0, 0, 0
                self._median.clear()       # 주행 진입 시 깨끗한 상태로
                self._ema = 0.0
            try:
                # throttle(0..100) → Target_Velocity, brake(0..100) → Brake_Depth
                self._can.send_drive_cmd(tx_steer, tx_throttle, tx_brake)
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
