"""Relationship-stage and network-quality updates.

Two independent axes, exactly as specced:
  - relationship_stage: what has actually happened between us (event-driven).
  - network_quality: whether this person is part of a *relevant* network
    (never auto-inferred from connection status alone — connection is a fact,
    "trusted relationship" is a judgment call the human makes).

Commercial escalations (Lead, Commercial Need Confirmed, Qualified Opportunity,
Client) require a `reason` string — callers from actions/outcomes pass the
outcome that justified it; nothing reaches these stages silently.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from .enums import NetworkQuality, RelationshipStage
from .models import Person, TimelineEvent
from .stages import COMMERCIAL_RELATIONSHIP_STAGES, StageTransitionError, assert_relationship_transition


def advance_relationship_stage(
    session: Session,
    person_id: int,
    target: RelationshipStage,
    *,
    reason: str,
    event_date=None,
) -> Person:
    """Move a person's relationship stage forward (or into Dormant/Disqualified).

    `reason` is mandatory and always recorded — a stage change with no
    supporting reason should not happen, commercial or not.
    """
    person = session.get(Person, person_id)
    if person is None:
        raise ValueError(f"Person {person_id} does not exist.")

    if target in COMMERCIAL_RELATIONSHIP_STAGES and not reason.strip():
        raise StageTransitionError(
            f"Cannot advance to '{target}' without a recorded reason/evidence."
        )

    assert_relationship_transition(person.relationship_stage, target)
    previous = person.relationship_stage
    person.relationship_stage = target

    session.add(
        TimelineEvent(
            person_id=person_id,
            company_id=person.current_company_id,
            event_type="Stage change",
            interpretation=f"Relationship: {previous.value} -> {target.value}",
            relationship_change=f"{previous.value} -> {target.value}",
            commercial_signal=reason if target in COMMERCIAL_RELATIONSHIP_STAGES else None,
            event_date=event_date,
        )
    )
    session.flush()
    return person


def set_network_quality(
    session: Session, person_id: int, quality: NetworkQuality, *, note: Optional[str] = None
) -> Person:
    """Set network quality explicitly. This is a HUMAN judgment call — the
    function never derives it from relationship_stage or connection status."""
    person = session.get(Person, person_id)
    if person is None:
        raise ValueError(f"Person {person_id} does not exist.")
    person.network_quality = quality
    if note:
        session.add(
            TimelineEvent(
                person_id=person_id,
                company_id=person.current_company_id,
                event_type="Manual note",
                interpretation=f"Network quality set to {quality.value}: {note}",
            )
        )
    session.flush()
    return person
