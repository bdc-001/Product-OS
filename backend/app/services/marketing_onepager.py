"""Sales one-pager (feature_brief): a buyer-facing A4 sheet built from a locked design-system template.

The writer first states the commercial case (the costly problem, who pays, why they would pay), then
writes a short problem -> solution story, picks one or two visuals that show the problem being solved,
and closes on three reasons to buy. Layout is deterministic and deliberately sparse: the brand
masthead, generous whitespace, real product captures and the brand footer. Approved copy is never
rewritten by a designer model. Density steps down until the copy fits one page.
"""
from __future__ import annotations

import base64
import html
import io
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.config import ROOT
from app.storage import WorkspaceDir

ASSETS = WorkspaceDir("release_notes", "assets")
WIDTH, HEIGHT = 794, 1123
ICONS = {
    "filter": '<path d="M3 5h18l-7 8.5V19l-4 2v-7.5z"/>',
    "layers": '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>',
    "gauge": '<path d="M4 18a8 8 0 1 1 16 0"/><path d="M12 18l4.5-6"/>',
    "pulse": '<path d="M3 12h4l2.5-6 5 12 2.5-6H21"/>',
    "message": '<path d="M4 5h16v11H9.5L4 20z"/>',
    "phone": '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/>',
    "alert": '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18h.01"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>',
    "table": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M3 15h18M9 10v10"/>',
    "download": '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "check": '<circle cx="12" cy="12" r="9"/><path d="M8 12.5l3 3 5-6"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6 6 0 0 1 4 6"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    "bolt": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
    "chart": '<path d="M3 20h18"/><path d="M6 16v-5M11 16V6M16 16v-8"/>',
    "link": '<path d="M10 14a4 4 0 0 0 6 0l3-3a4 4 0 0 0-6-6l-1 1"/><path d="M14 10a4 4 0 0 0-6 0l-3 3a4 4 0 0 0 6 6l1-1"/>',
    "eye": '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "sliders": '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "reset": '<path d="M4 12a8 8 0 1 0 3-6.2"/><path d="M4 4v4h4"/>',
    "shield": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
    "wand": '<path d="M4 20L15 9"/><path d="M14 4l1 2 2 1-2 1-1 2-1-2-2-1 2-1zM19 11l.7 1.3L21 13l-1.3.7L19 15l-.7-1.3L17 13l1.3-.7z"/>',
    "trend": '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    "wallet": '<rect x="3" y="6" width="18" height="14" rx="2"/><path d="M3 10h18M16 15h2"/>',
}
IconName = Literal[tuple(ICONS)]  # type: ignore[valid-type]


def _terse(text: str, words: int, what: str) -> None:
    if len(text.split()) > words:
        raise ValueError(f"{what} must stay within {words} words: {text[:80]!r}")


class Positioning(BaseModel):
    """The commercial case behind the sheet. Never printed; it decides what the page says."""
    problem: str = Field(min_length=20, max_length=320, description="The costly problem in the buyer's world, before any product words")
    buyer: str = Field(min_length=10, max_length=200, description="Who signs for it and who uses it day to day")
    why_pay: str = Field(min_length=20, max_length=320, description="Why that buyer would pay: the time, money, risk or revenue at stake")


class Story(BaseModel):
    heading: str = Field(min_length=6, max_length=52)
    text: str = Field(min_length=30, max_length=210)

    @model_validator(mode="after")
    def short(self):
        _terse(self.heading, 8, "A story heading")
        _terse(self.text, 32, "A problem or solution paragraph")
        return self


class Callout(BaseModel):
    label: str = Field(min_length=2, max_length=30, description="The on-screen element, in the product's own wording")
    text: str = Field(min_length=8, max_length=72, description="Why it matters, a few words")
    x: float = Field(ge=2, le=98, description="Pin position as a percentage of the screenshot width; on whitespace beside the element, never over its text")
    y: float = Field(ge=4, le=96, description="Pin position as a percentage of the screenshot height")

    @model_validator(mode="after")
    def short(self):
        _terse(self.text, 10, "A callout")
        return self


