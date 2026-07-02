pragma Singleton
import QtQuick

// ─────────────────────────────────────────────────────────────────────────
// 디자인 토큰 (단일 출처). 색·간격·라운드·모션을 여기서만 관리.
// 톤: 라이트(흰/옅은 회색) — 왼쪽 3D 흰 배경과 좌우 톤 통일.
// ※ 기능/상태와 무관한 순수 비주얼 토큰. 하드코딩 색을 이 토큰으로 대체한다.
// ※ 왼쪽 3D 위에 떠 있는 GEAR 표시/기어 슬라이드는 라이트 전환과 무관하게
//    어두운 오버레이로 유지 → 아래 "overlay*" 토큰 군을 따로 둔다.
// ─────────────────────────────────────────────────────────────────────────
QtObject {
    // ── 배경 (라이트: 흰 → 아주 옅은 회색 그라데이션) ────────────────
    readonly property color bgTop:    "#ffffff"
    readonly property color bgMid:    "#f7f8fa"
    readonly property color bgBottom: "#f1f3f5"

    // ── 카드/표면 (라이트: 흰/옅은 회색) ────────────────────────────
    readonly property color surfaceTop:    "#ffffffff"   // 카드 윗면(흰색)
    readonly property color surfaceBottom: "#fff4f5f7"   // 카드 아랫면(옅은 회색)
    readonly property color surfaceSolid:  "#ffeceef1"   // 불투명이 필요한 곳
    readonly property color surfaceRaised: "#fff8f9fb"   // 살짝 떠 보이는 면

    // ── 보더 / 구분선 (옅은 회색) ──────────────────────────────────
    readonly property color border:       "#ffe3e5e9"   // 카드 보더(옅은 회색)
    readonly property color borderStrong: "#ffd2d6dd"   // 트랙/구분선(살짝 진한 회색)
    readonly property color sheen:        "#30ffffff"    // 상단 하이라이트(흰 살짝; 라이트선 거의 안 보임)

    // ── 강조색 (블루) — 흰 배경에서 잘 보이게 살짝 진하게 ──────────────
    readonly property color accent:       "#2563eb"
    readonly property color accentSoft:   "#3b82f6"
    readonly property color accentBorder: "#802563eb"
    // rgba() 동적 합성을 위한 채널값 (accent=#2563eb)
    readonly property real accentR: 0.145
    readonly property real accentG: 0.388
    readonly property real accentB: 0.922

    // ── 텍스트 (라이트: 어두운 회색) ────────────────────────────────
    readonly property color textPrimary:   "#1a1f2b"    // 본문(어두운 회색)
    readonly property color textSecondary: "#6b7280"    // 보조(중간 회색)
    readonly property color textMuted:      "#7c8493"    // 흐린(중밝은 회색) — 흰 배경서 너무 흐리지 않게

    // ── 하단 내비게이션 바 (옅은 회색, 라이트) ──────────────────────
    readonly property int   navHeight: 152           // 바 높이(px) — 가시성 위해 2배(기존 76)
    readonly property color navBg:     "#f2dfe2e6"    // 옅은 회색(αRGB, ~95%) — 가시성 개선
    // 무입력 페이드: 평소(ACTIVE)엔 또렷, 10초 무입력→대기(AMBIENT)면 거의 안 보이게.
    //   (opacity 만 낮춤 — enabled/클릭 영역은 유지되어 흐릿해도 버튼 동작은 살아있음)
    readonly property real navOpacityActive: 1.0     // 또렷할 때(터치 직후/ACTIVE)
    readonly property real navOpacityIdle:   0.12    // 흐릴 때(무입력/AMBIENT, 거의 투명)
    readonly property int  navFadeMs:        450     // 또렷↔흐림 페이드 시간(ms)

    // ── 왼쪽 3D 위 다크 오버레이 — GEAR 표시 / 기어 슬라이드 전용 ──────
    //    (라이트 패널과 분리. 흰 3D 배경 위 어두운 알약/글래스를 그대로 유지)
    readonly property color overlayPillBg:        "#cc11151e"  // GEAR 알약 배경
    readonly property color overlayBorder:        "#26ffffff"  // 오버레이 보더/레일
    readonly property color overlaySurfaceTop:    "#26222a36"  // 기어 슬라이드 카드 윗면
    readonly property color overlaySurfaceBottom: "#2a161a24"  // 기어 슬라이드 카드 아랫면
    readonly property color overlayTextPrimary:   "#f4f6fb"    // 오버레이 본문(밝게)
    readonly property color overlayTextSecondary: "#9aa4b8"    // 오버레이 보조
    readonly property color overlayTextMuted:     "#5e6778"    // 오버레이 흐린

    // ── 간격 ──────────────────────────────────────────────────────
    readonly property int spaceXs: 8
    readonly property int spaceSm: 12
    readonly property int spaceMd: 16
    readonly property int spaceLg: 24
    readonly property int spaceXl: 32

    // ── 라운드 ────────────────────────────────────────────────────
    readonly property int radiusSm: 12
    readonly property int radius:   18
    readonly property int radiusLg: 22

    // ── 타이포 ────────────────────────────────────────────────────
    readonly property int fsLabel:  20
    readonly property int fsBody:   26
    readonly property int fsTitle:  34
    readonly property int fsHero:   42
    readonly property real tracking: 0.5      // letterSpacing

    // ── 모션 (200~300ms, 절제된 easing) ───────────────────────────
    readonly property int durFast: 140
    readonly property int durMed:  220
    readonly property int durSlow: 300
    readonly property int easeStandard: Easing.OutCubic
    readonly property int easeEmphasis: Easing.OutBack
}
