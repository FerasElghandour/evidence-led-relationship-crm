from __future__ import annotations

import datetime as dt

from src import companies, employment, people
from src.schemas import CompanyIn, EmploymentIn, PersonIn


def test_duplicate_companies_prevented_by_normalized_domain(session):
    c1, created1 = companies.create_or_get_company(
        session, CompanyIn(company_name="Acme", website="https://www.acme.com/about")
    )
    c2, created2 = companies.create_or_get_company(
        session, CompanyIn(company_name="Acme Inc.", website="acme.com")
    )
    assert created1 is True
    assert created2 is False
    assert c1.company_id == c2.company_id


def test_duplicate_people_prevented_by_linkedin_url(session):
    p1, created1 = people.create_or_get_person(
        session, PersonIn(full_name="Jane Doe", linkedin_profile_url="https://www.linkedin.com/in/janedoe/")
    )
    p2, created2 = people.create_or_get_person(
        session, PersonIn(full_name="Jane D.", linkedin_profile_url="https://www.linkedin.com/in/janedoe/")
    )
    assert created1 is True
    assert created2 is False
    assert p1.person_id == p2.person_id


def test_person_changing_companies_preserves_employment_history(session):
    person, _ = people.create_or_get_person(
        session, PersonIn(full_name="Sam Lee", linkedin_profile_url="https://www.linkedin.com/in/samlee/")
    )
    co_a, _ = companies.create_or_get_company(session, CompanyIn(company_name="Company A", website="a.com"))
    co_b, _ = companies.create_or_get_company(session, CompanyIn(company_name="Company B", website="b.com"))

    employment.add_employment(
        session,
        EmploymentIn(person_id=person.person_id, company_id=co_a.company_id, title="VP Growth",
                     start_date=dt.date(2022, 1, 1), is_current=True),
    )
    employment.add_employment(
        session,
        EmploymentIn(person_id=person.person_id, company_id=co_b.company_id, title="COO",
                     start_date=dt.date(2024, 1, 1), is_current=True),
    )

    history = employment.get_employment_history(session, person.person_id)
    assert len(history) == 2  # both rows preserved, nothing overwritten

    current = employment.current_employment(session, person.person_id)
    assert current.company_id == co_b.company_id
    assert current.title == "COO"

    closed_row = next(h for h in history if h.company_id == co_a.company_id)
    assert closed_row.is_current is False
    assert closed_row.end_date is not None  # closed out, not deleted

    session.refresh(person)
    assert person.current_company_id == co_b.company_id
