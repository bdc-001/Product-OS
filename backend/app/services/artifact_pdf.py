"""Print artifact HTML to PDF. Playwright Chromium first, then system Chrome."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

FILL_WARN_BELOW = 0.88
FILL_TARGET_LOW = 0.88
FILL_TARGET_HIGH = 0.98
EMPTY_BAND_MAX_PX = 80
# One PDF sheet per HTML .page, sized to that board. Do not lock paper to A4.
_PRINT_CSS = """
@page { margin: 0; }
html, body {
  margin: 0 !important;
  padding: 0 !important;
  background: #fff !important;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.page {
  height: auto !important;
  overflow: visible !important;
  margin: 0 !important;
  box-sizing: border-box;
  page-break-after: always;
  break-after: page;
  break-inside: avoid;
}
.page:last-child { page-break-after: auto; break-after: auto; }
.page-fit {
  position: relative;
  box-sizing: border-box;
  transform-origin: top left;
}
"""
_MEASURE_BOARDS = """() => {
  const pages = [...document.querySelectorAll('.page')];
  const els = pages.length ? pages : [document.body];
  return els.map((el) => {
    const r = el.getBoundingClientRect();
    return {
      w: Math.ceil(Math.max(el.scrollWidth, el.offsetWidth, r.width, 1)),
      h: Math.ceil(Math.max(el.scrollHeight, el.offsetHeight, r.height, 1)),
    };
  });
}"""

# Nested in-flow footers get hoisted and pinned. Parent padding is copied onto
# the chrome so text is not clipped at the 297mm edge. Scale into pageH - footH.
# Do not zero margin-top:auto — empty bands are a revise-loop problem, not CSS surgery.
_FIT_SCRIPT = """() => {
  const FOOT = /(foot|footer)/i;
  const classOf = (el) => String((el.getAttribute && el.getAttribute('class')) || '');

  const pages = [...document.querySelectorAll('.page')];
  const out = [];
  for (const page of pages) {
    const oldFit = page.querySelector(':scope > .page-fit');
    if (oldFit) {
      while (oldFit.firstChild) page.insertBefore(oldFit.firstChild, oldFit);
      oldFit.remove();
    }

    const foots = page.querySelectorAll('[class*="foot"]');
    if (foots.length) {
      const foot = foots[foots.length - 1];
      const host = foot.parentElement;
      let padL = '', padR = '', padB = '', padT = '';
      if (host && host !== page) {
        const cs = getComputedStyle(foot);
        const ps = getComputedStyle(host);
        padL = 'calc(' + cs.paddingLeft + ' + ' + ps.paddingLeft + ')';
        padR = 'calc(' + cs.paddingRight + ' + ' + ps.paddingRight + ')';
        padB = 'calc(' + cs.paddingBottom + ' + ' + ps.paddingBottom + ')';
        padT = cs.paddingTop;
      }
      if (host !== page) page.appendChild(foot);
      foot.style.position = 'absolute';
      foot.style.bottom = '0';
      foot.style.left = '0';
      foot.style.right = '0';
      foot.style.marginTop = '0';
      foot.style.boxSizing = 'border-box';
      if (padL) {
        foot.style.height = 'auto';
        foot.style.paddingLeft = padL;
        foot.style.paddingRight = padR;
        foot.style.paddingBottom = padB;
        if (padT) foot.style.paddingTop = padT;
      }
    }

    const feet = [...page.children].filter((el) => FOOT.test(classOf(el)));
    const pageBox = page.getBoundingClientRect();
    let footH = 0;
    for (const f of feet) {
      const fr = f.getBoundingClientRect();
      footH = Math.max(footH, pageBox.bottom - fr.top);
    }
    page.dataset.footH = String(Math.round(footH));

    const fit = document.createElement('div');
    fit.className = 'page-fit';
    for (const child of [...page.childNodes]) {
      if (child === fit) continue;
      if (feet.includes(child)) continue;
      fit.appendChild(child);
    }
    page.insertBefore(fit, page.firstChild || null);

    page.style.position = 'relative';
    page.style.display = 'flex';
    page.style.flexDirection = 'column';
    page.style.overflow = 'hidden';
    fit.style.position = 'relative';
    fit.style.boxSizing = 'border-box';
    fit.style.transformOrigin = 'top left';
    fit.style.transform = 'none';
    fit.style.width = '100%';
    fit.style.flex = '1 1 auto';
    fit.style.minHeight = '0';
    fit.style.alignSelf = 'stretch';
    fit.style.display = 'flex';
    fit.style.flexDirection = 'column';

    const pageH = page.clientHeight || 1123;
    const usable = Math.max(pageH - footH, 1);
    const origin = fit.getBoundingClientRect();
    let contentBottom = 0;
    fit.querySelectorAll('*').forEach((node) => {
      const r = node.getBoundingClientRect();
      if (r.height < 1 || r.width < 1) return;
      contentBottom = Math.max(contentBottom, r.bottom - origin.top);
    });
    const scale = Math.min(1, usable / Math.max(contentBottom, 1));
    if (scale < 0.999) {
      fit.style.transform = 'scale(' + scale + ')';
      fit.style.width = (100 / scale) + '%';
    }
    fit.style.overflow = 'hidden';
    fit.dataset.a4Scale = String(Math.round(scale * 10000) / 10000);
    out.push({
      page: out.length + 1,
      scale: Math.round(scale * 10000) / 10000,
      natural: Math.round(contentBottom),
      pageH,
      footH: Math.round(footH),
    });
  }
  document.documentElement.setAttribute('data-a4-fit', '1');
  return out;
}"""


def prepare_print_html(html: str) -> str:
    """Inject print CSS. Paper follows each .page box; do not lock A4."""
    text = re.sub(r"size\s*:\s*A4\b", "size: auto", html or "", flags=re.I)
    snippet = f"<style data-print-page>{_PRINT_CSS}</style>"
    lower = text.lower()
    at = lower.rfind("</head>")
    if at >= 0:
        return text[:at] + snippet + text[at:]
    at = lower.find("<body")
    if at >= 0:
        return text[:at] + snippet + text[at:]
    return snippet + text


def fit_pages_to_a4(html: str, *, timeout: int = 45) -> str:
    """Scale each overflowing .page so the designed board fits 210mm x 297mm.

    Opus lays out past the footer. This keeps that layout and shrinks it onto
    the sheet instead of clipping or asking the model for empty margin.
    """
    text = html or ""
    if "<html" not in text.lower() or "class" not in text.lower():
        return text
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 794, "height": 1123})
            page.set_content(text, wait_until="load", timeout=timeout * 1000)
            try:
                page.evaluate("() => document.fonts && document.fonts.ready")
            except Exception:
                pass
            rows = page.evaluate(_FIT_SCRIPT) or []
            fitted = page.content()
        finally:
            browser.close()
    for row in rows:
        if not isinstance(row, dict):
            continue
        scale = float(row.get("scale") or 1)
        log.info(
            "artifact a4-fit page=%s scale=%s natural=%s pageH=%s footH=%s",
            row.get("page"),
            scale,
            row.get("natural"),
            row.get("pageH"),
            row.get("footH"),
        )
        if scale < 0.85:
            log.warning("artifact a4-fit heavy shrink page=%s scale=%s", row.get("page"), scale)
    return fitted


_FILL_SCRIPT = """() => {
  const BODY = /(page__body|p[12]-body|body[12])/i;
  const classOf = (el) => String((el.getAttribute && el.getAttribute('class')) || '');
  const pages = [...document.querySelectorAll('.page')];
  const els = pages.length ? pages : [document.body];
  return els.map((el, i) => {
    const pageH = el.clientHeight || 1123;
    const pageRect = el.getBoundingClientRect();
    const foot = [...el.querySelectorAll('[class*="foot"]')].at(-1);
    const footTop = foot
      ? (foot.getBoundingClientRect().top - pageRect.top)
      : pageH;
    const usable = Math.max(footTop, 1);
    const skip = (node) => foot && (node === foot || foot.contains(node));
    const substantial = (n) => {
      if (skip(n)) return false;
      if (n.classList && n.classList.contains('page-fit')) return false;
      const r = n.getBoundingClientRect();
      return r.height >= 20 && r.width >= 40;
    };
    const host = el.querySelector(':scope > .page-fit') || el;
    const blocks = [];
    for (const child of [...host.children]) {
      if (!substantial(child)) continue;
      if (BODY.test(classOf(child))) {
        const inner = [...child.children].filter(substantial);
        if (inner.length) blocks.push(...inner);
        else blocks.push(child);
      } else {
        blocks.push(child);
      }
    }
    let contentBottom = 0;
    for (const node of blocks) {
      contentBottom = Math.max(contentBottom, node.getBoundingClientRect().bottom - pageRect.top);
    }
    let emptyBand = 0;
    for (let k = 1; k < blocks.length; k++) {
      const gap = blocks[k].getBoundingClientRect().top - blocks[k - 1].getBoundingClientRect().bottom;
      emptyBand = Math.max(emptyBand, gap);
    }
    const last = blocks[blocks.length - 1];
    if (last) {
      emptyBand = Math.max(
        emptyBand,
        (foot ? foot.getBoundingClientRect().top : pageRect.top + usable) - last.getBoundingClientRect().bottom
      );
    } else {
      emptyBand = usable;
    }
    const clipped = contentBottom > Math.min(pageH, usable) + 2;
    const ratio = Math.min(1, contentBottom / usable);
    return {
      page: i + 1,
      ratio: Math.round(ratio * 1000) / 1000,
      content_bottom: Math.round(contentBottom),
      usable: Math.round(usable),
      clipped: clipped,
      empty_band: Math.round(Math.max(emptyBand, 0)),
    };
  });
}"""

CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
    "chromium-browser",
)


def chrome_bin() -> str | None:
    for path in CHROME_CANDIDATES:
        if os.path.isabs(path) and Path(path).is_file():
            return path
        found = shutil.which(path)
        if found:
            return found
    return None


def html_to_png(html: str, dest: Path, *, width: int = 1280, height: int = 720, timeout: int = 45) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.set_content(html, wait_until="load", timeout=timeout * 1000)
            page.screenshot(path=str(dest), type="png")
        finally:
            browser.close()
    if not dest.is_file() or dest.stat().st_size < 100:
        raise RuntimeError("Playwright wrote an empty PNG.")
    return dest


def measure_page_fill(html: str, *, timeout: int = 45) -> list[dict]:
    """How much of each A4 .page is used, from the top to the last content (footer excluded)."""
    return inspect_brief_layout(html, timeout=timeout)["fills"]


def inspect_brief_layout(html: str, *, screenshots: bool = False, timeout: int = 45) -> dict:
    """One Chromium pass: fill rows plus optional PNG bytes of each .page."""
    from playwright.sync_api import sync_playwright

    pngs: list[bytes] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 794, "height": 1123})
            page.set_content(html, wait_until="load", timeout=timeout * 1000)
            try:
                page.evaluate("() => document.fonts && document.fonts.ready")
            except Exception:
                pass
            fills = page.evaluate(_FILL_SCRIPT)
            if screenshots:
                for el in page.query_selector_all(".page"):
                    pngs.append(el.screenshot(type="png"))
        finally:
            browser.close()
    rows = [row for row in (fills or []) if isinstance(row, dict)]
    return {"fills": rows, "pngs": pngs}


def layout_needs_revise(fills: list[dict]) -> bool:
    if not fills:
        return True
    for row in fills:
        if row.get("clipped"):
            return True
        ratio = float(row.get("ratio") or 0)
        if ratio < FILL_TARGET_LOW:
            return True
        if float(row.get("empty_band") or 0) > EMPTY_BAND_MAX_PX:
            return True
    return False


def log_page_fill(fills: list[dict], *, title: str = "") -> None:
    if not fills:
        log.warning("artifact fill: no .page elements title=%s", title)
        return
    for row in fills:
        ratio = float(row.get("ratio") or 0)
        pct = round(ratio * 100)
        clipped = bool(row.get("clipped"))
        empty = int(row.get("empty_band") or 0)
        log.info(
            "artifact fill title=%s page=%s ratio=%s clipped=%s empty_band=%s content_bottom=%s usable=%s",
            title,
            row.get("page"),
            f"{pct}%",
            clipped,
            empty,
            row.get("content_bottom"),
            row.get("usable"),
        )
        if clipped:
            log.warning("artifact fill overflow title=%s page=%s", title, row.get("page"))
        elif ratio < FILL_WARN_BELOW or empty > EMPTY_BAND_MAX_PX:
            log.warning(
                "artifact fill underfilled title=%s page=%s ratio=%s empty_band=%s (want %s–%s%%, empty<=%s)",
                title,
                row.get("page"),
                f"{pct}%",
                empty,
                int(FILL_TARGET_LOW * 100),
                int(FILL_TARGET_HIGH * 100),
                EMPTY_BAND_MAX_PX,
            )


def html_to_pdf(html: str, dest: Path, *, timeout: int = 60, fit: bool = False) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = fit_pages_to_a4(html, timeout=timeout) if fit else html
    printable = prepare_print_html(source)
    try:
        return _playwright_pdf(printable, dest, timeout=timeout)
    except Exception as exc:
        log.warning("playwright pdf failed; trying Chrome: %s", exc)
    return _chrome_pdf(printable, dest, timeout=timeout)


def _pdf_sheet_kwargs(width: int, height: int) -> dict:
    return {
        "width": f"{max(int(width), 1)}px",
        "height": f"{max(int(height) + 2, 1)}px",
        "print_background": True,
        "prefer_css_page_size": False,
        "scale": 1,
        "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
    }


def _merge_pdf_blobs(blobs: list[bytes], dest: Path) -> Path:
    from io import BytesIO

    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for blob in blobs:
        reader = PdfReader(BytesIO(blob))
        for pdf_page in reader.pages:
            writer.add_page(pdf_page)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as fh:
        writer.write(fh)
    return dest


def _playwright_pdf(html: str, dest: Path, *, timeout: int) -> Path:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 794, "height": 2400})
            page.emulate_media(media="print")
            page.set_content(html, wait_until="load", timeout=timeout * 1000)
            try:
                page.evaluate("() => document.fonts && document.fonts.ready")
            except Exception:
                pass
            boxes = page.evaluate(_MEASURE_BOARDS)
            if not isinstance(boxes, list) or not boxes:
                boxes = [{"w": 794, "h": 1123}]
            log.info(
                "pdf boards=%s",
                [(int(b.get("w") or 0), int(b.get("h") or 0)) for b in boxes],
            )
            if len(boxes) == 1:
                page.pdf(path=str(dest), **_pdf_sheet_kwargs(boxes[0]["w"], boxes[0]["h"]))
            else:
                blobs: list[bytes] = []
                for index, box in enumerate(boxes):
                    page.evaluate(
                        """(index) => {
                          document.querySelectorAll('.page').forEach((el, j) => {
                            el.style.setProperty('page-break-after', 'auto', 'important');
                            el.style.setProperty('break-after', 'auto', 'important');
                            if (j === index) el.style.removeProperty('display');
                            else el.style.setProperty('display', 'none', 'important');
                          });
                        }""",
                        index,
                    )
                    blobs.append(page.pdf(**_pdf_sheet_kwargs(box["w"], box["h"])))
                _merge_pdf_blobs(blobs, dest)
        finally:
            browser.close()
    if not dest.is_file() or dest.stat().st_size < 100:
        raise RuntimeError("Playwright wrote an empty PDF.")
    return dest


def _chrome_pdf(html: str, dest: Path, *, timeout: int) -> Path:
    chrome = chrome_bin()
    if not chrome:
        raise RuntimeError("Chromium/Chrome is required to render artifact PDFs.")
    with tempfile.TemporaryDirectory(prefix="artifact-html-") as tmp:
        source = Path(tmp) / "artifact.html"
        source.write_text(html, encoding="utf-8")
        user_data = Path(tmp) / "chrome-profile"
        user_data.mkdir()
        cmd = [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--disable-extensions",
            "--no-first-run",
            "--no-default-browser-check",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--allow-file-access-from-files",
            "--no-pdf-header-footer",
            f"--user-data-dir={user_data}",
            f"--print-to-pdf={dest}",
            source.resolve().as_uri(),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0 or not dest.is_file() or dest.stat().st_size < 100:
            log.error("chrome pdf failed code=%s stderr=%s", result.returncode, (result.stderr or "")[:2000])
            raise RuntimeError("Chrome failed to print the artifact PDF.")
    return dest
