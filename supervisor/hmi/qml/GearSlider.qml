import QtQuick
import QtQuick.Controls
import "."

// 세로 기어 슬라이드: 위=D, 중앙=P, 아래=R.
// 드래그 핸들이 3노치에 스냅. 한 칸씩(인접)만 이동 — Python에서 강제.
Item {
    id: root

    // 글래스 트랙 배경
    Card {
        anchors.fill: parent
        radius: Theme.radius
        elevation: 0.7
    }

    Slider {
        id: gearSlider
        anchors.left: parent.left
        anchors.leftMargin: Theme.spaceMd
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.topMargin: Theme.spaceMd
        anchors.bottomMargin: Theme.spaceMd
        width: 56
        orientation: Qt.Vertical
        from: 0          // 아래 = R
        to: 2            // 위 = D
        stepSize: 1
        snapMode: Slider.SnapAlways
        value: vehicleState.gearIndex
        onMoved: vehicleState.requestGearIndex(Math.round(value))

        // 인터록: 주행 모드가 아니면 드래그/터치 자체를 막는다(비활성).
        enabled: !vehicleState.gearLocked
        // 잠긴 느낌으로 전체를 부드럽게 흐리게
        opacity: vehicleState.gearLocked ? 0.45 : 1.0
        Behavior on opacity {
            NumberAnimation { duration: Theme.durMed; easing.type: Theme.easeStandard }
        }

        // 가는 세로 가이드 레일
        background: Rectangle {
            x: gearSlider.leftPadding + gearSlider.availableWidth / 2 - width / 2
            y: gearSlider.topPadding
            width: 6
            height: gearSlider.availableHeight
            radius: 3
            color: Theme.borderStrong
        }

        // 핸들 — 글래스 캡슐. 스냅 시 부드럽게 미끄러짐(드래그 중엔 즉시).
        handle: Rectangle {
            id: gearHandle
            implicitWidth: 44
            implicitHeight: 44
            radius: 12
            x: gearSlider.leftPadding + (gearSlider.availableWidth - width) / 2
            y: gearSlider.topPadding
               + gearSlider.visualPosition * (gearSlider.availableHeight - height)
            color: vehicleState.gearLocked ? "#6a7180"
                   : gearSlider.pressed ? Theme.accentSoft : "#eef1f7"
            border.color: vehicleState.gearLocked ? "#4a505c" : Theme.accent
            border.width: 2
            antialiasing: true
            Behavior on color { ColorAnimation { duration: Theme.durFast } }
            Behavior on y {
                enabled: !gearSlider.pressed
                NumberAnimation { duration: Theme.durMed; easing.type: Theme.easeEmphasis }
            }
            // 그립 느낌의 중앙 점
            Rectangle {
                anchors.centerIn: parent
                width: 16; height: 3; radius: 1.5
                color: Qt.rgba(0, 0, 0, 0.25)
            }
        }

        // 거부되었거나 상태가 바뀌면 권위값(gearIndex)으로 핸들 복귀
        Connections {
            target: vehicleState
            function onGearChanged() { gearSlider.value = vehicleState.gearIndex }
        }
    }

    // 잠금 상태에서 슬라이더를 눌렀을 때: 터치를 가로채 사유를 출력.
    MouseArea {
        anchors.fill: gearSlider
        visible: vehicleState.gearLocked
        enabled: vehicleState.gearLocked
        onClicked: vehicleState.gearBlockedNotice()
    }

    // D / P / R 라벨 (현재 기어는 accent 강조, 변화는 페이드)
    component GearLabel: Text {
        font.pixelSize: 28
        font.bold: true
        font.letterSpacing: Theme.tracking
        Behavior on color { ColorAnimation { duration: Theme.durMed } }
    }
    GearLabel {
        anchors.right: parent.right; anchors.rightMargin: Theme.spaceMd
        anchors.top: parent.top; anchors.topMargin: Theme.spaceSm
        text: "D"
        color: vehicleState.gear === "D" ? Theme.accentSoft : Theme.textMuted
    }
    GearLabel {
        anchors.right: parent.right; anchors.rightMargin: Theme.spaceMd
        anchors.verticalCenter: parent.verticalCenter
        text: "P"
        color: vehicleState.gear === "P" ? Theme.accentSoft : Theme.textMuted
    }
    GearLabel {
        anchors.right: parent.right; anchors.rightMargin: Theme.spaceMd
        anchors.bottom: parent.bottom; anchors.bottomMargin: Theme.spaceSm
        text: "R"
        color: vehicleState.gear === "R" ? Theme.accentSoft : Theme.textMuted
    }
}
