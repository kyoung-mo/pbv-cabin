import QtQuick
import "."

// 왼쪽 "차량" 영역 — QtQuick3D 실시간 3D 디지털 트윈.
//   · 배경: 루프 없는 컷어웨이 캐빈(Cabin3D). 카메라 고정 3/4 부감(차 모형 그대로, 조향 연동 없음).
//   · 오버레이: 좌상단 [세로 기어 슬라이드(D/P/R) → 그 아래 엑셀/브레이크 세로 막대] + 하단 중앙 GEAR 텍스트.
//   · 빈 곳 탭 → 홈(대기) → 모드 → 좌석 → 홈 순환(cycleCarArea).
Item {
    id: root

    // 운전대 표시 회전각(도) — wheelSteering(±127)을 ±135°로 매핑. +면 우회전(시계방향).
    //   (실제 조향각 방향 그대로. 화면상 반대로 돌면 부호만 뒤집으면 된다.)
    readonly property real steerVisAngle: {
        var s = Math.max(-127, Math.min(127, vehicleState.wheelSteering))
        return s / 127 * 135
    }

    // 3D 캐빈 (영역 전체)
    Cabin3D {
        id: cabin3d
        anchors.fill: parent
    }

    // 빈 곳 탭 (3D 위, 좌상단 컨트롤 아래):
    //   한 번 누를 때마다 홈(대기) → 모드 → 좌석 → 홈 순환. (cycleCarArea 가 상태 판단)
    MouseArea {
        anchors.fill: parent
        onClicked: vehicleState.cycleCarArea()
    }

    // ── 좌상단: 세로 기어 슬라이드(D/P/R) + 그 아래 엑셀/브레이크 세로 막대 ──
    //   엑셀/브레이크는 항상 실제 입력값(P에서도 읽어 표시). 실제 바퀴 정지는 CAN 게이트가 담당.
    //   세로로 아래→위로 차오른다.
    Column {
        id: leftStack
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 16
        spacing: 16

        GearSlider {
            width: 120
            height: 300
        }

        // 엑셀(A, 초록)/브레이크(B, 빨강) 세로 막대 — 기어 슬라이드 아래, 슬라이드 폭 안에서 중앙 정렬.
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 26

            // ── 엑셀 ──
            Column {
                spacing: 6
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: vehicleState.wheelThrottle + "%"
                    color: "#34c759"
                    font.pixelSize: 14
                    font.bold: true
                }
                Rectangle {                          // 세로 트랙
                    width: 16; height: 120; radius: 8
                    color: "#40000000"
                    border.color: Theme.overlayBorder
                    border.width: 1
                    Rectangle {                      // 아래→위 채움
                        anchors.bottom: parent.bottom
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: parent.width
                        radius: 8
                        color: "#34c759"
                        height: parent.height
                                * Math.max(0, Math.min(1, vehicleState.wheelThrottle / 100))
                        Behavior on height { NumberAnimation { duration: 60 } }
                    }
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "A"; color: "#34c759"
                    font.pixelSize: 15; font.bold: true
                }
            }

            // ── 브레이크 ──
            Column {
                spacing: 6
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: vehicleState.wheelBrake + "%"
                    color: "#ff3b30"
                    font.pixelSize: 14
                    font.bold: true
                }
                Rectangle {
                    width: 16; height: 120; radius: 8
                    color: "#40000000"
                    border.color: Theme.overlayBorder
                    border.width: 1
                    Rectangle {
                        anchors.bottom: parent.bottom
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: parent.width
                        radius: 8
                        color: "#ff3b30"
                        height: parent.height
                                * Math.max(0, Math.min(1, vehicleState.wheelBrake / 100))
                        Behavior on height { NumberAnimation { duration: 60 } }
                    }
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "B"; color: "#ff3b30"
                    font.pixelSize: 15; font.bold: true
                }
            }
        }

        // ── 운전대 모형 ── 실제 조향각(wheelSteering)을 반영해 좌/우로 회전. 12시 초록점=방향.
        Column {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 6

            // 조향값(도) — |각| < 3° 데드밴드는 0°, 아니면 L/R + 각도.
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: Math.abs(root.steerVisAngle) < 3
                      ? "0°"
                      : (vehicleState.wheelSteering > 0 ? "R " : "L ")
                        + Math.round(Math.abs(root.steerVisAngle)) + "°"
                color: Theme.overlayTextPrimary
                font.pixelSize: 14
                font.bold: true
            }

            SteeringWheel {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 96; height: 96
                angle: root.steerVisAngle
                rimColor: "#111418"                  // 겉 림 = 검은색(실제 운전대 톤)
                // 가운데(스포크·허브) = 차체 색을 따옴(기본 그레이, tint 켜면 carBodyColor).
                spokeColor: Cfg.carTint ? Cfg.carBodyColor : "#8c8c8c"
            }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "STEER"
                color: Theme.overlayTextSecondary
                font.pixelSize: 13
                font.letterSpacing: 1
                font.bold: true
            }
        }
    }

    // ── 하단 중앙: 기어 상태 텍스트(항상 표시) — 어두운 알약 backing ──
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
            // 현재 속도 — Drive_Status.Current_Velocity 수신 반영(주행 중에만 노출).
            Text {
                anchors.baseline: gearVal.baseline
                visible: vehicleState.currentVelocity > 0
                text: vehicleState.currentVelocity.toFixed(1) + " RPM"
                color: Theme.overlayTextSecondary
                font.pixelSize: 22
                font.letterSpacing: 1
            }
        }
    }
}
