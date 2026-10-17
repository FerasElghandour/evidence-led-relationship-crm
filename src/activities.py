"""Public activity records and the LinkedIn access-gate calculation.

LinkedIn activity is a CHANNEL-ACCESS condition, not part of company ICP fit
(spec §7) — this module only ever touches PublicActivity and
Person.linkedin_access_fit, never Company.company_icp_fit.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .enums import EvidenceClassification, FitLevel
from .models import Company, Evidence, Person, PublicActivity
from .schemas import ActivityIn

# Topics that count as commercially relevant per spec §7.
COMMERCIAL_TOPICS = {
    "growth",
    "sales",
    "marketing",
    "ecommerce",
    "retail",
    "distribution",
    "products",
    "operations",
    "execution",
    "profitability",
    "leadership",
    "business strategy",
}

# Explicitly NOT strong commercial activity, even if posted recently.
NON_COMMERCIAL_TOPICS = {
    "generic repost",
    "award",
    "personal celebration",
    "company anniversary",
    "generic job ad",
    "unrelated",
}

POST_WINDOW_DAYS = 30
COMMENT_WINDOW_DAYS = 21
INTERACTION_WINDOW_DAYS = 60
MIN_INTERACTIONS = 3


def add_activity(session: Session, data: ActivityIn) -> PublicActivity:
    record = PublicActivity(**data.model_dump())
    session.add(record)
    session.flush()
    return record


def list_activities(session: Session, person_id: int) -> list[PublicActivity]:
    stmt = (
        select(PublicActivity)
        .where(PublicActivity.person_id == person_id)
        .order_by(PublicActivity.activity_date.desc().nullslast())
    )
    return list(session.execute(stmt).scalars())


def evaluate_access_gate(
    activities: list[PublicActivity], as_of: Optional[dt.date] = None
) -> tuple[bool, str]:
    """Return (passes_gate, reason). Only counts activity whose
    commercial_relevance is not explicitly a non-commercial label."""
    as_of = as_of or dt.date.today()
    commercial = [a for a in activities if _is_commercial(a)]

    posts = [a for a in commercial if a.activity_type.value == "Post"]
    comments = [a for a in commercial if a.activity_type.value == "Comment"]

    recent_post = next(
        (a for a in posts if a.activity_date and (as_of - a.activity_date).days <= POST_WINDOW_DAYS),
        None,
    )
    if recent_post:
        return True, f"Posted {(as_of - recent_post.activity_date).days}d ago (commercial)"

    recent_comment = next(
        (a for a in comments if a.activity_date and (as_of - a.activity_date).days <= COMMENT_WINDOW_DAYS),
        None,
    )
    if recent_comment:
        return True, f"Commented meaningfully {(as_of - recent_comment.activity_date).days}d ago"

    within_60 = [
        a for a in commercial if a.activity_date and (as_of - a.activity_date).days <= INTERACTION_WINDOW_DAYS
    ]
    if len(within_60) >= MIN_INTERACTIONS:
        return True, f"{len(within_60)} commercially relevant interactions within 60 days"

    return False, "No qualifying commercial activity within the gate windows"


def _evidence_passes_access_gate(rows: list[Evidence], as_of: Optional[dt.date] = None) -> bool:
    """Evidence-record path for the Access Confirmed gate. A row only counts
    if it is SOURCED (source_url present — the spec is explicit that this
    gate is source-dependent) and its classification isn't Unsupported
    Assumption. Its window (post/comment/interaction) is inferred from
    evidence_type text when possible; otherwise it can only ever count toward
    the 3-interactions-in-60-days rule, never the tighter post/comment
    windows, since we cannot honestly claim a 30- or 21-day recency bar for
    an activity of unknown type."""
    as_of = as_of or dt.date.today()
    sourced = [
        r
        for r in rows
        if r.source_url
        and r.event_date is not None
        and r.classification != EvidenceClassification.UNSUPPORTED_ASSUMPTION
    ]
    if not sourced:
        return False

    def _kind(r: Evidence) -> str:
        t = (r.evidence_type or "").strip().lower()
        if "comment" in t:
            return "comment"
        if "post" in t:
            return "post"
        return "other"

    for r in sourced:
        age = (as_of - r.event_date).days
        if _kind(r) == "post" and age <= POST_WINDOW_DAYS:
            return True
        if _kind(r) == "comment" and age <= COMMENT_WINDOW_DAYS:
            return True

    within_60 = [r for r in sourced if (as_of - r.event_date).days <= INTERACTION_WINDOW_DAYS]
    return len(within_60) >= MIN_INTERACTIONS


def has_access_confirmed_evidence(
    session: Session, company: Company, as_of: Optional[dt.date] = None
) -> bool:
    """Access Confirmed gate: at least one relevant executive at this company
    has a structured, SOURCED public-activity or Evidence record proving they
    meet the LinkedIn access rules (posted <30d, commented meaningfully <21d,
    or >=3 relevant interactions <60d). A Person.linkedin_access_fit /
    last_visible_activity_date column set with no supporting record is not
    enough — see spec correction: 'A value stored only in
    last_visible_activity_date without supporting source evidence is not
    enough.'

    Queries Person fresh by current_company_id rather than reading
    `company.people` — that relationship collection can be cached stale
    within a session if it was accessed before a person was linked to this
    company."""
    person_ids = list(
        session.execute(select(Person.person_id).where(Person.current_company_id == company.company_id)).scalars()
    )
    if not person_ids:
        return False

    for pid in person_ids:
        sourced_activities = [a for a in list_activities(session, pid) if a.direct_url]
        passes, _ = evaluate_access_gate(sourced_activities, as_of)
        if passes:
            return True

    evidence_rows = list(
        session.execute(select(Evidence).where(Evidence.person_id.in_(person_ids))).scalars()
    )
    return _evidence_passes_access_gate(evidence_rows, as_of)


def is_ready_for_engagement_evidence(activity: PublicActivity) -> bool:
    """The stage-integrity rule: Ready for Engagement requires at least one
    stored public activity where direct_url is not empty, activity_date is
    not empty, commercial_relevance is true, engagement_opportunity is true,
    and review_status is approved (Reviewed, with an engagement_opportunity
    value that isn't a rejection). Strong fit alone is never enough — this is
    the one check that actually looks for a current, reviewed, engageable
    post or comment."""
    if not activity.direct_url:
        return False
    if activity.activity_date is None:
        return False
    if not activity.commercial_relevance or activity.commercial_relevance in ("None", "Unknown", ""):
        return False
    if not activity.engagement_opportunity or activity.engagement_opportunity in ("None", "Unknown", ""):
        return False
    if activity.review_status != "Reviewed":
        return False
    return True


def has_ready_for_engagement_evidence(activities: list[PublicActivity]) -> bool:
    return any(is_ready_for_engagement_evidence(a) for a in activities)


def refresh_person_access_fit(session: Session, person_id: int) -> Person:
    person = session.get(Person, person_id)
    if person is None:
        raise ValueError(f"Person {person_id} does not exist.")
    activities = list_activities(session, person_id)
    passes, reason = evaluate_access_gate(activities)
    person.linkedin_access_fit = FitLevel.STRONG if passes else FitLevel.WEAK
    if activities:
        latest = max((a.activity_date for a in activities if a.activity_date), default=None)
        person.last_visible_activity_date = latest
    session.flush()
    return person


def _is_commercial(activity: PublicActivity) -> bool:
    relevance = (activity.commercial_relevance or "").strip().lower()
    if relevance in NON_COMMERCIAL_TOPICS:
        return False
    if relevance in {"", "unknown"}:
        return False
    return True
