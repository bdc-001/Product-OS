import re

from app.config import settings
from app.services.people import extract_mention_ids, is_pm_sender, is_pm_tagged
from app.services.team import product_internal_chat_id, PRODUCT_INTERNAL_UNIQUE

TICKET_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")

BLOCKER_PATTERNS = (
    r"\bblocked\b",
    r"\bblocking\b",
    r"\bstuck\b",
    r"\bwaiting for\b",
    r"\bcan't proceed\b",
    r"\bcannot proceed\b",
    r"\bcant proceed\b",
    r"\bdependency\b",
    r"\bstill pending\b",
    r"\bpending on\b",
)
DECISION_PATTERNS = (
    r"\bdecided\b",
    r"\bagreed\b",
    r"\bapproved\b",
    r"\blaunch\b",
    r"\bship(?:ping|ped)?\b",
)
NOISY_FIELDS = {
    "labels",
    "label",
    "rank",
    "sprint",
    "timeestimate",
    "timespent",
    "worklog",
    "flagged",
}


def _keywords() -> list[str]:
    return [k.strip().lower() for k in settings.project_keywords.split(",") if k.strip()]


def extract_ticket_keys(text: str) -> list[str]:
    return list(dict.fromkeys(TICKET_RE.findall(text or "")))


def is_wallet_chat(name: str) -> bool:
    n = (name or "").lower().lstrip("#").strip()
    compact = n.replace(" ", "").replace("-", "").replace("_", "")
    return compact.startswith("wallet") or "walletbalance" in compact or "walletrecharge" in compact


def is_product_internal_chat(name: str = "", chat_id: str = "") -> bool:
    if (chat_id or "") == product_internal_chat_id():
        return True
    compact = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    return compact == PRODUCT_INTERNAL_UNIQUE or compact.endswith("productinternal")


REPORT_TYPE_NEEDLES = ("product/report requirement", "report requirement", "product requirement")


def classify_issue(issue_type: str = "", issue_key: str = "") -> str:
    """bug | report | task. Product/Report Requirement is its own PS type."""
    t = (issue_type or "").strip().lower()
    if any(needle in t for needle in REPORT_TYPE_NEEDLES):
        return "report"
    if t in {"bug", "defect", "incident"}:
        return "bug"
    if t:
        return "task"
    if (issue_key or "").upper().startswith("PS-"):
        return "bug"
    return "task"


def is_bug_ticket(key: str, issue_type: str = "") -> bool:
    return classify_issue(issue_type, key) == "bug"


def is_report_ticket(key: str, issue_type: str = "") -> bool:
    return classify_issue(issue_type, key) == "report"


JIRA_LINK_RE = re.compile(r"https?://\S*atlassian\.net/browse/[A-Z][A-Z0-9]+-\d+\S*", re.I)
MD_JIRA_RE = re.compile(r"\[([A-Z][A-Z0-9]+-\d+)\]\(https?://[^)]+\)", re.I)


def strip_jira_links(text: str) -> str:
    cleaned = MD_JIRA_RE.sub(r"\1", text or "")
    cleaned = JIRA_LINK_RE.sub("", cleaned)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def classify_message(text: str, chat_name: str = "", sender_id: str = "", sender: str = "") -> dict:
    lower = (text or "").lower()
    reasons: list[str] = []
    keys = extract_ticket_keys(text)
    if keys:
        reasons.append("jira_ref")
    if is_pm_tagged(text):
        reasons.append("pm_mention")
    if is_pm_sender(sender_id, sender):
        reasons.append("pm_conversation")
    if is_wallet_chat(chat_name):
        reasons.append("wallet_request")
    if is_product_internal_chat(chat_name) and is_pm_sender(sender_id, sender):
        reasons.append("weekly_plan")
    if any(keyword in lower for keyword in _keywords()):
        reasons.append("project_keyword")
    if any(re.search(pattern, lower) for pattern in BLOCKER_PATTERNS):
        reasons.append("blocker_signal")
    if any(re.search(pattern, lower) for pattern in DECISION_PATTERNS):
        reasons.append("decision_signal")
    return {
        "relevant": bool(reasons),
        "reasons": reasons,
        "ticket_keys": keys,
        "mention_ids": extract_mention_ids(text),
        "pm_tagged": is_pm_tagged(text),
    }


def is_noisy_field(field: str) -> bool:
    return (field or "").lower() in NOISY_FIELDS
