import QtQuick
import QtQuick3D

// 단색 클레이 톤 좌석 — 기본 도형(#Cube) 조립으로 만든 "도형 폴백".
//
// ※ 모델 파일을 쓰지 않은 이유:
//   · 이 Qt 빌드에는 런타임 glTF 로더(QtQuick3D.AssetUtils RuntimeLoader)가 없고,
//   · 무료 좌석 모델은 대부분 좌면+등받이가 하나로 융합된 단일 메시라
//     "등받이를 별도 노드로 좌면 기준 힌지" 요구를 만족시킬 수 없다.
//   따라서 좌면 / 베이스 / 등받이(힌지) / 헤드레스트를 각각의 도형 노드로 조립한다.
//
// 좌표계(로컬): 원점 = 좌석이 놓인 바닥면(y=0). +Z 가 좌석 정면(탑승자가 보는 방향).
//
// ── axis2 해석은 좌석 타입(isRear)에 따라 다르다 ──
//   · 앞좌석(isRear=false): axis2(0~180) → 좌석 전체 Y축 회전(deg). 0=정면(+Z).
//   · 뒷좌석(isRear=true) : axis2(0~100) → 좌석 전체 Z축 위치 이동(슬라이드).
//                            0=앞쪽으로 당김, 100=뒤쪽으로 밂.
//   회전 피벗·슬라이드 기준 모두 좌석 베이스 원점(좌면 중심 수직축)이다.
Node {
    id: seat

    // 좌석 타입 / 축 값 (각 좌석이 자기 current 값에만 바인딩됨)
    property bool isRear: false           // false=앞좌석(회전), true=뒷좌석(슬라이드)
    property real axis2: 0                 // 앞=회전(0~180) / 뒤=슬라이드(0~100) current
    property real recline: 90             // 리클라인 current (90=직립)

    // 이동 표시(보간 중 하이라이트) — Cabin3D 에서 vehicleState.seatMoving + Cfg 주입.
    property bool moving: false           // 이 좌석이 목표까지 이동(보간) 중인가
    property bool pinch: false            // 끼임(Pinch_Detected) 수신 — 빨간 경고 글로우
    property bool showIndicator: true     // 표시 on/off (Cfg.showMoveIndicator)
    property color glowColor: "#3B82F6"   // 하이라이트 색(이동)
    // 끼임이면 빨강·강조, 아니면 이동 시 파랑.
    property real glow: pinch ? 1.0 : ((moving && showIndicator) ? 1.0 : 0.0)
    readonly property color effGlowColor: pinch ? "#ff3b30" : glowColor
    Behavior on glow { NumberAnimation { duration: 200; easing.type: Easing.OutQuad } }
    // 이동/끼임 시 클레이 표면에 emissive 글로우. 끼임은 더 강하게(0.9), 이동은 0.6.
    readonly property real glowScale: pinch ? 0.9 : 0.6
    readonly property vector3d glowVec: Qt.vector3d(effGlowColor.r * glow * glowScale,
                                                    effGlowColor.g * glow * glowScale,
                                                    effGlowColor.b * glow * glowScale)

    // --- axis2 → 변환값 ---
    readonly property real rotateDeg: isRear ? 0 : axis2         // 앞: Y축 회전(deg)
    property real slideRange: 140         // 슬라이드 0→100 동안 -Z로 이동하는 총량
    property real slideForward: 40        // slide=0 일 때 +Z(앞)로 당겨지는 양
    readonly property real slideZ: isRear ? (slideForward - axis2 / 100 * slideRange) : 0

    // --- 리클라인: 90=직립 기준 (앞/뒤 최대각 비대칭) ---
    //   90       = 등받이 수직(직립)
    //   90 → 0   = 앞으로 접힘. 0 = 좌면 위로 완전히 포개짐(90° 폴드 → 틈 없음).
    //   90 → 180 = 뒤로 눕힘. 180 = 깊게 젖힌 상태(reclineMaxDeg).
    // 힌지가 좌면 뒤 모서리·착좌면 높이(y=seatTopY)에 있어, 90° 앞폴드 시
    // 등받이 밑면이 좌면 윗면에 정확히 맞닿는다.
    property real foldMaxDeg: 90        // 앞으로 접히는 최대각(0에서 평평히 포갬)
    property real reclineMaxDeg: 78     // 뒤로 눕는 최대각
    readonly property real reclineDeg: (recline >= 90)
        ? (recline - 90) / 90 * reclineMaxDeg
        : (recline - 90) / 90 * foldMaxDeg

    // 단색 톤
    property color frameColor:   "#7f868f"   // 베이스
    property color cushionColor: "#aeb4c0"   // 좌면
    property color backColor:    "#9aa1ad"   // 등받이/헤드레스트

    // 치수
    readonly property real seatW:        52   // 좌우 폭(X)
    readonly property real seatD:        50   // 앞뒤 깊이(Z)
    readonly property real seatTopY:     44   // 좌면 윗면 높이(착좌면)
    readonly property real cushionThick: 12
    readonly property real backH:        62   // 등받이 길이
    readonly property real backThick:    12

    // ── 좌석 본체 래퍼 ─────────────────────────────────────────
    // axis2(앞=Y회전 / 뒤=Z슬라이드)를 이 래퍼에 적용한다.
    // 래퍼 원점 = 좌석 베이스 원점이므로 회전은 좌면 기준으로 돈다.
    // 부드러운 보간은 서버측 current 트윈이 담당 — 여기 Behavior 없음.
    Node {
        id: body
        eulerRotation.y: seat.rotateDeg
        position: Qt.vector3d(0, 0, seat.slideZ)

        // ── 좌면(쿠션) ──────────────────────────────────────────
        Model {
            source: "#Cube"
            position: Qt.vector3d(0, seat.seatTopY - seat.cushionThick / 2, 0)
            scale: Qt.vector3d(seat.seatW / 100, seat.cushionThick / 100, seat.seatD / 100)
            materials: PrincipledMaterial {
                baseColor: seat.cushionColor
                roughness: 0.85
                metalness: 0.0
                emissiveFactor: seat.glowVec
            }
        }

        // ── 베이스 블록 ── 좌면 아래를 바닥까지 채우는 받침
        Model {
            source: "#Cube"
            property real baseH: seat.seatTopY - seat.cushionThick   // 0 ~ 좌면 밑
            position: Qt.vector3d(0, baseH / 2, 2)
            scale: Qt.vector3d((seat.seatW - 12) / 100, baseH / 100, (seat.seatD - 16) / 100)
            materials: PrincipledMaterial {
                baseColor: seat.frameColor
                roughness: 0.9
                metalness: 0.0
                emissiveFactor: seat.glowVec
            }
        }

        // ── 등받이 힌지 노드 ───────────────────────────────────
        // 좌면 뒤쪽 모서리(−Z) · 착좌면 높이(seatTopY)에 힌지축을 둔다.
        // 이 노드를 X축으로 음수 회전 → 등받이 윗부분이 뒤(−Z)로 눕는다.
        Node {
            id: backrest
            position: Qt.vector3d(0, seat.seatTopY, -seat.seatD / 2)
            eulerRotation.x: -seat.reclineDeg

            // 등받이 본체 — 힌지에서 위(+Y)로 솟음. 두께만큼 −Z로 밀어 힌지선과 정렬.
            Model {
                source: "#Cube"
                position: Qt.vector3d(0, seat.backH / 2, -seat.backThick / 2)
                scale: Qt.vector3d(seat.seatW / 100, seat.backH / 100, seat.backThick / 100)
                materials: PrincipledMaterial {
                    baseColor: seat.backColor
                    roughness: 0.85
                    metalness: 0.0
                    emissiveFactor: seat.glowVec
                }
            }
            // 헤드레스트 — 등받이와 함께 기운다.
            Model {
                source: "#Cube"
                position: Qt.vector3d(0, seat.backH + 9, -seat.backThick / 2)
                scale: Qt.vector3d(0.28, 0.18, (seat.backThick + 2) / 100)
                materials: PrincipledMaterial {
                    baseColor: seat.backColor
                    roughness: 0.85
                    metalness: 0.0
                    emissiveFactor: seat.glowVec
                }
            }
        }
    }
}
