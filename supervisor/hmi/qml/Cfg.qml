pragma Singleton
import QtQuick

// ───────────────────────────────────────────────────────────────────────────
// 3D 비주얼 상수 (단일 출처).
// 화면을 직접 못 보는 상태에서 "숫자만 바꿔" 조정할 수 있도록 차체/휠/카메라/
// 조명/좌석좌표/보닛투명/이동표시 값을 전부 여기에 모았다. (동작 로직과 무관)
// ───────────────────────────────────────────────────────────────────────────
QtObject {
    // ===== 차체 셸 (흰색 무광 클레이) =====
    readonly property color shellColor: "#eef0f2"   // 차체 색
    readonly property color floorColor: "#d9dade"   // 실내 바닥 색
    readonly property real bodyHalfW:   140         // 차체 반폭(X, ±)
    readonly property real bodyHalfL:   255         // 차체 반길이(Z, ±) — 뒷좌석 슬라이드 공간 확보
    readonly property real bodyHeight:  50          // 측면/뒤 도어라인 높이(Y)
    readonly property real bodyFrontH:  34          // 앞(보닛 라인) 높이(Y) — 앞 볼륨 보강
    readonly property real cornerR:     24          // 코너 라운딩 반경 — 뒤쪽 원기둥 어색해 축소
    readonly property real shellThick:  7           // 패널 두께
    readonly property real tumblehome:  6           // 측면 상단 안쪽 기울기(도)
    readonly property real shoulderR:   9           // 둥근 숄더/엣지 레일 반경
    readonly property real noseR:       14          // 앞코 라운딩 반경

    // ===== 앞 차체 디테일 (범퍼/헤드램프/그릴) — 스테이션왜건 앞모습 =====
    readonly property real bumperHalfW:    112       // 앞 범퍼 반폭(X)
    readonly property real bumperH:        16        // 범퍼 높이(Y)
    readonly property real bumperY:        10        // 범퍼 중심 높이(Y)
    readonly property real bumperProtrude: 8         // 앞면보다 앞으로 튀어나온 정도(Z)
    readonly property color lampColor:     "#f6f2d8" // 헤드램프 색(밝은 따뜻한 흰)
    readonly property real lampW:          26        // 헤드램프 폭
    readonly property real lampH:          11        // 헤드램프 높이
    readonly property real lampDepth:      8         // 헤드램프 두께(Z, 앞면서 돌출)
    readonly property real lampX:          86        // 헤드램프 좌우 위치(±)
    readonly property real lampY:          23        // 헤드램프 높이(Y)
    readonly property color grilleColor:   "#33373d" // 그릴(어두운 띠) 색
    readonly property real grilleW:        116       // 그릴 폭
    readonly property real grilleH:        9         // 그릴 높이
    readonly property real grilleY:        13        // 그릴 높이(Y, 범퍼 위)

    // ===== 휠 (진회색) =====
    readonly property color wheelColor: "#3a3d42"   // 휠 색
    readonly property real wheelRadius: 34          // 휠 반경
    readonly property real wheelWidth:  18          // 휠 폭(X)
    readonly property real wheelX:      150         // 휠 좌우 위치(±, 차체 바깥)
    readonly property real wheelFrontZ: 160         // 앞축 Z
    readonly property real wheelRearZ:  -185        // 뒤축 Z (길어진 차체에 맞춰 뒤로)
    readonly property real wheelY:      8           // 휠 중심 높이(Y)

    // ===== 카메라 (3/4 부감, 고정) =====
    readonly property real camDistance: 1050        // ACTIVE(왼쪽 40%) 시 카메라 거리(클수록 멀리/작게)
                                                    //   차+의자가 화면에 꽉 차면 ↑ 로 멀리서
    readonly property real camDistanceAmbient: 820  // AMBIENT(전체화면) 시 카메라 거리 — 가까이=차 크게
    readonly property real camPitch:    -32         // 부감 각도(X, 내려다봄)
    readonly property real camYaw:      -28         // 3/4 각도(Y)
    readonly property real camFov:      55          // 시야각(FOV)

    // ===== 대기(AMBIENT) 레이아웃 전환 =====
    // ACTIVE(왼쪽 차량 40% + 오른쪽 패널 60%) ↔ AMBIENT(차량 전체화면, 패널 슬라이드 아웃).
    readonly property int ambientTransitionMs: 360  // 패널 슬라이드/폭 확대/카메라 줌 전환 시간(ms)

    // ===== 조명 / 배경 =====
    readonly property color clearColor:    "#e9eaee"  // 배경색
    readonly property real keyBrightness:  1.15       // 키 라이트 밝기
    readonly property real fillBrightness: 0.5        // 필 라이트 밝기

    // ===== 좌석 좌표 (바닥 y=0 기준) =====
    readonly property real seatHalfX:  60           // 좌우 좌석 X(±)
    readonly property real seatFrontZ: 120          // 앞줄 Z
    readonly property real seatRearZ:  -15          // 뒷줄 기준 Z — 앞으로 당겨 뒤 슬라이드 공간↑
    readonly property real railLength: 170          // 슬라이드 레일 길이(Z) — 슬라이드 범위를 덮음

    // ===== GLB 스포츠카 (Sports_Car.qml) — 차 전체를 겉모습으로, 의자는 안에 =====
    // 네이티브 크기(미터): 폭 1.872 · 높이 1.187 · 길이 3.927. 앞=+Z(앞바퀴 +Z), 뒤=-Z.
    // 배치 개념: 차를 캐빈에 겹쳐 우리 의자 4개가 차 실내에 쏙 들어가게 정렬.
    //   차 앞=+Z(캐빈 앞과 동일) 이므로 회전 0. 박스 차체(CarBody)는 이제 안 쓴다.
    // 좌석 기준점: 앞줄 Z=+120, 뒷줄 Z=-15, 좌우 X=±60 (seatHalfX/seatFrontZ/seatRearZ).
    //
    // ▼ 화면 보고 숫자만 조정 — 가장 자주 만질 값은 carScale(크기)·carZ(앞뒤)·carY(높이).
    readonly property real  carScale: 165       // 크기 배율(1m→165유닛, x/y/z 균일=비율 유지).
                                                //   의자가 실내에 빠듯하면 ↑, 차가 너무 크면 ↓
    readonly property real  carRotY:  0         // Y축 회전(도). 0=차앞이 +Z(캐빈앞). 앞뒤 뒤집혔으면 180
    readonly property real  carX:     0         // 좌우 위치(±, +면 오른쪽). 중앙=0
    readonly property real  carY:     0         // 높이(Y). 의자가 차 바닥보다 가라앉으면 차를 -로 내림
    readonly property real  carZ:     80        // 앞뒤 위치(+Z=캐빈 앞). +면 차가 앞으로(콕핏이 앞좌석쪽)
                                                //   의자가 보닛/트렁크에 박히면 이 값으로 콕핏을 의자에 맞춤
    // 차체 색 맞춤(옵션) — 원본 GLB는 회색(#8c8c8c). 다른 색 원하면 carTint=true.
    readonly property bool  carTint:      false       // true 면 carBodyColor 로 차체색 교체
    readonly property color carBodyColor: "#ffeef0f2"  // 캐빈 차체 톤(shellColor)과 동일

    // ===== 차 겉껍데기 X-ray (좌석 제어/이동 중 반투명) =====
    // 평소엔 불투명한 완성차, 좌석 디테일 진입(SEAT_DETAIL)이나 의자 이동(보간) 중엔
    // White 차체 머티리얼을 반투명으로 페이드 → 안의 바닥+의자+레일이 비쳐 보인다.
    readonly property real carXrayOpacity: 0.25  // X-ray 시 차체 불투명도(0~1, 낮을수록 더 투명)
    readonly property int  carXrayFadeMs:  260   // 차체 불투명↔반투명 페이드 시간(ms)
    // 유리창(Windows)도 같이 페이드 — 검은 불투명 창이 막지 않도록 X-ray 시 사라지게.
    readonly property real carWindowXrayOpacity: 0.0  // X-ray 시 유리창 목표 불투명도(0=완전 사라짐)
    readonly property int  carWindowFadeMs:      340  // 창문 페이드 시간(ms, 서서히 사라지게 약간 길게)

    // ===== 보닛(앞 차체) 반투명 — 앞좌석 디테일 선택 시 =====
    readonly property real bonnetOpacityFront: 0.28 // 앞좌석 선택 시 보닛 불투명도(0~1)
    readonly property int  bonnetFadeMs:       220  // 페이드 시간(ms)

    // ===== 좌석 이동 표시(보간 중 하이라이트) =====
    readonly property bool  showMoveIndicator: true     // 이동중 표시 on/off
    readonly property color moveGlowColor:     "#3B82F6" // 하이라이트 색

    // ===== 모드 타일 배경 사진 위 어두운 스크림 (4장 톤 통일 + 라벨 가독성) =====
    // 검정 위 알파. 위는 약하게, 아래는 강하게. 사진이 너무 어두우면 값을 낮춰라.
    readonly property real modeScrimTopA: 0.34          // 상단 스크림 알파(약)
    readonly property real modeScrimMidA: 0.16          // 중간 스크림 알파
    readonly property real modeScrimBotA: 0.86          // 하단 스크림 알파(강, 라벨용)
}
