"""Employment history: a person changing companies never overwrites the past —
the current row is closed out (is_current=False, end_date set) and a new row
is opened. Person.current_company_id is updated as a pointer, but nothing is
deleted.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import EmploymentHistory, Person
from .schemas import EmploymentIn


def add_employment(session: Session, data: EmploymentIn) -> EmploymentHistory:
    person = session.get(Person, data.person_id)
    if person is None:
        raise ValueError(f"Person {data.person_id} does not exist.")

    if data.is_current:
        # Close out any previously-current rows for this person before opening
        # a new one — history is preserved, not overwritten.
        open_rows = session.execute(
            select(EmploymentHistory).where(
                EmploymentHistory.person_id == data.person_id,
                EmploymentHistory.is_current.is_(True),
            )
        ).scalars()
        for row in open_rows:
            row.is_current = False
            if row.end_date is None:
                row.end_date = data.start_date or dt.date.today()
        person.current_company_id = data.company_id

    record = EmploymentHistory(**data.model_dump())
    session.add(record)
    session.flush()
    return record


def get_employment_history(session: Session, person_id: int) -> list[EmploymentHistory]:
    stmt = (
        select(EmploymentHistory)
        .where(EmploymentHistory.person_id == person_id)
        .order_by(EmploymentHistory.is_current.desc(), EmploymentHistory.start_date.desc().nullslast())
    )
    return list(session.execute(stmt).scalars())


def current_employment(session: Session, person_id: int) -> Optional[EmploymentHistory]:
    stmt = select(EmploymentHistory).where(
        EmploymentHistory.person_id == person_id, EmploymentHistory.is_current.is_(True)
    )
    return session.execute(stmt).scalars().first()
