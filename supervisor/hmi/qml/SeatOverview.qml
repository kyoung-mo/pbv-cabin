import QtQuick
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

        Text {
            text: "좌석 선택"
            color: Theme.textPrimary
            font.pixelSize: Theme.fsTitle
            font.bold: true
            font.letterSpacing: Theme.tracking
            Layout.alignment: Qt.AlignHCenter
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
