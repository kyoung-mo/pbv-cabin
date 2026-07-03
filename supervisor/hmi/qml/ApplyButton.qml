import QtQuick
import QtQuick.Controls
import "."

// "적용" 버튼 — 목표값을 3D 좌석에 커밋한다.
//   · dirty(목표≠현재)일 때만 활성 + accent 강조.
//   · 같으면 비활성 + 흐리게 해서 "적용할 변경 없음"을 표시.
Button {
    id: btn

    property bool dirty: false
    text: "적용"
    enabled: dirty
    padding: 0
    implicitWidth: 116
    implicitHeight: 56

    opacity: dirty ? 1.0 : 0.4
    Behavior on opacity {
        NumberAnimation { duration: Theme.durMed; easing.type: Theme.easeStandard }
    }

    background: Card {
        radius: Theme.radiusSm
        highlighted: btn.dirty
        pressed: btn.pressed
        fillTop: btn.pressed ? "#553B82F6"
                             : (btn.dirty ? "#443B82F6" : Theme.surfaceTop)
        fillBottom: btn.pressed ? "#403B82F6"
                                : (btn.dirty ? "#2e3B82F6" : Theme.surfaceBottom)
    }

    contentItem: Text {
        text: btn.text
        color: btn.dirty ? Theme.textPrimary : Theme.textMuted
        font.pixelSize: Theme.fsLabel
        font.bold: true
        font.letterSpacing: Theme.tracking
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
}
