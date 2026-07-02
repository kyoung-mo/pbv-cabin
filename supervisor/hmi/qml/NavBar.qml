import QtQuick
import "."

// 하단 내비게이션 바 — 가로 3분할: 좌석 / 홈 / 모드.
//   · 반투명 흰색(라이트 테마). 상단 옅은 보더.
//   · 좌석 → goSeats(ACTIVE+SEAT_OVERVIEW), 홈 → goAmbient(대기), 모드 → goModes(ACTIVE+MODE_SELECT)
//   · 현재 상태에 해당하는 섹션은 accent 로 강조.
// ※ ② 단계에서 무입력 시 더 투명하게 페이드(클릭 영역은 유지) 예정.
Item {
    id: nav

    // 하단바는 항상 또렷하게 유지(홈/대기에서도 페이드하지 않음).
    opacity: Theme.navOpacityActive

    // 지금 활성 섹션(강조용) — uiMode/화면 상태에서 파생.
    readonly property string active:
        vehicleState.uiMode === "AMBIENT" ? "home"
        : (vehicleState.rightPanelScreen === "MODE_SELECT" ? "modes" : "seats")

    // 바 배경(반투명 흰색) + 상단 1px 보더
    Rectangle {
        anchors.fill: parent
        color: Theme.navBg
        Rectangle {
            anchors { top: parent.top; left: parent.left; right: parent.right }
            height: 1
            color: Theme.border
        }
    }

    Row {
        anchors.fill: parent

        Repeater {
            model: [
                { key: "seats", label: "좌석" },
                { key: "home",  label: "홈" },
                { key: "modes", label: "모드" }
            ]
            delegate: Item {
                id: cell
                required property var modelData
                width: nav.width / 3
                height: nav.height
                readonly property bool isActive: nav.active === modelData.key
                readonly property color tint: isActive ? Theme.accent : Theme.textSecondary

                Column {
                    anchors.centerIn: parent
                    spacing: 10
                    NavIcon {
                        anchors.horizontalCenter: parent.horizontalCenter
                        kind: cell.modelData.key
                        color: cell.tint
                        width: 48; height: 48       // 바 높이 2배에 맞춰 아이콘도 크게(가시성)
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: cell.modelData.label
                        color: cell.tint
                        font.pixelSize: Theme.fsLabel
                        font.bold: cell.isActive
                        font.letterSpacing: Theme.tracking
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        if (cell.modelData.key === "home")
                            vehicleState.goAmbient()
                        else if (cell.modelData.key === "seats")
                            vehicleState.goSeats()
                        else
                            vehicleState.goModes()
                    }
                }
            }
        }
    }
}
