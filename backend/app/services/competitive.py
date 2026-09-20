"""Competitor radar, parity matrix, pricing watch, and market sensing."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from html.parser import HTMLParser
from html import unescape
from urllib.parse import urlparse, urljoin

from sqlalchemy.orm import Session

from app.clients.http import get
from app.clients.llm import LLMClient
from app.models import (
    Competitor,
    CompetitorSignal,
    JiraIssue,
    MarketSignal,
    MarketWatch,
    ParityCapability,
    PricingSnapshot,
    Roadmap,
)
from app.services.time_window import now_local

log = logging.getLogger(__name__)

USER_AGENT = "SourabhBot-PM-Platform/1.0 (+local; public-page fetch)"

# Sense = Convin AI Phone / Agent platform (campaigns, voice agents, KB, widgets).
# Not Auto QA / conversation-intelligence QA tools (Observe, Gong, CallMiner, etc.).
DEFAULT_COMPETITORS: list[dict] = [
    {
        "slug": "retell-ai",
        "name": "Retell AI",
        "website": "https://www.retellai.com/",
        "blog_url": "https://www.retellai.com/blog",
        "pricing_url": "https://www.retellai.com/pricing",
        "aliases": ["retell"],
        "notes": "Sense rival — AI phone / voice agents",
    },
    {
        "slug": "bland-ai",
        "name": "Bland AI",
        "website": "https://www.bland.ai/",
        "blog_url": "https://www.bland.ai/blogs",
        "pricing_url": "https://www.bland.ai/pricing",
        "aliases": ["bland"],
        "notes": "Sense rival — outbound AI calling at scale",
    },
    {
        "slug": "vapi",
        "name": "Vapi",
        "website": "https://vapi.ai/",
        "blog_url": "https://vapi.ai/blog",
        "pricing_url": "https://vapi.ai/pricing",
        "aliases": ["vapi ai"],
        "notes": "Sense rival — developer voice-agent platform",
    },
    {
        "slug": "synthflow",
        "name": "Synthflow",
        "website": "https://synthflow.ai/",
        "blog_url": "https://synthflow.ai/blog",
        "pricing_url": "https://synthflow.ai/pricing",
        "aliases": ["synthflow ai"],
        "notes": "Sense rival — no-code voice agents",
    },
    {
        "slug": "air-ai",
        "name": "Air AI",
        "website": "https://air.ai/",
        "blog_url": "https://air.ai/blog",
        "pricing_url": "",
        "aliases": ["air.ai"],
        "notes": "Sense rival — autonomous phone agents",
    },
    {
        "slug": "elevenlabs-agents",
        "name": "ElevenLabs Agents",
        "website": "https://elevenlabs.io/conversational-ai",
        "blog_url": "https://elevenlabs.io/blog",
        "pricing_url": "https://elevenlabs.io/pricing",
        "aliases": ["elevenlabs", "eleven labs"],
        "notes": "Sense rival — conversational AI / voice agents",
    },
    {
        "slug": "polyai",
        "name": "PolyAI",
        "website": "https://poly.ai/",
        "blog_url": "https://poly.ai/blog",
        "pricing_url": "",
        "aliases": ["poly ai"],
        "notes": "Sense rival — enterprise voice assistants",
    },
    {
        "slug": "yellow-ai",
        "name": "Yellow.ai",
        "website": "https://yellow.ai/",
        "blog_url": "https://yellow.ai/blog",
        "pricing_url": "https://yellow.ai/pricing",
        "aliases": ["yellowai", "yellow ai"],
        "notes": "Sense rival — omnichannel AI agents (strong in India/APAC)",
    },
    {
        "slug": "sarvam",
        "name": "Sarvam AI",
        "website": "https://www.sarvam.ai/",
        "blog_url": "https://www.sarvam.ai/blog",
        "pricing_url": "",
        "aliases": ["sarvam.ai", "sarvam ai"],
        "notes": "Sense rival — Indic foundation models + voice agents",
    },
    {
        "slug": "gupshup",
        "name": "Gupshup",
        "website": "https://www.gupshup.io/",
        "blog_url": "https://www.gupshup.io/resources/blog",
        "pricing_url": "https://www.gupshup.io/pricing",
        "aliases": ["gupshup.ai", "gupshup ai"],
        "notes": "Sense rival — messaging + Voice AI platform",
    },
    {
        "slug": "bolna",
        "name": "Bolna AI",
        "website": "https://www.bolna.ai/",
        "blog_url": "https://www.bolna.ai/blog",
        "pricing_url": "https://www.bolna.ai/pricing",
        "aliases": ["bolna.ai", "bolna"],
        "notes": "Sense rival — Indic voice agents (dev + no-code)",
    },
    {
        "slug": "gnani",
        "name": "Gnani.ai",
        "website": "https://www.gnani.ai/",
        "blog_url": "https://www.gnani.ai/blog",
        "pricing_url": "",
        "aliases": ["gnani", "gnani ai"],
        "notes": "Sense rival — enterprise voice agents (BFSI / India)",
    },
    {
        "slug": "caller-digital",
        "name": "Caller Digital",
        "website": "https://caller.digital/",
        "blog_url": "https://caller.digital/blog",
        "pricing_url": "",
        "aliases": ["caller digital"],
        "notes": "Sense rival — India enterprise voice AI deployments",
    },
    {
        "slug": "exotel",
        "name": "Exotel",
        "website": "https://exotel.com/",
        "blog_url": "https://exotel.com/blog",
        "pricing_url": "https://exotel.com/pricing",
        "aliases": ["exotel ai"],
        "notes": "Sense rival — CPaaS + AI voice agents (India)",
    },
    {
        "slug": "haptik",
        "name": "Haptik",
        "website": "https://www.haptik.ai/",
        "blog_url": "https://www.haptik.ai/blog",
        "pricing_url": "",
        "aliases": ["haptik.ai"],
        "notes": "Sense rival — conversational AI / voice bots (India)",
    },
    {
        "slug": "skit-ai",
        "name": "Skit.ai",
        "website": "https://skit.ai/",
        "blog_url": "https://skit.ai/blog",
        "pricing_url": "",
        "aliases": ["skit", "skit ai"],
        "notes": "Sense rival — voice bots / contact automation",
    },
]

DEFAULT_CAPABILITIES = [
    "AI phone / voice agents (inbound + outbound)",
    "Campaign dialer & bulk lead upload",
    "Knowledge base grounding",
    "Multilingual / Indic languages",
    "Voice cloning & TTS quality",
    "Website voice/chat widget",
    "SMS / omnichannel agent",
    "CRM sync (Salesforce / HubSpot)",
    "Real-time transfer to human agent",
    "SSO / SAML",
    "Custom LLM / BYOK",
    "Campaign analytics & reporting",
]

DEFAULT_WATCHES: list[dict] = [
    # AI Capabilities = product-builder radar (models, setups, viral repos, patterns) — not corporate capability pages.
    {"category": "ai", "name": "OpenAI", "url": "https://openai.com/news/rss.xml", "notes": "Official model and product launches"},
    {"category": "ai", "name": "Google AI", "url": "https://blog.google/technology/ai/rss/", "notes": "Gemini and Google AI launches"},
    {
        "category": "ai",
        "name": "Anthropic / Claude",
        "url": "https://news.google.com/rss/search?q=Anthropic+OR+Claude+(model+OR+launch+OR+release+OR+API+OR+agent)&hl=en-US&gl=US&ceid=US:en",
        "notes": "Claude and Anthropic builder-facing news",
    },
    {"category": "ai", "name": "Hugging Face", "url": "https://huggingface.co/blog/feed.xml", "notes": "Models, spaces, open-source drops"},
    {"category": "ai", "name": "Simon Willison", "url": "https://simonwillison.net/atom/everything/", "notes": "Practical LLM tooling and patterns"},
    {"category": "ai", "name": "Latent Space", "url": "https://www.latent.space/feed", "notes": "AI engineer / product-builder discourse"},
    {
        "category": "ai",
        "name": "Viral GitHub / open-source AI",
        "url": "https://news.google.com/rss/search?q=GitHub+(trending+OR+stars+OR+viral)+(AI+OR+LLM+OR+agent+OR+%22open+source%22)&hl=en-US&gl=US&ceid=US:en",
        "notes": "Repos and open-source projects gaining attention",
    },
    {
        "category": "ai",
        "name": "Agent stacks & setups",
        "url": "https://news.google.com/rss/search?q=Hermes+OR+OpenClaw+OR+%22Open+WebUI%22+OR+LangGraph+OR+CrewAI+OR+AutoGen+OR+Ollama+OR+%22MCP+server%22+OR+%22AI+agent+framework%22&hl=en-US&gl=US&ceid=US:en",
        "notes": "New agent stacks, local setups, frameworks to try",
    },
    {
        "category": "ai",
        "name": "New models & releases",
        "url": "https://news.google.com/rss/search?q=%22new+model%22+OR+%22model+release%22+OR+GPT-5+OR+%22GPT-4%22+OR+Llama+OR+Mistral+OR+Gemini+OR+%22open+weights%22+(AI+OR+LLM)&hl=en-US&gl=US&ceid=US:en",
        "notes": "Frontier and open-weight model drops",
    },
    {
        "category": "ai",
        "name": "How builders use AI",
        "url": "https://news.google.com/rss/search?q=%22AI+agent%22+(product+OR+startup+OR+workflow+OR+%22voice+AI%22+OR+RAG)+OR+%22using+Claude%22+OR+%22using+GPT%22&hl=en-US&gl=US&ceid=US:en",
        "notes": "Usage patterns and product experiments worth copying",
    },
    {"category": "ai", "name": "Hacker News AI", "url": "https://news.google.com/rss/search?q=site:news.ycombinator.com+(AI+OR+LLM+OR+Claude+OR+GPT+OR+agent)&hl=en-US&gl=US&ceid=US:en", "notes": "HN AI chatter via Google News (hnrss is flaky)"},
    {
        "category": "industry",
        "name": "AI voice / phone agent news",
        "url": "https://news.google.com/rss/search?q=%22AI+phone+agent%22+OR+%22voice+AI+agent%22+OR+Sarvam+OR+Gupshup+OR+Bolna+OR+Retell+OR+Bland&hl=en-IN&gl=IN&ceid=IN:en",
        "notes": "Sense category — India + global voice agents",
    },
    {
        "category": "industry",
        "name": "Conversational AI agent platforms",
        "url": "https://news.google.com/rss/search?q=%22conversational+AI%22+voice+agent+OR+%22AI+voice+agent%22+platform&hl=en-US&gl=US&ceid=US:en",
        "notes": "",
    },
    {
        "category": "compliance",
        "name": "India DPDP / data protection news",
        "url": "https://news.google.com/rss/search?q=DPDP+OR+%22Digital+Personal+Data+Protection%22+India&hl=en-IN&gl=IN&ceid=IN:en",
        "notes": "Recording consent & residency implications",
    },
    {
        "category": "compliance",
        "name": "Call recording / TCPA-style consent news",
        "url": "https://news.google.com/rss/search?q=%22call+recording%22+consent+OR+TCPA+OR+%22two-party+consent%22+OR+%22AI+calling%22+regulation&hl=en-US&gl=US&ceid=US:en",
        "notes": "",
    },
    {
        "category": "integration",
        "name": "Salesforce Platform releases",
        "url": "https://www.salesforce.com/blog/category/developers/",
        "notes": "CRM partner API / platform changes",
    },
    {
        "category": "integration",
        "name": "HubSpot developers blog",
        "url": "https://developers.hubspot.com/blog",
        "notes": "",
    },
    {
        "category": "integration",
        "name": "Twilio / voice telephony developer",
        "url": "https://www.twilio.com/en-us/blog/developers",
        "notes": "Telephony & voice stack Sense sits on",
    },
]

# Legacy Auto QA seeds — deactivate if present (Sense radar should not track these).
AUTO_QA_SLUGS = {
    "observe-ai",
    "balto",
    "cresta",
    "gong",
    "callminer",
    "gistly",
    "enthu-ai",
    "level-ai",
    "maestroqa",
    "scorebuddy",
}

TAG_KEYWORDS = {
    "pricing": ("pricing", "price", "plan", "package", "seat", "add-on", "addon", "tier", "free trial"),
    "positioning": ("announce", "launch partnership", "rebrand", "position", "market", "leader", "g2"),
    "shipping": ("ship", "release", "changelog", "new feature", "now available", "ga ", "generally available"),
    "feature_parity": ("ai", "assist", "transcription", "coaching", "qa", "analytics", "crm", "whatsapp", "saml", "sso"),
}

# Publisher spam / fraud hosts — never ingest or show (Google News titles often append the source name).
BLOCKED_NEWS_DOMAINS = {
    "losgatan.com",
    "www.losgatan.com",
}
BLOCKED_NEWS_MARKERS = (
    "los gatan",
    "losgatan.com",
    "buy github stars",
    "buy github followers",
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self.parts: list[str] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg", "nav", "header", "footer"}:
            self._skip += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg", "nav", "header", "footer"} and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        text = (data or "").strip()
        if not text:
            return
        if self._in_title and not self.title:
            self.title = text[:240]
        if self._skip:
            return
        self.parts.append(text)


def _now() -> datetime:
    return now_local().replace(tzinfo=None)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return slug[:64] or "rival"


def _hash_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()[:40]


def _strip_html(html: str) -> tuple[str, str]:
    parser = _TextExtractor()
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:
        pass
    body = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    return parser.title.strip(), body[:12000]



class _ArticleLinks(HTMLParser):
    """Extract article permalinks from official listing pages, excluding navigation."""
    def __init__(self, base):
        super().__init__()
        self.base, self.href, self.words, self.items = base, "", [], []
        self.description = ""
    def handle_starttag(self, tag, attrs):
        if tag == "meta":
            meta = dict(attrs)
            if meta.get("name", meta.get("property", "")) in {"description", "og:description"}:
                self.description = meta.get("content", "")
        if tag == "a":
            self.href = urljoin(self.base, dict(attrs).get("href", ""))
            self.words = []
    def handle_data(self, data):
        if self.href: self.words.append(data.strip())
    def handle_endtag(self, tag):
        if tag != "a" or not self.href: return
        title = re.sub(r"\s+", " ", " ".join(self.words)).strip()
        url = urlparse(self.href)
        base = urlparse(self.base)
        if (url.scheme in {"http", "https"} and url.netloc == base.netloc
            and url.path.rstrip("/") != base.path.rstrip("/")
            and re.search(r"/(blogs?|news|changelog|updates|releases)/.+", url.path)
            and not re.search(r"/(tag|category|author|page)/", url.path)
            and len(title) > 24 and len(title) < 400
            and self.href not in {i["url"] for i in self.items}):
            self.items.append({"title": title, "url": self.href, "summary": ""})
        self.href = ""


def feature_evidence(row):
    text = f"{row.title} {row.summary} {row.raw_excerpt or ''}".lower()
    voice = bool(re.search(r"voice|phone|calling|speech|telephony|ivr|sip|latency|interrupt", text))
    omni = bool(re.search(r"omnichannel|multi.channel|orchestrat|workflow|whatsapp|sms|journey|handoff|handover", text))
    focus = (["Voicebots"] if voice else []) + (["Omnichannel orchestration"] if omni else [])
    if not focus: focus = ["Platform"]
    path = urlparse(row.url or "").path.rstrip("/")
    snapshot = row.source in {"website", "pricing", "g2"} or path in {"", "/blog", "/blogs", "/news", "/resources/blog"}
    announcement = not snapshot and bool(re.search(r"\b(launch(?:es|ed|ing)?|introducing|release(?:s|d)?|now available|new feature|changelog|what.s new)\b", f"{row.title} {row.summary}".lower()))
    state = "Release announcement" if announcement else "Feature signal" if row.tag == "feature_parity" or row.source == "changelog" else "Market update"
    return {"focus": focus, "release_status": state, "is_feature": announcement or row.tag == "feature_parity" or row.source == "changelog", "is_snapshot": snapshot,
            "sense_relevance": "Evaluate channel continuity, journey triggers, and human handoff in Sense." if omni else "Evaluate voice quality, call automation, and agent reliability in Sense." if voice else "Review platform impact before adding this to the Sense roadmap."}


def ai_capability(title, summary):
    """Classify AI radar items for a product builder exploring what to try next."""
    text = f"{title} {clean_summary(summary)}".lower()
    if re.search(
        r"funding grants|supporting.*journalism|support journalism|sponsorship|"
        r"crossword|olympics|\bnba\b|\bnfl\b|stock price|earnings|dividend|"
        r"weather forecast|horoscope",
        text,
    ):
        return None
    # Pure policy / markets chatter without a builder hook
    if re.search(r"\b(ai policy|regulation|congress|senate|lobbying|antitrust|stock|ipo)\b", text) and not re.search(
        r"\b(model|api|sdk|github|agent|open.?source|mcp|hermes|openclaw)\b", text
    ):
        return None
    if not re.search(
        r"\b(ai|llm|gpt|claude|gemini|llama|mistral|anthropic|openai|hugging.?face|"
        r"model|agent|github|open.?source|open.?weight|rag|mcp|hermes|openclaw|"
        r"langgraph|crewai|autogen|ollama|vllm|fine.?tun|voice|speech|codex|"
        r"cursor|copilot|tool.?use|multimodal|reasoning)\b",
        text,
    ):
        return None

    if re.search(r"\b(github|stars|trending|viral.?repo|open.?source|hugging.?face)\b", text) and re.search(
        r"\b(repo|project|library|framework|stars|trending|space)\b", text
    ):
        news_tag = "Viral repo"
    elif re.search(
        r"\b(hermes|openclaw|open.?webui|aider|continue\.dev|langgraph|crewai|autogen|"
        r"ollama|self.?host|local.?llm|agent.?framework|mcp\b|tool.?calling|setup|stack|harness)\b",
        text,
    ):
        news_tag = "Agent setup"
    elif re.search(
        r"\b(gpt-?\d|claude\s?(?:3|4|sonnet|opus|haiku)|gemini|llama\s?\d|mistral|"
        r"sonnet|opus|flash|o[13]\b|frontier model|foundation model|language model|"
        r"new(?:\s+\w+){0,3}\s+model|model (?:release|launch|drop|announc)|open.?weight|"
        r"fine.?tun(?:ing|e)|training a .+ model)\b",
        text,
    ):
        news_tag = "New model"
    elif re.search(r"\b(research|paper|arxiv|clinical.*study|benchmark study|\bresearch\b)\b", text):
        news_tag = "Research"
    elif re.search(r"\b(sdk|api\b|eval|benchmark|observability|vector|embedding|inference|vllm|tokenizer|devtools|kernel|webgpu)\b", text):
        news_tag = "Tooling"
    else:
        news_tag = "Builder pattern"

    area = (
        "Voice & audio"
        if re.search(r"voice|speech|audio|phone.?agent|tts|asr", text)
        else "Agents & tools"
        if re.search(r"agent|tool|mcp|hermes|openclaw|coding|codex|workflow", text)
        else "Open source"
        if re.search(r"github|open.?source|open.?weight|hugging.?face|ollama", text)
        else "Multimodal"
        if re.search(r"image|video|multimodal|vision", text)
        else "Models & reasoning"
    )
    maturity = (
        "Research"
        if re.search(r"\bresearch\b|benchmark|experiment|arxiv|clinical.*study", text)
        else "Preview / upcoming"
        if re.search(r"preview|coming soon|early access|waitlist|beta|alpha", text)
        else "Try now"
        if news_tag in {"Viral repo", "Agent setup", "Tooling"}
        else "Announcement"
    )
    lens = {
        "New model": "Skim capabilities vs cost/latency — could this upgrade Sense voice, reasoning, or BYOK options?",
        "Viral repo": "Clone or star it this week. Note what builders are copying and whether Sense should ship a similar pattern.",
        "Agent setup": "Worth a weekend spike: does this stack change how we build phone/voice agents or local demos?",
        "Builder pattern": "Product pattern to borrow — map it to a Sense epic or discard with a one-line reason.",
        "Tooling": "Check if this speeds evals, observability, or agent tooling in the Sense stack.",
        "Research": "Watch only unless it unlocks a concrete product bet in the next quarter.",
    }.get(news_tag, "Decide if this is worth exploring for Sense this week.")
    return {"ai_area": area, "maturity": maturity, "news_tag": news_tag, "sense_relevance": lens}


def signal_feed(db, view="news", q="", rival=0, focus="all", offset=0, limit=20, snapshots=False, tag="all"):
    query = db.query(CompetitorSignal).join(Competitor, Competitor.id == CompetitorSignal.competitor_id).filter(Competitor.active.is_(True))
    if rival: query = query.filter(CompetitorSignal.competitor_id == rival)
    if q.strip():
        from sqlalchemy import or_
        needle = "%" + q.strip() + "%"
        query = query.filter(or_(CompetitorSignal.title.ilike(needle), CompetitorSignal.summary.ilike(needle), CompetitorSignal.competitor_name.ilike(needle)))
    rows = []
    seen = set()
    for row in query.order_by(CompetitorSignal.seen_at.desc(), CompetitorSignal.id.desc()).all():
        if is_blocked_news(row.title, row.summary, row.url or "", row.competitor_name or ""):
            continue
        evidence = feature_evidence(row)
        price_change = row.source == "pricing" and "changed" in row.title.lower()
        if evidence["is_snapshot"] and not snapshots and not price_change: continue
        if view == "features" and not evidence["is_feature"]: continue
        if focus != "all" and focus not in evidence["focus"]: continue
        key = (row.competitor_id, row.url or row.title)
        if key in seen: continue
        seen.add(key)
        label = "Price Change" if price_change else "Feature Release" if evidence["release_status"] == "Release announcement" else "Pricing" if re.search(r"pric(?:e|ing)|cost|packaging", row.title.lower()) else "Feature Signal" if evidence["is_feature"] else "Industry News"
        rows.append({**signal_out(row), **evidence, "news_tag": label, "excerpt": row.raw_excerpt or row.summary})
    if view == "ai": rows = []
    if view != "features" and not rival:
        market = db.query(MarketSignal).join(MarketWatch, MarketWatch.id == MarketSignal.watch_id).filter(MarketWatch.active.is_(True))
        if view == "ai": market = market.filter(MarketSignal.category == "ai")
        else: market = market.filter(MarketSignal.category != "ai")
        for item in market.order_by(MarketSignal.seen_at.desc()).all():
            if is_blocked_news(item.title, item.summary, item.url or "", item.source_name or ""):
                continue
            if q.lower().strip() not in f"{item.title} {item.summary} {item.source_name}".lower(): continue
            ai = ai_capability(item.title, item.summary) if item.category == "ai" else {}
            if ai is None: continue
            evidence = feature_evidence(type("Evidence", (), {"title":item.title, "summary":clean_summary(item.summary,item.title), "raw_excerpt":item.raw_excerpt, "url":item.url, "source":"article", "tag":"positioning"})())
            if view == "ai":
                # Product-builder focus: match Sense lenses loosely against the article text.
                blob = f"{item.title} {item.summary}".lower()
                if focus == "Voicebots" and not re.search(r"voice|speech|audio|phone|tts|asr|telephony", blob):
                    continue
                if focus == "Omnichannel orchestration" and not re.search(r"omni|whatsapp|sms|channel|orchestrat|workflow|handoff", blob):
                    continue
                if focus == "Platform" and not re.search(r"model|sdk|api|infra|platform|eval|tool|github|open.?source|llm|agent", blob):
                    continue
            elif focus != "all" and focus not in evidence["focus"]:
                continue
            key = (item.watch_id, item.url or item.title)
            if ("market", key) in seen: continue
            seen.add(("market", key))
            if item.category == "ai":
                label = ai.get("news_tag") or "Builder pattern"
                sense = ai.get("sense_relevance") or evidence["sense_relevance"]
            else:
                label = {"industry":"Industry News", "compliance":"Compliance", "integration":"Integration"}.get(item.category,"Industry News")
                if item.category == "industry" and evidence["release_status"] == "Release announcement": label = "Feature Release"
                sense = evidence["sense_relevance"]
            rows.append({
                "id": -item.id,
                "competitor_name": item.source_name,
                "source": "builder feed" if item.category == "ai" else item.category,
                "title": item.title,
                "summary": clean_summary(item.summary, item.title),
                "url": item.url,
                "tag": item.category,
                "ask_eng": "",
                "seen_at": item.seen_at.isoformat() if item.seen_at else None,
                **evidence,
                "sense_relevance": sense,
                "news_tag": label,
                **{k: v for k, v in ai.items() if k != "news_tag" and k != "sense_relevance"},
                "excerpt": clean_summary(item.raw_excerpt or item.summary, item.title),
            })
    if tag != "all": rows = [r for r in rows if r["news_tag"] == tag]
    rows.sort(key=lambda row: row["seen_at"] or "", reverse=True)
    # Actual articles precede landing-page snapshots; newest observations first within each group.
    rows.sort(key=lambda row: row["is_snapshot"] and row["news_tag"] != "Price Change")
    return {"signals": rows[offset:offset + limit], "total": len(rows), "offset": offset}


def _fetch_public(url: str) -> dict:
    if not url or not url.startswith(("http://", "https://")):
        return {"ok": False, "error": "invalid url", "title": "", "text": "", "hash": ""}
    last_error = ""
    for attempt in range(2):
        try:
            response = get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/rss+xml,application/xml,text/xml,*/*"},
                follow_redirects=True,
                timeout=15,
            )
            response.raise_for_status()
            raw = response.text or ""
            content_type = (response.headers.get("content-type") or "").lower()
            if "xml" in content_type or raw.lstrip().startswith("<?xml") or "<rss" in raw[:500].lower():
                items = _parse_rss_items(raw)
                joined = "\n".join(f"{item['title']}: {item.get('summary', '')}" for item in items[:12])
                return {
                    "ok": True,
                    "error": "",
                    "title": items[0]["title"] if items else "RSS feed",
                    "text": joined,
                    "hash": _hash_text(joined),
                    "rss_items": items[:20],
                }
            title, text = _strip_html(raw)
            links = _ArticleLinks(url)
            links.feed(raw)
            if not title:
                title = urlparse(url).netloc or url
            return {"ok": True, "error": "", "title": title, "text": text, "hash": _hash_text(text), "rss_items": [], "articles": links.items[:6], "description": links.description}
        except Exception as exc:
            last_error = str(exc)[:240]
            # One retry for transient gateway / rate-limit failures.
            if attempt == 0 and re.search(r"\b(502|503|504|429)\b", last_error):
                import time
                time.sleep(1.2)
                continue
            break
    return {"ok": False, "error": last_error, "title": "", "text": "", "hash": "", "rss_items": []}


def is_blocked_news(title: str = "", summary: str = "", url: str = "", source: str = "") -> bool:
    """Drop known fraud / spam publishers that leak into Google News AI feeds."""
    host = urlparse(url or "").netloc.lower().removeprefix("www.")
    if host in {d.removeprefix("www.") for d in BLOCKED_NEWS_DOMAINS} or any(host.endswith("." + d.removeprefix("www.")) for d in BLOCKED_NEWS_DOMAINS):
        return True
    blob = f"{title} {summary} {url} {source}".lower()
    return any(marker in blob for marker in BLOCKED_NEWS_MARKERS)


def _parse_rss_items(xml_text: str) -> list[dict]:
    items: list[dict] = []
    for block in re.findall(r"<item\b[\s\S]*?</item>", xml_text or "", flags=re.I):
        title = re.search(r"<title[^>]*>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</title>", block, flags=re.I)
        link = re.search(r"<link[^>]*>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</link>", block, flags=re.I)
        desc = re.search(r"<description[^>]*>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</description>", block, flags=re.I)
        source = re.search(r"<source\b[^>]*url=[\"']([^\"']+)[\"'][^>]*>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</source>", block, flags=re.I)
        t = re.sub(r"<[^>]+>", "", (title.group(1) if title else "")).strip()
        u = re.sub(r"<[^>]+>", "", (link.group(1) if link else "")).strip()
        d = clean_summary(desc.group(1) if desc else "")
        d = re.sub(r"\s+", " ", d)[:400]
        publisher_url = (source.group(1) if source else "").strip()
        publisher = re.sub(r"<[^>]+>", "", (source.group(2) if source else "")).strip()
        if t and not is_blocked_news(t, d, publisher_url or u, publisher):
            items.append({"title": t[:300], "url": u[:500], "summary": d, "publisher": publisher, "publisher_url": publisher_url[:500]})
    return items


def _heuristic_tag(title: str, text: str) -> str:
    blob = f"{title} {text}".lower()
    scores = {tag: sum(1 for kw in kws if kw in blob) for tag, kws in TAG_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "positioning"


def _ask_eng_line(tag: str, title: str) -> str:
    if tag == "pricing":
        return f"Compare packaging language vs Sense for: {title[:120]}"
    if tag == "feature_parity":
        return f"Do we have an AC epic covering: {title[:120]}?"
    if tag == "positioning":
        return f"Update battlecard / messaging for: {title[:120]}"
    return f"Skim changelog impact on Sense roadmap: {title[:120]}"


def _llm_enrich(title: str, excerpt: str, competitor: str) -> dict | None:
    client = LLMClient()
    if not client.configured:
        return None
    try:
        data = client.complete_json(
            {
                "competitor": competitor,
                "title": title,
                "excerpt": excerpt[:2500],
                "return": {
                    "summary": "1-2 sentences",
                    "tag": "feature_parity|pricing|positioning|shipping",
                    "ask_eng": "one concrete eng/product question",
                },
            },
            system_prompt=(
                "You help a PM for Convin Sense — an AI phone / voice-agent platform "
                "(campaigns, outbound/inbound agents, KB, widgets). "
                "Ignore Auto QA / conversation-intelligence QA rivals. "
                "Return only JSON with keys summary, tag, ask_eng. Be terse."
            ),
            surface="competitor_radar",
            max_chars=4000,
            timeout=45,
        )
        if isinstance(data, dict):
            return data
    except Exception as exc:
        log.info("competitor llm enrich skipped: %s", exc)
    return None


def ensure_seeded(db: Session) -> None:
    """Seed Sense rivals; deactivate Auto QA leftovers."""
    for slug in AUTO_QA_SLUGS:
        row = db.query(Competitor).filter(Competitor.slug == slug).first()
        if row and row.active:
            row.active = False
            row.notes = ((row.notes or "") + " · deactivated: Auto QA, not Sense").strip(" ·")

    by_slug = {c.slug: c for c in db.query(Competitor).all()}
    for row in DEFAULT_COMPETITORS:
        existing = by_slug.get(row["slug"])
        if existing is None:
            db.add(
                Competitor(
                    slug=row["slug"],
                    name=row["name"],
                    aliases=row.get("aliases") or [],
                    website=row.get("website") or "",
                    changelog_url=row.get("changelog_url") or "",
                    blog_url=row.get("blog_url") or "",
                    pricing_url=row.get("pricing_url") or "",
                    g2_url=row.get("g2_url") or "",
                    notes=row.get("notes") or "",
                    active=True,
                    created_at=_now(),
                )
            )
        else:
            existing.active = True
            existing.name = row["name"]
            existing.aliases = row.get("aliases") or existing.aliases or []
            existing.website = row.get("website") or existing.website or ""
            existing.blog_url = row.get("blog_url") or existing.blog_url or ""
            existing.pricing_url = row.get("pricing_url") if "pricing_url" in row else (existing.pricing_url or "")
            existing.changelog_url = row.get("changelog_url") or existing.changelog_url or ""
            if row.get("notes"):
                existing.notes = row["notes"]

    existing_caps = {c.name for c in db.query(ParityCapability).all()}
    # Soft-retire Auto QA-oriented seed rows by renaming note; keep roadmap/jira rows.
    for cap in db.query(ParityCapability).filter(ParityCapability.source == "seed").all():
        lower = (cap.name or "").lower()
        if any(k in lower for k in ("auto qa", "scorecard", "coaching", "transcription & diarization", "agent assist")):
            if "Sense" not in (cap.notes or ""):
                cap.notes = "Legacy Auto QA seed — prefer Sense capability rows"
    for name in DEFAULT_CAPABILITIES:
        if name not in existing_caps:
            db.add(ParityCapability(name=name, source="seed", coverage={}, updated_at=_now()))

    existing_watch_urls = {w.url for w in db.query(MarketWatch).all()}
    for row in DEFAULT_WATCHES:
        if row["url"] in existing_watch_urls:
            continue
        # Avoid duplicate names when URL was migrated in place (e.g. Hacker News AI).
        if db.query(MarketWatch).filter(MarketWatch.name == row["name"], MarketWatch.category == row["category"]).first():
            continue
        db.add(
            MarketWatch(
                category=row["category"],
                name=row["name"],
                url=row["url"],
                notes=row.get("notes") or "",
                active=True,
                created_at=_now(),
            )
        )
        existing_watch_urls.add(row["url"])
    # Deactivate old Auto QA-oriented industry watches; refresh AI watch metadata for product-builder radar.
    for watch in db.query(MarketWatch).all():
        blob = f"{watch.name} {watch.notes}".lower()
        if "conversation intelligence" in blob or "ccaas / contact center news" in blob:
            watch.active = False
        if watch.category == "ai" and watch.name == "OpenAI capabilities":
            watch.name = "OpenAI"
            watch.notes = "Official model and product launches"
        # Replace flaky hnrss.org with Google News HN query for existing DBs.
        if watch.name == "Hacker News AI" and "hnrss.org" in (watch.url or ""):
            watch.url = "https://news.google.com/rss/search?q=site:news.ycombinator.com+(AI+OR+LLM+OR+Claude+OR+GPT+OR+agent)&hl=en-US&gl=US&ceid=US:en"
            watch.notes = "HN AI chatter via Google News (hnrss is flaky)"
        if "genesys cloud developer" in blob and "twilio" not in blob:
            # keep Genesys optional; Sense stack leans telephony — leave active unless clearly QA
            pass

    db.commit()


def competitor_out(row: Competitor) -> dict:
    return {
        "id": row.id,
        "slug": row.slug,
        "name": row.name,
        "aliases": row.aliases or [],
        "website": row.website or "",
        "changelog_url": row.changelog_url or "",
        "blog_url": row.blog_url or "",
        "pricing_url": row.pricing_url or "",
        "g2_url": row.g2_url or "",
        "notes": row.notes or "",
        "active": bool(row.active),
        "last_fetched_at": row.last_fetched_at.isoformat() if row.last_fetched_at else None,
    }


def clean_summary(text, fallback=""):
    value = unescape(unescape(text or ""))
    value = re.sub(r"<[^>]*>|<[^>]*$", " ", value)
    cleaned = re.sub(r"\s+", " ", value).strip()
    return fallback if fallback and len(cleaned) < 20 else cleaned or fallback


def signal_out(row: CompetitorSignal) -> dict:
    return {
        "id": row.id,
        "competitor_id": row.competitor_id,
        "competitor_name": row.competitor_name,
        "source": row.source,
        "title": row.title,
        "summary": clean_summary(row.summary, row.title),
        "url": row.url,
        "tag": row.tag,
        "ask_eng": row.ask_eng,
        "seen_at": row.seen_at.isoformat() if row.seen_at else None,
    }


def market_signal_out(row: MarketSignal) -> dict:
    return {
        "id": row.id,
        "watch_id": row.watch_id,
        "category": row.category,
        "source_name": row.source_name,
        "title": row.title,
        "summary": clean_summary(row.summary, row.title),
        "url": row.url,
        "affects_roadmap": row.affects_roadmap or "watch",
        "seen_at": row.seen_at.isoformat() if row.seen_at else None,
    }


def _record_competitor_signal(
    db: Session,
    competitor: Competitor,
    *,
    source: str,
    url: str,
    title: str,
    text: str,
    content_hash: str,
    use_llm: bool = False,
) -> CompetitorSignal | None:
    if not content_hash:
        return None
    existing = (
        db.query(CompetitorSignal)
        .filter(CompetitorSignal.competitor_id == competitor.id, CompetitorSignal.content_hash == content_hash)
        .first()
    )
    if existing:
        return None
    enrich = _llm_enrich(title, text, competitor.name) if use_llm else None
    tag = str((enrich or {}).get("tag") or _heuristic_tag(title, text))
    if tag not in TAG_KEYWORDS:
        tag = _heuristic_tag(title, text)
    summary = str((enrich or {}).get("summary") or text[:280] or title)
    ask = str((enrich or {}).get("ask_eng") or _ask_eng_line(tag, title))
    row = CompetitorSignal(
        competitor_id=competitor.id,
        competitor_name=competitor.name,
        source=source,
        title=(title or source)[:500],
        summary=summary[:2000],
        url=(url or "")[:500],
        tag=tag,
        ask_eng=ask[:1000],
        content_hash=content_hash,
        seen_at=_now(),
        raw_excerpt=(text or "")[:4000],
    )
    db.add(row)
    return row


def _fetch_competitor(db: Session, competitor: Competitor) -> dict:
    created = 0
    errors: list[str] = []
    sources = [
        ("changelog", competitor.changelog_url),
        ("blog", competitor.blog_url),
        ("pricing", competitor.pricing_url),
        ("g2", competitor.g2_url),
        ("website", competitor.website if not competitor.blog_url else ""),
    ]
    for source, url in sources:
        if not url:
            continue
        fetched = _fetch_public(url)
        if not fetched.get("ok"):
            errors.append(f"{source}: {fetched.get('error')}")
            continue
        rss_items = fetched.get("rss_items") or []
        if not rss_items and source in {"blog", "changelog"}:
            for article in (fetched.get("articles") or [])[:4]:
                detail = _fetch_public(article["url"])
                if detail.get("ok"):
                    rss_items.append({"title": detail.get("title") or article["title"], "url": article["url"], "summary": ((detail.get("description") or "") + "\n\n" + detail.get("text", "")).strip()})
        if rss_items:
            for item in rss_items[:8]:
                h = _hash_text(f"{item.get('title')}|{item.get('url')}|{item.get('summary')}")
                row = _record_competitor_signal(
                    db,
                    competitor,
                    source=source,
                    url=str(item.get("url") or url),
                    title=str(item.get("title") or ""),
                    text=str(item.get("summary") or ""),
                    content_hash=h,
                    use_llm=False,
                )
                if row:
                    created += 1
        else:
            row = _record_competitor_signal(
                db,
                competitor,
                source=source,
                url=url,
                title=str(fetched.get("title") or source),
                text=str(fetched.get("text") or ""),
                content_hash=str(fetched.get("hash") or ""),
                use_llm=False,
            )
            if row:
                created += 1
        if source == "pricing" and fetched.get("ok"):
            _pricing_snapshot(db, competitor, url, fetched)
    competitor.last_fetched_at = _now()
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        errors.append(f"commit: {exc}")
    return {"competitor": competitor.name, "signals_created": created, "errors": errors}


def _pricing_snapshot(db: Session, competitor: Competitor, url: str, fetched: dict) -> None:
    content_hash = str(fetched.get("hash") or "")
    excerpt = str(fetched.get("text") or "")[:3000]
    previous = (
        db.query(PricingSnapshot)
        .filter(PricingSnapshot.competitor_id == competitor.id)
        .order_by(PricingSnapshot.fetched_at.desc())
        .first()
    )
    changed = bool(previous and previous.content_hash and previous.content_hash != content_hash)
    note = ""
    if changed:
        note = "Public pricing page text changed vs last snapshot (plan names, limits, or AI add-on language may have moved)."
        _record_competitor_signal(
            db,
            competitor,
            source="pricing",
            url=url,
            title=f"{competitor.name} pricing page changed",
            text=note + "\n" + excerpt[:800],
            content_hash=_hash_text(f"pricing-change|{content_hash}"),
        )
    db.add(
        PricingSnapshot(
            competitor_id=competitor.id,
            competitor_name=competitor.name,
            url=url,
            content_hash=content_hash,
            excerpt=excerpt,
            changed=changed,
            change_note=note,
            fetched_at=_now(),
        )
    )


def _fetch_watch(db: Session, watch: MarketWatch) -> dict:
    fetched = _fetch_public(watch.url)
    created = 0
    if not fetched.get("ok"):
        watch.last_fetched_at = _now()
        db.commit()
        return {"watch": watch.name, "signals_created": 0, "error": fetched.get("error")}
    items = fetched.get("rss_items") or []
    if not items:
        items = [
            {
                "title": fetched.get("title") or watch.name,
                "url": watch.url,
                "summary": (fetched.get("text") or "")[:400],
            }
        ]
    for item in items[:10]:
        title = str(item.get("title") or "")[:500]
        summary = str(item.get("summary") or "")[:2000]
        url = str(item.get("url") or watch.url)[:500]
        publisher = str(item.get("publisher") or "")
        publisher_url = str(item.get("publisher_url") or "")
        if is_blocked_news(title, summary, publisher_url or url, publisher):
            continue
        h = _hash_text(f"{watch.id}|{title}|{url}")
        exists = db.query(MarketSignal).filter(MarketSignal.content_hash == h).first()
        if exists:
            continue
        affects = _guess_affects(watch.category, title, summary)
        db.add(
            MarketSignal(
                watch_id=watch.id,
                category=watch.category,
                source_name=watch.name,
                title=title,
                summary=summary,
                url=url,
                affects_roadmap=affects,
                content_hash=h,
                seen_at=_now(),
                raw_excerpt=summary[:2000],
            )
        )
        created += 1
    watch.last_fetched_at = _now()
    db.commit()
    return {"watch": watch.name, "signals_created": created, "error": ""}


def _guess_affects(category: str, title: str, summary: str) -> str:
    blob = f"{title} {summary}".lower()
    if category == "compliance":
        keys = ("dpdp", "consent", "recording", "residency", "gdpr", "ccpa", "tcpa", "privacy")
        return "yes" if any(k in blob for k in keys) else "watch"
    if category == "integration":
        keys = ("breaking", "deprecate", "api", "webhook", "oauth", "version", "migration")
        return "yes" if any(k in blob for k in keys) else "watch"
    if category == "ai":
        keys = ("model", "agent", "voice", "speech", "github", "open source", "hermes", "openclaw", "mcp", "llm")
        return "watch" if any(k in blob for k in keys) else "no"
    keys = ("contact center", "ccaas", "conversation ai", "agent assist", "transcription", "dialer")
    return "watch" if any(k in blob for k in keys) else "no"


def sync_capabilities_from_roadmap(db: Session) -> int:
    roadmap = db.query(Roadmap).order_by(Roadmap.updated_at.desc()).first()
    added = 0
    existing_names = {c.name for c in db.query(ParityCapability).all()}
    epics = list(roadmap.epics or []) if roadmap else []

    def _add(name: str, source: str, epic_key: str = "") -> None:
        nonlocal added
        title = (name or "").strip()
        if not title or title in existing_names:
            return
        existing_names.add(title)
        db.add(
            ParityCapability(
                name=title[:256],
                source=source,
                epic_key=(epic_key or "")[:32],
                coverage={},
                updated_at=_now(),
            )
        )
        added += 1

    for epic in epics:
        if not isinstance(epic, dict):
            continue
        _add(str(epic.get("title") or ""), "roadmap", str(epic.get("key") or ""))
    for issue in (
        db.query(JiraIssue)
        .filter(JiraIssue.issue_key.like("AC-%"), JiraIssue.issue_type.ilike("%epic%"))
        .limit(40)
        .all()
    ):
        _add(issue.summary or "", "jira", issue.issue_key)
    if added:
        try:
            db.commit()
        except Exception:
            db.rollback()
            added = 0
    return added


def refresh_all(db: Session) -> dict:
    ensure_seeded(db)
    try:
        sync_capabilities_from_roadmap(db)
    except Exception as exc:
        log.warning("parity sync skipped: %s", exc)
        db.rollback()
    competitor_results = []
    for row in db.query(Competitor).filter(Competitor.active.is_(True)).all():
        try:
            competitor_results.append(_fetch_competitor(db, row))
        except Exception as exc:
            db.rollback()
            competitor_results.append({"competitor": row.name, "signals_created": 0, "errors": [str(exc)[:200]]})
    market_results = []
    for watch in db.query(MarketWatch).filter(MarketWatch.active.is_(True)).all():
        try:
            market_results.append(_fetch_watch(db, watch))
        except Exception as exc:
            db.rollback()
            market_results.append({"watch": watch.name, "signals_created": 0, "error": str(exc)[:200]})
    try:
        rebuild_parity_suggestions(db)
    except Exception as exc:
        log.warning("parity suggestions skipped: %s", exc)
        db.rollback()
    return {
        "ok": True,
        "competitors": competitor_results,
        "market": market_results,
        "refreshed_at": _now().isoformat(),
    }


def rebuild_parity_suggestions(db: Session) -> list[dict]:
    """Mark coverage hints from recent competitor signals; suggest gaps without matching epic."""
    ensure_seeded(db)
    competitors = db.query(Competitor).filter(Competitor.active.is_(True)).all()
    caps = db.query(ParityCapability).all()
    recent = (
        db.query(CompetitorSignal)
        .filter(CompetitorSignal.tag.in_(["feature_parity", "shipping"]))
        .order_by(CompetitorSignal.seen_at.desc())
        .limit(80)
        .all()
    )
    suggestions: list[dict] = []
    for signal in recent:
        title_l = (signal.title or "").lower()
        matched_cap = None
        for cap in caps:
            tokens = [t for t in re.split(r"[^a-z0-9]+", (cap.name or "").lower()) if len(t) > 3]
            if tokens and sum(1 for t in tokens if t in title_l) >= max(1, min(2, len(tokens) // 2)):
                matched_cap = cap
                break
        rival = next((c for c in competitors if c.id == signal.competitor_id), None)
        slug = rival.slug if rival else _slugify(signal.competitor_name)
        if matched_cap:
            coverage = dict(matched_cap.coverage or {})
            coverage[slug] = coverage.get(slug) or "partial"
            matched_cap.coverage = coverage
            matched_cap.updated_at = _now()
        else:
            has_epic = bool(
                db.query(JiraIssue)
                .filter(
                    JiraIssue.issue_key.like("AC-%"),
                    JiraIssue.summary.ilike(f"%{(signal.title or '')[:40]}%"),
                )
                .first()
            )
            if not has_epic:
                suggestions.append(
                    {
                        "signal_id": signal.id,
                        "competitor": signal.competitor_name,
                        "title": signal.title,
                        "url": signal.url,
                        "reason": "Rival signal with no matching Sense capability/epic",
                        "ask_eng": signal.ask_eng,
                    }
                )
    db.commit()
    return suggestions[:40]


def digest(db: Session, days: int = 14) -> dict:
    ensure_seeded(db)
    signals = (
        db.query(CompetitorSignal)
        .order_by(CompetitorSignal.seen_at.desc())
        .limit(100)
        .all()
    )
    shipped = [signal_out(s) for s in signals if s.tag in {"shipping", "feature_parity"}][:30]
    messaging = [signal_out(s) for s in signals if s.tag == "positioning"][:20]
    pricing = [signal_out(s) for s in signals if s.tag == "pricing"][:20]
    ask_eng = [
        {"competitor": s.competitor_name, "ask_eng": s.ask_eng, "title": s.title, "id": s.id}
        for s in signals
        if s.ask_eng
    ][:25]
    return {
        "shipped": shipped,
        "messaging": messaging,
        "pricing": pricing,
        "ask_eng": ask_eng,
        "generated_at": _now().isoformat(),
    }


def parity_matrix(db: Session) -> dict:
    ensure_seeded(db)
    sync_capabilities_from_roadmap(db)
    competitors = [competitor_out(c) for c in db.query(Competitor).filter(Competitor.active.is_(True)).all()]
    rows = []
    for cap in db.query(ParityCapability).order_by(ParityCapability.name.asc()).all():
        rows.append(
            {
                "id": cap.id,
                "name": cap.name,
                "source": cap.source,
                "epic_key": cap.epic_key,
                "coverage": cap.coverage or {},
                "notes": cap.notes or "",
            }
        )
    gaps = rebuild_parity_suggestions(db)
    return {"competitors": competitors, "capabilities": rows, "gap_suggestions": gaps}


def pricing_history(db: Session) -> dict:
    ensure_seeded(db)
    snaps = db.query(PricingSnapshot).order_by(PricingSnapshot.fetched_at.desc()).limit(60).all()
    return {
        "snapshots": [
            {
                "id": s.id,
                "competitor_id": s.competitor_id,
                "competitor_name": s.competitor_name,
                "url": s.url,
                "changed": bool(s.changed),
                "change_note": s.change_note,
                "excerpt": (s.excerpt or "")[:500],
                "fetched_at": s.fetched_at.isoformat() if s.fetched_at else None,
            }
            for s in snaps
        ]
    }


def market_overview(db: Session, category: str | None = None) -> dict:
    ensure_seeded(db)
    q = db.query(MarketSignal).order_by(MarketSignal.seen_at.desc())
    if category:
        q = q.filter(MarketSignal.category == category)
    signals = q.limit(80).all()
    watches = db.query(MarketWatch).filter(MarketWatch.active.is_(True)).all()
    if category:
        watches = [w for w in watches if w.category == category]
    return {
        "watches": [
            {
                "id": w.id,
                "category": w.category,
                "name": w.name,
                "url": w.url,
                "notes": w.notes,
                "last_fetched_at": w.last_fetched_at.isoformat() if w.last_fetched_at else None,
            }
            for w in watches
        ],
        "signals": [market_signal_out(s) for s in signals],
    }


def upsert_competitor(db: Session, body: dict, competitor_id: int | None = None) -> Competitor:
    ensure_seeded(db)
    name = str(body.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    slug = str(body.get("slug") or _slugify(name)).strip() or _slugify(name)
    if competitor_id:
        row = db.query(Competitor).filter(Competitor.id == competitor_id).first()
        if not row:
            raise ValueError("competitor not found")
    else:
        row = db.query(Competitor).filter(Competitor.slug == slug).first()
        if row is None:
            row = Competitor(slug=slug, created_at=_now())
            db.add(row)
    row.name = name
    row.slug = slug
    row.aliases = body.get("aliases") if isinstance(body.get("aliases"), list) else (row.aliases or [])
    for field in ("website", "changelog_url", "blog_url", "pricing_url", "g2_url", "notes"):
        if field in body and body[field] is not None:
            setattr(row, field, str(body[field] or "")[:500 if field != "notes" else 4000])
    if "active" in body:
        row.active = bool(body["active"])
    db.commit()
    db.refresh(row)
    return row


def set_market_affects(db: Session, signal_id: int, value: str) -> MarketSignal:
    row = db.query(MarketSignal).filter(MarketSignal.id == signal_id).first()
    if not row:
        raise ValueError("signal not found")
    if value not in {"yes", "no", "watch"}:
        raise ValueError("affects_roadmap must be yes|no|watch")
    row.affects_roadmap = value
    db.commit()
    db.refresh(row)
    return row


def set_parity_cell(db: Session, capability_id: int, competitor_slug: str, level: str) -> ParityCapability:
    row = db.query(ParityCapability).filter(ParityCapability.id == capability_id).first()
    if not row:
        raise ValueError("capability not found")
    if level not in {"strong", "partial", "gap", "unknown", ""}:
        raise ValueError("invalid coverage level")
    coverage = dict(row.coverage or {})
    if level:
        coverage[competitor_slug] = level
    elif competitor_slug in coverage:
        del coverage[competitor_slug]
    row.coverage = coverage
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row
