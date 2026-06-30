import QtQuick
import "."

// 하단 내비게이션 바 — 가로 3분할: 좌석 / 홈 / 모드.
//   · 반투명 흰색(라이트 테마). 상단 옅은 보더.
//   · 좌석 → goSeats(ACTIVE+SEAT_OVERVIEW), 홈 → goAmbient(대기), 모드 → goModes(ACTIVE+MODE_SELECT)
//   · 현재 상태에 해당하는 섹션은 accent 로 강조.
// ※ ② 단계에서 무입력 시 더 투명하게 페이드(클릭 영역은 유지) 예정.
Item {
    id: nav

    // 무입력 페이드 — 대기(AMBIENT, 10초 무입력)면 거의 투명, ACTIVE면 또렷.
    //   ※ opacity 만 낮춘다. enabled/visible 은 그대로라 흐릿해도 버튼 클릭/동작은 유지되고,
    //     좌석/모드를 누르면 ACTIVE 복귀(_register_activity)로 다시 또렷해진다.
    opacity: vehicleState.uiMode === "AMBIENT" ? Theme.navOpacityIdle
                                               : Theme.navOpacityActive
    Behavior on opacity {
        NumberAnimation { duration: Theme.navFadeMs; easing.type: Easing.InOutQuad }
    }

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
                    spacing: 5
                    NavIcon {
                        anchors.horizontalCenter: parent.horizontalCenter
                        kind: cell.modelData.key
                        color: cell.tint
                        width: 26; height: 26
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: cell.modelData.label
                        color: cell.tint
                        font.pixelSize: Theme.fsLabel - 4
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