class DiagramNode(BaseModel):
    label: str = Field(min_length=2, max_length=24)
    text: str = Field(default="", max_length=64)

    @model_validator(mode="after")
    def short(self):
        _terse(self.text, 10, "A diagram node")
        return self


class Diagram(BaseModel):
    """flow: a sequence of 3-4 stages. split: two genuine sides (before/after). hub: one source serving 3-4 places."""
    kind: Literal["flow", "split", "hub"]
    center: str = Field(default="", max_length=30, description="hub only: the shared source")
    nodes: list[DiagramNode] = Field(min_length=2, max_length=4)

    @model_validator(mode="after")
    def shape(self):
        if (self.kind == "hub") != bool(self.center.strip()):
            raise ValueError("Only a hub diagram names a center, and a hub needs one.")
        if self.kind in {"hub", "flow"} and len(self.nodes) < 3:
            raise ValueError(f"A {self.kind} diagram needs at least three nodes.")
        if self.kind == "split" and len(self.nodes) != 2:
            raise ValueError("A split diagram has exactly two sides.")
        return self


class Visual(BaseModel):
    kind: Literal["screenshot", "diagram"]
    heading: str = Field(min_length=4, max_length=44, description="Short, plain header; no colon chains")
    caption: str = Field(default="", max_length=120, description="Screenshots: what it shows and that data is illustrative")
    screenshot: str = Field(default="", description="id from verified_screenshots (screenshot visuals only)")
    callouts: list[Callout] = Field(default_factory=list, max_length=2, description="Optional; only for an element a buyer would miss")
    diagram: Diagram | None = None

    @model_validator(mode="after")
    def shape(self):
        _terse(self.heading, 7, "A visual heading")
        if self.kind == "screenshot":
            if not self.screenshot.strip() or len(self.caption.strip()) < 15:
                raise ValueError("A screenshot visual needs a verified screenshot id and a caption.")
            if self.diagram:
                raise ValueError("A screenshot visual does not carry a diagram.")
        else:
            if not self.diagram:
                raise ValueError("A diagram visual needs a diagram.")
            if self.screenshot or self.callouts:
                raise ValueError("A diagram visual has no screenshot or callouts.")
        return self


class Value(BaseModel):
    icon: IconName  # type: ignore[valid-type]
    title: str = Field(min_length=3, max_length=30, description="The buyer payoff, not the field name")
    text: str = Field(min_length=10, max_length=100)

    @model_validator(mode="after")
    def short(self):
        _terse(self.title, 5, "A value title")
        _terse(self.text, 16, "A value line")
        return self


class OnePager(BaseModel):
    """Sales collateral: one clean A4 page a seller can hand to a buyer."""
    product: str = Field(min_length=2, max_length=28, description="Product area shown in the product pill, e.g. Agents")
    feature: str = Field(min_length=3, max_length=40, description="Buyer-facing feature name")
    positioning: Positioning
    title: str = Field(min_length=10, max_length=56, description="The outcome in the buyer's words; not the feature name")
    dek: str = Field(min_length=40, max_length=180)
    audience: str = Field(min_length=10, max_length=90, description="Completes 'For ...'")
    problem: Story = Field(description="The buyer's costly situation today")
    solution: Story = Field(description="How the feature removes that problem")
    visuals: list[Visual] = Field(min_length=1, max_length=2)
    value: list[Value] = Field(min_length=3, max_length=3, description="Why teams pay for it")
    cta: str = Field(min_length=10, max_length=90, description="One next step that fits on one line")
    body: str = Field(default="", description="Leave empty; Markdown is assembled from the approved copy.")

    @model_validator(mode="after")
    def sales_shape(self):
        _terse(self.title, 9, "The headline")
        _terse(self.dek, 28, "The dek")
        if self.title.strip().casefold() == self.feature.strip().casefold():
            raise ValueError("The headline sells the outcome; the feature name already sits in the product pill.")
        if sum(v.kind == "diagram" for v in self.visuals) > 1:
            raise ValueError("Use at most one diagram; the second visual should be product proof.")
        if len({v.screenshot for v in self.visuals if v.screenshot}) < sum(v.kind == "screenshot" for v in self.visuals):
            raise ValueError("Each screenshot visual uses a different capture.")
        titles = [v.title.casefold() for v in self.value]
        if len(set(titles)) != len(titles):
            raise ValueError("Each reason to buy makes a different point.")
        return self


