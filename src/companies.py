"""Company domain logic: creation with dedup, fit/classification updates kept
separate from each other, and guarded stage transitions.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from .activities import has_access_confirmed_evidence, has_ready_for_engagement_evidence
from .enums import CompanyClassification, CompanyStage, FitLevel
from .evidence import has_icp_approval_evidence
from .models import Company, Person, PublicActivity
from .schemas import CompanyIn
from .stages import StageTransitionError, assert_company_transition


def normalize_domain(website: Optional[str], fallback_name: Optional[str] = None) -> Optional[str]:
    """Normalize a website URL (or company name, as a last resort) into a
    stable dedup key: lowercase host without 'www.' or scheme."""
    if website:
        parsed = urlparse(website if "://" in website else f"//{website}")
        host = (parsed.netloc or parsed.path).lower().strip("/")
        host = re.sub(r"^www\.", "", host)
        host = host.split("/")[0]
        if host:
            return host
    if fallback_name:
        slug = re.sub(r"[^a-z0-9]+", "-", fallback_name.lower()).strip("-")
        return f"name:{slug}" if slug else None
    return None


def create_or_get_company(session: Session, data: CompanyIn) -> tuple[Company, bool]:
    """Create a company, or return the existing one by normalized domain.

    Returns (company, created).
    """
    domain = data.normalized_domain or normalize_domain(data.website, data.company_name)
    if domain:
        existing = session.execute(
            select(Company).where(Company.normalized_domain == domain)
        ).scalar_one_or_none()
        if existing:
            return existing, False

    company = Company(**data.model_dump(exclude={"normalized_domain"}), normalized_domain=domain)
    session.add(company)
    session.flush()
    return company, True


def get_company(session: Session, company_id: int) -> Optional[Company]:
    return session.get(Company, company_id)


def set_company_icp_fit(session: Session, company_id: int, fit: FitLevel, reason: Optional[str] = None) -> Company:
    """Update company ICP fit ONLY. Never touches linkedin_access_fit."""
    company = _require(session, company_id)
    company.company_icp_fit = fit
    if reason:
        company.company_icp_reason = reason
    session.flush()
    return company


def set_linkedin_access_fit(session: Session, company_id: int, fit: FitLevel) -> Company:
    """Update LinkedIn access fit ONLY. Never touches company_icp_fit."""
    company = _require(session, company_id)
    company.linkedin_access_fit = fit
    session.flush()
    return company


def set_classification(session: Session, company_id: int, classification: CompanyClassification) -> Company:
    company = _require(session, company_id)
    company.company_classification = classification
    session.flush()
    return company


def advance_company_stage(session: Session, company_id: int, target: CompanyStage) -> Company:
    company = _require(session, company_id)
    if target == CompanyStage.ICP_APPROVED:
        _assert_icp_approved_evidence(session, company)
    elif target == CompanyStage.ACCESS_CONFIRMED:
        _assert_access_confirmed_evidence(session, company)
    elif target == CompanyStage.READY_FOR_ENGAGEMENT:
        _assert_ready_for_engagement_evidence(session, company)
    assert_company_transition(company.current_stage, target)
    company.current_stage = target
    session.flush()
    return company


def _assert_icp_approved_evidence(session: Session, company: Company) -> None:
    """Stage-integrity rule: a company may reach ICP Approved only when at
    least one structured Evidence record supports the company fit. A
    classification (Core ICP / Secondary ICP / ...) or a fit column
    (company_icp_fit=Strong) set as a bare imported conclusion, with zero
    supporting Evidence rows, is not enough — the company stays at
    Researching until that evidence is recorded."""
    if not has_icp_approval_evidence(session, company.company_id):
        raise StageTransitionError(
            f"Cannot mark '{company.company_name}' ICP Approved: no structured Evidence "
            "record supports the company fit. A classification or fit column set without "
            "a supporting Evidence row is not enough."
        )


def _assert_access_confirmed_evidence(session: Session, company: Company) -> None:
    """Stage-integrity rule: a company may reach Access Confirmed only when a
    structured, SOURCED public-activity or Evidence record proves a relevant
    executive meets the LinkedIn access gate. Person.linkedin_access_fit or
    last_visible_activity_date set with no supporting record is not enough."""
    if not has_access_confirmed_evidence(session, company):
        raise StageTransitionError(
            f"Cannot mark '{company.company_name}' Access Confirmed: no structured, sourced "
            "public-activity or Evidence record proves a relevant executive meets the "
            "LinkedIn access gate (posted <30d, commented <21d, or >=3 interactions <60d). "
            "A last_visible_activity_date or linkedin_access_fit column alone is not enough."
        )


def _assert_ready_for_engagement_evidence(session: Session, company: Company) -> None:
    """Stage-integrity rule: a company may only be marked Ready for
    Engagement when the database holds at least one stored public activity
    (for one of its people) with a direct URL, a date, commercial relevance,
    a marked engagement opportunity, and an approved (Reviewed) status.
    Strong company/access fit alone — including from prior research summaries
    that were never stored as a PublicActivity row — is never sufficient.

    Queries Person fresh by current_company_id rather than reading
    `company.people` — that relationship collection can be cached stale
    within a session if it was accessed before a person was linked to this
    company (e.g. a new person attached after the collection first loaded)."""
    person_ids = list(
        session.execute(select(Person.person_id).where(Person.current_company_id == company.company_id)).scalars()
    )
    activities: list[PublicActivity] = []
    if person_ids:
        activities = list(
            session.execute(
                select(PublicActivity).where(PublicActivity.person_id.in_(person_ids))
            ).scalars()
        )
    if not has_ready_for_engagement_evidence(activities):
        raise StageTransitionError(
            f"Cannot mark '{company.company_name}' Ready for Engagement: no stored public "
            "activity meets the evidence bar (direct URL, date, commercial relevance, "
            "engagement opportunity, and Reviewed status). Strong fit alone is not enough."
        )


def list_companies(
    session: Session,
    classification: Optional[CompanyClassification] = None,
    stage: Optional[CompanyStage] = None,
) -> list[Company]:
    stmt = select(Company)
    if classification:
        stmt = stmt.where(Company.company_classification == classification)
    if stage:
        stmt = stmt.where(Company.current_stage == stage)
    return list(session.execute(stmt.order_by(Company.company_name)).scalars())


def _require(session: Session, company_id: int) -> Company:
    company = session.get(Company, company_id)
    if company is None:
        raise ValueError(f"Company {company_id} does not exist.")
    return company
