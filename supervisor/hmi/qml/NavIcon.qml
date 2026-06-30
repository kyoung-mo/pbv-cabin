import QtQuick

// 하단바용 심플 아이콘 — Canvas로 그린다(외부 SVG/이펙트 모듈 불필요).
//   kind: "seats"(좌석) / "home"(홈) / "modes"(격자)
//   color: 채움색(상위에서 활성/비활성 틴트 전달). 색/종류 바뀌면 다시 그림.
Canvas {
    id: ic
    property string kind: "home"
    property color color: "#000000"
    width: 26
    height: 26
    antialiasing: true
    onColorChanged: requestPaint()
    onKindChanged: requestPaint()

    onPaint: {
        var ctx = getContext("2d")
        ctx.reset()
        ctx.fillStyle = ic.color
        var w = width, h = height

        if (kind === "home") {
            // 지붕(삼각형) + 몸체(둥근 사각)
            ctx.beginPath()
            ctx.moveTo(w * 0.50, h * 0.10)
            ctx.lineTo(w * 0.93, h * 0.47)
            ctx.lineTo(w * 0.07, h * 0.47)
            ctx.closePath()
            ctx.fill()
            ctx.beginPath()
            ctx.roundedRect(w * 0.20, h * 0.44, w * 0.60, h * 0.46, 3, 3)
            ctx.fill()
        } else if (kind === "seats") {
            // 등받이(상단 바) + 쿠션(아래 큰 면) — 위에서 본 좌석 느낌
            ctx.beginPath()
            ctx.roundedRect(w * 0.26, h * 0.14, w * 0.48, h * 0.22, 3, 3)
            ctx.fill()
            ctx.beginPath()
            ctx.roundedRect(w * 0.18, h * 0.42, w * 0.64, h * 0.40, 4, 4)
            ctx.fill()
        } else { // modes — 2x2 격자
            var pad = w * 0.16
            var gap = w * 0.12
            var s = (w - 2 * pad - gap) / 2
            for (var i = 0; i < 2; i++) {
                for (var j = 0; j < 2; j++) {
                    ctx.beginPath()
                    ctx.roundedRect(pad + i * (s + gap), pad + j * (s + gap), s, s, 2, 2)
                    ctx.fill()
                }
            }
        }
    }
}
