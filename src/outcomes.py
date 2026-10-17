"""Outcome recording. This is where the spec's sharpest rule lives:

    A reaction is not automatically a lead.
    A reply is not automatically a lead.
    A connection is not automatically a relationship.

So this module auto-advances relationship_stage only for the mechanical,
objectively-evidenced states (Engaged / Familiar / Connected / Conversation
Active). It NEVER auto-advances to Lead, Commercial Need Confirmed, Qualified
Opportunity, or Client — those require an explicit, human-justified call into
leads.py / opportunities.py / relationships.py with a stated reason.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from .enums import (
    NON_LEAD_OUTCOMES,
    OutcomeType,
    RelationshipStage,
    TimelineEventType,
)
from .models import EngagementAction, Outcome, Person, TimelineEvent
from .relationships import advance_relationship_stage
from .schemas import OutcomeIn
from .stages import StageTransitionError

# Only mechanical, non-commercial relationship progress is auto-applied.
# Anything commercial (Lead and beyond) must go through an explicit call.
_MECHANICAL_ADVANCE = {
    OutcomeType.FOLLOW: RelationshipStage.ENGAGED,
    OutcomeType.CONNECTION_ACCEPTED: RelationshipStage.CONNECTED,
    OutcomeType.MESSAGE_REPLY: RelationshipStage.FAMILIAR,
    OutcomeType.CONVERSATION_STARTED: RelationshipStage.CONVERSATION_ACTIVE,
}

_OUTCOME_TIMELINE_MAP = {
    OutcomeType.NO_VISIBLE_RESPONSE: TimelineEventType.NO_RESPONSE,
    OutcomeType.REACTION: TimelineEventType.COMMENT_LIKED,
    OutcomeType.REPLY: TimelineEventType.COMMENT_REPLY_RECEIVED,
    OutcomeType.PROFILE_VIEW: TimelineEventType.PROFILE_VIEW,
    OutcomeType.FOLLOW: TimelineEventType.FOLLOWED,
    OutcomeType.CONNECTION_ACCEPTED: TimelineEventType.CONNECTION_ACCEPTED,
    OutcomeType.MESSAGE_REPLY: TimelineEventType.MESSAGE_REPLY_RECEIVED,
    OutcomeType.CONVERSATION_STARTED: TimelineEventType.CONVERSATION_STARTED,
    OutcomeType.INTRODUCTION_RECEIVED: TimelineEventType.INTRODUCTION_RECEIVED,
    OutcomeType.REFERRAL_RECEIVED: TimelineEventType.REFERRAL_RECEIVED,
    OutcomeType.CALL_BOOKED: TimelineEventType.CALL_BOOKED,
    OutcomeType.COMMERCIAL_NEED_CONFIRMED: TimelineEventType.COMMERCIAL_NEED_IDENTIFIED,
    OutcomeType.PROPOSAL_REQUESTED: TimelineEventType.MANUAL_NOTE,
    OutcomeType.WON: TimelineEventType.WON,
    OutcomeType.LOST: TimelineEventType.LOST,
}


def record_outcome(session: Session, data: OutcomeIn) -> Outcome:
    action = session.get(EngagementAction, data.action_id)
    if action is None:
        raise ValueError(f"Action {data.action_id} does not exist.")

    outcome = Outcome(**data.model_dump())
    session.add(outcome)
    action.status = "Outcome Recorded"
    session.flush()

    person = session.get(Person, action.person_id)
    person.total_interactions = (person.total_interactions or 0) + 1
    outcome_date = data.outcome_date or dt.date.today()
    person.date_last_engaged = dt.datetime.combine(outcome_date, dt.time.min)
    if person.date_first_engaged is None:
        person.date_first_engaged = person.date_last_engaged

    if data.outcome_type == OutcomeType.CONVERSATION_STARTED and person.date_first_conversation is None:
        person.date_first_conversation = person.date_last_engaged

    session.add(
        TimelineEvent(
            person_id=person.person_id,
            company_id=action.company_id or person.current_company_id,
            event_date=outcome_date,
            event_type=_OUTCOME_TIMELINE_MAP.get(data.outcome_type, TimelineEventType.MANUAL_NOTE),
            related_url=action.related_activity_url,
            their_response=data.outcome_notes,
            commercial_signal=data.commercial_signal
            if data.outcome_type not in NON_LEAD_OUTCOMES
            else None,
        )
    )

    target = _MECHANICAL_ADVANCE.get(data.outcome_type)
    if target is not None:
        try:
            advance_relationship_stage(
                session,
                person.person_id,
                target,
                reason=f"Outcome recorded: {data.outcome_type.value}",
                event_date=outcome_date,
            )
        except StageTransitionError:
            # Not a valid move from the current stage (e.g. already past it) —
            # this is expected and not an error; no silent stage regression.
            pass

    session.flush()
    return outcome


def list_outcomes(session: Session, action_id: int) -> list[Outcome]:
    return [o for o in session.get(EngagementAction, action_id).outcomes]
