import QtQuick
import QtQuick3D
import "."

// 흰색 클레이 차체 외곽(셸) — 전시장 클레이 목업 같은 "흰 차 모형".
// 루프 없는 컷어웨이라 안의 좌석 4개가 다 보인다(좌석/바닥/레일은 별도).
//
// 각진 #Cube 느낌을 줄이려고:
//   · 측면 패널을 텀블홈으로 위쪽 안으로 기울임
//   · 상단에 둥근 숄더 레일(실린더)
//   · 앞코/뒤꼬리/네 코너를 실린더로 둥글게
// 모든 치수/색은 Cfg 에서 가져온다(내일 숫자만 바꿔 조정).
//
// 보닛(앞 차체: 페시아·후드·앞코·앞코너)은 bonnetMat 그룹으로 묶어, 앞좌석
// 디테일 선택 시 bonnetOpacity 로 반투명 처리한다.
Node {
    id: car

    // 앞좌석 선택 시 1.0→Cfg.bonnetOpacityFront 로 부드럽게 페이드(불투명도).
    property real bonnetOpacity: 1.0
    Behavior on bonnetOpacity {
        NumberAnimation { duration: Cfg.bonnetFadeMs; easing.type: Easing.InOutQuad }
    }

    // ── 파생 치수 ──
    readonly property real hw: Cfg.bodyHalfW
    readonly property real hl: Cfg.bodyHalfL
    readonly property real bh: Cfg.bodyHeight
    readonly property real fh: Cfg.bodyFrontH
    readonly property real rr: Cfg.cornerR
    readonly property real th: Cfg.shellThick
    readonly property real sideZHalf: hl - rr        // 측면 패널 반길이(Z)
    readonly property real capXHalf:  hw - rr        // 앞뒤 캡 반길이(X)

    // ── 공유 머티리얼 ──
    PrincipledMaterial {                              // 차체(불투명)
        id: shellMat
        baseColor: Cfg.shellColor
        roughness: 0.95
        metalness: 0.0
    }
    PrincipledMaterial {                              // 보닛 그룹(반투명 대상)
        id: bonnetMat
        baseColor: Cfg.shellColor
        roughness: 0.95
        metalness: 0.0
        opacity: car.bonnetOpacity
    }
    PrincipledMaterial {                              // 휠(진회색)
        id: wheelMat
        baseColor: Cfg.wheelColor
        roughness: 0.7
        metalness: 0.1
    }
    PrincipledMaterial {                              // 헤드램프(밝게 빛나는 느낌)
        id: lampMat
        baseColor: Cfg.lampColor
        roughness: 0.3
        metalness: 0.0
        emissiveFactor: Qt.vector3d(0.45, 0.43, 0.3) // 살짝 발광
        opacity: car.bonnetOpacity
    }
    PrincipledMaterial {                              // 그릴(어두운 띠)
        id: grilleMat
        baseColor: Cfg.grilleColor
        roughness: 0.6
        metalness: 0.2
        opacity: car.bonnetOpacity
    }

    // ── 측면 패널 (z 방향, x=±hw) — 텀블홈 ──
    Model {
        source: "#Cube"
        position: Qt.vector3d(-car.hw, car.bh / 2, 0)
        eulerRotation.z: -Cfg.tumblehome
        scale: Qt.vector3d(car.th / 100, car.bh / 100, (2 * car.sideZHalf) / 100)
        materials: shellMat
    }
    Model {
        source: "#Cube"
        position: Qt.vector3d(car.hw, car.bh / 2, 0)
        eulerRotation.z: Cfg.tumblehome
        scale: Qt.vector3d(car.th / 100, car.bh / 100, (2 * car.sideZHalf) / 100)
        materials: shellMat
    }

    // ── 둥근 숄더 레일 (측면 상단, z축 실린더) ──
    Model {
        source: "#Cylinder"
        position: Qt.vector3d(-(car.hw - 4), car.bh, 0)
        eulerRotation.x: 90
        scale: Qt.vector3d(Cfg.shoulderR / 50, (2 * car.sideZHalf) / 100, Cfg.shoulderR / 50)
        materials: shellMat
    }
    Model {
        source: "#Cylinder"
        position: Qt.vector3d(car.hw - 4, car.bh, 0)
        eulerRotation.x: 90
        scale: Qt.vector3d(Cfg.shoulderR / 50, (2 * car.sideZHalf) / 100, Cfg.shoulderR / 50)
        materials: shellMat
    }

    // ── 뒤쪽 마감 (x 방향, z=-hl) + 둥근 뒤꼬리 레일 ──
    Model {
        source: "#Cube"
        position: Qt.vector3d(0, car.bh / 2, -car.hl)
        scale: Qt.vector3d((2 * car.capXHalf) / 100, car.bh / 100, car.th / 100)
        materials: shellMat
    }
    Model {
        source: "#Cylinder"
        position: Qt.vector3d(0, car.bh, -car.hl)
        eulerRotation.z: 90
        scale: Qt.vector3d(Cfg.shoulderR / 50, (2 * car.capXHalf) / 100, Cfg.shoulderR / 50)
        materials: shellMat
    }

    // ── 뒤 코너 라운딩 (세로 실린더, 높이=차체) ──
    Model {
        source: "#Cylinder"
        position: Qt.vector3d(-car.capXHalf, car.bh / 2, -car.sideZHalf)
        scale: Qt.vector3d(car.rr / 50, car.bh / 100, car.rr / 50)
        materials: shellMat
    }
    Model {
        source: "#Cylinder"
        position: Qt.vector3d(car.capXHalf, car.bh / 2, -car.sideZHalf)
        scale: Qt.vector3d(car.rr / 50, car.bh / 100, car.rr / 50)
        materials: shellMat
    }

    // ═══ 보닛 그룹 (앞 차체 — 반투명 대상) ═══════════════════════════
    // 앞 차체 볼륨(솔리드) — 바닥~보닛 높이까지 꽉 채워 "앞이 비어 보임" 제거.
    // 앞좌석 앞(zBack)부터 앞 끝(hl)까지. 앞좌석 컷어웨이는 그대로(좌석은 이 뒤).
    readonly property real bonnetBackZ: Cfg.seatFrontZ + 25   // 앞 볼륨 뒤끝

    // 박스로 만든 앞부분 전체를 한 노드로 묶어 Cfg.useBoxFront 로 on/off.
    // GLB 스포츠카 앞부분(Sports_Car)을 쓸 때는 false 로 꺼서 겹침/이중 앞코 방지.
    Node {
        visible: Cfg.useBoxFront

        Model {
            source: "#Cube"
            position: Qt.vector3d(0, car.fh / 2, (car.hl + car.bonnetBackZ) / 2)
            scale: Qt.vector3d((2 * car.capXHalf) / 100, car.fh / 100,
                               (car.hl - car.bonnetBackZ) / 100)
            materials: bonnetMat
        }
        // 후드 크라운(완만한 슬로프) — 볼륨 위에서 앞으로 살짝 낮아짐(두툼하게).
        Model {
            source: "#Cube"
            position: Qt.vector3d(0, car.fh - 1, (car.hl + car.bonnetBackZ) / 2)
            eulerRotation.x: 5
            scale: Qt.vector3d((2 * car.capXHalf * 0.96) / 100, 0.10,
                               (car.hl - car.bonnetBackZ) / 100)
            materials: bonnetMat
        }
        // 둥근 앞코(가로 실린더)
        Model {
            source: "#Cylinder"
            position: Qt.vector3d(0, Cfg.noseR + 2, car.hl)
            eulerRotation.z: 90
            scale: Qt.vector3d(Cfg.noseR / 50, (2 * car.capXHalf) / 100, Cfg.noseR / 50)
            materials: bonnetMat
        }
        // 앞 코너 라운딩 (세로 실린더, 높이=보닛 라인)
        Model {
            source: "#Cylinder"
            position: Qt.vector3d(-car.capXHalf, car.fh / 2, car.sideZHalf)
            scale: Qt.vector3d(car.rr / 50, car.fh / 100, car.rr / 50)
            materials: bonnetMat
        }
        Model {
            source: "#Cylinder"
            position: Qt.vector3d(car.capXHalf, car.fh / 2, car.sideZHalf)
            scale: Qt.vector3d(car.rr / 50, car.fh / 100, car.rr / 50)
            materials: bonnetMat
        }

        // ── 앞면 디테일 (범퍼 한 단 + 헤드램프 2 + 그릴) — "앞이 비어 보임" 제거 ──
        // 앞 범퍼(앞면보다 한 단 앞으로 돌출하는 낮은 볼륨)
        Model {
            source: "#Cube"
            position: Qt.vector3d(0, Cfg.bumperY, car.hl)
            scale: Qt.vector3d((2 * Cfg.bumperHalfW) / 100, Cfg.bumperH / 100,
                               (2 * Cfg.bumperProtrude) / 100)
            materials: bonnetMat
        }
        // 그릴(범퍼 위 어두운 가로 띠)
        Model {
            source: "#Cube"
            position: Qt.vector3d(0, Cfg.grilleY, car.hl + 1)
            scale: Qt.vector3d(Cfg.grilleW / 100, Cfg.grilleH / 100, 0.06)
            materials: grilleMat
        }
        // 헤드램프 좌/우(앞면에서 살짝 돌출, 밝게)
        Model {
            source: "#Cube"
            position: Qt.vector3d(-Cfg.lampX, Cfg.lampY, car.hl + 1)
            scale: Qt.vector3d(Cfg.lampW / 100, Cfg.lampH / 100, Cfg.lampDepth / 100)
            materials: lampMat
        }
        Model {
            source: "#Cube"
            position: Qt.vector3d(Cfg.lampX, Cfg.lampY, car.hl + 1)
            scale: Qt.vector3d(Cfg.lampW / 100, Cfg.lampH / 100, Cfg.lampDepth / 100)
            materials: lampMat
        }
    }

    // ── 휠 4개 (x축 실린더, 차체 바깥 하단) ──
    component Wheel: Model {
        source: "#Cylinder"
        eulerRotation.z: 90                          // 축 Y→X (좌우로 눕힘)
        scale: Qt.vector3d(Cfg.wheelRadius / 50, Cfg.wheelWidth / 100, Cfg.wheelRadius / 50)
        materials: wheelMat
    }
    Wheel { position: Qt.vector3d(-Cfg.wheelX, Cfg.wheelY, Cfg.wheelFrontZ) }   // 앞-좌
    Wheel { position: Qt.vector3d(Cfg.wheelX,  Cfg.wheelY, Cfg.wheelFrontZ) }   // 앞-우
    Wheel { position: Qt.vector3d(-Cfg.wheelX, Cfg.wheelY, Cfg.wheelRearZ) }    // 뒤-좌
    Wheel { position: Qt.vector3d(Cfg.wheelX,  Cfg.wheelY, Cfg.wheelRearZ) }    // 뒤-우
}