def onepager_text(content: dict) -> list[str]:
    """Every approved string the rendered page must show verbatim."""
    texts = [content.get(k, "") for k in ("product", "feature", "title", "dek", "audience")]
    for key in ("problem", "solution"):
        story = content.get(key) or {}
        texts += [story.get("heading", ""), story.get("text", "")]
    for visual in content.get("visuals") or []:
        texts += [visual.get("heading", ""), visual.get("caption", "")]
        for callout in visual.get("callouts") or []:
            texts += [callout.get("label", ""), callout.get("text", "")]
        diagram = visual.get("diagram") or {}
        texts.append(diagram.get("center", ""))
        for node in diagram.get("nodes") or []:
            texts += [node.get("label", ""), node.get("text", "")]
    for item in content.get("value") or []:
        texts += [item.get("title", ""), item.get("text", "")]
    texts.append(content.get("cta", ""))
    return [text for text in texts if text]


def _visual_markdown(v: dict) -> str:
    lines = [f"## {v['heading']}"]
    if v.get("caption"):
        lines.append(v["caption"])
    if v.get("diagram"):
        d = v["diagram"]
        lead = f"{d['center']}: " if d.get("center") else ""
        lines.append(lead + "\n".join(f"- **{n['label']}** {n.get('text', '')}".rstrip() for n in d["nodes"]))
    if v.get("callouts"):
        lines.append("\n".join(f"- **{c['label']}** {c['text']}" for c in v["callouts"]))
    return "\n\n".join(lines)


def onepager_markdown(value: dict) -> str:
    parts = [f"**{value['product']} · {value['feature']}**", value["dek"], f"For {value['audience']}",
             f"## {value['problem']['heading']}\n\n{value['problem']['text']}",
             f"## {value['solution']['heading']}\n\n{value['solution']['text']}"]
    parts += [_visual_markdown(v) for v in value["visuals"]]
    parts.append("## Why teams pay for it\n\n" + "\n".join(f"- **{v['title']}** {v['text']}" for v in value["value"]))
    parts.append(value["cta"])
    return "\n\n".join(parts)


def onepager_units(value: dict) -> dict[str, str]:
    """Editorial review units: every public string on the sheet, grouped by where it sits."""
    units = {
        "hero": "\n".join([value["title"], value["dek"], value["audience"]]),
        "problem": f"{value['problem']['heading']}\n{value['problem']['text']}",
        "solution": f"{value['solution']['heading']}\n{value['solution']['text']}",
    }
    for index, visual in enumerate(value["visuals"]):
        units[f"visuals[{index}]"] = _visual_markdown(visual)
    for index, item in enumerate(value["value"]):
        units[f"value[{index}]"] = f"{item['title']}\n{item['text']}"
    units["cta"] = value["cta"]
    return units


def _tokens(text: str) -> set[str]:
    stop = {"and", "the", "of", "for", "a", "an", "to", "updates", "update", "new", "improvements", "release", "v2"}
    return {word.rstrip("s") for word in re.findall(r"[a-z0-9]+", str(text).casefold()) if word not in stop}


