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
        }
        Model {
            id: sportsCar2_FrontLeftWheel_Cylinder_017
            objectName: "SportsCar2_FrontLeftWheel_Cylinder.017"
            source: "meshes/sportsCar2_FrontLeftWheel_Cylinder_017_mesh.mesh"
            materials: [
                grey_material,
                black_material
            ]
        }
        Model {
            id: sportsCar2_FrontRightWheel_Cylinder_018
            objectName: "SportsCar2_FrontRightWheel_Cylinder.018"
            source: "meshes/sportsCar2_FrontRightWheel_Cylinder_018_mesh.mesh"
            materials: [
                grey_material,
                black_material
            ]
        }
    }

    // Animations:
}
