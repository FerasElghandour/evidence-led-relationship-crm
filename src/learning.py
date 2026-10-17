"""Breakdown queries for the Learning Review screen: which company profiles,
buyer roles, triggers, actions, lead sources, and role-conflict levels
produced movement. Each returns simple (dimension_value, count) rows — no
scoring, no weighting, just honest counts for a human to read.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Company, EngagementAction, Lead, Opportunity, Person


@dataclass
class BreakdownRow:
    dimension_value: str
    leads: int
    opportunities: int
    wins: int


def _breakdown(session: Session, company_attr) -> list[BreakdownRow]:
    stmt = (
        select(company_attr, func.count(Lead.lead_id.distinct()))
        .select_from(Company)
        .outerjoin(Lead, Lead.company_id == Company.company_id)
        .group_by(company_attr)
    )
    rows = session.execute(stmt).all()

    result = []
    for value, lead_count in rows:
        label = value if value not in (None, "") else "Unknown"
        opp_count = session.execute(
            select(func.count(Opportunity.opportunity_id))
            .join(Company, Opportunity.company_id == Company.company_id)
            .where(company_attr == value)
        ).scalar_one()
        win_count = session.execute(
            select(func.count(Opportunity.opportunity_id))
            .join(Company, Opportunity.company_id == Company.company_id)
            .where(company_attr == value, Opportunity.stage == "Won")
        ).scalar_one()
        result.append(BreakdownRow(str(label), lead_count, opp_count, win_count))
    return sorted(result, key=lambda r: r.leads, reverse=True)


def results_by_category(session: Session) -> list[BreakdownRow]:
    return _breakdown(session, Company.category)


def results_by_country(session: Session) -> list[BreakdownRow]:
    return _breakdown(session, Company.country)


def results_by_trigger(session: Session) -> list[BreakdownRow]:
    return _breakdown(session, Company.trigger_type)


def results_by_role_conflict(session: Session) -> list[BreakdownRow]:
    return _breakdown(session, Company.role_conflict_level)


def results_by_revenue_band(session: Session) -> list[BreakdownRow]:
    stmt = select(Company.estimated_revenue_min, Company.estimated_revenue_max, Company.company_id)
    rows = session.execute(stmt).all()
    buckets: dict[str, list[int]] = {}
    for rmin, rmax, company_id in rows:
        label = _band_label(rmin, rmax)
        buckets.setdefault(label, []).append(company_id)

    result = []
    for label, company_ids in buckets.items():
        leads = session.execute(
            select(func.count(Lead.lead_id)).where(Lead.company_id.in_(company_ids))
        ).scalar_one()
        opps = session.execute(
            select(func.count(Opportunity.opportunity_id)).where(Opportunity.company_id.in_(company_ids))
        ).scalar_one()
        wins = session.execute(
            select(func.count(Opportunity.opportunity_id)).where(
                Opportunity.company_id.in_(company_ids), Opportunity.stage == "Won"
            )
        ).scalar_one()
        result.append(BreakdownRow(label, leads, opps, wins))
    return sorted(result, key=lambda r: r.leads, reverse=True)


def _band_label(rmin: Optional[float], rmax: Optional[float]) -> str:
    if rmin is None and rmax is None:
        return "Unknown"
    if rmin is not None and rmax is not None:
        return f"${rmin/1e6:.0f}M–${rmax/1e6:.0f}M"
    return "Unknown"


def results_by_buyer_role(session: Session) -> list[BreakdownRow]:
    stmt = (
        select(Person.buyer_role, func.count(Lead.lead_id))
        .select_from(Person)
        .outerjoin(Lead, Lead.person_id == Person.person_id)
        .group_by(Person.buyer_role)
    )
    rows = session.execute(stmt).all()
    result = []
    for role, lead_count in rows:
        opp_count = session.execute(
            select(func.count(Opportunity.opportunity_id))
            .join(Person, Opportunity.primary_contact_id == Person.person_id)
            .where(Person.buyer_role == role)
        ).scalar_one()
        win_count = session.execute(
            select(func.count(Opportunity.opportunity_id))
            .join(Person, Opportunity.primary_contact_id == Person.person_id)
            .where(Person.buyer_role == role, Opportunity.stage == "Won")
        ).scalar_one()
        result.append(BreakdownRow(str(role), lead_count, opp_count, win_count))
    return sorted(result, key=lambda r: r.leads, reverse=True)


def results_by_action_type(session: Session) -> list[BreakdownRow]:
    """Which action types preceded a meaningful response, using the action's
    own outcomes rather than lead/opportunity joins (actions are the atomic
    unit of 'what did I do')."""
    stmt = select(EngagementAction.action_type, func.count(EngagementAction.action_id)).group_by(
        EngagementAction.action_type
    )
    rows = session.execute(stmt).all()
    return [BreakdownRow(str(action_type), count, 0, 0) for action_type, count in rows]


def results_by_lead_source(session: Session) -> list[BreakdownRow]:
    stmt = select(Lead.lead_source, func.count(Lead.lead_id)).group_by(Lead.lead_source)
    rows = session.execute(stmt).all()
    result = []
    for source, lead_count in rows:
        win_count = session.execute(
            select(func.count(Opportunity.opportunity_id))
            .join(Lead, Opportunity.lead_id == Lead.lead_id)
            .where(Lead.lead_source == source, Opportunity.stage == "Won")
        ).scalar_one()
        result.append(BreakdownRow(str(source), lead_count, 0, win_count))
    return sorted(result, key=lambda r: r.leads, reverse=True)
