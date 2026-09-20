"""Extract customer-visible features from a scoped git diff. Evidence only."""

from __future__ import annotations

import logging
from pathlib import Path

from app.clients.llm import LLMJsonError, chat_json
from app.services.codebase import _git, codebase_root
from app.services.prompts import with_preamble

log = logging.getLogger(__name__)

EXTRACT_PROMPT = with_preamble(
    """You are extracting shipped product changes from a git diff for Convin's go_services.
Input: merge commit subjects (PR titles), a diff --stat, README diffs, and an optional live summary.

A feature is customer/CSM-visible: a new capability, changed flow, new screen/
table/report, or new config users touch.
NOT features: refactors, dependency bumps, CI changes, tests, renames, logging,
internal config. Group those in "internal" as one line each.

Rules:
- Evidence only. Every feature must trace to a PR subject, changed file path,
  or README text in the payload. Quote the evidence in "evidence".
- Never invent UI labels, table names, or settings not present in the payload.
- confidence: HIGH = explicit in a PR title or README; MEDIUM = clear from file
  paths and diffs; LOW = inferred. For LOW, say what's missing in "gap".
- Max 8 features. Merge near-duplicates.
- If nothing customer-visible shipped, return an empty features list — do not pad.

Return JSON:
{"features": [
  {"name": "...",
   "what": "...",
   "why": "...",
   "modules": ["..."],
   "confidence": "HIGH|MEDIUM|LOW",
   "evidence": "...",
   "gap": ""}],
 "internal": ["..."],
 "not_enough_evidence": ""}
"""
)


def default_checked(confidence: str) -> bool:
    return (confidence or "").upper() in {"HIGH", "MEDIUM"}


def features_to_features_in_short(result: dict, checked: list[str] | None = None) -> str:
    lines = []
    wanted = {name.strip() for name in (checked or []) if str(name).strip()} if checked is not None else None
    for item in result.get("features") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        what = str(item.get("what") or "").strip()
        if not name:
            continue
        if wanted is not None and name not in wanted:
            continue
        line = f"{name} — {what}" if what else name
        if (item.get("confidence") or "").upper() == "LOW":
            line += "  [unverified]"
        lines.append(line)
    return "\n".join(lines)


def gather_evidence(repo: Path, base_sha: str, head_sha: str) -> dict:
    def git(*args: str) -> str:
        proc = _git(repo, *args, timeout=90)
        return proc.stdout if proc.returncode == 0 else ""

    if not base_sha or not head_sha:
        return {"merge_subjects": [], "diff_stat": "", "readme_diffs": []}
    spec = f"{base_sha}..{head_sha}"
    subjects = [line.strip() for line in git("log", spec, "--merges", "--format=%s").splitlines() if line.strip()]
    if not subjects:
        subjects = [line.strip() for line in git("log", spec, "--format=%s", "-30").splitlines() if line.strip()]
    stat = git("diff", "--stat", spec)
    readme_hits = []
    for line in stat.splitlines():
        path = line.split("|")[0].strip()
        if not path or ("README" not in path and "docs/" not in path.lower()):
            continue
        diff = git("diff", spec, "--", path)[:4000]
        readme_hits.append({"path": path, "diff": diff})
        if len(readme_hits) >= 5:
            break
    return {"merge_subjects": subjects, "diff_stat": stat[:8000], "readme_diffs": readme_hits}


def _clean_extraction(raw: dict) -> dict:
    features = []
    for item in (raw.get("features") or [])[:8]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()[:120]
        if not name:
            continue
        conf = str(item.get("confidence") or "MEDIUM").upper()
        if conf not in {"HIGH", "MEDIUM", "LOW"}:
            conf = "MEDIUM"
        modules = item.get("modules") if isinstance(item.get("modules"), list) else []
        features.append(
            {
                "name": name,
                "what": str(item.get("what") or "").strip()[:240],
                "why": str(item.get("why") or "").strip()[:240],
                "modules": [str(m)[:120] for m in modules[:6] if m],
                "confidence": conf,
                "evidence": str(item.get("evidence") or "").strip()[:400],
                "gap": str(item.get("gap") or "").strip()[:240],
            }
        )
    internal = [str(row).strip()[:200] for row in (raw.get("internal") or []) if str(row).strip()][:12]
    return {"features": features, "internal": internal, "not_enough_evidence": str(raw.get("not_enough_evidence") or "")[:300]}


def extract_features(base_sha: str, head_sha: str, extra: dict | None = None) -> dict:
    repo = codebase_root()
    evidence = gather_evidence(repo, base_sha, head_sha)
    if extra:
        evidence.update({k: v for k, v in extra.items() if v})
    try:
        raw = chat_json(
            surface="feature_extract",
            system=EXTRACT_PROMPT,
            payload=evidence,
            temperature=0.2,
            max_chars=14000,
        )
        return _clean_extraction(raw)
    except LLMJsonError:
        log.exception("feature extract LLM failed")
        return _clean_extraction({"features": [], "internal": ["Feature extract LLM failed; list features in Comms."]})
    except Exception:
        log.exception("feature extract failed")
        return _clean_extraction({"features": [], "internal": ["Could not extract features from the diff."]})
