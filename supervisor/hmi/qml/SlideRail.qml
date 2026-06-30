import QtQuick
import QtQuick3D

// 뒷좌석 슬라이드 가이드 — 바닥에 깔린 리니어 액추에이터 레일 한 쌍(고정 형상).
// 좌석이 이 레일 위를 Z축으로 슬라이드하는 것처럼 보이게 한다.
// 길이는 슬라이드 이동 범위(slide 0~100)를 덮는다.
//
// ※ Seat3D 의 슬라이드 수식과 정합:
//    뒷좌석 center z = base(-30) + (40 - slide/100*140)  → slide0=+10, slide100=-130.
//    그 구간(+10~-130, 중심 -60, 길이 140)을 약간의 여유와 함께 덮는다.
Node {
    id: rail
    property real seatX: 0             // 덮을 뒷좌석의 X 중심
    property real centerZ: -60         // 슬라이드 범위 중심(Z)
    property real length: 160          // 슬라이드 0~100 구간을 덮는 길이(Z)
    property real gauge: 26            // 두 레일 사이 간격(좌우) — 시트 바닥 안쪽에 위치
    property real railW: 7             // 레일 폭(X)
    property real railH: 5             // 레일 높이(바닥 위)
    property color railColor: "#5a5f67"   // 클레이보다 어두운 중간 회색

    // 좌측 레일
    Model {
        source: "#Cube"
        position: Qt.vector3d(rail.seatX - rail.gauge / 2, rail.railH / 2, rail.centerZ)
        scale: Qt.vector3d(rail.railW / 100, rail.railH / 100, rail.length / 100)
        materials: PrincipledMaterial {
            baseColor: rail.railColor
            roughness: 0.55
            metalness: 0.25
        }
    }
    // 우측 레일
    Model {
        source: "#Cube"
        position: Qt.vector3d(rail.seatX + rail.gauge / 2, rail.railH / 2, rail.centerZ)
        scale: Qt.vector3d(rail.railW / 100, rail.railH / 100, rail.length / 100)
        materials: PrincipledMaterial {
            baseColor: rail.railColor
            roughness: 0.55
            metalness: 0.25
        }
    }
}
