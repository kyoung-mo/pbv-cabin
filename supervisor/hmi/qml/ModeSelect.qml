import QtQuick
import QtQuick.Layouts
import "."

// MODE_SELECT (기본): 2x2 글래스 타일 4개. 누르면 cabin_mode 갱신 + accent 글로우 강조.
Item {
    id: root

    GridLayout {
        anchors.fill: parent
        anchors.margins: Theme.spaceXl
        columns: 2
        rowSpacing: Theme.spaceLg
        columnSpacing: Theme.spaceLg

        Repeater {
            model: [
                { name: "주행",        color: "#3367d6", img: "drive" },
                { name: "회의",        color: "#2e9e4f", img: "meeting" },
                { name: "Full-space", color: "#b8860b", img: "fullspace" },
                { name: "휴식",        color: "#8e44ad", img: "rest" }
            ]
            delegate: Card {
                required property var modelData
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: Theme.radius

                // 선택 = accent 글로우, 누름 = 눌림 피드백
                highlighted: vehicleState.cabinMode === modelData.name
                pressed: tileMouse.pressed
                // 인터록: 주행/후진 중이면 타일을 잠가 부드럽게 흐리게
                opacity: vehicleState.modeLocked ? 0.4 : 1.0
                Behavior on opacity {
                    NumberAnimation { duration: Theme.durMed; easing.type: Theme.easeStandard }
                }

                // 모드별 실사풍 배경 이미지 (기존 유지)
                Image {
                    anchors.fill: parent
                    source: "../assets/modes/" + modelData.img + ".png"
                    fillMode: Image.PreserveAspectCrop
                    smooth: true
                }
                // 톤 통일 + 글자 가독성용 스크림 (위 살짝 / 아래 강하게) — 강도는 Cfg 상수.
                // CC0/PD 사진 4장의 제각각 톤을 어두운 그라데이션으로 통일한다.
                Rectangle {
                    anchors.fill: parent
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Qt.rgba(0, 0, 0, Cfg.modeScrimTopA) }
                        GradientStop { position: 0.5; color: Qt.rgba(0, 0, 0, Cfg.modeScrimMidA) }
                        GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, Cfg.modeScrimBotA) }
                    }
                }

                Text {
                    anchors.left: parent.left
                    anchors.bottom: parent.bottom
                    anchors.margins: Theme.spaceLg
                    text: modelData.name
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fsHero
                    font.bold: true
                    font.letterSpacing: Theme.tracking
                }

                MouseArea {
                    id: tileMouse
                    anchors.fill: parent
                    // 잠겨 있으면 모드 변경 대신 사유만 출력
                    onClicked: {
                        if (vehicleState.modeLocked)
                            vehicleState.modeBlockedNotice()
                        else
                            vehicleState.selectMode(modelData.name)
                    }
                }
            }
        }
    }
}
