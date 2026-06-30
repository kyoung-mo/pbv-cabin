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

    // ── 레이싱휠 실시간 표시 (상단 중앙) — 인터록과 무관하게 항상 따라옴(문서 §5.2) ──
    //   조향각 게이지(중앙 0, 좌/우 ±130°) + 엑셀/브레이크 막대. 휠 스레드 → onWheelInput.
    Rectangle {
        id: steerHud
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 16
        width: 280
        height: 84
        radius: 16
        color: Theme.overlayPillBg
        border.color: Theme.overlayBorder
        border.width: 1

        Column {
            anchors.centerIn: parent
            spacing: 8
            width: parent.width - 28

            // 상단: "조향" + 각도값
            Row {
                width: parent.width
                Text {
                    text: "조향"
                    color: Theme.overlayTextSecondary
                    font.pixelSize: 16
                    font.letterSpacing: 2
                }
                Item { width: parent.width - steerLbl.width - steerDeg.width; height: 1 }
                Text {
                    id: steerLbl
                    visible: false
                    text: "조향"
                    font.pixelSize: 16
                }
                Text {
                    id: steerDeg
                    text: vehicleState.wheelSteering + "°"
                    color: Theme.overlayTextPrimary
                    font.pixelSize: 18
                    font.bold: true
                }
            }

            // 조향 게이지 — 중앙 0, 인디케이터가 좌우로 이동
            Rectangle {
                id: track
                width: parent.width
                height: 10
                radius: 5
                color: "#33000000"
                // 중앙 눈금
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 2; height: parent.height + 6
                    y: -3
                    color: Theme.overlayTextSecondary
                    opacity: 0.6
                }
                // 인디케이터 (조향 비율만큼 중앙에서 이동, ±130° 풀스케일)
                Rectangle {
                    width: 18; height: 18; radius: 9
                    color: Theme.accent
                    y: (parent.height - height) / 2
                    x: (parent.width - width) / 2
                        + Math.max(-1, Math.min(1, vehicleState.wheelSteering / 130))
                          * (parent.width - width) / 2
                    Behavior on x { NumberAnimation { duration: 60 } }
                }
            }

            // 하단: 엑셀(초록)/브레이크(빨강) 막대
            Row {
                width: parent.width
                spacing: 8
                Row {
                    spacing: 4
                    Text { text: "A"; color: "#34c759"; font.pixelSize: 13; font.bold: true }
                    Rectangle {
                        width: 96; height: 8; radius: 4; color: "#33000000"
                        anchors.verticalCenter: parent.verticalCenter
                        Rectangle {
                            width: parent.width * Math.max(0, Math.min(1, vehicleState.wheelThrottle / 100))
                            height: parent.height; radius: 4; color: "#34c759"
                            Behavior on width { NumberAnimation { duration: 60 } }
                        }
                    }
                }
                Row {
                    spacing: 4
                    Text { text: "B"; color: "#ff3b30"; font.pixelSize: 13; font.bold: true }
                    Rectangle {
                        width: 96; height: 8; radius: 4; color: "#33000000"
                        anchors.verticalCenter: parent.verticalCenter
                        Rectangle {
                            width: parent.width * Math.max(0, Math.min(1, vehicleState.wheelBrake / 100))
                            height: parent.height; radius: 4; color: "#ff3b30"
                            Behavior on width { NumberAnimation { duration: 60 } }
                        }
                    }
                }
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
