"""ICP Approved and Access Confirmed stage-integrity rules:

- ICP Approved requires at least one structured Evidence record supporting
  the company fit. A classification/fit column set as a bare imported
  conclusion, with zero supporting Evidence rows, is not enough.
- Access Confirmed requires a structured, SOURCED public-activity or Evidence
  record proving a relevant executive meets the LinkedIn access gate. A
  Person.linkedin_access_fit / last_visible_activity_date column alone is
  not enough, and an unsourced Evidence row (no source_url) — even a real
  imported research finding — cannot satisfy this source-dependent gate.
"""
from __future__ import annotations

import datetime as dt

import pytest

from src import activities, companies, employment, evidence, people
from src.enums import ActivityType, CompanyStage, EvidenceClassification, FitLevel
from src.schemas import ActivityIn, CompanyIn, EmploymentIn, EvidenceIn, PersonIn
from src.stages import StageTransitionError


def _strong_fit_company(session) -> "Company":  # noqa: F821 (typing only)
    company, _ = companies.create_or_get_company(
        session, CompanyIn(company_name="Test Co", website="testco.com")
    )
    companies.set_company_icp_fit(session, company.company_id, FitLevel.STRONG)
    companies.set_linkedin_access_fit(session, company.company_id, FitLevel.STRONG)
    return company


def _attach_person(session, company, **overrides) -> "Person":  # noqa: F821
    defaults = dict(
        full_name="Test Person",
        linkedin_profile_url="https://www.linkedin.com/in/test-person-iag/",
    )
    defaults.update(overrides)
    person, _ = people.create_or_get_person(session, PersonIn(**defaults))
    employment.add_employment(
        session, EmploymentIn(person_id=person.person_id, company_id=company.company_id, is_current=True)
    )
    return person


# --- ICP Approved -----------------------------------------------------------


def test_zero_evidence_blocks_icp_approved(session):
    """A company cannot become ICP Approved with zero evidence records —
    even with company_icp_fit already set to Strong."""
    company = _strong_fit_company(session)
    assert evidence.list_evidence(session, company_id=company.company_id) == []
    with pytest.raises(StageTransitionError):
        companies.advance_company_stage(session, company.company_id, CompanyStage.ICP_APPROVED)


def test_classification_field_alone_does_not_satisfy_icp_approved(session):
    """Setting company_icp_fit / company_classification is not, by itself,
    evidence. Only a structured Evidence row is."""
    company = _strong_fit_company(session)
    companies.set_classification(session, company.company_id, companies.CompanyClassification.CORE)
    with pytest.raises(StageTransitionError):
        companies.advance_company_stage(session, company.company_id, CompanyStage.ICP_APPROVED)


def test_unsupported_assumption_alone_does_not_satisfy_icp_approved(session):
    company = _strong_fit_company(session)
    evidence.add_evidence(
        session,
        EvidenceIn(
            company_id=company.company_id,
            evidence_text="Unverified guess about this company.",
            classification=EvidenceClassification.UNSUPPORTED_ASSUMPTION,
        ),
    )
    with pytest.raises(StageTransitionError):
        companies.advance_company_stage(session, company.company_id, CompanyStage.ICP_APPROVED)


def test_inference_evidence_does_satisfy_icp_approved(session):
    """ICP fit is inherently research-quality — Inference/Hypothesis
    evidence (even unsourced, even low reliability) is sufficient here,
    unlike the stricter, source-dependent Access Confirmed gate below."""
    company = _strong_fit_company(session)
    evidence.add_evidence(
        session,
        EvidenceIn(
            company_id=company.company_id,
            evidence_text="Category: Beauty. Revenue estimate: $20M (basis: follower count + press).",
            classification=EvidenceClassification.INFERENCE,
            reliability="Medium",
            source_name="Previous ICP research",
        ),
    )
    result = companies.advance_company_stage(session, company.company_id, CompanyStage.ICP_APPROVED)
    assert result.current_stage == CompanyStage.ICP_APPROVED


# --- Access Confirmed --------------------------------------------------------


