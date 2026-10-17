"""Opportunity creation. Gated hard: an opportunity can only be created when
problem + authority + potential value + a next step are all present. Public
research alone can never satisfy this — authority_confirmed and
potential_value_confirmed must be explicitly True, which only a human
reviewing a real conversation can assert.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .companies import advance_company_stage
from .enums import CompanyStage, LeadStage, OpportunityStage, RelationshipStage
from .leads import advance_lead_stage
from .models import Lead, Opportunity, Person, _utcnow
from .relationships import advance_relationship_stage
from .schemas import OpportunityCreateIn
from .stages import StageTransitionError, assert_opportunity_transition


class QualificationError(ValueError):
    """Raised when an opportunity is attempted without the required evidence."""


def create_opportunity(session: Session, data: OpportunityCreateIn) -> Opportunity:
    lead = session.get(Lead, data.lead_id)
    if lead is None:
        raise ValueError(f"Lead {data.lead_id} does not exist.")

    missing = []
    if not data.problem.strip():
        missing.append("relevant problem")
    if not data.authority_confirmed:
        missing.append("relevant authority or access to authority")
    if not data.potential_value_confirmed:
        missing.append("potential commercial value")
    if not data.next_step.strip():
        missing.append("agreed next commercial step")
    if missing:
        raise QualificationError(
            "Cannot create a Qualified Opportunity — missing: " + ", ".join(missing)
        )

    opportunity = Opportunity(
        **data.model_dump(exclude={"authority_confirmed", "potential_value_confirmed"})
    )
    session.add(opportunity)
    session.flush()

    # The opportunity's `problem` field IS the commercial-need evidence, so
    # walk the lead through the intermediate stage rather than requiring a
    # separate prior call — but never skip the stage silently either.
    if lead.lead_stage in (LeadStage.NEW, LeadStage.EXPLORING):
        advance_lead_stage(
            session, lead.lead_id, LeadStage.COMMERCIAL_NEED_CONFIRMED, reason=data.problem
        )
    advance_lead_stage(session, lead.lead_id, LeadStage.QUALIFIED, reason="Opportunity qualified")

    if data.primary_contact_id:
        person = session.get(Person, data.primary_contact_id)
        if person:
            person.date_became_qualified = _utcnow()
            try:
                advance_relationship_stage(
                    session,
                    person.person_id,
                    RelationshipStage.QUALIFIED_OPPORTUNITY,
                    reason=data.problem,
                )
            except StageTransitionError:
                pass

    if data.company_id:
        try:
            advance_company_stage(session, data.company_id, CompanyStage.QUALIFIED_OPPORTUNITY)
        except StageTransitionError:
            pass

    session.flush()
    return opportunity


def advance_opportunity_stage(
    session: Session, opportunity_id: int, target: OpportunityStage, *, lost_reason: Optional[str] = None
) -> Opportunity:
    opp = session.get(Opportunity, opportunity_id)
    if opp is None:
        raise ValueError(f"Opportunity {opportunity_id} does not exist.")
    assert_opportunity_transition(opp.stage, target)
    opp.stage = target

    if target in (OpportunityStage.WON, OpportunityStage.LOST):
        opp.actual_close_date = _utcnow()
        if target == OpportunityStage.LOST:
            opp.lost_reason = lost_reason

        person = session.get(Person, opp.primary_contact_id) if opp.primary_contact_id else None
        if person:
            if target == OpportunityStage.WON:
                person.date_won = opp.actual_close_date
                try:
                    advance_relationship_stage(
                        session, person.person_id, RelationshipStage.CLIENT, reason="Opportunity won"
                    )
                except StageTransitionError:
                    pass
            else:
                person.date_lost = opp.actual_close_date

        if opp.company_id:
            target_company_stage = CompanyStage.WON if target == OpportunityStage.WON else CompanyStage.LOST
            try:
                advance_company_stage(session, opp.company_id, target_company_stage)
            except StageTransitionError:
                pass

    session.flush()
    return opp


def list_opportunities(session: Session) -> list[Opportunity]:
    return list(session.execute(select(Opportunity).order_by(Opportunity.created_at.desc())).scalars())
