"""Read-only release projection. No detection state, workers, or publishing writes."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote, urlsplit

from sqlalchemy.orm import Session

from app.models import MarketingCampaign, MarketingFeature, ReleaseJob, ReleasePack
from app.services.feature_artifacts import ARTIFACT_DIR
from app.services.marketing import CAMPAIGN_DIR
from app.services.release_detect import detect_release_merges, release_re
from app.storage import from_stored


def safe_url(value) -> str:
    text = str(value or "").strip()
    try:
        parsed = urlsplit(text)
    except ValueError:
        return ""
    return text if parsed.scheme in {"https", "http"} and parsed.netloc else ""


def _records(folder: Path):
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                yield path, data
        except (OSError, ValueError):
            continue


def release_workspace(db: Session) -> dict:
    warnings = []
    try:
        merges = detect_release_merges(lookback=300, read_only=True)
    except (OSError, RuntimeError):
        merges = None
    if merges is None:
        warnings.append("Local merge history is unavailable. Showing saved release records; refresh the codebase to recover history.")
    jobs = db.query(ReleaseJob).order_by(ReleaseJob.id.desc()).all()
    packs = db.query(ReleasePack).order_by(ReleasePack.id.desc()).all()
    features = db.query(MarketingFeature).order_by(MarketingFeature.id.desc()).all()
    campaigns = db.query(MarketingCampaign).order_by(MarketingCampaign.id.desc()).all()
    releases = {}
    release_pattern = release_re()
    for merge in merges or []:
        if not release_pattern.fullmatch(merge.get("branch", "")):
            continue
        sha = merge["sha"]
        releases[sha] = dict(id=sha, branch=merge["branch"], sha=sha,
                             merged_at=merge.get("merged_at", ""), merge_verified=True,
                             source_shas=list(dict.fromkeys([sha] + (merge.get("parents") or [])[1:])) )
    for job in jobs:
        matches = [r for r in releases.values() if r["branch"] == job.branch and len(job.sha) >= 7 and r["sha"].startswith(job.sha)]
        if release_pattern.fullmatch(job.branch) and job.sha not in releases and len(matches) != 1:
            releases[job.sha] = dict(id=job.sha, branch=job.branch, sha=job.sha,
                                     merged_at=job.merged_at, merge_verified=False, source_shas=[job.sha])
    by_branch = defaultdict(list)
    for row in releases.values():
        by_branch[row["branch"]].append(row)
        row.update(changes=[], features=[], assessments=[], campaigns=[], artifacts=[], comms=[], jobs=[])

    def match(branch, sha="", *, branch_fallback=False):
        candidates = by_branch.get(branch, [])
        if sha:
            matched = [r for r in candidates if any(
                len(sha) >= 7 and (s.startswith(sha) or sha.startswith(s)) for s in r["source_shas"] if len(s) >= 7)]
            return matched[0] if len(matched) == 1 else None
        return candidates[0] if branch_fallback and len(candidates) == 1 else None

    def evidence_release(evidence):
        found = {}
        for item in evidence if isinstance(evidence, list) else []:
            if not isinstance(item, dict):
                continue
            row = match(item.get("branch"), item.get("sha", ""))
            if row:
                found[row["id"]] = row
        return list(found.values())

    def add_artifact(row, *, name, url, source, association="commit", drive_url=""):
        if url and not any(a["url"] == url for a in row["artifacts"]):
            row["artifacts"].append(dict(name=name, url=url, source=source,
                                         association=association, drive_url=safe_url(drive_url)))

    pack_links = {}
    for job in jobs:
        row = match(job.branch, job.sha)
        if not row:
            continue
        row["jobs"].append(dict(id=job.id, status=job.status, error=job.error_detail or "",
                                url=f"/comms?release_job={job.id}", pack_id=job.pack_id))
        if job.pack_id:
            pack_links.setdefault(job.pack_id, (row, job))
        extraction = job.extraction if isinstance(job.extraction, dict) else {}
        for feature in extraction.get("features") or []:
            if isinstance(feature, dict):
                row["changes"].append({k: str(feature.get(k) or "") for k in ("name", "what", "confidence", "evidence")})
        for internal in extraction.get("internal") or []:
            row["changes"].append(dict(name=str(internal), what="", confidence="", evidence="", internal=True))
        stored_pdf = from_stored(job.pdf_path)
        if stored_pdf and stored_pdf.is_file():
            add_artifact(row, name="Release notes PDF", url=f"/api/comms/release-jobs/{job.id}/pdf", source="Comms")
        for item in extraction.get("artifacts") or []:
            if isinstance(item, dict):
                add_artifact(row, name=item.get("feature") or "Feature artifact", url=safe_url(item.get("url")), source="Release")

    unlinked = dict(features=0, comms=0, artifacts=0)
    feature_links = defaultdict(list)
    for feature in features:
        rows = evidence_release(feature.evidence)
        if not rows:
            unlinked["features"] += 1
        decision = feature.decision if isinstance(feature.decision, dict) else {}
        buyer = feature.status != "dismissed" and decision.get("verdict") == "approve" and decision.get("sellable") is not False
        for row in rows:
            feature_links[feature.id].append(row)
            row["features"].append(dict(id=feature.id, name=feature.name, summary=feature.summary or feature.description,
                                        module=feature.module, status=feature.status, buyer_facing=buyer,
                                        verdict=decision.get("verdict") or "unassessed", rationale=decision.get("rationale") or "",
                                        url=f"/marketing?feature={feature.id}"))

    # Discovery keeps rejected/internal assessments outside the working mastersheet.
    for _, audit in _records(CAMPAIGN_DIR / "discovery"):
        row = match(audit.get("release"), audit.get("sha", ""))
        if not row:
            continue
        for item in audit.get("assessments") or []:
            if not isinstance(item, dict):
                continue
            decision = item.get("decision") or {}
            assessment = dict(name=item.get("name") or "Unnamed change", summary=item.get("summary") or item.get("description") or "",
                              verdict=decision.get("verdict") or "unassessed", rationale=decision.get("rationale") or "")
            if assessment not in row["assessments"]:
                row["assessments"].append(assessment)

    for campaign in campaigns:
        snapshot = campaign.feature_snapshot if isinstance(campaign.feature_snapshot, dict) else {}
        direct = evidence_release(snapshot.get("evidence"))
        # A feature's older campaign is useful context, but isn't a release-specific artifact.
        for row in direct or feature_links.get(campaign.feature_id, []):
            association = "commit" if direct else "feature"
            row["campaigns"].append(dict(id=campaign.id, name=snapshot.get("name") or "Campaign",
                                         status=campaign.status, error=campaign.error or "", association=association,
                                         url=f"/marketing?campaign={campaign.id}"))
            for asset in campaign.assets or []:
                if isinstance(asset, dict) and asset.get("filename"):
                    name = asset["filename"]
                    local = CAMPAIGN_DIR / str(campaign.id) / name
                    if Path(name).name != name:
                        continue
                    url = f"/api/marketing/campaigns/{campaign.id}/files/{quote(name, safe='')}" if local.is_file() else safe_url(asset.get("drive_url"))
                    add_artifact(row, name=name, url=url, source="Marketing", association=association, drive_url=asset.get("drive_url"))

    for pack in packs:
        linked = pack_links.get(pack.id)
        row = linked[0] if linked else match(pack.branch, pack.commit_sha)
        association = "commit"
        if row is None and not pack.commit_sha:
            row = match(pack.branch, branch_fallback=True)
            association = "branch"
        if row is None:
            unlinked["comms"] += 1
            continue
        job = linked[1] if linked else None
        # ReleasePack has no publication state of its own. Only an explicit job can prove approval.
        state = "published" if job and job.status == "uploaded" and job.drive_file_id != "dryrun" else "approved_locally" if job and job.status == "uploaded" else "draft"
        row["comms"].append(dict(id=pack.id, title=pack.title or "Untitled draft", kind=pack.kind,
                                 state=state, association=association, url=f"/comms?pack={pack.id}",
                                 review_url=f"/comms?release_job={job.id}" if job else ""))
        for artifact in pack.artifacts or []:
            if isinstance(artifact, dict):
                add_artifact(row, name=artifact.get("feature") or "Feature artifact", url=safe_url(artifact.get("url")), source="Comms")

    for path, meta in _records(ARTIFACT_DIR):
        pdf = path.with_suffix(".pdf")
        drive_url = safe_url(meta.get("url") or meta.get("drive_url"))
        local = pdf.is_file()
        if not local and not drive_url:
            continue
        sha = meta.get("sha") or meta.get("commit_sha") or ""
        row = match(meta.get("branch"), sha, branch_fallback=not sha)
        if row is None:
            unlinked["artifacts"] += 1
            continue
        add_artifact(row, name=meta.get("title") or path.stem,
                     url=f"/api/artifacts/files/{quote(pdf.name, safe='')}" if local else drive_url, source="Artifacts",
                     association="commit" if sha else "branch", drive_url=drive_url)

    for row in releases.values():
        row.pop("source_shas")
        failed = any(j["status"].startswith("error:") for j in row["jobs"]) or any(c["status"] in {"failed", "partial"} for c in row["campaigns"])
        awaiting = any(j["status"] == "pending_review" for j in row["jobs"])
        row["state"] = "needs_attention" if failed else "awaiting_review" if awaiting else "drafts" if any(c["state"] == "draft" for c in row["comms"]) else "tracked"
        row["counts"] = dict(buyer_facing=sum(f["buyer_facing"] for f in row["features"]),
                              artifacts=len(row["artifacts"]), drafts=sum(c["state"] == "draft" for c in row["comms"]))
    return dict(releases=sorted(releases.values(), key=lambda r: (r["merged_at"] or r["branch"], r["sha"]), reverse=True),
                warnings=warnings, unlinked=unlinked, history_limit=300)
