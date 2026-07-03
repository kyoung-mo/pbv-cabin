import QtQuick
import "."

// 글래스 카드 — 테슬라풍 떠 보이는 둥근 패널.
//   · 그림자/글로우: 블러 이펙트 모듈이 없는 환경이라 동심(겹친) 스트로크로 근사.
//   · 상단 내부 sheen 으로 유리 윤곽 느낌.
//   · pressed=true 면 살짝 눌리는 피드백(scale↓), highlighted=true 면 accent 글로우.
// 콘텐츠는 default property 로 받아 둥근 본체 안에 clip 되어 배치된다.
Item {
    id: card

    property real radius: Theme.radius
    property color fillTop: Theme.surfaceTop
    property color fillBottom: Theme.surfaceBottom
    property color borderColor: Theme.border
    property bool highlighted: false
    property bool pressed: false
    property real elevation: 1.0
    property bool clipContent: true
    // 풀블리드(가득 채우는) 콘텐츠를 둥근 본체 안쪽으로 살짝 들여 배치하는 여백.
    // clip 은 사각이라 둥근 모서리를 못 따라가므로(이미지가 코너로 삐져나옴),
    // 이미지를 이만큼 들이면 사각 코너가 둥근 본체 안에 들어가 본체(밝은 면)가
    // 둥근 프레임처럼 감싼다. 기본 0(글자/아이콘 카드엔 영향 없음).
    property real contentInset: 0

    default property alias content: contentHolder.data

    // 눌림 피드백 — 본체와 오버레이를 함께 스케일
    scale: pressed ? 0.975 : 1.0
    Behavior on scale {
        NumberAnimation { duration: Theme.durFast; easing.type: Theme.easeStandard }
    }

    // ── 드롭섀도 — 라이트 배경용: 아주 옅고 부드러운 사방 동심 스트로크 ──────
    // 흰 배경에선 진한/한쪽 치우친 그림자가 띠(밴딩)·잘림처럼 보여서, 사방 균일하게
    // 살짝 아래로만 치우치게(+1px) 깔고 알파를 크게 낮춰 매끈하게 번지도록.
    Repeater {
        model: 10
        Rectangle {
            z: -2
            property int k: index + 1
            x: -k
            y: -k + 1                            // 사방 균일 + 1px 만 아래로
            width: card.width + 2 * k
            height: card.height + 2 * k
            radius: card.radius + k
            color: "transparent"
            antialiasing: true
            border.width: 1
            border.color: Qt.rgba(0, 0, 0, 0.030 * card.elevation * (1 - index / 10))
        }
    }

    // ── 선택 글로우 (accent, 사방 동심 스트로크) ────────────────────
    Repeater {
        model: 7
        Rectangle {
            z: -1
            property int k: index + 1
            x: -k * 1.6
            y: -k * 1.6
            width: card.width + 3.2 * k
            height: card.height + 3.2 * k
            radius: card.radius + k * 1.6
            color: "transparent"
            antialiasing: true
            border.width: 2
            border.color: Qt.rgba(Theme.accentR, Theme.accentG, Theme.accentB,
                                  0.18 * (1 - index / 7))
            opacity: card.highlighted ? 1 : 0
            Behavior on opacity {
                NumberAnimation { duration: Theme.durMed; easing.type: Theme.easeStandard }
            }
        }
    }

    // ── 본체 (글래스 그라데이션) ────────────────────────────────────
    Rectangle {
        id: body
        anchors.fill: parent
        radius: card.radius
        clip: card.clipContent
        antialiasing: true
        gradient: Gradient {
            GradientStop { position: 0.0; color: card.fillTop }
            GradientStop { position: 1.0; color: card.fillBottom }
        }

        // 콘텐츠 홀더 — contentInset 만큼 안쪽으로 들여, 풀블리드 이미지의 사각
        // 코너가 둥근 본체 밖으로 삐져나오지 않게 한다(본체가 둥근 프레임 역할).
        Item {
            id: contentHolder
            anchors.fill: parent
            anchors.margins: card.contentInset
        }
    }

    // ── 보더 + 상단 sheen (콘텐츠 위) ───────────────────────────────
    Rectangle {
        anchors.fill: parent
        radius: card.radius
        color: "transparent"
        antialiasing: true
        border.width: 1
        border.color: card.highlighted ? Theme.accentBorder : card.borderColor
        Behavior on border.color { ColorAnimation { duration: Theme.durMed } }

        // 상단 내부 하이라이트 — 얇은 밝은 띠로 유리 윤곽
        Rectangle {
            anchors.top: parent.top
            anchors.topMargin: 1
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width - card.radius
            height: 1.5
            radius: 1
            color: Theme.sheen
        }
    }
}
