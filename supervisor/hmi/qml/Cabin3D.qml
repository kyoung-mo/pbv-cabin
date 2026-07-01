import QtQuick
import QtQuick3D
import "."
import "../assets/models/sports_car"   // balsam 변환된 Sports_Car.qml (GLB)

// 왼쪽 차량 영역의 실시간 3D "디지털 트윈".
//   · 흰색 클레이 차체 셸(CarBody, 루프 없는 컷어웨이) 안에 좌석 4개.
//   · 카메라는 고정 3/4 부감(드래그 회전 없음). 모든 비주얼 수치는 Cfg 에서 가져온다.
//   · 그림자/이펙트는 Pi5 고려해 가볍게(저폴리 + 라이트 2개, 그림자 OFF).
View3D {
    id: view

    // ── 차 겉껍데기 X-ray 트리거 ──────────────────────────────────
    // 좌석이 하나라도 이동(보간) 중이거나, 좌석 디테일(SEAT_DETAIL) 화면이면
    // GLB 차체(White 메시)를 반투명으로 페이드 → 안의 바닥+의자+레일이 비쳐 보인다.
    // ※ 단, ACTIVE 화면에서만. AMBIENT(대기)는 완성된 차를 보여주는 상태라 항상 불투명.
    readonly property bool anySeatMoving:
        vehicleState.seatMoving["driver"] || vehicleState.seatMoving["passenger"]
        || vehicleState.seatMoving["rear_left"] || vehicleState.seatMoving["rear_right"]
    readonly property bool xrayActive:
        vehicleState.uiMode === "ACTIVE"
        && (anySeatMoving || vehicleState.rightPanelScreen === "SEAT_DETAIL")
    // 실제로 차체에 먹이는 불투명도(부드럽게 페이드). 평소 1.0 → X-ray 시 Cfg.carXrayOpacity.
    property real carShellOpacity: xrayActive ? Cfg.carXrayOpacity : 1.0
    Behavior on carShellOpacity {
        NumberAnimation { duration: Cfg.carXrayFadeMs; easing.type: Easing.InOutQuad }
    }
    // 유리창 불투명도(부드럽게 페이드). 평소 1.0 → X-ray 시 Cfg.carWindowXrayOpacity(0).
    property real carWindowOpacity: xrayActive ? Cfg.carWindowXrayOpacity : 1.0
    Behavior on carWindowOpacity {
        NumberAnimation { duration: Cfg.carWindowFadeMs; easing.type: Easing.InOutQuad }
    }

    // ── 카메라 거리: AMBIENT(전체화면)에선 가까이 당겨 차를 크게, ACTIVE는 기존 ──
    property real camZ: vehicleState.uiMode === "AMBIENT" ? Cfg.camDistanceAmbient
                                                          : Cfg.camDistance
    Behavior on camZ {
        NumberAnimation { duration: Cfg.ambientTransitionMs; easing.type: Easing.InOutQuad }
    }
    // ── 카메라 가로 패닝: AMBIENT 전체화면에서 차량을 가로 중앙으로(카메라 로컬 X 이동) ──
    property real camPanX: vehicleState.uiMode === "AMBIENT" ? Cfg.camAmbientPanX : 0
    Behavior on camPanX {
        NumberAnimation { duration: Cfg.ambientTransitionMs; easing.type: Easing.InOutQuad }
    }

    environment: SceneEnvironment {
        clearColor: Cfg.clearColor
        backgroundMode: SceneEnvironment.Color
        antialiasingMode: SceneEnvironment.MSAA
        antialiasingQuality: SceneEnvironment.Medium
    }

    // ── 4바퀴 구르기 각도 누적 ──────────────────────────────────
    // 엑셀(wheelThrottle%)에 비례해 매 프레임 각도를 쌓는다(frameTime=초 기반 → 프레임률 무관).
    //   방향: 기어 D=전진(+) / R=후진(−). running 이 P·엑셀0 을 배제 → 그때는 각도 유지(정지, Pi 절약).
    FrameAnimation {
        id: wheelRoll
        property real angle: 0
        running: vehicleState.gear !== "P" && vehicleState.wheelThrottle > 0
        onTriggered: {
            var dir = vehicleState.gear === "R" ? -1 : 1     // running 이 P 를 이미 배제
            var thr = Math.max(0, Math.min(100, vehicleState.wheelThrottle)) / 100
            var d = dir * thr * Cfg.wheelRollMaxDps * frameTime
            angle += Cfg.wheelRollInvert ? -d : d
            if (angle > 100000 || angle < -100000)           // float 누적 폭주 방지(360 배수로 접기)
                angle = angle % 360
        }
    }

    // ── 카메라 리그 ── 원점을 바라보는 orbit 리그. 3/4 부감 "고정"(상수=Cfg).
    Node {
        id: cameraRig
        eulerRotation.x: Cfg.camPitch
        eulerRotation.y: Cfg.camYaw

        PerspectiveCamera {
            id: camera
            x: view.camPanX                          // 화면 가로 패닝(카메라 로컬 X)
            z: view.camZ
            fieldOfView: Cfg.camFov
            clipNear: 10
            clipFar: 4000
        }
    }

    // ── 라이트 (키 + 필) — 부드러운 클레이 음영, 그림자 OFF ──
    DirectionalLight {
        eulerRotation.x: -52
        eulerRotation.y: -35
        brightness: Cfg.keyBrightness
        castsShadow: false
    }
    DirectionalLight {
        eulerRotation.x: -20
        eulerRotation.y: 150
        brightness: Cfg.fillBrightness
        castsShadow: false
    }

    // ── 차량 ──────────────────────────────────────────────────────
    Node {
        id: cabin

        // (실내 바닥 제거: GLB 차에 자체 바닥이 있어 우리 floor는 삐져나와 어색 → 삭제.
        //  의자 4개 + 슬라이드 레일만 유지.)

        // ── GLB 스포츠카 (차 전체 = 겉모습) ──────────────────────────
        // 박스 차체(CarBody)는 폐기하고 이 GLB 차로 대체. 의자 4개가 차 실내에
        // 들어가도록 캐빈에 겹쳐 정렬한다(위치/스케일/회전 전부 Cfg 상수).
        // 좌석 제어/이동 중엔 shellOpacity 를 낮춰(carShellOpacity) 안이 비쳐 보인다.
        Sports_Car {
            position: Qt.vector3d(Cfg.carX, Cfg.carY, Cfg.carZ)
            scale: Qt.vector3d(Cfg.carScale, Cfg.carScale, Cfg.carScale)
            eulerRotation.y: Cfg.carRotY
            bodyColor: Cfg.carTint ? Cfg.carBodyColor : "#ff8c8c8c"
            shellOpacity: view.carShellOpacity        // X-ray: 평소 1.0, 좌석 이동/디테일 시 반투명
            windowOpacity: view.carWindowOpacity      // X-ray: 유리창도 같이 사라짐

            // ── 앞바퀴 조향 ── 기어 D/R 일 때만 wheelSteering(±127)을 ±maxDeg로 압축 매핑, P면 0.
            //   (부호가 반대면 Cfg.wheelSteerInvert=true. 회전은 Sports_Car 내부에서 제자리로 처리.)
            steerDeg: {
                var g = vehicleState.gear
                if (g !== "D" && g !== "R")
                    return 0
                var s = Math.max(-127, Math.min(127, vehicleState.wheelSteering))
                var deg = s / 127 * Cfg.wheelSteerMaxDeg
                return Cfg.wheelSteerInvert ? -deg : deg
            }
            Behavior on steerDeg {
                NumberAnimation { duration: Cfg.wheelSteerSmoothMs; easing.type: Easing.OutQuad }
            }

            // ── 4바퀴 구르기 ── 위 FrameAnimation 이 누적한 각도(도)를 그대로 전달(보간 X, raw).
            rollDeg: wheelRoll.angle
        }

        // ── 뒷좌석 슬라이드 레일 (바닥 고정) ──
        // centerZ = 슬라이드 경로 중심(= seatRearZ - 30; Seat3D slideForward40/range140 기준)
        SlideRail { seatX: -Cfg.seatHalfX; centerZ: Cfg.seatRearZ - 30; length: Cfg.railLength }
        SlideRail { seatX: Cfg.seatHalfX;  centerZ: Cfg.seatRearZ - 30; length: Cfg.railLength }

        // ── 좌석 4개 ──────────────────────────────────────────────
        // 각 좌석은 자기 좌석의 current 값(seatPose)·이동상태(seatMoving)에만 반응.
        //   recline → 등받이 기울기 / axis2 → 앞=Y회전, 뒤=Z슬라이드(isRear)
        Seat3D {   // 운전석 (front-left)
            id: seatDriver
            isRear: false
            position: Qt.vector3d(-Cfg.seatHalfX, 0, Cfg.seatFrontZ)
            recline: vehicleState.seatPose["driver"].recline
            axis2: vehicleState.seatPose["driver"].axis2
            moving: vehicleState.seatMoving["driver"]
            pinch: vehicleState.seatPinch["driver"]
            showIndicator: Cfg.showMoveIndicator
            glowColor: Cfg.moveGlowColor
        }
        Seat3D {   // 조수석 (front-right)
            id: seatPassenger
            isRear: false
            position: Qt.vector3d(Cfg.seatHalfX, 0, Cfg.seatFrontZ)
            recline: vehicleState.seatPose["passenger"].recline
            axis2: vehicleState.seatPose["passenger"].axis2
            moving: vehicleState.seatMoving["passenger"]
            pinch: vehicleState.seatPinch["passenger"]
            showIndicator: Cfg.showMoveIndicator
            glowColor: Cfg.moveGlowColor
        }
        Seat3D {   // 뒷좌석 좌 (rear-left)
            id: seatRearLeft
            isRear: true
            position: Qt.vector3d(-Cfg.seatHalfX, 0, Cfg.seatRearZ)
            recline: vehicleState.seatPose["rear_left"].recline
            axis2: vehicleState.seatPose["rear_left"].axis2
            moving: vehicleState.seatMoving["rear_left"]
            pinch: vehicleState.seatPinch["rear_left"]
            showIndicator: Cfg.showMoveIndicator
            glowColor: Cfg.moveGlowColor
        }
        Seat3D {   // 뒷좌석 우 (rear-right)
            id: seatRearRight
            isRear: true
            position: Qt.vector3d(Cfg.seatHalfX, 0, Cfg.seatRearZ)
            recline: vehicleState.seatPose["rear_right"].recline
            axis2: vehicleState.seatPose["rear_right"].axis2
            moving: vehicleState.seatMoving["rear_right"]
            pinch: vehicleState.seatPinch["rear_right"]
            showIndicator: Cfg.showMoveIndicator
            glowColor: Cfg.moveGlowColor
        }
    }
}
