"""ICP versioning. Versions are append-only: create_version() always inserts a
new row; there is no update function. propose_change() builds a diff for a
human to review — it never writes to the database by itself. A new version
can only be persisted via approve_version(), which requires approved=True.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ICPVersion

ICP_VERSION_1 = dict(
    version_name="ICP Version 1",
    effective_date=dt.date(2026, 7, 13),
    company_definition=(
        "Founder-led consumer brands in Canada or the United States. Core revenue "
        "$8M-$30M; secondary $30M-$50M. Priority categories: pet food & pet "
        "wellness, supplements & nutrition, beauty & personal care, premium food & "
        "beverage. Multichannel (DTC, Amazon, retail, wholesale, distribution, or "
        "subscription), enough complexity to require cross-functional coordination, "
        "visible commercial ambition, expanding a channel/market/geography/category/"
        "segment or facing a visible growth/profitability constraint, not recently "
        "acquired into a much larger corporation."
    ),
    buyer_definition=(
        "Primary: Founder, CEO, Co-CEO. Secondary: COO, General Manager, VP Sales "
        "and Marketing (qualifies only when they own several commercial "
        "responsibilities — sales, marketing, ecommerce, retail, distribution, "
        "revenue, commercial budget, contribution margin, cross-functional "
        "execution — judged by actual responsibility, not title)."
    ),
    revenue_bands="Core $8M-$30M; Secondary $30M-$50M",
    categories="Pet food & pet wellness; Supplements & nutrition; Beauty & personal care; Premium food & beverage",
    triggers=(
        "Retail expansion, channel expansion, product-category launch, geographic "
        "expansion, new commercial leadership, acquisition-cost pressure, growth "
        "plateau, margin pressure, restructuring, new funding, major partnership, "
        "operational transformation. A trigger increases relevance; it does not "
        "prove buying intent. Personal-life circumstances are never a trigger."
    ),
    disqualifiers=(
        "Recently acquired into a larger corporate structure; too small to afford; "
        "too large for the offer; single-channel or very simple business; no "
        "visible growth ambition; no relevant executive; no active LinkedIn path; "
        "internal team clearly already owns and covers the work; external support "
        "would strongly conflict with the executive's role; no relevant trigger; "
        "no credible proof match; outside the four priority categories."
    ),
    linkedin_access_rule=(
        "A relevant person passes the access gate when they have posted within 30 "
        "days, or commented meaningfully within 21 days, or had at least three "
        "visible professional interactions within 60 days, on commercially relevant "
        "topics (growth, sales, marketing, ecommerce, retail, distribution, "
        "products, operations, execution, profitability, leadership, business "
        "strategy). LinkedIn access is a channel-access condition, not part of "
        "company ICP fit."
    ),
    change_reason="Initial locked hypothesis, validated on 22 researched companies.",
    supporting_outcomes="22 companies researched: 4 Core ICP, 3 Secondary ICP, 6 Monitor, 9 Reject.",
    approved=True,
)


@dataclass
class ProposedICPChange:
    existing_rule: str
    proposed_rule: str
    evidence: str
    companies_involved: int
    people_involved: int
    actions_involved: int
    observed_outcomes: str


def get_current_version(session: Session) -> Optional[ICPVersion]:
    stmt = select(ICPVersion).where(ICPVersion.approved.is_(True)).order_by(ICPVersion.created_at.desc())
    return session.execute(stmt).scalars().first()


def get_version(session: Session, version_name: str) -> Optional[ICPVersion]:
    return session.execute(
        select(ICPVersion).where(ICPVersion.version_name == version_name)
    ).scalar_one_or_none()


def create_initial_version(session: Session) -> ICPVersion:
    existing = get_version(session, ICP_VERSION_1["version_name"])
    if existing:
        return existing
    version = ICPVersion(**ICP_VERSION_1)
    session.add(version)
    session.flush()
    return version


def propose_change(
    *,
    existing_rule: str,
    proposed_rule: str,
    evidence: str,
    companies_involved: int,
    people_involved: int,
    actions_involved: int,
    observed_outcomes: str,
) -> ProposedICPChange:
    """Builds the diff object for human review. Does NOT write to the database."""
    return ProposedICPChange(
        existing_rule=existing_rule,
        proposed_rule=proposed_rule,
        evidence=evidence,
        companies_involved=companies_involved,
        people_involved=people_involved,
        actions_involved=actions_involved,
        observed_outcomes=observed_outcomes,
    )


def approve_version(
    session: Session,
    *,
    version_name: str,
    proposal: ProposedICPChange,
    approved: bool,
    **extra_fields,
) -> ICPVersion:
    """Persist a new ICP version FROM a proposal. Requires explicit human
    approval (approved=True) — this is the only path that writes a new
    version, and prior versions are never mutated."""
    if not approved:
        raise ValueError("Cannot create an ICP version without explicit human approval.")
    if get_version(session, version_name) is not None:
        raise ValueError(f"ICP version '{version_name}' already exists — versions are immutable.")

    version = ICPVersion(
        version_name=version_name,
        effective_date=dt.date.today(),
        change_reason=proposal.evidence,
        supporting_outcomes=proposal.observed_outcomes,
        approved=True,
        **extra_fields,
    )
    session.add(version)
    session.flush()
    return version


def list_versions(session: Session) -> list[ICPVersion]:
    return list(session.execute(select(ICPVersion).order_by(ICPVersion.created_at)).scalars())
