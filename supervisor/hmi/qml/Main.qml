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
}
