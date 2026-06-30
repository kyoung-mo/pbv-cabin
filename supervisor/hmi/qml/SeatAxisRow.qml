import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// 좌석 축(리클라인/회전/슬라이드) 1줄 — 라벨 + 값 + accent 슬라이더.
// 값/조작 로직은 갖지 않고, movedTo(v) 시그널로 상위(VehicleState 슬롯)에 위임.
ColumnLayout {
    id: row
    spacing: Theme.spaceSm

    property string label: ""
    property string unit: ""
    property int value: 0
    property int to: 180
    signal movedTo(int v)

    RowLayout {
        Layout.fillWidth: true
        Text {
            text: row.label
            color: Theme.textSecondary
            font.pixelSize: Theme.fsLabel
            font.letterSpacing: Theme.tracking
        }
        Text {
            text: "(" + row.unit + ")"
            color: Theme.textMuted
            font.pixelSize: Theme.fsLabel - 3
        }
        Item { Layout.fillWidth: true }
        // 현재 값 — accent 강조, 변화 시 부드럽게(스테이지4 Behavior)
        Text {
            id: valueText
            property real anim: row.value
            Behavior on anim {
                NumberAnimation { duration: Theme.durFast; easing.type: Theme.easeStandard }
            }
            text: Math.round(anim)
            color: Theme.accentSoft
            font.pixelSize: Theme.fsBody
            font.bold: true
        }
    }

    Slider {
        id: s
        Layout.fillWidth: true
        from: 0
        to: row.to
        stepSize: 1
        value: row.value
        onMoved: row.movedTo(Math.round(value))

        background: Rectangle {
            x: s.leftPadding
            y: s.topPadding + s.availableHeight / 2 - height / 2
            width: s.availableWidth
            height: 8
            radius: 4
            color: Theme.borderStrong

            // 채워진 구간 — accent 그라데이션
            Rectangle {
                width: s.position * parent.width
                height: parent.height
                radius: 4
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: Theme.accent }
                    GradientStop { position: 1.0; color: Theme.accentSoft }
                }
            }
        }

        handle: Rectangle {
            x: s.leftPadding + s.visualPosition * (s.availableWidth - width)
            y: s.topPadding + s.availableHeight / 2 - height / 2
            implicitWidth: 28
            implicitHeight: 28
            radius: 14
            color: s.pressed ? Theme.accentSoft : "#f4f6fb"
            border.color: Theme.accent
            border.width: 2
            scale: s.pressed ? 1.12 : 1.0
            Behavior on scale {
                NumberAnimation { duration: Theme.durFast; easing.type: Theme.easeStandard }
            }
        }
    }
}
