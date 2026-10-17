"""Stage-integrity rule: a company may only be marked Ready for Engagement
when the database holds at least one stored public activity with a direct
URL, a date, commercial relevance, a marked engagement opportunity, and an
approved (Reviewed) status. Strong company/access fit — including from a
prior research summary that was never stored as a PublicActivity row — is
never sufficient on its own.
"""
from __future__ import annotations

import datetime as dt

import pytest

from src import activities, companies, employment, evidence, people
from src.activities import has_ready_for_engagement_evidence, is_ready_for_engagement_evidence
from src.enums import ActivityType, CompanyStage, EvidenceClassification, FitLevel
from src.schemas import ActivityIn, CompanyIn, EmploymentIn, EvidenceIn, PersonIn
from src.stages import StageTransitionError


def _company_ready_to_test(session) -> "Company":  # noqa: F821 (typing only)
    """A company with Strong/Strong fit, legitimately advanced through ICP
    Approved and Access Confirmed via real supporting evidence for each gate
    (see test_icp_access_evidence_gates.py for those gates' own dedicated
    tests) — exactly the state that used to be wrongly treated as
    engagement-ready straight from a bare fit column."""
    company, _ = companies.create_or_get_company(
        session, CompanyIn(company_name="Test Co", website="testco.com")
    )
    companies.set_company_icp_fit(session, company.company_id, FitLevel.STRONG)
    companies.set_linkedin_access_fit(session, company.company_id, FitLevel.STRONG)

    evidence.add_evidence(
        session,
        EvidenceIn(
            company_id=company.company_id,
            evidence_text="Category: Test. Multichannel, founder-led.",
            classification=EvidenceClassification.INFERENCE,
            reliability="Medium",
        ),
    )
    companies.advance_company_stage(session, company.company_id, CompanyStage.ICP_APPROVED)

    seed_person, _ = people.create_or_get_person(
        session, PersonIn(full_name="Seed Person", linkedin_profile_url="https://www.linkedin.com/in/seed-person-rfe/")
    )
    employment.add_employment(
        session, EmploymentIn(person_id=seed_person.person_id, company_id=company.company_id, is_current=True)
    )
    evidence.add_evidence(
        session,
        EvidenceIn(
            person_id=seed_person.person_id,
            evidence_type="LinkedIn Post",
            evidence_text="Posted about retail expansion.",
            classification=EvidenceClassification.OBSERVED_BEHAVIOUR,
            reliability="High",
            source_url="https://www.linkedin.com/posts/seed-example/",
            event_date=dt.date.today() - dt.timedelta(days=3),
        ),
    )
    companies.advance_company_stage(session, company.company_id, CompanyStage.ACCESS_CONFIRMED)
    return company


def _attach_person(session, company) -> "Person":  # noqa: F821
    person, _ = people.create_or_get_person(
        session, PersonIn(full_name="Test Person", linkedin_profile_url="https://www.linkedin.com/in/test-person-rfe/")
    )
    employment.add_employment(
        session, EmploymentIn(person_id=person.person_id, company_id=company.company_id, is_current=True)
    )
    return person


def test_strong_fit_alone_does_not_allow_ready_for_engagement(session):
    company = _company_ready_to_test(session)
    with pytest.raises(StageTransitionError):
        companies.advance_company_stage(session, company.company_id, CompanyStage.READY_FOR_ENGAGEMENT)


def test_zero_activities_blocks_the_transition(session):
    company = _company_ready_to_test(session)
    _attach_person(session, company)
    with pytest.raises(StageTransitionError):
        companies.advance_company_stage(session, company.company_id, CompanyStage.READY_FOR_ENGAGEMENT)


def _add_activity(session, person, **overrides):
    defaults = dict(
        person_id=person.person_id,
        activity_type=ActivityType.POST,
        direct_url="https://www.linkedin.com/posts/example-activity/",
        activity_date=dt.date.today(),
        commercial_relevance="High",
        engagement_opportunity="Strong",
    )
    defaults.update(overrides)
    activity = activities.add_activity(session, ActivityIn(**defaults))
    return activity


@pytest.mark.parametrize(
    "field,value",
    [
        ("direct_url", None),
        ("activity_date", None),
        ("commercial_relevance", "None"),
        ("commercial_relevance", "Unknown"),
        ("engagement_opportunity", "None"),
        ("engagement_opportunity", None),
    ],
)
def test_partial_evidence_blocks_the_transition(session, field, value):
    company = _company_ready_to_test(session)
    person = _attach_person(session, company)
    activity = _add_activity(session, person, **{field: value})
    activity.review_status = "Reviewed"  # everything reviewed except the missing field under test
    session.flush()

    assert not is_ready_for_engagement_evidence(activity)
    with pytest.raises(StageTransitionError):
        companies.advance_company_stage(session, company.company_id, CompanyStage.READY_FOR_ENGAGEMENT)


def test_unreviewed_activity_blocks_the_transition(session):
    company = _company_ready_to_test(session)
    person = _attach_person(session, company)
    activity = _add_activity(session, person)
    assert activity.review_status == "Pending"  # default — never auto-approved
    with pytest.raises(StageTransitionError):
        companies.advance_company_stage(session, company.company_id, CompanyStage.READY_FOR_ENGAGEMENT)


def test_full_qualifying_evidence_allows_the_transition(session):
    company = _company_ready_to_test(session)
    person = _attach_person(session, company)
    activity = _add_activity(session, person)
    activity.review_status = "Reviewed"
    session.flush()

    assert is_ready_for_engagement_evidence(activity)
    assert has_ready_for_engagement_evidence([activity])

    result = companies.advance_company_stage(session, company.company_id, CompanyStage.READY_FOR_ENGAGEMENT)
    assert result.current_stage == CompanyStage.READY_FOR_ENGAGEMENT


def test_seed_never_forces_ready_for_engagement_from_fit_alone(session):
    """Regression test for the exact bug reported: the seed used to force
    cohort companies straight to Ready for Engagement based on fit alone,
    with zero stored activities. It must now stop no later than Access
    Confirmed, and only reach that far when real supporting evidence
    (imported via _import_company_evidence) exists for the ICP-approval
    gate — see test_icp_access_evidence_gates.py::
    test_seed_evidence_import_never_reaches_access_confirmed for the
    corresponding proof that unsourced imported evidence alone stops the
    seed at ICP Approved, not Access Confirmed."""
    from src.imports import _advance_company_stage_safely, _import_company_evidence
    from src.enums import CompanyClassification

    company, _ = companies.create_or_get_company(
        session, CompanyIn(company_name="Seed Test Co", website="seedtestco.com")
    )
    row = dict(
        company_classification=CompanyClassification.CORE,
        company_icp_fit=FitLevel.STRONG,
        linkedin_access_fit=FitLevel.STRONG,
        category="Test category",
    )
    _import_company_evidence(session, company, row)
    _advance_company_stage_safely(session, company, row)

    assert company.current_stage == CompanyStage.ICP_APPROVED
    assert company.current_stage != CompanyStage.ACCESS_CONFIRMED
    assert company.current_stage != CompanyStage.READY_FOR_ENGAGEMENT
