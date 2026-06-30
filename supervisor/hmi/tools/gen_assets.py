"""모든 HMI 에셋을 순수 Pillow+numpy로 생성한다 (외부 다운로드/라이선스 0).

생성물:
  assets/car/car_00..35.png   - PBV 밴 360° 턴테이블 (드래그 회전용)
  assets/modes/*.png          - 모드 4종 타일 배경 (주행/회의/Full-space/휴식)
  assets/seats/overview.png   - 위에서 본 캐빈 좌석 배치
  assets/seats/seat.png       - 좌석 상세 측면 일러스트

재생성:  python3 tools/gen_assets.py
"""

import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from carlib import build_van, render_frame

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")


# =====================================================================
# 차량 턴테이블
# =====================================================================
def gen_car(n=36):
    out = os.path.join(ASSETS, "car")
    os.makedirs(out, exist_ok=True)
    faces = build_van()
    for i in range(n):
        yaw = 360.0 * i / n
        img = render_frame(faces, yaw)
        img.save(os.path.join(out, f"car_{i:02d}.png"))
    print(f"car: {n} frames")


# =====================================================================
# 공통 헬퍼: 세로 그라데이션
# =====================================================================
def vgrad(w, h, top, bot):
    t = np.array(top, float)
    b = np.array(bot, float)
    ramp = (t[None, :] + (b - t)[None, :] * np.linspace(0, 1, h)[:, None])
    arr = np.repeat(ramp[:, None, :], w, axis=1).astype(np.uint8)
    return Image.fromarray(arr, "RGB").convert("RGBA")


def rrect(draw, box, r, fill):
    draw.rounded_rectangle(box, radius=r, fill=fill)


# =====================================================================
# 모드 타일 (각 600x460)
# =====================================================================
def _mode_drive(w, h):
    img = vgrad(w, h, (38, 52, 92), (12, 16, 30))   # 황혼 하늘
    d = ImageDraw.Draw(img, "RGBA")
    horizon = int(h * 0.52)
    d.rectangle([0, horizon, w, h], fill=(20, 22, 30))   # 도로
    # 원근 차선
    cx = w // 2
    for k in range(7):
        f = k / 7.0
        y0 = horizon + int((h - horizon) * f)
        y1 = horizon + int((h - horizon) * (f + 0.5 / 7))
        ww0 = 6 + f * 26
        d.polygon([(cx - ww0, y1), (cx + ww0, y1),
                   (cx + ww0 * 0.6, y0), (cx - ww0 * 0.6, y0)],
                  fill=(230, 220, 140, 220))
    # 가장자리 라인
    d.line([(cx - 230, h), (cx - 40, horizon)], fill=(180, 190, 210, 120), width=4)
    d.line([(cx + 230, h), (cx + 40, horizon)], fill=(180, 190, 210, 120), width=4)
    # 해
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([cx - 70, horizon - 120, cx + 70, horizon + 20], fill=(255, 180, 90, 230))
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    img.alpha_composite(glow)
    return img


def _mode_meeting(w, h):
    img = vgrad(w, h, (46, 40, 64), (24, 22, 34))
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy = w // 2, int(h * 0.56)
    # 둥근 테이블
    d.ellipse([cx - 150, cy - 70, cx + 150, cy + 70], fill=(120, 90, 64))
    d.ellipse([cx - 150, cy - 80, cx + 150, cy + 60], fill=(150, 112, 78))
    # 둘러앉은 좌석 4개
    seats = [(-200, -10), (200, -10), (-110, 120), (110, 120)]
    for dx, dy in seats:
        x, y = cx + dx, cy + dy
        rrect(d, [x - 46, y - 46, x + 46, y + 30], 16, (70, 88, 120))
        rrect(d, [x - 46, y - 70, x + 46, y - 30], 14, (90, 110, 146))
    # 따뜻한 천장 조명
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([cx - 120, 10, cx + 120, 150], fill=(255, 210, 150, 200))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)))
    return img


def _mode_fullspace(w, h):
    img = vgrad(w, h, (30, 70, 88), (14, 30, 40))   # 탁 트인 분위기
    d = ImageDraw.Draw(img, "RGBA")
    horizon = int(h * 0.46)
    d.rectangle([0, horizon, w, h], fill=(40, 58, 66))
    # 바닥 원근 그리드
    cx = w // 2
    for k in range(-6, 7):
        x = cx + k * 50
        d.line([(cx + k * 16, horizon), (x, h)], fill=(120, 160, 170, 90), width=2)
    for k in range(1, 7):
        f = k / 6.0
        y = horizon + int((h - horizon) * f * f)
        d.line([(0, y), (w, y)], fill=(120, 160, 170, 90), width=2)
    # 큰 파노라마 창 빛
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).rectangle([40, 20, w - 40, horizon - 20], fill=(170, 220, 235, 120))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(30)))
    return img


