"""오프스크린 렌더링으로 HMI 각 화면을 PNG로 캡처 — 비주얼 셀프점검 전용.

실행:
    QT_QPA_PLATFORM=offscreen python3 tools/capture.py [출력디렉터리]

기능/상태 로직은 건드리지 않는다. vehicleState의 기존 @Slot만 호출해
3화면(MODE_SELECT / SEAT_OVERVIEW / SEAT_DETAIL)을 차례로 그린 뒤 grabWindow.
"""

import os
import sys

from PySide6.QtCore import QUrl, QTimer, QCoreApplication
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

HMI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HMI)
from vehicle_state import VehicleState  # noqa: E402


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HMI, "_shots")
    os.makedirs(out_dir, exist_ok=True)

    app = QGuiApplication(sys.argv)
    QQuickStyle.setStyle("Basic")

    engine = QQmlApplicationEngine()
    state = VehicleState()
    engine.rootContext().setContextProperty("vehicleState", state)
    engine.rootContext().setContextProperty("startWindowed", True)

    engine.load(QUrl.fromLocalFile(os.path.join(HMI, "qml", "Main.qml")))
    win = engine.rootObjects()[0]
    win.setWidth(1280)
    win.setHeight(720)

    # 캡처할 화면 시나리오: (이름, 준비 콜백)
    shots = [
        ("01_mode_select", lambda: state._set_screen("MODE_SELECT")),
        ("02_mode_drive_selected", lambda: (state._set_screen("MODE_SELECT"),
                                            state.selectMode("주행"))),
        ("03_seat_overview", lambda: state._set_screen("SEAT_OVERVIEW")),
        ("04_seat_detail_front", lambda: state.selectSeat("driver")),
        ("05_seat_detail_rear", lambda: state.selectSeat("rear_left")),
        # 인터록 잠금 비주얼: 주행 모드 + 기어 D → 모드 타일 흐림 + 기어 핸들 회색
        ("06_locked_mode_tiles", lambda: (state._set_screen("MODE_SELECT"),
                                          state.selectMode("주행"),
                                          state.requestGearIndex(2))),
    ]

    idx = {"i": 0}

    def grab_next():
        if idx["i"] >= len(shots):
            QTimer.singleShot(100, app.quit)
            return
        name, prep = shots[idx["i"]]
        prep()
        # 렌더 반영을 위해 한 박자 쉬고 grab
        def do_grab():
            img = win.grabWindow()
            path = os.path.join(out_dir, name + ".png")
            img.save(path)
            print("SHOT:", path, img.width(), "x", img.height())
            idx["i"] += 1
            QTimer.singleShot(250, grab_next)
        # 전환 애니메이션(~450ms)이 끝난 최종 상태를 잡도록 충분히 대기
        QTimer.singleShot(650, do_grab)

    QTimer.singleShot(500, grab_next)
    rc = app.exec()
    print("CAPTURE DONE ->", out_dir)
    sys.exit(rc)


if __name__ == "__main__":
    main()
