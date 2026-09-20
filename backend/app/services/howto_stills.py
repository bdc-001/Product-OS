"""Labeled product stills for How to Use 8.x when a live product URL is not available.

JSX cannot emit a PNG. These stills follow the Activate WhatsApp Analytics layout
(cards, funnel, template table, daily trend, blocked leads) rather than stock photos.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.config import ROOT

SLATE = (15, 23, 42)
INK = (30, 41, 59)
MUTED = (100, 116, 139)
LINE = (226, 232, 240)
CARD = (255, 255, 255)
PAGE = (248, 250, 252)
GREEN = (22, 163, 74)
BLUE = (37, 99, 235)
AMBER = (217, 119, 6)
RED = (220, 38, 38)
TEAL = (13, 148, 136)
W = 1280
H = 720


def render_whatsapp_analytics_stills(dest: Path | None = None) -> dict[str, Path]:
    dest = Path(dest) if dest else ROOT / "data" / "howto_stills" / "whatsapp_analytics"
    dest.mkdir(parents=True, exist_ok=True)
    drawers = {
        "8.1": _draw_overview,
        "8.2": _draw_templates,
        "8.3": _draw_daily_trend,
        "8.4": _draw_blocked_leads,
    }
    out: dict[str, Path] = {}
    for key, draw in drawers.items():
        path = dest / f"{key}.png"
        draw().save(path, "PNG")
        out[key] = path
    return out


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = (
        [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
        if bold
        else [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
        ]
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (W, H), PAGE)
    return image, ImageDraw.Draw(image)


def _round(draw: ImageDraw.ImageDraw, box, radius: int, fill, outline=None) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=1)


def _text(draw: ImageDraw.ImageDraw, xy, text: str, size: int, fill=INK, bold: bool = False) -> None:
    draw.text(xy, text, font=_font(size, bold), fill=fill)


def _header(draw: ImageDraw.ImageDraw, subtitle: str) -> None:
    _round(draw, (24, 20, W - 24, 92), 16, CARD, LINE)
    _round(draw, (40, 36, 72, 68), 10, (220, 252, 231))
    _text(draw, (48, 42), "W", 16, GREEN, True)
    _text(draw, (84, 34), "WhatsApp Analytics", 20, INK, True)
    _text(draw, (84, 62), subtitle, 13, MUTED)
    _round(draw, (W - 220, 38, W - 44, 70), 8, PAGE, LINE)
    _text(draw, (W - 204, 46), "Last 7 days", 13, MUTED)


def _draw_overview() -> Image.Image:
    image, draw = _canvas()
    _header(draw, "Delivery, engagement & health across your WABA")
    cards = [
        ("TOTAL ATTEMPTED", "12,480", "send attempts", "+8.2% vs prev", GREEN),
        ("SENT", "640", "awaiting delivery receipt", "5.1%", MUTED),
        ("DELIVERED", "10,210", "81.8% delivery", "+1.4 pp", GREEN),
        ("READ", "7,640", "61.2% read", "+0.8 pp", BLUE),
        ("FAILED", "1,030", "8.3% failed", "-0.6 pp", RED),
    ]
    gap = 16
    left = 24
    top = 112
    width = (W - 48 - gap * 4) // 5
    for i, (label, value, note, delta, color) in enumerate(cards):
        x = left + i * (width + gap)
        _round(draw, (x, top, x + width, top + 148), 18, CARD, LINE)
        _text(draw, (x + 16, top + 16), label, 11, MUTED, True)
        _text(draw, (x + 16, top + 48), value, 26, SLATE, True)
        _text(draw, (x + 16, top + 86), note, 12, MUTED)
        _round(draw, (x + 16, top + 110, x + 132, top + 132), 10, (240, 253, 244) if color == GREEN else PAGE)
        _text(draw, (x + 24, top + 113), delta, 11, color, True)

    _round(draw, (24, 280, W - 24, H - 24), 18, CARD, LINE)
    _text(draw, (44, 300), "Delivery Funnel", 16, INK, True)
    bars = [("Attempted", 12480, BLUE), ("Delivered", 10210, TEAL), ("Read", 7640, GREEN), ("Failed", 1030, RED)]
    max_v = bars[0][1]
    base_y = 620
    bar_w = 140
    start_x = 90
    for i, (label, value, color) in enumerate(bars):
        h = int(280 * (value / max_v))
        x = start_x + i * 220
        draw.rectangle((x, base_y - h, x + bar_w, base_y), fill=color)
        _text(draw, (x, base_y + 12), label, 13, MUTED, True)
        _text(draw, (x, base_y - h - 24), f"{value:,}", 13, INK, True)
    return image


def _draw_templates() -> Image.Image:
    image, draw = _canvas()
    _header(draw, "Template performance for the selected period")
    _round(draw, (24, 112, W - 24, H - 24), 18, CARD, LINE)
    _text(draw, (44, 132), "Template Analytics", 16, INK, True)
    _text(draw, (44, 158), "4 templates configured", 12, MUTED)
    headers = ["Template Name", "Category", "Status", "Sent", "Delivered", "Read", "Failed", "Delivery %"]
    rows = [
        ["welcome_offer", "Marketing", "Approved", "4,820", "4,110", "3,040", "210", "85.3%"],
        ["payment_reminder", "Utility", "Approved", "3,640", "3,410", "2,880", "90", "93.7%"],
        ["kyc_followup", "Utility", "Approved", "2,110", "1,760", "1,120", "180", "83.4%"],
        ["free_flow_reply", "Free-flowing", "—", "1,910", "930", "600", "550", "48.7%"],
    ]
    cols = [220, 130, 110, 110, 130, 100, 100, 120]
    x0, y0 = 44, 196
    x = x0
    for header, width in zip(headers, cols):
        _text(draw, (x, y0), header.upper(), 11, MUTED, True)
        x += width
    draw.line((44, y0 + 28, W - 44, y0 + 28), fill=LINE, width=1)
    y = y0 + 44
    for row in rows:
        x = x0
        for cell, width in zip(row, cols):
            _text(draw, (x, y), cell, 13, INK, cell == row[0])
            x += width
        y += 52
        draw.line((44, y - 16, W - 44, y - 16), fill=LINE, width=1)
    return image


def _draw_daily_trend() -> Image.Image:
    image, draw = _canvas()
    _header(draw, "Daily activity for the selected date range")
    _round(draw, (24, 112, W - 24, H - 24), 18, CARD, LINE)
    _text(draw, (44, 132), "Daily Trends", 16, INK, True)
    legend = [("Attempted", BLUE), ("Delivered", TEAL), ("Read", GREEN)]
    lx = 44
    for label, color in legend:
        _round(draw, (lx, 168, lx + 12, 180), 3, color)
        _text(draw, (lx + 20, 164), label, 13, MUTED)
        lx += 140
    plot = (80, 210, W - 80, 620)
    draw.rectangle(plot, outline=LINE)
    attempted = [980, 1120, 1260, 1410, 1680, 1890, 2140]
    delivered = [810, 940, 1040, 1180, 1410, 1590, 1820]
    read = [540, 630, 710, 820, 990, 1140, 1320]
    series = [(attempted, BLUE), (delivered, TEAL), (read, GREEN)]
    left, top, right, bottom = plot
    max_v = max(attempted)
    for i in range(5):
        y = top + int((bottom - top) * i / 4)
        draw.line((left, y, right, y), fill=(241, 245, 249), width=1)
    for values, color in series:
        pts = []
        for i, value in enumerate(values):
            x = left + int((right - left) * i / (len(values) - 1))
            y = bottom - int((bottom - top) * (value / max_v))
            pts.append((x, y))
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=color)
        draw.line(pts, fill=color, width=3)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for i, day in enumerate(days):
        x = left + int((right - left) * i / 6) - 12
        _text(draw, (x, bottom + 12), day, 12, MUTED)
    return image


def _draw_blocked_leads() -> Image.Image:
    image, draw = _canvas()
    _header(draw, "Engagement health and at-risk leads")
    _round(draw, (24, 112, 430, H - 24), 18, CARD, LINE)
    _text(draw, (44, 132), "Engagement Health", 16, INK, True)
    cx, cy, r = 227, 360, 110
    slices = [(220, GREEN), (90, AMBER), (40, RED), (18, (124, 58, 237))]
    start = -90
    total = sum(n for n, _ in slices)
    for count, color in slices:
        extent = 360 * count / total
        draw.pieslice((cx - r, cy - r, cx + r, cy + r), start, start + extent, fill=color)
        start += extent
    draw.ellipse((cx - 58, cy - 58, cx + 58, cy + 58), fill=CARD)
    _text(draw, (cx - 28, cy - 18), "368", 22, SLATE, True)
    _text(draw, (cx - 22, cy + 10), "leads", 12, MUTED)
    labels = [("Active", GREEN), ("Degraded", AMBER), ("Likely Blocked", RED), ("Likely Spam", (124, 58, 237))]
    y = 520
    for label, color in labels:
        _round(draw, (48, y, 60, y + 12), 3, color)
        _text(draw, (70, y - 2), label, 13, INK)
        y += 28
    _round(draw, (454, 112, W - 24, H - 24), 18, CARD, LINE)
    _text(draw, (476, 132), "Blocked & At-Risk Leads", 16, INK, True)
    _round(draw, (W - 210, 128, W - 48, 158), 8, (254, 242, 242), (254, 226, 226))
    _text(draw, (W - 198, 134), "Export CSV", 12, RED, True)
    headers = ["Phone", "Lead", "Status", "Confidence"]
    rows = [
        ["+91 98•••412", "Ravi K", "Likely Blocked", "0.92"],
        ["+91 90•••118", "Meera S", "Likely Blocked", "0.87"],
        ["+91 80•••773", "Amit P", "Likely Spam", "0.81"],
        ["+91 99•••204", "Neha D", "Degraded", "0.64"],
    ]
    cols = [170, 140, 160, 120]
    x0, y0 = 476, 180
    x = x0
    for header, width in zip(headers, cols):
        _text(draw, (x, y0), header.upper(), 11, MUTED, True)
        x += width
    y = y0 + 36
    for row in rows:
        x = x0
        for cell, width in zip(row, cols):
            _text(draw, (x, y), cell, 13, RED if "Blocked" in cell or "Spam" in cell else INK)
            x += width
        y += 48
    return image
