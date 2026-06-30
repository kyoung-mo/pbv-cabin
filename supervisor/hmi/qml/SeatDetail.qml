import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// SEAT_DETAIL: 선택된 좌석 1개를 크게 표시 + 슬라이더 2개.
//   앞좌석(운전석/조수석): 리클라인 0~180 + 회전 0~180
//   뒷좌석(좌/우)        : 리클라인 0~180 + 슬라이드 0~100
// 슬라이더 value는 vehicleState의 현재좌석 Property에 binding으로 초기화되므로
// (Loader 재생성 시) 저장된 값이 그대로 복원된다.
Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spaceLg
        spacing: Theme.spaceLg

        // 상단: 뒤로 버튼 + 좌석명
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spaceMd

            // 글래스 "뒤로" 버튼
            Button {
                id: backBtn
                text: "←  뒤로"
                font.pixelSize: Theme.fsLabel
                font.bold: true
                padding: 0
                background: Card {
                    radius: Theme.radiusSm
                    fillTop: backBtn.pressed ? "#14000000" : Theme.surfaceTop
                    fillBottom: backBtn.pressed ? "#0a000000" : Theme.surfaceBottom
                    pressed: backBtn.pressed
                    implicitWidth: 140
                    implicitHeight: 56
                }
                contentItem: Text {
                    text: backBtn.text
                    color: Theme.textPrimary
                    font: backBtn.font
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: vehicleState.backToOverview()
            }
            Text {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spaceSm
                text: vehicleState.curSeatLabel
                color: Theme.textPrimary
                font.pixelSize: Theme.fsTitle
                font.bold: true
                font.letterSpacing: Theme.tracking
            }
        }

        // 끼임 경고 배너 — 현재 선택 좌석의 Pinch_Detected 수신 시.
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            visible: vehicleState.seatPinch[vehicleState.selectedSeat] === true
            radius: Theme.radiusSm
            color: "#1aff3b30"
            border.color: "#ff3b30"
            border.width: 1
            Row {
                anchors.centerIn: parent
                spacing: 10
                Text {
                    text: "⚠"
                    color: "#ff3b30"
                    font.pixelSize: Theme.fsLabel + 4
                    font.bold: true
                    SequentialAnimation on opacity {
                        running: parent.parent.visible
                        loops: Animation.Infinite
                        NumberAnimation { from: 1.0; to: 0.3; duration: 450 }
                        NumberAnimation { from: 0.3; to: 1.0; duration: 450 }
                    }
                }
                Text {
                    text: "끼임 감지 — 안전을 위해 동작이 정지될 수 있습니다"
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fsLabel
                    font.bold: true
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }

        // 좌석 큰 박스 — 글래스 카드 + 실사풍 좌석 일러스트
        Card {
            Layout.fillWidth: true
            Layout.preferredHeight: 230
            radius: Theme.radiusLg
            // 앞좌석은 살짝 푸른 틴트, 뒷좌석은 흰 카드 — 둘 다 라이트
            fillTop: vehicleState.curIsFront ? "#ffeaf1fc" : Theme.surfaceTop
            fillBottom: Theme.surfaceBottom

            Image {
                anchors.fill: parent
                anchors.margins: Theme.spaceSm
                source: "../assets/seats/seat.png"
                fillMode: Image.PreserveAspectFit
                smooth: true
            }
            Text {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: Theme.spaceMd
                text: vehicleState.curSeatLabel
                color: Theme.textPrimary
                font.pixelSize: Theme.fsHero
                font.bold: true
                font.letterSpacing: Theme.tracking
                opacity: 0.92
            }
        }

        // --- 리클라인: 슬라이더(목표값) + "적용" 버튼 ---
        // 슬라이더는 target 만 정하고, "적용"을 눌러야 3D가 목표까지 서서히 움직인다.
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spaceMd
            SeatAxisRow {
                Layout.fillWidth: true
                label: "리클라인"
                unit: "0~180 · 90=직립"
                value: vehicleState.curReclineTarget
                to: 180
                onMovedTo: function (v) { vehicleState.setReclineTarget(v) }
            }
            ApplyButton {
                Layout.alignment: Qt.AlignVCenter
                dirty: vehicleState.curReclineDirty
                onClicked: vehicleState.applyRecline()
            }
        }

        // --- 축2 (앞=회전 0~180 / 뒤=슬라이드 0~100) + "적용" 버튼 ---
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spaceMd
            SeatAxisRow {
                Layout.fillWidth: true
                label: vehicleState.curAxis2Name
                unit: "0~" + vehicleState.curAxis2Max
                value: vehicleState.curAxis2Target
                to: vehicleState.curAxis2Max
                onMovedTo: function (v) { vehicleState.setAxis2Target(v) }
            }
            ApplyButton {
                Layout.alignment: Qt.AlignVCenter
                dirty: vehicleState.curAxis2Dirty
                onClicked: vehicleState.applyAxis2()
            }
        }

        // 아래 여백
        Item { Layout.fillHeight: true }
    }
}
