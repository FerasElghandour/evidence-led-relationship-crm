from __future__ import annotations

import pytest

from src.enums import CompanyStage, LeadStage, OpportunityStage, RelationshipStage
from src.stages import (
    StageTransitionError,
    assert_company_transition,
    assert_lead_transition,
    assert_opportunity_transition,
    assert_relationship_transition,
)


def test_company_stage_valid_forward_path():
    assert_company_transition(CompanyStage.RESEARCHING, CompanyStage.ICP_APPROVED)
    assert_company_transition(CompanyStage.ICP_APPROVED, CompanyStage.ACCESS_CONFIRMED)
    assert_company_transition(CompanyStage.ACCESS_CONFIRMED, CompanyStage.READY_FOR_ENGAGEMENT)
    assert_company_transition(CompanyStage.READY_FOR_ENGAGEMENT, CompanyStage.ENGAGING)


def test_company_stage_cannot_skip_ahead():
    with pytest.raises(StageTransitionError):
        assert_company_transition(CompanyStage.RESEARCHING, CompanyStage.QUALIFIED_OPPORTUNITY)


def test_company_stage_cannot_move_backward_past_park():
    with pytest.raises(StageTransitionError):
        assert_company_transition(CompanyStage.ENGAGING, CompanyStage.RESEARCHING)


def test_company_can_park_to_monitor_from_any_active_stage():
    assert_company_transition(CompanyStage.ENGAGING, CompanyStage.MONITOR)
    assert_company_transition(CompanyStage.QUALIFIED_OPPORTUNITY, CompanyStage.LOST)


def test_relationship_stage_valid_forward_path():
    assert_relationship_transition(RelationshipStage.RESEARCHED, RelationshipStage.OBSERVING)
    assert_relationship_transition(RelationshipStage.OBSERVING, RelationshipStage.ENGAGED)
    assert_relationship_transition(RelationshipStage.ENGAGED, RelationshipStage.FAMILIAR)
    assert_relationship_transition(RelationshipStage.FAMILIAR, RelationshipStage.CONNECTED)
    assert_relationship_transition(RelationshipStage.CONNECTED, RelationshipStage.CONVERSATION_ACTIVE)
    assert_relationship_transition(RelationshipStage.CONVERSATION_ACTIVE, RelationshipStage.LEAD)


def test_relationship_stage_researched_to_lead_is_allowed_for_referral_cases():
    # Deliberate design choice: a referral/introduction can make someone a
    # Lead before they've ever been personally engaged. The evidence guard
    # (a mandatory, non-empty reason — see relationships.py) is what keeps
    # this honest, not the stage map.
    assert_relationship_transition(RelationshipStage.RESEARCHED, RelationshipStage.LEAD)


def test_relationship_stage_cannot_skip_from_researched_to_qualified_opportunity():
    with pytest.raises(StageTransitionError):
        assert_relationship_transition(RelationshipStage.RESEARCHED, RelationshipStage.QUALIFIED_OPPORTUNITY)


def test_relationship_dormant_can_reactivate():
    assert_relationship_transition(RelationshipStage.DORMANT, RelationshipStage.ENGAGED)


def test_relationship_disqualified_is_terminal():
    with pytest.raises(StageTransitionError):
        assert_relationship_transition(RelationshipStage.DISQUALIFIED, RelationshipStage.LEAD)


def test_lead_stage_valid_path_and_terminal_states():
    assert_lead_transition(LeadStage.NEW, LeadStage.EXPLORING)
    assert_lead_transition(LeadStage.EXPLORING, LeadStage.COMMERCIAL_NEED_CONFIRMED)
    assert_lead_transition(LeadStage.COMMERCIAL_NEED_CONFIRMED, LeadStage.QUALIFIED)
    assert_lead_transition(LeadStage.QUALIFIED, LeadStage.CONVERTED)
    with pytest.raises(StageTransitionError):
        assert_lead_transition(LeadStage.CONVERTED, LeadStage.NEW)


def test_opportunity_stage_valid_path_and_terminal_states():
    assert_opportunity_transition(OpportunityStage.QUALIFICATION, OpportunityStage.DISCOVERY)
    assert_opportunity_transition(OpportunityStage.DISCOVERY, OpportunityStage.SOLUTION_DEVELOPMENT)
    assert_opportunity_transition(OpportunityStage.SOLUTION_DEVELOPMENT, OpportunityStage.PROPOSAL)
    assert_opportunity_transition(OpportunityStage.PROPOSAL, OpportunityStage.WON)
    with pytest.raises(StageTransitionError):
        assert_opportunity_transition(OpportunityStage.WON, OpportunityStage.LOST)
