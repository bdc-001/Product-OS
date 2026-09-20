"""
Convin marketing design system for release-note Docs.

Source: Convin Marketing Design System — Primary/500 #1A62F2, Text/Primary #050505,
Helvetica (headlines) + Inter (body). Presentation artifacts use
app.services.design_system and a separate PDF pipeline.
"""

CONVIN_DOCS = {
    "accent": "1A62F2",
    "accent_dark": "0A2E7A",
    "ink": "050505",
    "muted": "3F3F3F",
    "chip_orange_bg": "EEF4FF",
    "chip_orange_tx": "1A62F2",
    "chip_green_bg": "D8F8E8",
    "chip_green_tx": "0A5C32",
    "font": "Inter",
    "heading_font": "Helvetica",
    "title_size": 22,
    "h2_size": 14,
    "h3_size": 12,
    "body_size": 11,
    "margin_top": 72.0,
    "margin_bottom": 72.0,
    "margin_left": 72.0,
    "margin_right": 72.0,
    "image_width_pt": 420.0,
}


def chip_style(kind: str) -> dict:
    """kind: 'orange' | 'green' — brand info chip vs success."""
    return {
        "orange": {"bg": CONVIN_DOCS["chip_orange_bg"], "tx": CONVIN_DOCS["chip_orange_tx"]},
        "green": {"bg": CONVIN_DOCS["chip_green_bg"], "tx": CONVIN_DOCS["chip_green_tx"]},
    }[kind]


def rgb_color(hexs: str) -> dict:
    raw = (hexs or "050505").strip().lstrip("#")
    if len(raw) != 6:
        raw = "050505"
    return {
        "color": {
            "rgbColor": {
                "red": int(raw[0:2], 16) / 255,
                "green": int(raw[2:4], 16) / 255,
                "blue": int(raw[4:6], 16) / 255,
            }
        }
    }


def pt(magnitude: float) -> dict:
    return {"magnitude": float(magnitude), "unit": "PT"}


def font_family(bold: bool = False, family: str | None = None) -> dict:
    return {"fontFamily": family or CONVIN_DOCS["font"], "weight": 700 if bold else 400}


def named_style_request(style_type: str, *, size: float, bold: bool, fg: str, space_below: float = 6, family: str | None = None) -> dict:
    """Pin a Docs named style so HEADING_* does not snap back to Arial."""
    return {
        "updateNamedStyle": {
            "namedStyle": {
                "namedStyleType": style_type,
                "textStyle": {
                    "weightedFontFamily": font_family(bold, family),
                    "fontSize": pt(size),
                    "foregroundColor": rgb_color(fg),
                    "bold": bold,
                },
                "paragraphStyle": {"spaceBelow": pt(space_below)},
            },
            "fields": "namedStyleType,textStyle.weightedFontFamily,textStyle.fontSize,textStyle.foregroundColor,textStyle.bold,paragraphStyle.spaceBelow",
        }
    }


def theme_named_style_requests() -> list[dict]:
    t = CONVIN_DOCS
    head = t["heading_font"]
    body = t["font"]
    return [
        named_style_request("NORMAL_TEXT", size=t["body_size"], bold=False, fg=t["ink"], space_below=8, family=body),
        named_style_request("TITLE", size=t["title_size"], bold=True, fg=t["ink"], space_below=8, family=head),
        named_style_request("SUBTITLE", size=t["body_size"], bold=False, fg=t["muted"], space_below=6, family=body),
        named_style_request("HEADING_1", size=t["title_size"], bold=True, fg=t["ink"], space_below=8, family=head),
        named_style_request("HEADING_2", size=t["h2_size"], bold=True, fg=t["accent"], space_below=6, family=head),
        named_style_request("HEADING_3", size=t["h3_size"], bold=True, fg=t["ink"], space_below=4, family=head),
    ]
