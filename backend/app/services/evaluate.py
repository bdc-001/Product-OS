from sqlalchemy.orm import Session

from app.models import Evaluation, Insight, Standup
from app.services.prompts import ACTION_TYPES, parse_standup_items


def evaluate_standup(db: Session, standup: Standup, insights: list[Insight]) -> Evaluation:
    high_insights = [i for i in insights if i.confidence == "HIGH"]
    blockers = [i for i in insights if i.type == "blocker"]
    risks = [i for i in insights if i.type == "risk"]
    items = (
        (standup.needs_attention or [])
        + (standup.at_risk or [])
        + (standup.completed or [])
        + (standup.team_signals or [])
        + (standup.todays_actions or [])
        + (standup.bugs or [])
        + (standup.tasks or [])
        + (standup.wallet_requests or [])
        + (standup.long_pending or [])
        + (getattr(standup, "week_actions", None) or [])
    )
    grounded = [i for i in items if i.get("sources") and i.get("why")]
    with_actions = [i for i in items if i.get("action")]
    invented = [i for i in items if not i.get("sources")]
    noisy = [i for i in items if (i.get("confidence") or "").upper() == "LOW"]

    signal = _score(len([i for i in items if i.get("issue_key") or i.get("title")]), max(len(high_insights), 1), 92)
    if blockers and not standup.needs_attention:
        signal = min(signal, 55)
    prioritization = 88 if (standup.needs_attention or not blockers) else 60
    grounding = 96 if items and len(grounded) / max(len(items), 1) >= 0.9 else 70
    if not items:
        grounding = 80
    actionability = 82 if len(getattr(standup, "week_actions", None) or standup.todays_actions or []) >= min(2, len(insights) or 2) else 64
    completeness = 88
    if blockers and not any("block" in (x.get("title") or "").lower() for x in (standup.needs_attention or [])):
        completeness = 62
    if risks and not standup.at_risk:
        completeness = min(completeness, 68)
    noise_score = 90 if len(noisy) <= 1 else 72
    hallucination = 95 if not invented else max(40, 95 - 15 * len(invented))

    overall = round(
        (
            signal * 0.18
            + prioritization * 0.14
            + grounding * 0.20
            + actionability * 0.16
            + completeness * 0.16
            + noise_score * 0.08
            + hallucination * 0.08
        ),
        1,
    )
    evaluation = Evaluation(
        standup_id=standup.id,
        overall=overall,
        signal_detection=signal,
        prioritization=prioritization,
        grounding=grounding,
        actionability=actionability,
        completeness=completeness,
        noise=noise_score,
        hallucination=hallucination,
        notes={
            "insight_count": len(insights),
            "item_count": len(items),
            "grounded_ratio": round(len(grounded) / max(len(items), 1), 2),
            "action_count": len(with_actions),
            "ungrounded": len(invented),
            "golden": compare_to_golden(standup, insights, items),
        },
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


def compare_to_golden(standup: Standup, insights: list[Insight], items: list) -> dict:
    blockers = [i for i in insights if i.type == "blocker"]
    drift = []
    if blockers and not (standup.needs_attention or []):
        drift.append("blocker insights missing from needs_attention")
    week = getattr(standup, "week_actions", None) or []
    if any(i.type == "blocker" for i in insights) and not any("block" in (x.get("title") or "").lower() or x.get("kind") == "blocker" for x in week + (standup.needs_attention or [])):
        drift.append("no blocker card on the briefing")
    ungrounded = [i for i in items if not i.get("sources")]
    if items and len(ungrounded) / len(items) > 0.25:
        drift.append("ungrounded item ratio above 25%")
    bad_type = [
        i.get("title")
        for i in items
        if i.get("action_type") and str(i.get("action_type")).lower() not in ACTION_TYPES
    ]
    if bad_type:
        drift.append(f"action_type not in enum ({len(bad_type)} items)")
    if (standup.todays_actions or []) and len(standup.todays_actions) > 6:
        drift.append("todays_actions over cap of 6")
    bad_shape = 0
    for item in (standup.needs_attention or [])[:12]:
        if item.get("title") and not parse_standup_items([item], limit=1):
            bad_shape += 1
    if bad_shape:
        drift.append(f"{bad_shape} needs_attention items failed schema")
    return {"ok": not drift, "drift": drift}


def _score(found: int, expected: int, target: int) -> float:
    if expected <= 0:
        return float(target)
    return round(min(100, target * min(found / expected, 1.2)), 1)
