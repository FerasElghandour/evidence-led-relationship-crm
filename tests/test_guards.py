"""Tests for the spec's sharpest rules: the ones that keep the system honest.

Reaction/reply/connection != lead. Lead != opportunity. Trigger != confirmed
need. Unsupported assumptions never advance anything. ICP fit and LinkedIn
access stay independent. Connection status and relationship quality stay
independent.
"""
from __future__ import annotations

import pytest

from src import actions, companies, evidence, leads, opportunities, outcomes, people, relationships
from src.enums import (
    ActionType,
    EvidenceClassification,
    FitLevel,
    LeadSource,
    NetworkQuality,
    OutcomeType,
    RelationshipStage,
    RoleConflict,
    TriggerType,
)
from src.models import Company, Lead, Opportunity, Person
from src.opportunities import QualificationError
from src.schemas import (
    ActionIn,
    CompanyIn,
    EvidenceIn,
    LeadCreateIn,
    OpportunityCreateIn,
    OutcomeIn,
    PersonIn,
)
from src.stages import StageTransitionError


def _make_company(session, **overrides) -> Company:
    data = dict(company_name="Test Co", website="testco.com")
    data.update(overrides)
    c, _ = companies.create_or_get_company(session, CompanyIn(**data))
    return c


def _make_person(session, url="https://www.linkedin.com/in/test-person/", **overrides) -> Person:
    data = dict(full_name="Test Person", linkedin_profile_url=url)
    data.update(overrides)
    p, _ = people.create_or_get_person(session, PersonIn(**data))
    return p


def test_unsupported_assumption_cannot_raise_company_icp_fit(session):
    company = _make_company(session)
    evidence.add_evidence(
        session,
        EvidenceIn(
            company_id=company.company_id,
            evidence_text="They probably need help with everything.",
            classification=EvidenceClassification.UNSUPPORTED_ASSUMPTION,
        ),
    )
    # Nothing in the evidence module touches company_icp_fit — assert the caller
    # contract: only classifications in QUALIFYING_CLASSIFICATIONS may justify it.
    assert not evidence.is_actionable_for_qualification(EvidenceClassification.UNSUPPORTED_ASSUMPTION)
    assert not evidence.is_actionable_for_qualification(EvidenceClassification.HYPOTHESIS)
    assert company.company_icp_fit == FitLevel.UNKNOWN  # untouched


def test_reaction_does_not_create_a_lead(session):
    person = _make_person(session)
    action = actions.record_action(
        session, ActionIn(person_id=person.person_id, action_type=ActionType.COMMENT)
    )
    outcomes.record_outcome(
        session, OutcomeIn(action_id=action.action_id, outcome_type=OutcomeType.REACTION)
    )
    lead_count = session.query(Lead).count()
    assert lead_count == 0
    session.refresh(person)
    assert person.relationship_stage != RelationshipStage.LEAD


def test_reply_does_not_automatically_create_a_lead(session):
    person = _make_person(session)
    action = actions.record_action(
        session, ActionIn(person_id=person.person_id, action_type=ActionType.COMMENT)
    )
    outcomes.record_outcome(
        session, OutcomeIn(action_id=action.action_id, outcome_type=OutcomeType.REPLY)
    )
    assert session.query(Lead).count() == 0


def test_connection_accepted_does_not_create_a_lead_or_imply_trusted_relationship(session):
    person = _make_person(session)
    action = actions.record_action(
        session, ActionIn(person_id=person.person_id, action_type=ActionType.CONNECTION_REQUEST)
    )
    outcomes.record_outcome(
        session, OutcomeIn(action_id=action.action_id, outcome_type=OutcomeType.CONNECTION_ACCEPTED)
    )
    session.refresh(person)
    assert session.query(Lead).count() == 0
    assert person.relationship_stage == RelationshipStage.CONNECTED
    # network_quality is a SEPARATE, human-set judgment — never auto-inferred.
    assert person.network_quality == NetworkQuality.UNKNOWN


def test_lead_requires_explicit_reason_and_does_not_auto_create_opportunity(session):
    person = _make_person(session)
    lead = leads.create_lead(
        session,
        LeadCreateIn(
            person_id=person.person_id,
            lead_source=LeadSource.LINKEDIN_MESSAGE,
            lead_reason="They asked directly how I approach margin diagnostics for their category.",
        ),
    )
    assert session.query(Opportunity).count() == 0
    session.refresh(person)
    assert person.relationship_stage == RelationshipStage.LEAD
    assert person.date_became_lead is not None