def _icp_approved_company(session) -> "Company":  # noqa: F821
    company = _strong_fit_company(session)
    evidence.add_evidence(
        session,
        EvidenceIn(
            company_id=company.company_id,
            evidence_text="Category: Pet wellness.",
            classification=EvidenceClassification.INFERENCE,
            reliability="Medium",
        ),
    )
    companies.advance_company_stage(session, company.company_id, CompanyStage.ICP_APPROVED)
    return company


def test_last_visible_activity_date_alone_does_not_satisfy_access_confirmed(session):
    """A person's last_visible_activity_date column, set with no supporting
    structured record, must not satisfy Access Confirmed."""
    company = _icp_approved_company(session)
    _attach_person(session, company, last_visible_activity_date=dt.date.today(), linkedin_access_fit=FitLevel.STRONG)

    with pytest.raises(StageTransitionError):
        companies.advance_company_stage(session, company.company_id, CompanyStage.ACCESS_CONFIRMED)


def test_zero_activity_and_zero_evidence_blocks_access_confirmed(session):
    company = _icp_approved_company(session)
    _attach_person(session, company)
    assert not activities.has_access_confirmed_evidence(session, company)
    with pytest.raises(StageTransitionError):
        companies.advance_company_stage(session, company.company_id, CompanyStage.ACCESS_CONFIRMED)


def test_unsourced_evidence_cannot_satisfy_access_confirmed(session):
    """Missing source evidence cannot satisfy a source-dependent access rule
    — even a real imported research finding, even with a recent event_date,
    even classified as a strong Confirmed Fact. Access Confirmed requires a
    SOURCE (source_url), full stop."""
    company = _icp_approved_company(session)
    person = _attach_person(session, company)
    evidence.add_evidence(
        session,
        EvidenceIn(
            person_id=person.person_id,
            evidence_type="LinkedIn Post",
            evidence_text="Posted about retail expansion.",
            classification=EvidenceClassification.CONFIRMED_FACT,
            reliability="High",
            event_date=dt.date.today(),
            source_url=None,  # <-- the missing piece
        ),
    )
    assert not activities.has_access_confirmed_evidence(session, company)
    with pytest.raises(StageTransitionError):
        companies.advance_company_stage(session, company.company_id, CompanyStage.ACCESS_CONFIRMED)


def test_imported_low_reliability_hypothesis_does_not_advance_access_confirmed(session):
    """Regression test for the exact seed pattern: a Hypothesis-classified,
    Low-reliability, unsourced 'previous research' evidence row must never
    silently satisfy Access Confirmed."""
    company = _icp_approved_company(session)
    person = _attach_person(session, company)
    evidence.add_evidence(
        session,
        EvidenceIn(
            person_id=person.person_id,
            evidence_type="Person research summary",
            evidence_text="Believed to post about growth topics.",
            classification=EvidenceClassification.HYPOTHESIS,
            reliability="Low",
            source_name="Previous ICP research",
            source_url=None,
            event_date=None,
        ),
    )
    assert not activities.has_access_confirmed_evidence(session, company)
    with pytest.raises(StageTransitionError):
        companies.advance_company_stage(session, company.company_id, CompanyStage.ACCESS_CONFIRMED)


def test_sourced_evidence_with_recent_event_date_satisfies_access_confirmed(session):
    """The positive case: a person-scoped Evidence row that IS sourced, IS
    dated, and passes the day-window math is sufficient — matching the
    spec's 'public-activity OR evidence record' language."""
    company = _icp_approved_company(session)
    person = _attach_person(session, company)
    evidence.add_evidence(
        session,
        EvidenceIn(
            person_id=person.person_id,
            evidence_type="LinkedIn Post",
            evidence_text="Posted about a new retail partnership.",
            classification=EvidenceClassification.OBSERVED_BEHAVIOUR,
            reliability="High",
            source_url="https://www.linkedin.com/posts/example-real-post/",
            event_date=dt.date.today() - dt.timedelta(days=5),
        ),
    )
    assert activities.has_access_confirmed_evidence(session, company)
    result = companies.advance_company_stage(session, company.company_id, CompanyStage.ACCESS_CONFIRMED)
    assert result.current_stage == CompanyStage.ACCESS_CONFIRMED


