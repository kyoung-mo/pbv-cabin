import QtQuick
import QtQuick3D

Item {
    width: 700; height: 500
    View3D {
        anchors.fill: parent
        environment: SceneEnvironment { clearColor: "#202830"; backgroundMode: SceneEnvironment.Color }
        // 3/4 측면·약간 위 (앱보다 낮춰 바퀴가 보이게)
        Node {
            eulerRotation.x: -15
            eulerRotation.y: -35
            PerspectiveCamera { z: 6; fieldOfView: 45 }
        }
        DirectionalLight { eulerRotation.x: -40; eulerRotation.y: -30 }
        DirectionalLight { eulerRotation.x: -10; eulerRotation.y: 150 }
        Sports_Car { id: car; objectName: "car" }
    }
}
