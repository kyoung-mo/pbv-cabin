"""차량 HMI 엔트리포인트 (PySide6 + QML, 스텝1: CAN 없이 화면/입력 검증).

실행:
    python3 main.py            # 풀스크린
    HMI_WINDOWED=1 python3 main.py   # 창모드(검증/원격 X11 편의)
    HMI_SELFTEST=1 QT_QPA_PLATFORM=offscreen python3 main.py  # QML 로드만 확인

종료: Esc 키
"""

import os
import sys

from PySide6.QtCore import QUrl, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from vehicle_state import VehicleState


def main():
    app = QGuiApplication(sys.argv)
    # 색깔 박스 placeholder 위주라 기본(Basic) 스타일로 고정 — 슬라이더/버튼 가시성 확보
    QQuickStyle.setStyle("Basic")

    engine = QQmlApplicationEngine()
    state = VehicleState()
    # QML 전역에서 vehicleState 로 접근
    engine.rootContext().setContextProperty("vehicleState", state)

    # 환경변수로 풀스크린/창모드 선택 (QML에서 읽음)
    windowed = bool(os.environ.get("HMI_WINDOWED"))
    engine.rootContext().setContextProperty("startWindowed", windowed)

    qml_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "qml", "Main.qml")
    engine.load(QUrl.fromLocalFile(qml_path))

    if not engine.rootObjects():
        print("ERROR: QML 로드 실패", file=sys.stderr)
        sys.exit(1)

    # QML 로드만 검증하고 바로 종료하는 모드 (디스플레이 없이 문법 확인용)
    if os.environ.get("HMI_SELFTEST"):
        print("SELFTEST: QML 로드 성공")
        QTimer.singleShot(300, app.quit)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