def verified_screenshots(*feature_names: str) -> list[dict]:
    """Real product captures from release-note pipelines whose feature matches any of these names."""
    wanted = [_tokens(name) for name in feature_names if _tokens(name)]
    if not wanted or not ASSETS.is_dir():
        return []
    found = []
    for note_path in sorted(ASSETS.glob("**/note.json")):
        try:
            note = json.loads(note_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        labels = [note.get("feature", ""), note.get("title", ""), note_path.parent.name.replace("-", " "), *(note.get("aliases") or [])]
        names = [_tokens(n) for n in labels]
        if not any(n and (w <= n or n <= w) for n in names for w in wanted):
            continue
        for section in note.get("sections") or []:
            shot = section.get("screenshot") or {}
            shot_id = f"{note_path.parent.relative_to(ASSETS).as_posix()}/{shot.get('id', '')}"
            if shot.get("id") and screenshot_path(shot_id):
                found.append({"id": shot_id, "caption": shot.get("caption", ""), "section": section.get("heading", "")})
    return found


def screenshot_path(shot_id: str) -> Path | None:
    folder, _, name = str(shot_id).rpartition("/")
    base = (ASSETS / folder).resolve()
    if not name or ASSETS.resolve() not in base.parents and base != ASSETS.resolve():
        return None
    for candidate in (base / "raw" / f"{name}.png", base / f"{name}.png"):
        if candidate.is_file():
            return candidate
    return None


def _shot(path: Path) -> tuple[str, float]:
    """Embedded PNG data URI and its width/height ratio."""
    from PIL import Image
    with Image.open(path) as image:
        picture = image.convert("RGB")
        picture.thumbnail((1800, 1800))
        buffer = io.BytesIO()
        picture.save(buffer, "PNG", optimize=True)
        ratio = picture.width / max(1, picture.height)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"), ratio


def _e(value) -> str:
    return html.escape(str(value or ""), quote=True)


def _icon(name: str) -> str:
    return (f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')


# Roomiest first: the renderer keeps the largest scale that fits one page. shot is the primary
# visual's max height, second the supporting visual's.
DENSITY = [
    {"title": 38, "dek": 15.5, "body": 12.5, "gap": 26, "pad": 36, "shot": 270, "second": 150},
    {"title": 36, "dek": 15, "body": 12.25, "gap": 22, "pad": 32, "shot": 255, "second": 136},
    {"title": 34, "dek": 14.5, "body": 12, "gap": 19, "pad": 28, "shot": 240, "second": 122},
    {"title": 32, "dek": 14, "body": 11.5, "gap": 16, "pad": 24, "shot": 220, "second": 110},
]


def _css(d: dict) -> str:
    return f"""
@page {{ size: {WIDTH}px {HEIGHT}px; margin: 0; }}
*{{box-sizing:border-box}}
html,body{{margin:0;padding:0;background:#fff}}
.page{{width:{WIDTH}px;height:{HEIGHT}px;overflow:hidden;display:flex;flex-direction:column;background:#fff;color:#151515;
  font:400 {d['body']}px/1.55 Inter,"Helvetica Neue",Arial,sans-serif;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.d{{font-family:"Helvetica Now Display","Satoshi","Helvetica Neue",Helvetica,Arial,sans-serif;letter-spacing:-.02em}}
.hero{{position:relative;flex:0 0 auto;overflow:hidden;color:#fff;padding:{d['pad']}px 56px {d['pad'] + 4}px;
  background:radial-gradient(80% 120% at 100% 0%,rgba(26,98,242,.55) 0%,rgba(26,98,242,0) 60%),
  linear-gradient(160deg,#0A2E7A 0%,#071B4D 55%,#050B18 100%)}}
.hero .motif{{position:absolute;right:-40px;top:-20px;width:380px;height:260px;opacity:.38}}
.mast{{position:relative;display:flex;align-items:center;justify-content:space-between}}
.mast img{{height:24px;display:block}}
.pill{{display:inline-flex;align-items:center;gap:8px;padding:4px 12px 4px 10px;border:1px solid rgba(175,202,251,.4);
  border-radius:999px;background:rgba(26,98,242,.16);font-size:11px;font-weight:500;color:#D6E4FF}}
.pill i{{width:7px;height:7px;border-radius:50%;background:#5FE6EB}}
.pill b{{color:#fff;font-weight:500}}
.pill s{{text-decoration:none;width:1px;height:11px;background:rgba(175,202,251,.5)}}
h1{{position:relative;margin:22px 0 0;font-size:{d['title']}px;line-height:1.08;font-weight:700;max-width:682px;text-wrap:balance}}
.dek{{position:relative;margin:10px 0 0;font-size:{d['dek']}px;line-height:1.5;color:#D6E4FF;max-width:640px}}
.aud{{position:relative;margin:10px 0 0;font-size:{d['body'] - .5}px;color:#AFCAFB}}
.aud span{{color:#5FE6EB;font-weight:500;margin-right:6px}}
.body{{flex:1 1 auto;display:flex;flex-direction:column;justify-content:space-between;gap:{d['gap']}px;
  padding:{d['gap'] + 4}px 56px {d['gap'] + 2}px}}
.label{{display:block;font-size:10px;font-weight:600;letter-spacing:.12em;text-transform:uppercase}}
h2{{margin:0;font-size:17px;line-height:1.25;font-weight:700;color:#050505}}
h3{{margin:6px 0 0;font-size:16px;line-height:1.3;font-weight:700;color:#050505}}
.story{{display:grid;grid-template-columns:1fr 1fr;gap:40px}}
.story > div + div{{position:relative}}
.story > div + div:before{{content:"";position:absolute;left:-20px;top:2px;bottom:2px;width:1px;background:#E3E8F2}}
.story p{{margin:6px 0 0;color:#3F3F3F}}
.story .problem .label{{color:#8A93A6}}
.story .solution .label{{color:#1A62F2}}
.visual{{margin:0}}
.frame{{display:flex;justify-content:center;align-items:center;padding:10px;border:1px solid #E3E8F2;border-radius:14px;background:#F7F9FC}}
.shot{{position:relative;display:inline-block;line-height:0}}
.shot img{{display:block;max-width:100%;border-radius:8px;box-shadow:0 1px 2px rgba(10,46,122,.06),0 6px 18px rgba(10,46,122,.08)}}
.side{{display:grid;grid-template-columns:188px minmax(0,1fr);gap:24px;align-items:center}}
.side .vtext{{display:flex;flex-direction:column;gap:8px}}
.side .cap{{font-size:{d['body'] - .5}px;line-height:1.5;color:#6A6A6A}}
.side .shot img{{max-height:{d['shot']}px}}
.side.second .shot img{{max-height:{d['second'] + 60}px}}
.side.solo .shot img{{max-height:{d['shot'] + 80}px}}
.strip{{display:flex;flex-direction:column;gap:10px}}
.strip .frame{{padding:8px}}
.vhead{{display:flex;align-items:baseline;justify-content:space-between;gap:24px}}
.vhead h2{{flex:0 0 auto}}
.vhead .cap{{max-width:330px;text-align:right;font-size:10.5px;line-height:1.4;color:#8A93A6}}
.strip .shot img{{max-height:{d['second']}px}}
.strip.primary .shot img,.strip.solo .shot img{{max-height:{d['shot']}px}}
.pin{{position:absolute;width:20px;height:20px;margin:-10px 0 0 -10px;border-radius:50%;background:#1A62F2;color:#fff;
  font:700 10.5px/20px Inter,Arial,sans-serif;text-align:center;box-shadow:0 0 0 3px #fff}}
.cap{{margin:0}}
.notes{{display:flex;flex-direction:column;gap:6px;margin:0;padding:0;list-style:none;font-size:{d['body'] - 1}px;color:#3F3F3F}}
.strip .notes{{flex-direction:row;gap:24px}}
.notes li{{display:flex;gap:8px;align-items:baseline}}
.notes b{{flex:0 0 16px;height:16px;border-radius:50%;background:#1A62F2;color:#fff;font:700 9.5px/16px Inter,Arial,sans-serif;text-align:center}}
.notes strong{{font-weight:600;color:#050505;margin-right:4px}}
.dia{{display:grid;gap:12px;align-items:stretch}}
.dia .node{{border:1px solid #E3E8F2;border-radius:12px;background:#fff;padding:12px 14px}}
.dia .node strong{{display:block;font-size:13px;line-height:1.25;color:#0A2E7A}}
.dia .node span{{display:block;margin-top:3px;color:#3F3F3F;font-size:{d['body'] - .5}px;line-height:1.4}}
.dia .node.last{{background:#0A2E7A;border-color:#0A2E7A}}
.dia .node.last strong{{color:#fff}}
.dia .node.last span{{color:#D6E4FF}}
.dia .link{{display:flex;align-items:center;justify-content:center;color:#1A62F2}}
.dia .link svg{{width:16px;height:16px}}
.hub{{display:flex;flex-direction:column;align-items:center;gap:14px}}
.hub .center{{padding:7px 18px;border-radius:999px;background:#0A2E7A;color:#fff;font-size:12.5px;font-weight:700}}
.hub .kids{{width:100%;display:grid;grid-template-columns:repeat(var(--n),1fr);gap:12px}}
.value h2{{margin-bottom:12px}}
.vals{{display:grid;grid-template-columns:repeat(3,1fr);gap:32px}}
.val + .val{{position:relative}}
.val + .val:before{{content:"";position:absolute;left:-16px;top:2px;bottom:2px;width:1px;background:#E3E8F2}}
.val-h{{display:flex;align-items:center;gap:10px}}
.val .ic{{flex:0 0 28px;height:28px;border-radius:8px;background:#EEF4FF;color:#1A62F2;display:flex;align-items:center;justify-content:center}}
.val .ic svg{{width:15px;height:15px}}
.val strong{{display:block;font-size:13.5px;line-height:1.25;color:#050505}}
.val > span{{display:block;margin-top:7px;color:#3F3F3F;line-height:1.5}}
.cta{{flex:0 0 auto;display:flex;align-items:center;gap:14px;padding:13px 56px;color:#fff;
  background:linear-gradient(100deg,#1A62F2 0%,#144ECF 55%,#103EA6 100%)}}
.cta .label{{flex:0 0 auto;padding:4px 10px;border-radius:999px;background:rgba(255,255,255,.16);color:#fff;letter-spacing:.1em}}
.cta strong{{font-size:14px;line-height:1.35;font-weight:600}}
.foot{{flex:0 0 40px;display:flex;align-items:center;justify-content:space-between;padding:0 56px;
  background:#050505;color:#8A93A6;font-size:10.5px;font-weight:500;letter-spacing:.12em;text-transform:uppercase}}
.foot img{{height:16px;display:block}}
"""


MOTIF = (
    '<svg class="motif" viewBox="0 0 360 260" fill="none" aria-hidden="true">'
    '<g stroke="#7DA8F8" stroke-width="1">'
    '<path d="M10 220C90 200 120 120 200 110S320 60 350 20" opacity=".55"/>'
    '<path d="M40 250C120 230 150 160 230 150S330 110 360 70" opacity=".35"/></g>'
    '<g fill="#5FE6EB"><circle cx="200" cy="110" r="3"/><circle cx="230" cy="150" r="2.5" opacity=".7"/></g></svg>'
)
ARROW = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" '
         'stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>')


def _diagram(d: dict) -> str:
    nodes = d["nodes"]
    cells = [f'<div class="node{" last" if d["kind"] != "hub" and i == len(nodes) - 1 else ""}"><strong>{_e(n["label"])}</strong>'
             + (f'<span>{_e(n["text"])}</span>' if n.get("text") else "") + "</div>"
             for i, n in enumerate(nodes)]
    if d["kind"] == "hub":
        return (f'<div class="hub"><div class="center">{_e(d["center"])}</div>'
                f'<div class="kids dia" style="--n:{len(nodes)}">{"".join(cells)}</div></div>')
    columns = " 22px ".join(["1fr"] * len(nodes))
    joined = f'<div class="link">{ARROW}</div>'.join(cells)
    return f'<div class="dia" style="grid-template-columns:{columns}">{joined}</div>'


def _visual(v: dict, feature: str, role: str) -> str:
    head = f'<h2 class="d">{_e(v["heading"])}</h2>'
    caption = f'<p class="cap">{_e(v["caption"])}</p>' if v.get("caption") else ""
    if v["kind"] == "diagram":
        return f'<figure class="visual {role}"><div class="vhead">{head}{caption}</div>{_diagram(v["diagram"])}</figure>'
    path = screenshot_path(v["screenshot"])
    if not path:
        raise ValueError(f"Screenshot {v['screenshot']!r} is not a verified product capture; use an id from verified_screenshots.")
    uri, ratio = _shot(path)
    callouts = v.get("callouts") or []
    pins = "".join(f'<b class="pin" style="left:{c["x"]:.1f}%;top:{c["y"]:.1f}%">{i}</b>' for i, c in enumerate(callouts, start=1))
    notes = ("<ol class=\"notes\">" + "".join(f'<li><b>{i}</b><div><strong>{_e(c["label"])}</strong>{_e(c["text"])}</div></li>'
                                              for i, c in enumerate(callouts, start=1)) + "</ol>") if callouts else ""
    frame = f'<div class="frame"><div class="shot"><img src="{uri}" alt="{_e(feature)} in {{{{brand_product}}}}">{pins}</div></div>'
    # Wide strips read best full width under a one-line header; taller captures sit beside their text.
    if ratio >= 2.6:
        return f'<figure class="visual strip {role}"><div class="vhead">{head}{caption}</div>{frame}{notes}</figure>'
    return f'<figure class="visual side {role}"><div class="vtext">{head}{caption}{notes}</div>{frame}</figure>'


def onepager_html(content: dict, level: int = 0) -> str:
    d = DENSITY[level]
    c = content
    hero = (
        f'<header class="hero">{MOTIF}'
        f'<div class="mast"><img src="{{{{brand_on_dark}}}}" alt="{{{{brand_name}}}}">'
        f'<span class="pill"><i></i><b>{{{{brand_product}}}}</b><s></s>{_e(c["product"])}</span></div>'
        f'<h1 class="d">{_e(c["title"])}</h1><p class="dek">{_e(c["dek"])}</p>'
        f'<p class="aud"><span>For</span>{_e(c["audience"])}</p></header>'
    )
    story = (
        f'<section class="story"><div class="problem"><span class="label">The problem</span>'
        f'<h3 class="d">{_e(c["problem"]["heading"])}</h3><p>{_e(c["problem"]["text"])}</p></div>'
        f'<div class="solution"><span class="label">With {_e(c["feature"])}</span>'
        f'<h3 class="d">{_e(c["solution"]["heading"])}</h3><p>{_e(c["solution"]["text"])}</p></div></section>'
    )
    visuals = c["visuals"]
    roles = ["solo"] if len(visuals) == 1 else ["primary", "second"]
    figures = "".join(_visual(v, c["feature"], role) for v, role in zip(visuals, roles))
    value = ('<section class="value"><h2 class="d">Why teams pay for it</h2><div class="vals">'
             + "".join(f'<div class="val"><div class="val-h"><span class="ic">{_icon(v["icon"])}</span><strong class="d">{_e(v["title"])}</strong></div>'
                       f'<span>{_e(v["text"])}</span></div>' for v in c["value"])
             + "</div></section>")
    page = (
        f'<section class="page">{hero}<main class="body">{story}{figures}{value}</main>'
        f'<div class="cta"><span class="label">Next step</span><strong class="d">{_e(c["cta"])}</strong></div>'
        f'<footer class="foot"><img src="{{{{brand_on_dark}}}}" alt="{{{{brand_name}}}}"><span>Product one-pager</span></footer></section>'
    )
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{_e(c["title"])}</title>'
            f"<style>{_css(d)}</style></head><body>{page}</body></html>")


def render_onepager(content: dict, folder: Path, set_step=lambda *a: None):
    """Largest type scale that holds every approved word on one A4 page, no clipping."""
    from app.services.marketing_design import render_design
    content = OnePager.model_validate(content).model_dump() | {"body": content.get("body", "")}
    last = "One-pager could not fit the approved copy on one page."
    for level in range(len(DENSITY)):
        try:
            return render_design("feature_brief", content, onepager_html(content, level), folder)
        except ValueError as exc:
            last = str(exc)
            if "omitted or rewrote" in last or "lost approved copy" in last or "verified product capture" in last:
                raise
            set_step("feature_brief", {"status": "running", "design_repair_attempt": level + 1})
    raise ValueError(last + " Shorten the one-pager copy.")
