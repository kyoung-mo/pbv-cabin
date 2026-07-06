"""차량 HMI 엔트리포인트 (PySide6 + QML, 스텝2: 실제 can0 양방향 연동).

구성:
  · CanHub      — can0 송수신 허브(DBC=cantools). RX 스레드 → Qt Signal.
  · VehicleState— 단일 상태 객체. 입력→인터록→CAN 송신, 수신→트윈 갱신.
  · WheelInput  — 레이싱휠 → Drive_Cmd 50ms 주기 송신(별도 스레드).

실행:
    python3 main.py            # 풀스크린
    HMI_WINDOWED=1 python3 main.py   # 창모드(검증/원격 X11 편의)
    HMI_SELFTEST=1 QT_QPA_PLATFORM=offscreen python3 main.py  # QML 로드만 확인
    HMI_NOCAN=1 python3 main.py      # CAN/휠 없이 화면만(콘솔 폴백)

STM32 존 ECU 가 없을 때 자체 검증: 다른 터미널에서
    python3 tools/dummy_ecu.py
를 띄우면, 좌석 적용 시 나간 *_Seat_Cmd 에 대응하는 *_Seat_Status 가 돌아와
3D 트윈의 현재 recline 포즈가 따라 움직인다(실물 ECU 붙으면 그대로 동작).

종료: Esc 키
"""

import os
import sys

from PySide6.QtCore import QUrl, QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from vehicle_state import VehicleState


def _make_can_hub():
    """CanHub 생성(실패해도 앱은 CAN 없이 계속). 반환: CanHub | None."""
    if os.environ.get("HMI_NOCAN"):
        print("HMI_NOCAN: CAN/휠 비활성 — 콘솔 폴백으로 실행")
        return None
    try:
        from can_hub import CanHub
        hub = CanHub()
        print("CAN: can0 연결 + model_car_net.dbc 로드 완료")
        return hub
    except Exception as e:
        print(f"WARN: CAN 초기화 실패 → CAN 없이 실행: {e}", file=sys.stderr)
        return None


def _make_wheel(can_hub, state):
    """WheelInput 시작(실패해도 앱은 휠 없이 계속). 반환: WheelInput | None."""
    if can_hub is None:
        return None
    try:
        from wheel_input import WheelInput
        wheel = WheelInput(can_hub, state.drive_enabled)
        # 휠 → 화면 즉각 반영(인터록 무관). RX 와 동일하게 QueuedConnection 으로 GUI 스레드에.
        wheel.wheelInput.connect(state.onWheelInput, Qt.QueuedConnection)
        # 휠 패들 기어 변속 → VehicleState(단일 기어 상태). 터치 슬라이더와 동일 경로.
        wheel.gearShift.connect(state.onWheelGearShift, Qt.QueuedConnection)
        wheel.start()
        return wheel
    except Exception as e:
        print(f"WARN: 휠 입력 비활성: {e}", file=sys.stderr)
        return None


def main():
    app = QGuiApplication(sys.argv)
    # 색깔 박스 placeholder 위주라 기본(Basic) 스타일로 고정 — 슬라이더/버튼 가시성 확보
    QQuickStyle.setStyle("Basic")

    # ── CAN 허브 + 상태 객체 ──────────────────────────────────────────
    can_hub = _make_can_hub()
    state = VehicleState(can_hub=can_hub)

    # 수신(RX 스레드) → 상태 슬롯: QueuedConnection 으로 GUI 스레드에서 실행(스레드 안전)
    if can_hub is not None:
        can_hub.seatStatusReceived.connect(state.onSeatStatus, Qt.QueuedConnection)
        can_hub.driveStatusReceived.connect(state.onDriveStatus, Qt.QueuedConnection)
        can_hub.busError.connect(lambda m: print(f"CAN: {m}", file=sys.stderr),
                                 Qt.QueuedConnection)
        can_hub.start_rx()
        # 부팅 자동 원점 정렬(뒷좌석 슬라이드) — slide4 는 부팅 호밍이 꺼져 있어(SLIDE_HOMING=0)
        #   전원 시 놓인 위치를 0으로 간주한다. 절대위치 명령 전에 254(호밍)로 물리 원점을 잡는다.
        #   버스/ECU 가 자리잡도록 잠깐 뒤에 시작(그동안 화면은 homingActive 오버레이로 잠금).
        QTimer.singleShot(1200, state.homeRearSlides)
        # 앞좌석 초기 자세(리클라인 90°/회전 0°)를 메인 제어기에서 능동 송신(0x110/0x111).
        QTimer.singleShot(1200, state.initFrontSeats)

    # ── 레이싱휠 → Drive_Cmd ──────────────────────────────────────────
    wheel = _make_wheel(can_hub, state)

    # ── QML ───────────────────────────────────────────────────────────
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("vehicleState", state)
    windowed = bool(os.environ.get("HMI_WINDOWED"))
    engine.rootContext().setContextProperty("startWindowed", windowed)

    qml_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "qml", "Main.qml")
    engine.load(QUrl.fromLocalFile(qml_path))

    if not engine.rootObjects():
        print("ERROR: QML 로드 실패", file=sys.stderr)
        _shutdown(wheel, can_hub)
        sys.exit(1)

    # QML 로드만 검증하고 바로 종료하는 모드 (디스플레이 없이 문법 확인용)
    if os.environ.get("HMI_SELFTEST"):
        print("SELFTEST: QML 로드 성공")
        QTimer.singleShot(300, app.quit)

    # 종료 시 스레드(휠/CAN RX) 정리 — 앱 이벤트루프 종료 직전.
    app.aboutToQuit.connect(lambda: _shutdown(wheel, can_hub))

    rc = app.exec()
    _shutdown(wheel, can_hub)   # 멱등 — 이중 호출 안전
    sys.exit(rc)


_shutdown_done = False


def _shutdown(wheel, can_hub):
    """휠/CAN RX 스레드 + 버스 정리(멱등)."""
    global _shutdown_done
    if _shutdown_done:
        return
    _shutdown_done = True
    if wheel is not None:
        wheel.stop()
    if can_hub is not None:
        can_hub.stop()
    print("SHUTDOWN: 스레드/버스 정리 완료")


if __name__ == "__main__":
    main()