def test_sourced_public_activity_satisfies_access_confirmed(session):
    company = _icp_approved_company(session)
    person = _attach_person(session, company)
    activities.add_activity(
        session,
        ActivityIn(
            person_id=person.person_id,
            activity_type=ActivityType.POST,
            direct_url="https://www.linkedin.com/posts/example/",
            activity_date=dt.date.today(),
            commercial_relevance="High",
        ),
    )
    result = companies.advance_company_stage(session, company.company_id, CompanyStage.ACCESS_CONFIRMED)
    assert result.current_stage == CompanyStage.ACCESS_CONFIRMED


def test_unsourced_public_activity_does_not_satisfy_access_confirmed(session):
    """A PublicActivity row with no direct_url is exactly the same problem
    as unsourced Evidence — it must not count either."""
    company = _icp_approved_company(session)
    person = _attach_person(session, company)
    activities.add_activity(
        session,
        ActivityIn(
            person_id=person.person_id,
            activity_type=ActivityType.POST,
            direct_url=None,
            activity_date=dt.date.today(),
            commercial_relevance="High",
        ),
    )
    assert not activities.has_access_confirmed_evidence(session, company)
    with pytest.raises(StageTransitionError):
        companies.advance_company_stage(session, company.company_id, CompanyStage.ACCESS_CONFIRMED)


# --- Ready for Engagement still requires the approved-activity guard --------


def test_ready_for_engagement_still_requires_approved_activity_after_access_confirmed(session):
    """Regression guard: reaching Access Confirmed via a sourced Evidence
    record must NOT, by itself, unlock Ready for Engagement. That stage
    still needs its own stricter, Reviewed, engagement-marked record (see
    test_ready_for_engagement_gate.py for the full suite)."""
    company = _icp_approved_company(session)
    person = _attach_person(session, company)
    evidence.add_evidence(
        session,
        EvidenceIn(
            person_id=person.person_id,
            evidence_type="LinkedIn Post",
            evidence_text="Posted about a new retail partnership.",
            classification=EvidenceClassification.OBSERVED_BEHAVIOUR,
            reliability="High",
            source_url="https://www.linkedin.com/posts/example-real-post/",
            event_date=dt.date.today() - dt.timedelta(days=5),
        ),
    )
    companies.advance_company_stage(session, company.company_id, CompanyStage.ACCESS_CONFIRMED)

    with pytest.raises(StageTransitionError):
        companies.advance_company_stage(session, company.company_id, CompanyStage.READY_FOR_ENGAGEMENT)


def test_seed_evidence_import_never_reaches_access_confirmed(session):
    """Regression test for the exact bug reported: the seed's imported
    Evidence rows (Inference/Hypothesis, always unsourced) must get a
    Strong/Strong company to ICP Approved and STOP there — never Access
    Confirmed — until a real sourced activity record is added."""
    from src.imports import _advance_company_stage_safely, _import_company_evidence
    from src.enums import CompanyClassification

    company, _ = companies.create_or_get_company(
        session, CompanyIn(company_name="Seed Test Co 2", website="seedtestco2.com")
    )
    row = dict(
        company_classification=CompanyClassification.CORE,
        company_icp_fit=FitLevel.STRONG,
        linkedin_access_fit=FitLevel.STRONG,
        category="Beauty and personal care",
        country="United States",
        commercial_trigger="Retail expansion into new stores.",
        company_icp_reason="Founder-led, in-band revenue, multichannel.",
        possible_external_support_reason="Leadership bandwidth during expansion.",
    )
    _import_company_evidence(session, company, row)
    assert len(evidence.list_evidence(session, company_id=company.company_id)) > 0

    _advance_company_stage_safely(session, company, row)

    assert company.current_stage == CompanyStage.ICP_APPROVED
    assert company.current_stage != CompanyStage.ACCESS_CONFIRMED
