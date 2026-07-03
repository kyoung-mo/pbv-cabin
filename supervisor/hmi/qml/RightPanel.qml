import QtQuick
import "."

// 오른쪽 패널: right_panel_screen 상태에 따라 3화면 중 하나를 binding으로 표시.
// Loader가 화면 전환 시 컴포넌트를 새로 만들므로, SEAT_DETAIL 재진입 시
// 슬라이더가 저장된 좌석 각도값으로 다시 초기화된다(값 유지).
//
// 전환은 즉시 교체가 아니라 크로스페이드 + 살짝 슬라이드/스케일(약 220~300ms).
//   · vehicleState.rightPanelScreen 이 바뀌면 현재 화면을 페이드아웃(살짝 축소)
//   · 그 시점에 표시 컴포넌트(shown)를 실제로 교체
//   · 새 화면을 오른쪽에서 슬라이드 + 페이드인 (OutCubic)
// ※ 상태/로직은 그대로. shown 은 표시용 로컬 미러일 뿐이다.
Item {
    id: root

    // 현재 "표시 중인" 화면 — 전환 애니메이션 동안 권위 상태보다 늦게 따라간다.
    // ※ 라이브 바인딩이면 권위 상태와 동시에 갱신돼 전환 가드가 무력화되므로,
    //   초기값만 한 번 세팅하고 이후엔 swapAnim 의 ScriptAction 에서만 갱신한다.
    property string shown: ""
    Component.onCompleted: shown = vehicleState.rightPanelScreen

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Theme.bgTop }
            GradientStop { position: 0.5; color: Theme.bgMid }
            GradientStop { position: 1.0; color: Theme.bgBottom }
        }
    }

    Item {
        id: content
        anchors.fill: parent
        transform: Translate { id: slide; x: 0 }

        Loader {
            anchors.fill: parent
            sourceComponent: {
                switch (root.shown) {
                case "MODE_SELECT":   return modeSelectComp
                case "SEAT_OVERVIEW": return seatOverviewComp
                case "SEAT_DETAIL":   return seatDetailComp
                default:              return modeSelectComp
                }
            }
        }
    }

    Component { id: modeSelectComp;   ModeSelect {} }
    Component { id: seatOverviewComp; SeatOverview {} }
    Component { id: seatDetailComp;   SeatDetail {} }

    // 권위 상태가 바뀌면 크로스페이드 전환 시작
    Connections {
        target: vehicleState
        function onRightPanelScreenChanged() {
            if (vehicleState.rightPanelScreen !== root.shown)
                swapAnim.restart()
        }
    }

    SequentialAnimation {
        id: swapAnim
        // ① 나가기: 페이드아웃 + 살짝 축소
        ParallelAnimation {
            NumberAnimation {
                target: content; property: "opacity"; to: 0.0
                duration: Theme.durFast; easing.type: Theme.easeStandard
            }
            NumberAnimation {
                target: content; property: "scale"; to: 0.985
                duration: Theme.durFast; easing.type: Theme.easeStandard
            }
        }
        // ② 표시 컴포넌트 교체 + 들어올 위치(오른쪽)로 점프
        ScriptAction {
            script: {
                root.shown = vehicleState.rightPanelScreen
                slide.x = 28
            }
        }
        // ③ 들어오기: 슬라이드 + 페이드인 + 스케일 복귀
        ParallelAnimation {
            NumberAnimation {
                target: content; property: "opacity"; to: 1.0
                duration: Theme.durSlow; easing.type: Theme.easeStandard
            }
            NumberAnimation {
                target: content; property: "scale"; to: 1.0
                duration: Theme.durSlow; easing.type: Theme.easeStandard
            }
            NumberAnimation {
                target: slide; property: "x"; to: 0
                duration: Theme.durSlow; easing.type: Theme.easeStandard
            }
        }
    }
}
