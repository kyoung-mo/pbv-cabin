import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// SEAT_OVERVIEW: 차량을 위에서 본 평면도(top-view)로 좌석 4개를 공간 배치.
//   · 위=앞(운전석/조수석), 아래=뒤(뒷좌석 좌/우). 좌/우도 실제 위치대로.
//   · 각 좌석 = 좌석 모양 아이콘(등받이 바 + 쿠션) + 라벨. 운전석엔 스티어링 힌트.
//   · 선택/호버 시 accent 글로우·테두리 강조, 현재 선택 좌석 표시.
//   · 클릭 → 기존처럼 selectSeat(sid) → SEAT_DETAIL.
// Theme 토큰으로 오른쪽 패널 톤과 통일.
Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spaceLg
        spacing: Theme.spaceMd

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spaceMd

            Text {
                text: "좌석 선택"
                color: Theme.textPrimary
                font.pixelSize: Theme.fsTitle
                font.bold: true
                font.letterSpacing: Theme.tracking
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                Layout.leftMargin: 110   // 오른쪽 버튼 폭만큼 보정해 제목을 시각 중앙에
            }

            // 뒷좌석 슬라이드 수동 원점 정렬(끼임/estop 후 재정렬용). 호밍 중엔 비활성.
            Button {
                id: homeBtn
                text: "원점 잡기"
                enabled: !vehicleState.homingActive
                font.pixelSize: Theme.fsLabel
                font.bold: true
                padding: 0
                Layout.preferredWidth: 110
                Layout.preferredHeight: 44
                background: Card {
                    radius: Theme.radiusSm
                    fillTop: homeBtn.pressed ? "#14000000" : Theme.surfaceTop
                    fillBottom: homeBtn.pressed ? "#0a000000" : Theme.surfaceBottom
                    pressed: homeBtn.pressed
                    opacity: homeBtn.enabled ? 1.0 : 0.4
                }
                contentItem: Text {
                    text: homeBtn.text
                    color: Theme.textPrimary
                    font: homeBtn.font
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: vehicleState.homeRearSlides()
            }
        }

        // ── 차량 평면도(위=앞) ──────────────────────────────────────
        Rectangle {
            id: plan
            Layout.alignment: Qt.AlignHCenter
            Layout.fillHeight: true
            // 세로로 긴 차체 비율 — 높이에 맞춰 폭 결정.
            Layout.preferredWidth: Math.min(root.width - 2 * Theme.spaceLg, height * 0.72)
            radius: Theme.radiusLg + 8
            gradient: Gradient {
                GradientStop { position: 0.0; color: Theme.surfaceRaised }
                GradientStop { position: 1.0; color: Theme.surfaceSolid }
            }
            border.color: Theme.borderStrong
            border.width: 1

            // 앞유리/후드 힌트 (상단 = 차 앞)
            Rectangle {
                id: frontHint
                anchors { top: parent.top; left: parent.left; right: parent.right }
                anchors.margins: 12
                height: 34
                radius: Theme.radiusSm
                color: Theme.border                  // 옅은 회색 헤더 띠(라이트)
                Text {
                    anchors.centerIn: parent
                    text: "▲  앞 (FRONT)"
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fsLabel - 5
                    font.letterSpacing: 3
                }
            }

            // 좌석 4개 — 2x2 (앞줄 위 / 뒷줄 아래, 좌-우)
            GridLayout {
                anchors {
                    top: frontHint.bottom
                    left: parent.left
                    right: parent.right
                    bottom: parent.bottom
                    margins: Theme.spaceLg
                }
                columns: 2
                rowSpacing: Theme.spaceXl
                columnSpacing: Theme.spaceLg

                Repeater {
                    model: [
                        { sid: "driver",     label: "운전석",     wheel: true  },
                        { sid: "passenger",  label: "조수석",     wheel: false },
                        { sid: "rear_left",  label: "뒷좌석(좌)", wheel: false },
                        { sid: "rear_right", label: "뒷좌석(우)", wheel: false }
                    ]

                    delegate: Card {
                        id: tile
                        required property var modelData
                        property bool isSel: vehicleState.selectedSeat === modelData.sid

                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: Theme.radiusLg
                        highlighted: isSel || hov.hovered
                        pressed: ma.pressed
                        // 선택=옅은 블루 틴트 / 평소=흰·옅은 회색 카드
                        fillTop:    isSel ? "#ffe6efff" : Theme.surfaceTop
                        fillBottom: isSel ? "#ffd9e6ff" : Theme.surfaceBottom
                        Behavior on fillTop    { ColorAnimation { duration: Theme.durMed } }
                        Behavior on fillBottom { ColorAnimation { duration: Theme.durMed } }

                        // ── 좌석 모양 아이콘 ──
                        Item {
                            anchors.fill: parent
                            anchors.margins: Theme.spaceMd

                            // 등받이(상단 바)
                            Rectangle {
                                id: seatBack
                                anchors { top: parent.top; horizontalCenter: parent.horizontalCenter }
                                width: parent.width * 0.74
                                height: parent.height * 0.20
                                radius: Theme.radiusSm
                                color: tile.isSel ? Theme.accent : "#ff7c8696"   // 평소=살짝 진한 회색
                                Behavior on color { ColorAnimation { duration: Theme.durMed } }
                            }
                            // 쿠션(아래 큰 면)
                            Rectangle {
                                id: seatCushion
                                anchors { top: seatBack.bottom; topMargin: 5
                                          horizontalCenter: parent.horizontalCenter }
                                width: parent.width * 0.82
                                height: parent.height * 0.46
                                radius: Theme.radiusSm
                                color: tile.isSel ? Theme.accentSoft : "#ff9aa3b2"  // 평소=중간 회색
                                Behavior on color { ColorAnimation { duration: Theme.durMed } }

                                // 스티어링 휠 힌트(운전석만)
                                Rectangle {
                                    visible: tile.modelData.wheel
                                    anchors.centerIn: parent
                                    width: Math.min(parent.width, parent.height) * 0.42
                                    height: width
                                    radius: width / 2
                                    color: "transparent"
                                    border.color: tile.isSel ? "#cfe0ff" : Theme.textSecondary
                                    border.width: 3
                                }
                            }
                            // 라벨
                            Text {
                                anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter }
                                text: tile.modelData.label
                                color: Theme.textPrimary
                                font.pixelSize: Theme.fsLabel
                                font.bold: true
                                font.letterSpacing: Theme.tracking
                            }
                        }

                        // 끼임 경고 배지 — Seat_Status.*_Pinch_Detected 수신 시.
                        Rectangle {
                            visible: vehicleState.seatPinch[tile.modelData.sid] === true
                            anchors { top: parent.top; right: parent.right; margins: 8 }
                            width: pinchTxt.width + 18
                            height: pinchTxt.height + 10
                            radius: height / 2
                            color: "#ff3b30"
                            z: 5
                            // 깜빡임으로 주의 환기
                            SequentialAnimation on opacity {
                                running: parent.visible
                                loops: Animation.Infinite
                                NumberAnimation { from: 1.0; to: 0.35; duration: 450 }
                                NumberAnimation { from: 0.35; to: 1.0; duration: 450 }
                            }
                            Text {
                                id: pinchTxt
                                anchors.centerIn: parent
                                text: "⚠ 끼임"
                                color: "white"
                                font.pixelSize: Theme.fsLabel - 4
                                font.bold: true
                            }
                        }

                        HoverHandler { id: hov }
                        MouseArea {
                            id: ma
                            anchors.fill: parent
                            onClicked: vehicleState.selectSeat(tile.modelData.sid)
                        }
                    }
                }
            }
        }
    }
}
