"""한 번의 화면 전환(SEAT_OVERVIEW→SEAT_DETAIL)을 여러 프레임으로 캡처 —
크로스페이드/슬라이드가 실제로 일어나는지 셀프점검용.

실행: QT_QPA_PLATFORM=offscreen python3 tools/capture_transition.py [출력디렉터리]
"""

import os
import sys

from PySide6.QtCore import QUrl, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

HMI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HMI)
from vehicle_state import VehicleState  # noqa: E402


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HMI, "_trans")
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

    # 먼저 오버뷰로 안정화
    QTimer.singleShot(400, lambda: state._set_screen("SEAT_OVERVIEW"))

    def fire():
        state.selectSeat("driver")   # 전환 트리거
        # 전환 진행 중 여러 프레임 grab (0~500ms)
        for i, t in enumerate([40, 110, 180, 260, 360, 500]):
            def grab(i=i, t=t):
                img = win.grabWindow()
                p = os.path.join(out_dir, f"t_{i}_{t}ms.png")
                img.save(p)
                print("SHOT:", p)
            QTimer.singleShot(t, grab)
        QTimer.singleShot(800, app.quit)

    QTimer.singleShot(900, fire)
    rc = app.exec()
    sys.exit(rc)


if __name__ == "__main__":
    main()
