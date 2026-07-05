import QtQuick
import QtQuick.Controls
import QtQuick.Window
import "."

// 풀스크린 가로화면.
//   · ACTIVE : 좌우 2분할(왼쪽 차량 40% / 오른쪽 패널 60%) — 기존 화면.
//   · AMBIENT: 오른쪽 패널이 오른쪽으로 슬라이드 아웃, 왼쪽 차량이 전체 폭으로 확대.
//     (기어 슬라이드/ GEAR 표시는 LeftCar 안에 있어 폭 확대 시 화면 중앙으로 자동 정렬.)
ApplicationWindow {
    id: win
    visible: true
    width: 1280
    height: 720
    visibility: startWindowed ? Window.Windowed : Window.FullScreen
    title: "PBV Cabin HMI (step1)"
    color: Theme.bgBottom

    // 대기 모드 여부 — uiMode 에 바인딩. 레이아웃 전환의 단일 트리거.
    readonly property bool ambient: vehicleState.uiMode === "AMBIENT"

    // 검증 편의: Esc로 종료
    Shortcut { sequence: "Esc"; onActivated: Qt.quit() }

    // Row 대신 절대배치 — 폭/위치를 개별 애니메이션해 부드럽게 전환한다.
    // 콘텐츠 영역 — 하단 내비바 높이만큼 비워, 패널/3D가 바에 가리지 않게 한다.
    Item {
        anchors.fill: parent
        anchors.bottomMargin: Theme.navHeight

        // 왼쪽 차량 3D: ACTIVE 40% → AMBIENT 전체 폭.
        LeftCar {
            id: leftCar
            x: 0
            height: parent.height
            width: win.ambient ? parent.width : parent.width * 0.4
            Behavior on width {
                NumberAnimation {
                    duration: Cfg.ambientTransitionMs; easing.type: Easing.InOutQuad
                }
            }
        }

        // 오른쪽 패널: 폭은 고정(60%), x로 화면 밖(오른쪽)까지 슬라이드 + 페이드.
        //   ACTIVE x = 40%(차량 오른쪽 끝) → AMBIENT x = 전체 폭(완전히 밖).
        RightPanel {
            id: rightPanel
            height: parent.height
            width: parent.width * 0.6
            x: win.ambient ? parent.width : parent.width * 0.4
            opacity: win.ambient ? 0.0 : 1.0
            enabled: !win.ambient            // 대기 중엔 패널 입력 비활성(화면 밖)
            Behavior on x {
                NumberAnimation {
                    duration: Cfg.ambientTransitionMs; easing.type: Easing.InOutQuad
                }
            }
            Behavior on opacity {
                NumberAnimation {
                    duration: Cfg.ambientTransitionMs; easing.type: Easing.InOutQuad
                }
            }
        }
    }

    // 하단 내비게이션 바 — 화면 하단 가로 전체. 콘텐츠 위(z-order 최상단)에 고정.
    NavBar {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: Theme.navHeight
    }

    // 뒷좌석 슬라이드 원점 정렬(호밍) 중 — 전체 화면 잠금 오버레이.
    //   vehicleState.homingActive 동안 뒤 입력을 막고 안내를 띄운다(모드/좌석 명령 겹침 방지).
    Rectangle {
        id: homingOverlay
        anchors.fill: parent
        z: 1000
        visible: vehicleState.homingActive
        color: "#cc0b0f14"
        // 뒤 콘텐츠 입력 완전 차단
        MouseArea { anchors.fill: parent; hoverEnabled: true; onClicked: {} }

        Column {
            anchors.centerIn: parent
            width: Math.min(parent.width * 0.72, 660)
            spacing: 22

            Rectangle {   // 회전 스피너
                anchors.horizontalCenter: parent.horizontalCenter
                width: 54; height: 54; radius: 27
                color: "transparent"; border.color: "#4f9dff"; border.width: 5
                Rectangle {
                    width: 12; height: 12; radius: 6; color: "#4f9dff"
                    anchors.top: parent.top; anchors.horizontalCenter: parent.horizontalCenter
                }
                RotationAnimation on rotation {
                    running: homingOverlay.visible
                    loops: Animation.Infinite; from: 0; to: 360; duration: 900
                }
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "뒷좌석 슬라이드 원점 정렬"
                color: "white"; font.pixelSize: 30; font.bold: true
            }
            // 단계별 안내(왼쪽/오른쪽) — vehicleState.homingPrompt
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                lineHeight: 1.3
                text: vehicleState.homingPrompt
                color: "#c9d2df"; font.pixelSize: 18
            }
            // 확인/다음 버튼 — 단계 진행(왼쪽 완료→오른쪽, 오른쪽 완료→주행 원복)
            Rectangle {
                id: confirmBtn
                anchors.horizontalCenter: parent.horizontalCenter
                width: confirmTxt.implicitWidth + 68
                height: 62; radius: 12
                color: confirmMa.pressed ? "#2f6fd0" : "#4f9dff"
                Text {
                    id: confirmTxt
                    anchors.centerIn: parent
                    text: vehicleState.homingConfirmText
                    color: "white"; font.pixelSize: 20; font.bold: true
                }
                MouseArea {
                    id: confirmMa
                    anchors.fill: parent
                    onClicked: vehicleState.confirmHomingStep()
                }
            }
        }
    }
}
