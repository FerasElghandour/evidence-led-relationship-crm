"""Engagement actions: the manual thing you actually did (comment, follow,
connection request, message, ...). Every action creates a timeline entry.
Outcomes (what happened in response) are recorded separately in outcomes.py.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .enums import TimelineEventType
from .models import EngagementAction, Person, TimelineEvent
from .schemas import ActionIn

_ACTION_TIMELINE_MAP = {
    "Follow": TimelineEventType.FOLLOWED,
    "Comment": TimelineEventType.COMMENT_POSTED,
    "Connection Request": TimelineEventType.CONNECTION_REQUEST_SENT,
    "Direct Message": TimelineEventType.MESSAGE_SENT,
    "Reply": TimelineEventType.COMMENT_POSTED,
    "Call Request": TimelineEventType.CALL_REQUESTED,
    "Introduction Request": TimelineEventType.MANUAL_NOTE,
    "Introduction Made": TimelineEventType.MANUAL_NOTE,
    "Referral Given": TimelineEventType.MANUAL_NOTE,
    "Meeting": TimelineEventType.MANUAL_NOTE,
    "No Action": TimelineEventType.MANUAL_NOTE,
    "Share Resource": TimelineEventType.MANUAL_NOTE,
}


def record_action(session: Session, data: ActionIn) -> EngagementAction:
    person = session.get(Person, data.person_id)
    if person is None:
        raise ValueError(f"Person {data.person_id} does not exist.")

    action = EngagementAction(**data.model_dump())
    session.add(action)
    session.flush()

    session.add(
        TimelineEvent(
            person_id=data.person_id,
            company_id=data.company_id or person.current_company_id,
            event_date=action.action_date,
            event_time=action.action_time,
            event_type=_ACTION_TIMELINE_MAP.get(action.action_type.value, TimelineEventType.MANUAL_NOTE),
            related_url=action.related_activity_url,
            exact_text_used=action.exact_text,
            interpretation=action.reason_for_action,
        )
    )
    session.flush()
    return action


def list_actions(session: Session, person_id: int) -> list[EngagementAction]:
    stmt = (
        select(EngagementAction)
        .where(EngagementAction.person_id == person_id)
        .order_by(EngagementAction.action_date.desc())
    )
    return list(session.execute(stmt).scalars())


def actions_awaiting_outcome(session: Session) -> list[EngagementAction]:
    stmt = select(EngagementAction).where(EngagementAction.status == "Awaiting Outcome")
    return list(session.execute(stmt).scalars())
