import QtQuick
import QtQuick3D

Node {
    id: node

    // 차체(White) 머티리얼 색을 밖에서 덮어쓸 수 있게 노출. 기본값은 원본 GLB 색.
    // Cabin3D 에서 Cfg.carTint 켜면 Cfg.carBodyColor(흰 차체 톤)로 교체된다.
    property color bodyColor: "#ff8c8c8c"
    // 차 겉껍데기(통짜 White 메시) 불투명도 — 밖에서 X-ray 제어. 1=완성차, 0.2~0.3=속 비침.
    // 페이드(Behavior)는 Cabin3D 쪽 carShellOpacity 에서 처리한다(여기는 값만 받음).
    property real shellOpacity: 1.0
    // 유리창(Windows) 불투명도 — X-ray 시 0으로 페이드해 창문이 사라지고 안이 드러남.
    property real windowOpacity: 1.0

    // 앞바퀴 조향각(도). Cabin3D 에서 기어·wheelSteering 을 압축 매핑해 넣어준다(P면 0).
    // 각 앞바퀴는 자기 메시의 AABB 중심을 pivot=position 으로 잡아 "제자리"에서만 Y축 회전.
    //   ※ pivot 만 걸고 position 을 안 맞추면 바퀴가 원점(차 중심)으로 순간이동해 차체에 파묻힌다.
    //     반드시 position=pivot(=중심) 으로 둘을 같게 걸어 0°일 때 변위 0 → 지금 보이는 상태 유지.
    property real steerDeg: 0

    // 4바퀴 구르기 각도(도, 누적). Cabin3D 의 FrameAnimation 이 엑셀·기어로 계속 누적해 넣는다.
    // 구르기 = 차축(X축) 회전. 조향(Y)과 축이 달라 안 섞인다. 앞바퀴는 조향 노드 "안"에서 구른다.
    //   중심(pivot=position=ctr)은 조향과 동일 → 0°에서 변위 0, 제자리에서만 데굴데굴 구른다.
    property real rollDeg: 0

    // Resources
    PrincipledMaterial {
        id: white_material
        objectName: "White"
        baseColor: node.bodyColor
        roughness: 0.9039215445518494
        opacity: node.shellOpacity                  // X-ray 시 낮춰 안의 의자가 비침
        // 반투명이 실제로 보이도록 Blend (원본 Opaque는 opacity 무시). 1.0이면 불투명과 동일.
        alphaMode: PrincipledMaterial.Blend
    }
    PrincipledMaterial {
        id: windows_material
        objectName: "Windows"
        baseColor: "#ff070707"
        roughness: 0.9039215445518494
        opacity: node.windowOpacity                 // X-ray 시 0으로 페이드 → 창문 사라짐
        alphaMode: PrincipledMaterial.Blend         // opacity 적용되도록 Blend
    }
    PrincipledMaterial {
        id: grey_material
        objectName: "Grey"
        baseColor: "#ff202020"
        roughness: 0.9039215445518494
        opacity: node.windowOpacity                 // 사이드/백미러 검은 부분 — 창문과 같이 사라짐
        alphaMode: PrincipledMaterial.Blend         // (Grey는 휠 림에도 쓰여 X-ray 시 같이 페이드됨)
    }
    PrincipledMaterial {
        id: headlights_material
        objectName: "Headlights"
        baseColor: "#ffa34c1a"
        roughness: 0.9039215445518494
        alphaMode: PrincipledMaterial.Opaque
    }
    PrincipledMaterial {
        id: tailLights_material
        objectName: "TailLights"
        baseColor: "#ffa3130f"
        roughness: 0.9039215445518494
        alphaMode: PrincipledMaterial.Opaque
    }
    PrincipledMaterial {
        id: black_material
        objectName: "Black"
        baseColor: "#ff030303"
        roughness: 0.9039215445518494
        alphaMode: PrincipledMaterial.Opaque
    }

    // Nodes:
    Node {
        id: root
        objectName: "ROOT"
        Model {
            id: sportsCar2_Cube_006
            objectName: "SportsCar2_Cube.006"
            source: "meshes/sportsCar2_Cube_006_mesh.mesh"
            materials: [
                white_material,
                windows_material,
                grey_material,
                headlights_material,
                tailLights_material
            ]
        }
        Model {
            id: sportsCar2_BackWheels_Cylinder_002
            objectName: "SportsCar2_BackWheels_Cylinder.002"
            source: "meshes/sportsCar2_BackWheels_Cylinder_002_mesh.mesh"
            materials: [
                black_material,
                grey_material
            ]
            // 뒷바퀴 2개가 한 메시 → AABB 중심은 뒤차축 중점(축선 위).
            // 그 중심 기준 X축(차축) 회전이면 두 바퀴 다 제자리에서 굴러간다. 조향 없음.
            readonly property vector3d ctr: Qt.vector3d(
                (bounds.minimum.x + bounds.maximum.x) / 2,
                (bounds.minimum.y + bounds.maximum.y) / 2,
                (bounds.minimum.z + bounds.maximum.z) / 2)
            position: ctr
            pivot: ctr
            eulerRotation.x: node.rollDeg
        }
        // ── 앞바퀴: 조향(Y) 노드 안에 구르기(X) Model 을 중첩 → 두 회전이 안 섞임 ──
        //   부모(조향)·자식(구르기) 둘 다 pivot=position=ctr(같은 바퀴중심).
        //   합성: T(ctr)·Ry(steer)·Rx(roll)·T(-ctr) → 제자리에서 꺾이며 구른다. 0°에서 변위 0.
        Node {
            id: frontLeftSteer
            position: sportsCar2_FrontLeftWheel_Cylinder_017.ctr
            pivot: sportsCar2_FrontLeftWheel_Cylinder_017.ctr
            eulerRotation.y: node.steerDeg
            Model {
                id: sportsCar2_FrontLeftWheel_Cylinder_017
                objectName: "SportsCar2_FrontLeftWheel_Cylinder.017"
                source: "meshes/sportsCar2_FrontLeftWheel_Cylinder_017_mesh.mesh"
                materials: [
                    grey_material,
                    black_material
                ]
                // 메시 AABB 중심(런타임 bounds에서 자동 계산 — 실측 좌표 하드코딩 불필요).
                readonly property vector3d ctr: Qt.vector3d(
                    (bounds.minimum.x + bounds.maximum.x) / 2,
                    (bounds.minimum.y + bounds.maximum.y) / 2,
                    (bounds.minimum.z + bounds.maximum.z) / 2)
                position: ctr
                pivot: ctr
                eulerRotation.x: node.rollDeg          // 구르기(차축 X) — 조향(부모 Y)과 분리
            }
        }
        Node {
            id: frontRightSteer
            position: sportsCar2_FrontRightWheel_Cylinder_018.ctr
            pivot: sportsCar2_FrontRightWheel_Cylinder_018.ctr
            eulerRotation.y: node.steerDeg
            Model {
                id: sportsCar2_FrontRightWheel_Cylinder_018
                objectName: "SportsCar2_FrontRightWheel_Cylinder.018"
                source: "meshes/sportsCar2_FrontRightWheel_Cylinder_018_mesh.mesh"
                materials: [
                    grey_material,
                    black_material
                ]
                readonly property vector3d ctr: Qt.vector3d(
                    (bounds.minimum.x + bounds.maximum.x) / 2,
                    (bounds.minimum.y + bounds.maximum.y) / 2,
                    (bounds.minimum.z + bounds.maximum.z) / 2)
                position: ctr
                pivot: ctr
                eulerRotation.x: node.rollDeg
            }
        }
    }

    // Animations:
}
