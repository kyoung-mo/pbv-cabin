import QtQuick
import "."

// 왼쪽 "차량" 영역 — QtQuick3D 실시간 3D 디지털 트윈.
//   · 배경: 루프 없는 컷어웨이 캐빈(Cabin3D). 카메라는 고정 3/4 부감(회전 드래그 없음).
//   · 오버레이: 좌상단 세로 기어 슬라이드 + 하단 GEAR 텍스트(기존 유지).
//   · 빈 곳을 탭하면 기존처럼 화면 토글(MODE_SELECT ↔ SEAT_OVERVIEW).
// ※ 차량 전체 회전(턴테이블 PNG/드래그)은 제거됨.
Item {
    id: root

    // 3D 캐빈 (영역 전체)
    Cabin3D {
        id: cabin3d
        anchors.fill: parent
    }

    // 빈 곳 탭 (3D 위, 기어 슬라이드 아래에 위치해 슬라이드 조작은 방해 안 함):
    //   · AMBIENT : wakeFromAmbient() → ACTIVE 복귀(화면 토글 안 함).
    //   · ACTIVE  : 기존처럼 화면 토글(MODE_SELECT ↔ SEAT_OVERVIEW).
    // ※ 기어 슬라이드는 이 MouseArea 위에 있어, 기어 조작은 wake/토글을 부르지 않음.
    MouseArea {
        anchors.fill: parent
        onClicked: {
            if (vehicleState.uiMode === "AMBIENT")
                vehicleState.wakeFromAmbient()
            else
                vehicleState.toggleCarArea()
        }
    }

    // 기어 상태 텍스트 (항상 표시) — 밝은 클레이 배경 위 가독성용 어두운 알약 backing.
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 22
        width: gearRow.width + 36
        height: gearRow.height + 18
        radius: height / 2
        color: Theme.overlayPillBg
        border.color: Theme.overlayBorder
        border.width: 1

        Row {
            id: gearRow
            anchors.centerIn: parent
            spacing: 12
            Text {
                anchors.baseline: gearVal.baseline
                text: "GEAR"
                color: Theme.overlayTextSecondary
                font.pixelSize: 22
                font.letterSpacing: 2
            }
            Text {
                id: gearVal
                text: vehicleState.gear
                color: Theme.overlayTextPrimary
                font.pixelSize: 38
                font.bold: true
                font.letterSpacing: Theme.tracking
            }
        }
    }

    // 좌상단 세로 기어 슬라이드 (탭 토글 MouseArea 위 → 슬라이더 조작 분리)
    GearSlider {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 16
        width: 120
        height: 300
    }
}
