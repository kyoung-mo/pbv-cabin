pragma Singleton
import QtQuick

// ─────────────────────────────────────────────────────────────────────────
// 디자인 토큰 (단일 출처). 색·간격·라운드·모션을 여기서만 관리.
// 레퍼런스: 테슬라 센터 디스플레이 — 딥 다크 + 글래스 카드 + 절제된 강조.
// ※ 기능/상태와 무관한 순수 비주얼 토큰. 하드코딩 색을 이 토큰으로 대체한다.
// ─────────────────────────────────────────────────────────────────────────
QtObject {
    // ── 배경 (딥 네이비/차콜 그라데이션) ─────────────────────────────
    readonly property color bgTop:    "#161b26"
    readonly property color bgMid:    "#11151e"
    readonly property color bgBottom: "#0d1017"

    // ── 카드/표면 (반투명 어두운 회색 글래스) ───────────────────────
    readonly property color surfaceTop:    "#26222a36"   // αRGB: 살짝 떠 보이는 윗면
    readonly property color surfaceBottom: "#2a161a24"
    readonly property color surfaceSolid:  "#1a2030"      // 불투명이 필요한 곳
    readonly property color surfaceRaised:  "#222a3d"

    // ── 보더 / 구분선 (미세한 흰색) ────────────────────────────────
    readonly property color border:       "#16ffffff"   // ~8% 흰색
    readonly property color borderStrong: "#26ffffff"
    readonly property color sheen:        "#1effffff"    // 상단 내부 하이라이트

    // ── 강조색 (차분한 블루) — 선택/활성에만 사용 ───────────────────
    readonly property color accent:       "#3B82F6"
    readonly property color accentSoft:   "#5b9bf8"
    readonly property color accentBorder: "#803B82F6"
    // rgba() 동적 합성을 위한 채널값
    readonly property real accentR: 0.231
    readonly property real accentG: 0.510
    readonly property real accentB: 0.965

    // ── 텍스트 ────────────────────────────────────────────────────
    readonly property color textPrimary:   "#F4F6FB"
    readonly property color textSecondary: "#9aa4b8"
    readonly property color textMuted:      "#5e6778"

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
