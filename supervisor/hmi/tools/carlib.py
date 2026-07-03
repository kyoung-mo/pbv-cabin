"""소프트웨어 3D 렌더러 + PBV 밴 메시 (Pillow + numpy 전용).

이 Pi에는 blender/trimesh 같은 3D 도구가 없어서, 외부 다운로드 없이
순수 numpy로 저폴리 밴을 만들고 화가 알고리즘(painter's)으로 평면 셰이딩한다.
결과는 차량을 yaw 각도별로 굽는 360° 턴테이블 프레임이다 (라이선스 청정).
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


# =====================================================================
# 메시 구성: 각 면(face)은 (정점 Nx3, 기본색 RGB, 셰이딩여부)
# =====================================================================
def _quad(p0, p1, p2, p3, color, lit=True):
    return (np.array([p0, p1, p2, p3], dtype=float), np.array(color, float), lit)


def box(cx, cy, cz, sx, sy, sz, color, lit=True, faces="all"):
    """축정렬 박스. faces로 특정 면만 선택 가능(예: 윗면 생략)."""
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    # 8 꼭짓점
    x0, x1 = cx - hx, cx + hx
    y0, y1 = cy - hy, cy + hy
    z0, z1 = cz - hz, cz + hz
    v = {
        "A": (x0, y0, z0), "B": (x1, y0, z0), "C": (x1, y1, z0), "D": (x0, y1, z0),
        "E": (x0, y0, z1), "F": (x1, y0, z1), "G": (x1, y1, z1), "H": (x0, y1, z1),
    }
    F = {
        "front":  ("E", "F", "G", "H"),   # +z
        "back":   ("B", "A", "D", "C"),   # -z
        "left":   ("A", "E", "H", "D"),   # -x
        "right":  ("F", "B", "C", "G"),   # +x
        "top":    ("H", "G", "C", "D"),   # +y
        "bottom": ("A", "B", "F", "E"),   # -y
    }
    keys = F.keys() if faces == "all" else faces
    out = []
    for k in keys:
        a, b, c, d = F[k]
        out.append(_quad(v[a], v[b], v[c], v[d], color, lit))
    return out


def cylinder_x(cx, cy, cz, radius, width, color, hub, n=18):
    """x축(차폭 방향)으로 누운 원기둥 = 바퀴. 옆면 + 타이어 캡 + 작은 허브."""
    hw = width / 2
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = np.stack([np.cos(ang) * radius + cy, np.sin(ang) * radius + cz], axis=1)
    out = []
    for i in range(n):
        j = (i + 1) % n
        y0, z0 = ring[i]
        y1, z1 = ring[j]
        out.append(_quad((cx - hw, y0, z0), (cx + hw, y0, z0),
                         (cx + hw, y1, z1), (cx - hw, y1, z1), color, lit=True))
    # 바깥쪽 타이어 캡(어두운 색) — 전체 반경
    capx = cx + hw + 0.001
    cap = [(capx, ring[i][0], ring[i][1]) for i in range(n)]
    out.append((np.array(cap, float), np.array(color, float), False))
    # 작은 허브(밝은 회색) — 캡보다 더 바깥
    hr = radius * 0.46
    hub_ring = np.stack([np.cos(ang) * hr + cy, np.sin(ang) * hr + cz], axis=1)
    hubx = cx + hw + 0.003
    hcap = [(hubx, hub_ring[i][0], hub_ring[i][1]) for i in range(n)]
    out.append((np.array(hcap, float), np.array(hub, float), False))
    return out


# =====================================================================
# PBV 밴 메시 (front = +z)
# =====================================================================
def build_van():
    body = (104, 140, 196)      # 메인 바디(블루)
    body_lo = (58, 66, 86)      # 하부 클래딩(다크)
    roof = (122, 160, 212)
    glass = (30, 44, 60)        # 글라스
    tire = (26, 26, 30)
    hub = (158, 164, 174)
    head = (235, 244, 255)      # 헤드램프
    tail = (200, 60, 55)        # 테일램프

    L, W = 4.2, 1.9             # 길이(z), 폭(x)
    faces = []

    # 하부(휠하우스 라인까지) 다크 클래딩 (바닥면은 안 보이므로 생략 → 깊이정렬 깔끔)
    faces += box(0, -0.30, 0, W, 0.55, L, body_lo,
                 faces=("front", "back", "left", "right"))
    # 메인 바디(허리 위)
    faces += box(0, 0.45, -0.1, W, 1.05, L - 0.2, body,
                 faces=("front", "back", "left", "right"))
    # 루프(약간 좁게 → 그린하우스 느낌)
    faces += box(0, 1.18, -0.15, W - 0.22, 0.5, L - 1.0, roof)

    # 그린하우스(유리) — 바디보다 살짝 바깥으로 빼서 위에 그려지게
    e = 0.012
    gy, gh = 0.95, 0.62
    gz0, gz1 = -(L - 1.0) / 2, (L - 1.0) / 2
    # 측면 유리(좌/우)
    faces.append(_quad((-W / 2 - e, gy - gh / 2, gz0), (-W / 2 - e, gy - gh / 2, gz1),
                       (-W / 2 - e, gy + gh / 2, gz1 - 0.15), (-W / 2 - e, gy + gh / 2, gz0 + 0.15),
                       glass, lit=False))
    faces.append(_quad((W / 2 + e, gy - gh / 2, gz1), (W / 2 + e, gy - gh / 2, gz0),
                       (W / 2 + e, gy + gh / 2, gz0 + 0.15), (W / 2 + e, gy + gh / 2, gz1 - 0.15),
                       glass, lit=False))
    # 앞 유리(전면, +z), 위로 갈수록 뒤로 눕는 경사
    fz = (L - 0.2) / 2 + e
    faces.append(_quad((-(W - 0.3) / 2, gy - gh / 2, fz), ((W - 0.3) / 2, gy - gh / 2, fz),
                       ((W - 0.4) / 2, gy + gh / 2, fz - 0.45), (-(W - 0.4) / 2, gy + gh / 2, fz - 0.45),
                       glass, lit=False))
    # 뒷 유리(후면, -z)
    bz = -(L - 0.2) / 2 - e
    faces.append(_quad(((W - 0.3) / 2, gy - gh / 2, bz), (-(W - 0.3) / 2, gy - gh / 2, bz),
                       (-(W - 0.4) / 2, gy + gh / 2, bz + 0.30), ((W - 0.4) / 2, gy + gh / 2, bz + 0.30),
                       glass, lit=False))

    # 헤드램프(앞면 좌우 하단)
    fz2 = (L - 0.2) / 2 + 0.02
    for sx in (-1, 1):
        cxh = sx * (W / 2 - 0.32)
        faces.append(_quad((cxh - 0.22, 0.15, fz2), (cxh + 0.22, 0.15, fz2),
                           (cxh + 0.22, 0.42, fz2), (cxh - 0.22, 0.42, fz2), head, lit=False))
    # 테일램프(뒷면 좌우)
    bz2 = -(L - 0.2) / 2 - 0.02
    for sx in (-1, 1):
        cxh = sx * (W / 2 - 0.30)
        faces.append(_quad((cxh + 0.20, 0.20, bz2), (cxh - 0.20, 0.20, bz2),
                           (cxh - 0.20, 0.50, bz2), (cxh + 0.20, 0.50, bz2), tail, lit=False))

    # 바퀴 4개
    wr, ww = 0.40, 0.24
    wx = W / 2 - 0.06
    wz = (L - 0.2) / 2 - 0.80
    for sx in (-wx, wx):
        for sz in (-wz, wz):
            faces += cylinder_x(sx, -0.42, sz, wr, ww, tire, hub)

    return faces


# =====================================================================
# 렌더 파이프라인
# =====================================================================
def _rot_y(t):
    c, s = np.cos(t), np.sin(t)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def _rot_x(t):
    c, s = np.cos(t), np.sin(t)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def render_frame(faces, yaw_deg, size=(620, 460), pitch_deg=16.0,
                 cam_d=8.0, focal=620.0, light=(-0.45, 0.85, 0.45)):
    W, H = size
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    R = _rot_x(np.radians(pitch_deg)) @ _rot_y(np.radians(yaw_deg))
    L = np.array(light, float)
    L = L / np.linalg.norm(L)
    cx, cy = W / 2, H / 2 + 30

    def project(P):
        v = P @ R.T
        z = v[:, 2] + cam_d
        sx = cx + focal * v[:, 0] / z
        sy = cy - focal * v[:, 1] / z
        return np.stack([sx, sy], axis=1), v

    # ---- 바닥 그림자(소프트 타원) ----
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    ground = np.array([[-1.3, -0.95, -2.2], [1.3, -0.95, -2.2],
                       [1.3, -0.95, 2.2], [-1.3, -0.95, 2.2]], float)
    gp, _ = project(ground)
    gx0, gy0 = gp[:, 0].min(), gp[:, 1].min()
    gx1, gy1 = gp[:, 0].max(), gp[:, 1].max()
    sd.ellipse([gx0, gy0, gx1, gy1], fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    img.alpha_composite(shadow)

    cam = np.array([0.0, 0.0, -cam_d])      # 뷰공간 카메라 위치
    # ---- 면 정렬(화가 알고리즘) + 백페이스 컬링 ----
    prepared = []
    for verts, color, lit in faces:
        scr, view = project(verts)
        centroid = view.mean(axis=0)
        # 법선(뷰공간). 물체 중심(원점) 기준으로 바깥쪽을 향하도록 정렬.
        n = np.cross(view[1] - view[0], view[2] - view[0])
        nn = np.linalg.norm(n)
        if nn < 1e-9:
            continue                         # 퇴화 면(엣지온) 제거 → 잔상 라인 방지
        n = n / nn
        if float(n @ centroid) < 0:
            n = -n                           # 바깥쪽 법선으로 통일
        # 카메라를 등진 면은 그리지 않음(반대편 램프 비침 제거)
        if float(n @ (cam - centroid)) <= 0.02:
            continue
        if lit:
            diff = max(0.0, float(n @ L))
            shade = 0.54 + 0.58 * diff      # ambient + diffuse
            col = tuple(int(min(255, c * shade)) for c in color)
        else:
            col = tuple(int(c) for c in color)
        prepared.append((centroid[2], scr, col))

    prepared.sort(key=lambda t: t[0], reverse=True)  # 먼 것 먼저
    draw = ImageDraw.Draw(img)
    for _, scr, col in prepared:
        pts = [(float(x), float(y)) for x, y in scr]
        draw.polygon(pts, fill=col + (255,))
    return img
