"""Person domain logic: creation with dedup by LinkedIn URL, fit/role fields
kept independent, and guarded relationship-stage access.

Relationship-stage transitions themselves live in relationships.py (they need
evidence-gating that belongs with the rest of the commercial-signal rules).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .enums import FitLevel, NextAction, PersonStatus
from .models import Person
from .schemas import PersonIn


def create_or_get_person(session: Session, data: PersonIn) -> tuple[Person, bool]:
    """Create a person, or return the existing one by LinkedIn profile URL.

    Returns (person, created).
    """
    existing = session.execute(
        select(Person).where(Person.linkedin_profile_url == data.linkedin_profile_url)
    ).scalar_one_or_none()
    if existing:
        return existing, False

    person = Person(**data.model_dump())
    session.add(person)
    session.flush()
    return person, True


def get_person(session: Session, person_id: int) -> Optional[Person]:
    return session.get(Person, person_id)


def set_person_icp_role_fit(session: Session, person_id: int, fit: FitLevel) -> Person:
    """Role fit is about how well this person matches the buyer model.
    Kept separate from linkedin_access_fit (reachability) on purpose."""
    person = _require(session, person_id)
    person.role_fit = fit
    session.flush()
    return person


def set_person_access_fit(session: Session, person_id: int, fit: FitLevel) -> Person:
    person = _require(session, person_id)
    person.linkedin_access_fit = fit
    session.flush()
    return person


def set_next_action(
    session: Session, person_id: int, action: Optional[NextAction], action_date=None
) -> Person:
    """NextAction.NO_ACTION is a first-class, explicitly permitted value —
    the system must never force an action just to maintain activity volume."""
    person = _require(session, person_id)
    person.next_action = action
    person.next_action_date = action_date
    session.flush()
    return person


def set_person_status(session: Session, person_id: int, status: PersonStatus) -> Person:
    person = _require(session, person_id)
    person.status = status
    session.flush()
    return person


def list_people(session: Session, status: Optional[PersonStatus] = None) -> list[Person]:
    stmt = select(Person)
    if status:
        stmt = stmt.where(Person.status == status)
    return list(session.execute(stmt.order_by(Person.full_name)).scalars())


def _require(session: Session, person_id: int) -> Person:
    person = session.get(Person, person_id)
    if person is None:
        raise ValueError(f"Person {person_id} does not exist.")
    return person
