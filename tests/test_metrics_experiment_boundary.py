"""EXPERIMENT_START_DATE protection: engagement actions/outcomes dated before
the current experiment (Sales Navigator reconciliation history, or anything
else imported after the fact) must never be counted in funnel/conversion
metrics or sales-cycle durations — only genuine current-experiment activity.
"""
from __future__ import annotations

import datetime as dt

from src import activities, companies, employment, outcomes, people
from src.actions import record_action
from src.enums import ActionType, CompanyStage, EvidenceClassification, FitLevel, OutcomeType
from src.evidence import add_evidence
from src.metrics import EXPERIMENT_START_DATE, compute_funnel
from src.schemas import ActionIn, CompanyIn, EmploymentIn, EvidenceIn, OutcomeIn, PersonIn
from src.sales_cycle import _first_outcome_date


def _company(session):
    company, _ = companies.create_or_get_company(session, CompanyIn(company_name="Test Co", website="testco.com"))
    return company


def _person(session, company, name="Test Person"):
    person, _ = people.create_or_get_person(
        session, PersonIn(full_name=name, linkedin_profile_url=f"https://www.linkedin.com/in/{name.lower().replace(' ', '-')}/")
    )
    employment.add_employment(session, EmploymentIn(person_id=person.person_id, company_id=company.company_id, is_current=True))
    return person


def test_pre_experiment_action_excluded_from_people_engaged(session):
    company = _company(session)
    person = _person(session, company)

    before = EXPERIMENT_START_DATE - dt.timedelta(days=21)
    record_action(
        session,
        ActionIn(company_id=company.company_id, person_id=person.person_id, action_type=ActionType.CONNECTION_REQUEST, action_date=before),
    )
    funnel = compute_funnel(session)
    assert funnel.people_engaged == 0


def test_post_experiment_action_counts_toward_people_engaged(session):
    company = _company(session)
    person = _person(session, company)

    record_action(
        session,
        ActionIn(company_id=company.company_id, person_id=person.person_id, action_type=ActionType.COMMENT, action_date=EXPERIMENT_START_DATE),
    )
    funnel = compute_funnel(session)
    assert funnel.people_engaged == 1


def test_pre_experiment_reply_excluded_from_people_responded(session):
    company = _company(session)
    person = _person(session, company)

    before = EXPERIMENT_START_DATE - dt.timedelta(days=14)
    action = record_action(
        session,
        ActionIn(company_id=company.company_id, person_id=person.person_id, action_type=ActionType.DIRECT_MESSAGE, action_date=before),
    )
    outcomes.record_outcome(session, OutcomeIn(action_id=action.action_id, outcome_type=OutcomeType.MESSAGE_REPLY, outcome_date=before))

    funnel = compute_funnel(session)
    assert funnel.people_engaged == 0
    assert funnel.people_responded == 0


def test_pre_experiment_reply_excluded_from_sales_cycle_first_reply(session):
    """A real historical reply must not seed first_engagement_to_first_reply_days."""
    company = _company(session)
    person = _person(session, company)

    before = EXPERIMENT_START_DATE - dt.timedelta(days=14)
    action = record_action(
        session,
        ActionIn(company_id=company.company_id, person_id=person.person_id, action_type=ActionType.DIRECT_MESSAGE, action_date=before),
    )
    outcomes.record_outcome(session, OutcomeIn(action_id=action.action_id, outcome_type=OutcomeType.MESSAGE_REPLY, outcome_date=before))

    first_reply = _first_outcome_date(session, person.person_id, {OutcomeType.REPLY, OutcomeType.MESSAGE_REPLY})
    assert first_reply is None


def test_post_experiment_reply_is_found_by_sales_cycle(session):
    company = _company(session)
    person = _person(session, company)

    action = record_action(
        session,
        ActionIn(company_id=company.company_id, person_id=person.person_id, action_type=ActionType.DIRECT_MESSAGE, action_date=EXPERIMENT_START_DATE),
    )
    outcomes.record_outcome(
        session, OutcomeIn(action_id=action.action_id, outcome_type=OutcomeType.MESSAGE_REPLY, outcome_date=EXPERIMENT_START_DATE + dt.timedelta(days=1))
    )

    first_reply = _first_outcome_date(session, person.person_id, {OutcomeType.REPLY, OutcomeType.MESSAGE_REPLY})
    assert first_reply is not None


def test_historical_import_tag_pattern_is_queryable_in_notes(session):
    """The tag block written into existing text fields (no schema change) must
    be present and parseable — this is the audit trail the reconciliation
    correction relies on, exercised end-to-end here rather than asserted only
    against the live database by inspection."""
    company = _company(session)
    person = _person(session, company)

    before = EXPERIMENT_START_DATE - dt.timedelta(days=21)
    action = record_action(
        session,
        ActionIn(
            company_id=company.company_id,
            person_id=person.person_id,
            action_type=ActionType.CONNECTION_REQUEST,
            action_date=before,
            reason_for_action=(
                "[HISTORICAL IMPORT — Sales Navigator reconciliation, 2026-07-14]\n"
                "Data origin: Sales Navigator historical timeline\n"
                "Historical import: Yes\n"
                "Date precision: Approximate\n"
                "Imported during reconciliation: Yes\n"
                "Eligible for funnel metrics: No\n"
                "Eligible for sales-cycle metrics: No\n"
                "---\n"
            ),
        ),
    )
    assert "Historical import: Yes" in action.reason_for_action
    assert "Eligible for funnel metrics: No" in action.reason_for_action
