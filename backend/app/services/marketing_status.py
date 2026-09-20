"""Feature-level content inventory, independent of campaign pagination and sheet tags."""
from app.services.marketing_manager import FORMATS, PENDING


def content_inventory(feature, campaigns):
    inventory = {}
    for key in FORMATS:
        candidates = []
        for campaign in campaigns:
            if campaign.feature_id != feature.id:
                continue
            content = campaign.content or {}
            decision = content.get("decision") or {}
            state = content.get("formats", {}).get(key, {})
            selected = key in content.get("requested_formats", []) or any(a["format"] == key for a in decision.get("assignments", []))
            if not state and not selected:
                continue
            status = state.get("status") or (campaign.status if campaign.status in PENDING else
                     "needs_evidence" if campaign.status == "deferred" else
                     "not_selected" if campaign.status in {"skipped", "cancelled"} else "failed")
            if status == "rendering" and campaign.status in {"failed", "partial"}:
                status = "failed"
            candidates.append((campaign, {
                "status": status, "campaign_id": campaign.id, "revision": campaign.feature_revision,
                "stale": campaign.feature_revision != feature.revision,
                "error": state.get("error") or (campaign.error if status == "failed" else ""),
                "reason": decision.get("rationale", ""),
                "assets": [a for a in campaign.assets or [] if a.get("channel") == key],
                "delivery": "uploaded" if any(a.get("file_id") for a in campaign.assets or [] if a.get("channel") == key) else "local",
            }))
        if candidates:
            # Current revision first, then a completed asset, then the most recent request.
            _, inventory[key] = max(candidates, key=lambda pair: (
                pair[0].feature_revision == feature.revision, pair[1]["status"] == "completed", pair[0].id))
        else:
            reason = (feature.decision or {}).get("omitted_formats", {}).get(key, "")
            inventory[key] = {"status": "not_selected" if reason else "not_started", "reason": reason, "assets": [], "stale": False}
    return inventory
