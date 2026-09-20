"""Convin marketing design tokens for presentation artifacts.

Source: Convin Marketing Design System (Helvetica Now Display + Inter).
Helvetica Now Display is not licensed here; Helvetica Neue is the Mac substitute.
Satoshi in the PDF is the website face — artifacts use the marketing pairing.
"""

from __future__ import annotations

from pathlib import Path

from PIL import ImageFont

FONT_DIR = Path(__file__).resolve().parents[1] / "fonts"

# Primary
PRIMARY_900 = "0A2E7A"
PRIMARY_800 = "103EA6"
PRIMARY_700 = "144ECF"
PRIMARY_600 = "1658E1"
PRIMARY_500 = "1A62F2"
PRIMARY_400 = "4A84F5"
PRIMARY_300 = "7DA8F8"
PRIMARY_200 = "AFCAFB"
PRIMARY_100 = "D1E1FD"
PRIMARY_50 = "EEF4FF"

# Accent
ACCENT_1 = "1580EB"
ACCENT_2 = "FCED02"
ACCENT_3 = "1AC468"
ACCENT_4 = "F93739"
ACCENT_5 = "F8AA0D"
ACCENT_6 = "5FE6EB"

# Neutral / text
INK = "050505"
INK_800 = "0A0A0A"
INK_700 = "0F0F0F"
INK_600 = "121212"
INK_500 = "151515"
MUTED = "3F3F3F"
MUTED_300 = "6A6A6A"
MUTED_200 = "959595"
NEUTRAL_50 = "EBEBEB"
INVERSE = "F1F1F1"
WHITE = "FFFFFF"

PAGE = PRIMARY_50
BRAND = PRIMARY_500
NAVY = PRIMARY_900
YELLOW = ACCENT_2
CARD = WHITE
ELEVATION_FILL = PRIMARY_200

RADIUS = 20
SLIDE_W, SLIDE_H = 1920, 1080
MARGIN = 72

# Marketing type scale (px)
DISPLAY_XL, DISPLAY_XL_LH = 72, 80
DISPLAY_L, DISPLAY_L_LH = 56, 64
DISPLAY_M, DISPLAY_M_LH = 48, 56
H1, H1_LH = 40, 48
H2, H2_LH = 32, 40
H3, H3_LH = 24, 32
H4, H4_LH = 20, 28
BODY_XL, BODY_XL_LH = 20, 32
BODY_L, BODY_L_LH = 18, 28
BODY_M, BODY_M_LH = 16, 26
BODY_S, BODY_S_LH = 14, 22
BODY_XS, BODY_XS_LH = 12, 18
STAT_L, STAT_L_LH = 32, 36
TRACKING = -2


def rgb(hexs: str) -> tuple[int, int, int]:
    raw = (hexs or INK).lstrip("#")
    if len(raw) != 6:
        raw = INK
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def font_display(size: int, *, medium: bool = False) -> ImageFont.ImageFont:
    faces = [
        ("/System/Library/Fonts/HelveticaNeue.ttc", 10 if medium else 1),
        ("/System/Library/Fonts/Helvetica.ttc", 1),
        ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 0),
    ]
    return _truetype(faces, size)


def font_body(size: int, *, medium: bool = False) -> ImageFont.ImageFont:
    name = "Inter-Medium.ttf" if medium else "Inter-Regular.ttf"
    bundled = FONT_DIR / name
    faces = [
        (str(bundled), 0),
        ("/System/Library/Fonts/Supplemental/Arial.ttf", 0),
        ("/System/Library/Fonts/Helvetica.ttc", 0),
    ]
    return _truetype(faces, size)


def _truetype(faces: list[tuple[str, int]], size: int) -> ImageFont.ImageFont:
    for path, index in faces:
        try:
            return ImageFont.truetype(path, size, index=index)
        except OSError:
            continue
    return ImageFont.load_default()
