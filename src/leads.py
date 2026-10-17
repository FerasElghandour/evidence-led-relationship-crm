"""Lead creation. This is the single place a Lead row is ever created — it is
always an explicit, human-justified call (schema requires a non-empty
lead_reason). Nothing in actions.py or outcomes.py creates a Lead as a side
effect, which is how "a reaction/reply/connection is not automatically a
lead" holds structurally rather than by convention.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .companies import advance_company_stage
from .enums import CompanyStage, LeadStage, LeadStatus, RelationshipStage
from .models import Lead, Person, TimelineEvent, _utcnow
from .relationships import advance_relationship_stage
from .schemas import LeadCreateIn
from .stages import StageTransitionError, assert_lead_transition


def create_lead(session: Session, data: LeadCreateIn) -> Lead:
    person = session.get(Person, data.person_id)
    if person is None:
        raise ValueError(f"Person {data.person_id} does not exist.")

    lead = Lead(**data.model_dump())
    session.add(lead)
    session.flush()

    person.date_became_lead = person.date_became_lead or _utcnow()
    person.lead_status = LeadStage.NEW.value

    session.add(
        TimelineEvent(
            person_id=person.person_id,
            company_id=data.company_id or person.current_company_id,
            event_type="Lead created",
            commercial_signal=data.lead_reason,
            interpretation=f"Lead source: {data.lead_source.value}",
        )
    )

    try:
        advance_relationship_stage(
            session, person.person_id, RelationshipStage.LEAD, reason=data.lead_reason
        )
    except StageTransitionError:
        pass  # already past Lead, or not yet at a precursor stage — don't block lead creation

    if data.company_id:
        try:
            advance_company_stage(session, data.company_id, CompanyStage.LEAD_CREATED)
        except StageTransitionError:
            pass

    session.flush()
    return lead


def advance_lead_stage(session: Session, lead_id: int, target: LeadStage, *, reason: str) -> Lead:
    lead = session.get(Lead, lead_id)
    if lead is None:
        raise ValueError(f"Lead {lead_id} does not exist.")
    assert_lead_transition(lead.lead_stage, target)
    lead.lead_stage = target
    if target == LeadStage.DISQUALIFIED:
        lead.lead_status = LeadStatus.DISQUALIFIED
        lead.disqualification_reason = reason
    elif target == LeadStage.CONVERTED:
        lead.lead_status = LeadStatus.CONVERTED
    session.flush()
    return lead


def list_leads(session: Session, status: Optional[LeadStatus] = None) -> list[Lead]:
    stmt = select(Lead)
    if status:
        stmt = stmt.where(Lead.lead_status == status)
    return list(session.execute(stmt.order_by(Lead.lead_created_date.desc())).scalars())
