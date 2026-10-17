"""Sales-cycle duration calculations from actual timestamps.

The sales cycle never starts at "researched", "followed", or "connected" —
only at date_became_lead (spec §13). Every duration function returns None
when the underlying dates aren't both present, rather than guessing.

EXPERIMENT_START_DATE (see metrics.py) also gates _first_outcome_date: real
historical outreach imported via Sales Navigator reconciliation predates the
current engagement loop and must never seed a stage-duration or sales-cycle
calculation, even if a person's anchor dates were ever set from old data.
"""
from __future__ import annotations

import datetime as dt
import statistics
from dataclasses import dataclass
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from .enums import OutcomeType
from .metrics import EXPERIMENT_START_DATE
from .models import EngagementAction, Opportunity, Outcome, Person


def days_between(start: Optional[dt.datetime], end: Optional[dt.datetime]) -> Optional[int]:
    if start is None or end is None:
        return None
    return max((end - start).days, 0)


def _first_outcome_date(
    session: Session, person_id: int, outcome_types: set[OutcomeType]
) -> Optional[dt.datetime]:
    stmt = (
        select(Outcome.outcome_date)
        .join(EngagementAction, Outcome.action_id == EngagementAction.action_id)
        .where(
            EngagementAction.person_id == person_id,
            Outcome.outcome_type.in_(outcome_types),
            EngagementAction.action_date >= EXPERIMENT_START_DATE,
        )
        .order_by(Outcome.outcome_date.asc())
    )
    result = session.execute(stmt).scalars().first()
    if result is None:
        return None
    return dt.datetime.combine(result, dt.time.min)


@dataclass
class PersonCycleMetrics:
    person_id: int
    first_engagement_to_first_reply_days: Optional[int]
    first_engagement_to_conversation_days: Optional[int]
    conversation_to_lead_days: Optional[int]
    lead_to_call_days: Optional[int]
    call_to_proposal_days: Optional[int]
    proposal_to_close_days: Optional[int]
    lead_cycle_days: Optional[int]  # lead -> qualified
    complete_cycle_days: Optional[int]  # lead -> final decision


def compute_person_cycle_metrics(session: Session, person: Person) -> PersonCycleMetrics:
    first_reply = _first_outcome_date(
        session, person.person_id, {OutcomeType.REPLY, OutcomeType.MESSAGE_REPLY}
    )
    first_call_booked = _first_outcome_date(session, person.person_id, {OutcomeType.CALL_BOOKED})
    first_proposal = _first_outcome_date(session, person.person_id, {OutcomeType.PROPOSAL_REQUESTED})
    close_date = person.date_won or person.date_lost

    return PersonCycleMetrics(
        person_id=person.person_id,
        first_engagement_to_first_reply_days=days_between(person.date_first_engaged, first_reply),
        first_engagement_to_conversation_days=days_between(
            person.date_first_engaged, person.date_first_conversation
        ),
        conversation_to_lead_days=days_between(person.date_first_conversation, person.date_became_lead),
        lead_to_call_days=days_between(person.date_became_lead, first_call_booked),
        call_to_proposal_days=days_between(first_call_booked, first_proposal),
        proposal_to_close_days=days_between(first_proposal, close_date),
        lead_cycle_days=days_between(person.date_became_lead, person.date_became_qualified),
        complete_cycle_days=days_between(person.date_became_lead, close_date),
    )


def opportunity_cycle_days(opportunity: Opportunity) -> Optional[int]:
    """Qualified opportunity -> won or lost."""
    return days_between(opportunity.qualified_date, opportunity.actual_close_date)


def average_and_median(values: Sequence[Optional[int]]) -> tuple[Optional[float], Optional[float], int]:
    """Return (average, median, n) over the non-None values. (None, None, 0) if empty."""
    clean = [v for v in values if v is not None]
    if not clean:
        return None, None, 0
    return statistics.mean(clean), statistics.median(clean), len(clean)