def test_opportunity_cannot_be_created_from_public_research_alone(session):
    """Even with a well-formed problem statement and next step — the kind of
    thing public research alone can produce — the opportunity is refused
    unless authority and potential value have been explicitly confirmed by a
    human who had the actual conversation."""
    person = _make_person(session)
    lead = leads.create_lead(
        session,
        LeadCreateIn(person_id=person.person_id, lead_reason="Expressed interest in a related topic."),
    )
    with pytest.raises(QualificationError):
        opportunities.create_opportunity(
            session,
            OpportunityCreateIn(
                lead_id=lead.lead_id,
                primary_contact_id=person.person_id,
                opportunity_name="Test Opp",
                problem="Looks like a margin problem based on their public posts.",
                next_step="Reach out to confirm.",
                authority_confirmed=False,  # not confirmed — must fail
                potential_value_confirmed=False,  # not confirmed — must fail
            ),
        )
    assert session.query(Opportunity).count() == 0


def test_opportunity_schema_rejects_empty_problem_or_next_step(session):
    with pytest.raises(Exception):  # pydantic ValidationError — schema-level guard
        OpportunityCreateIn(
            lead_id=1,
            opportunity_name="Test Opp",
            problem="",
            next_step="",
            authority_confirmed=True,
            potential_value_confirmed=True,
        )


def test_opportunity_succeeds_once_full_qualification_evidence_is_present(session):
    person = _make_person(session)
    lead = leads.create_lead(
        session, LeadCreateIn(person_id=person.person_id, lead_reason="Discussed a specific margin problem.")
    )
    opp = opportunities.create_opportunity(
        session,
        OpportunityCreateIn(
            lead_id=lead.lead_id,
            primary_contact_id=person.person_id,
            opportunity_name="Margin diagnostic",
            problem="Contribution margin unclear across SKUs.",
            next_step="Discovery call scheduled for next week.",
            authority_confirmed=True,
            potential_value_confirmed=True,
        ),
    )
    assert opp.opportunity_id is not None
    session.refresh(lead)
    assert lead.lead_stage.value == "Qualified"


def test_trigger_does_not_confirm_commercial_need(session):
    """A commercial_trigger on a Company is just a recorded event — it must
    never, by itself, move the company past ICP_APPROVED-type evidence into a
    'Commercial Need Confirmed' company stage."""
    company = _make_company(
        session,
        commercial_trigger="Retail expansion into 400 new stores",
        trigger_type=TriggerType.RETAIL_EXPANSION,
    )
    assert company.current_stage.value == "Researching"
    assert company.commercial_trigger is not None
    # No function in companies.py maps "has a trigger" to "commercial need
    # confirmed" — advancing that far requires the guarded Lead/Opportunity path.


def test_company_icp_fit_and_linkedin_access_fit_are_independent(session):
    company = _make_company(session)
    companies.set_company_icp_fit(session, company.company_id, FitLevel.STRONG, reason="Great fit")
    session.refresh(company)
    assert company.company_icp_fit == FitLevel.STRONG
    assert company.linkedin_access_fit == FitLevel.UNKNOWN  # untouched by the ICP-fit call

    companies.set_linkedin_access_fit(session, company.company_id, FitLevel.WEAK)
    session.refresh(company)
    assert company.company_icp_fit == FitLevel.STRONG  # untouched by the access-fit call
    assert company.linkedin_access_fit == FitLevel.WEAK


def test_network_quality_is_never_derived_from_relationship_stage(session):
    person = _make_person(session)
    relationships.advance_relationship_stage(
        session, person.person_id, RelationshipStage.OBSERVING, reason="Started monitoring their posts"
    )
    session.refresh(person)
    assert person.relationship_stage == RelationshipStage.OBSERVING
    assert person.network_quality == NetworkQuality.UNKNOWN  # not auto-set

    relationships.set_network_quality(session, person.person_id, NetworkQuality.FAMILIAR, note="Third good exchange")
    session.refresh(person)
    assert person.network_quality == NetworkQuality.FAMILIAR
    assert person.relationship_stage == RelationshipStage.OBSERVING  # untouched


def test_commercial_relationship_advance_requires_a_reason(session):
    person = _make_person(session)
    relationships.advance_relationship_stage(
        session, person.person_id, RelationshipStage.ENGAGED, reason="Commented on their post"
    )
    relationships.advance_relationship_stage(
        session, person.person_id, RelationshipStage.FAMILIAR, reason="Second interaction"
    )
    relationships.advance_relationship_stage(
        session, person.person_id, RelationshipStage.CONNECTED, reason="Accepted connection"
    )
    relationships.advance_relationship_stage(
        session, person.person_id, RelationshipStage.CONVERSATION_ACTIVE, reason="Exchanged messages"
    )
    with pytest.raises(StageTransitionError):
        relationships.advance_relationship_stage(session, person.person_id, RelationshipStage.LEAD, reason="   ")