def _mode_rest(w, h):
    img = vgrad(w, h, (28, 24, 48), (8, 8, 18))
    d = ImageDraw.Draw(img, "RGBA")
    # 달
    d.ellipse([w - 150, 40, w - 70, 120], fill=(230, 232, 245))
    d.ellipse([w - 135, 36, w - 60, 110], fill=(28, 24, 48))
    # 별
    for x, y, r in [(80, 60, 3), (160, 110, 2), (240, 50, 2),
                    (300, 130, 3), (120, 160, 2), (360, 90, 2)]:
        d.ellipse([x - r, y - r, x + r, y + r], fill=(220, 225, 245))
    # 리클라인된 좌석 실루엣
    cx, cy = int(w * 0.42), int(h * 0.74)
    d.polygon([(cx - 130, cy + 40), (cx + 150, cy + 40),
               (cx + 150, cy + 10), (cx - 60, cy + 10)], fill=(54, 50, 78))  # 시트 베이스
    d.polygon([(cx - 130, cy + 40), (cx - 60, cy + 10),
               (cx - 30, cy - 90), (cx - 95, cy - 80)], fill=(64, 60, 92))   # 등받이(눕힘)
    # 따뜻한 무드등
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([cx - 40, cy - 40, cx + 200, cy + 80], fill=(180, 120, 90, 150))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(45)))
    return img


def gen_modes(w=600, h=460):
    out = os.path.join(ASSETS, "modes")
    os.makedirs(out, exist_ok=True)
    mapping = {
        "drive": _mode_drive, "meeting": _mode_meeting,
        "fullspace": _mode_fullspace, "rest": _mode_rest,
    }
    for name, fn in mapping.items():
        fn(w, h).save(os.path.join(out, f"{name}.png"))
    print("modes: 4 tiles")


# =====================================================================
# 좌석 오버뷰 (위에서 본 캐빈) + 좌석 상세
# =====================================================================
def gen_seat_overview(w=600, h=620):
    img = vgrad(w, h, (26, 30, 40), (16, 18, 26))
    d = ImageDraw.Draw(img, "RGBA")
    # 캐빈 바닥
    rrect(d, [60, 50, w - 60, h - 50], 40, (44, 50, 64))
    rrect(d, [70, 60, w - 70, h - 60], 34, (54, 62, 78))
    # 앞유리(상단)
    rrect(d, [110, 70, w - 110, 120], 16, (80, 120, 150))
    # 스티어링(운전석 앞)
    d.ellipse([105, 150, 175, 220], outline=(180, 190, 205), width=10)
    # 좌석은 QML이 인터랙티브 카드로 그 위에 올린다(선택 하이라이트용) → 여기선 셸만.
    out = os.path.join(ASSETS, "seats")
    os.makedirs(out, exist_ok=True)
    img.save(os.path.join(out, "overview.png"))
    print("seats: overview")


def gen_seat_side(w=600, h=360):
    img = vgrad(w, h, (40, 46, 62), (22, 26, 36))
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy = int(w * 0.5), int(h * 0.78)
    # 바닥 그림자
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([cx - 170, cy + 20, cx + 190, cy + 70], fill=(0, 0, 0, 120))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)))
    # 시트 쿠션
    rrect(d, [cx - 150, cy - 10, cx + 120, cy + 34], 18, (74, 92, 128))
    rrect(d, [cx - 150, cy - 4, cx + 120, cy + 24], 14, (96, 118, 160))
    # 등받이
    d.polygon([(cx - 150, cy - 6), (cx - 96, cy - 6),
               (cx - 60, cy - 180), (cx - 120, cy - 176)], fill=(86, 106, 146))
    d.polygon([(cx - 144, cy - 8), (cx - 104, cy - 8),
               (cx - 70, cy - 172), (cx - 116, cy - 168)], fill=(108, 132, 178))
    # 헤드레스트
    rrect(d, [cx - 132, cy - 210, cx - 78, cy - 168], 14, (96, 118, 160))
    # 다리/베이스
    rrect(d, [cx - 120, cy + 30, cx - 96, cy + 56], 6, (50, 58, 76))
    rrect(d, [cx + 80, cy + 30, cx + 104, cy + 56], 6, (50, 58, 76))
    img.save(os.path.join(ASSETS, "seats", "seat.png"))
    print("seats: side")


if __name__ == "__main__":
    gen_car()
    gen_modes()
    gen_seat_overview()
    gen_seat_side()
    print("DONE")
