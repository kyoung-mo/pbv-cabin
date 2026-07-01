import QtQuick
import "."

// ── 조향각 시각화 운전대 ──────────────────────────────────────────
// 왼쪽 오버레이(기어·엑셀/브레이크) 아래에 놓는 운전대 모형.
//   · Canvas 로 림+스포크+허브를 "한 번만" 그리고, Item 자체를 rotation 으로 돌린다
//     (내용은 static → 회전해도 재페인트 없음 = Pi 가벼움).
//   · angle 은 밖에서 조향각을 매핑해 넣는다(+면 시계방향=우회전). 12시 accent 점이 방향을 알려준다.
Item {
    id: root

    property real angle: 0                              // 표시 회전각(도). +시계방향(우), −반시계(좌).
    property color rimColor:    Theme.overlayTextPrimary
    property color spokeColor:  Theme.overlayTextSecondary
    property color markerColor: "#34c759"              // 12시 방향 표식(회전 방향 한눈에)

    implicitWidth: 96
    implicitHeight: 96

    Canvas {
        id: canvas
        anchors.fill: parent
        rotation: root.angle
        transformOrigin: Item.Center
        Behavior on rotation { NumberAnimation { duration: 80; easing.type: Easing.OutQuad } }

        // 색이 밖에서 바뀌면 다시 그린다(평소엔 정적).
        Connections {
            target: root
            function onRimColorChanged()    { canvas.requestPaint() }
            function onSpokeColorChanged()  { canvas.requestPaint() }
            function onMarkerColorChanged() { canvas.requestPaint() }
        }

        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            var cx = width / 2, cy = height / 2
            var R  = Math.min(width, height) / 2 - 8    // 림 중심 반경
            var rimW = Math.max(6, R * 0.16)
            var hubR = R * 0.30

            ctx.lineCap = "round"

            // 림(바깥 링)
            ctx.lineWidth = rimW
            ctx.strokeStyle = root.rimColor
            ctx.beginPath()
            ctx.arc(cx, cy, R, 0, Math.PI * 2)
            ctx.stroke()

            // 스포크 3개 — 9시(좌)·3시(우)·6시(하). 12시는 비워 표식 자리.
            ctx.lineWidth = Math.max(5, R * 0.14)
            ctx.strokeStyle = root.spokeColor
            var ends = [Math.PI, 0, Math.PI / 2]
            for (var i = 0; i < ends.length; i++) {
                var a = ends[i]
                ctx.beginPath()
                ctx.moveTo(cx + Math.cos(a) * hubR,          cy + Math.sin(a) * hubR)
                ctx.lineTo(cx + Math.cos(a) * (R - rimW / 2), cy + Math.sin(a) * (R - rimW / 2))
                ctx.stroke()
            }

            // 허브(중앙)
            ctx.fillStyle = root.spokeColor
            ctx.beginPath()
            ctx.arc(cx, cy, hubR, 0, Math.PI * 2)
            ctx.fill()

            // 12시 표식(accent) — 회전하면 좌/우로 움직여 조향 방향이 보인다.
            ctx.fillStyle = root.markerColor
            ctx.beginPath()
            ctx.arc(cx, cy - R, rimW * 0.72, 0, Math.PI * 2)
            ctx.fill()
        }
    }
}
