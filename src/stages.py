"""Stage-transition rules and guards.

Every entity keeps its own independent stage. Transitions are validated against
explicit maps so nothing advances by accident. Commercial advances additionally
require supporting evidence (enforced in the domain modules, not here).
"""
from __future__ import annotations

from .enums import (
    CompanyStage,
    LeadStage,
    OpportunityStage,
    RelationshipStage,
)


class StageTransitionError(ValueError):
    """Raised when a stage change is not permitted."""


# --- Company stage transitions -------------------------------------------------
_PARK = {CompanyStage.MONITOR, CompanyStage.REJECT}
_COMPANY: dict[CompanyStage, set[CompanyStage]] = {
    CompanyStage.RESEARCHING: {CompanyStage.ICP_APPROVED, *_PARK},
    CompanyStage.ICP_APPROVED: {CompanyStage.ACCESS_CONFIRMED, *_PARK},
    CompanyStage.ACCESS_CONFIRMED: {CompanyStage.READY_FOR_ENGAGEMENT, *_PARK},
    CompanyStage.READY_FOR_ENGAGEMENT: {CompanyStage.ENGAGING, *_PARK},
    CompanyStage.ENGAGING: {CompanyStage.CONVERSATION_STARTED, CompanyStage.LOST, *_PARK},
    CompanyStage.CONVERSATION_STARTED: {CompanyStage.LEAD_CREATED, CompanyStage.LOST, *_PARK},
    CompanyStage.LEAD_CREATED: {CompanyStage.COMMERCIAL_NEED_CONFIRMED, CompanyStage.LOST, *_PARK},
    CompanyStage.COMMERCIAL_NEED_CONFIRMED: {CompanyStage.QUALIFIED_OPPORTUNITY, CompanyStage.LOST, *_PARK},
    CompanyStage.QUALIFIED_OPPORTUNITY: {CompanyStage.CALL_BOOKED, CompanyStage.PROPOSAL, CompanyStage.LOST},
    CompanyStage.CALL_BOOKED: {CompanyStage.PROPOSAL, CompanyStage.LOST},
    CompanyStage.PROPOSAL: {CompanyStage.WON, CompanyStage.LOST},
    CompanyStage.WON: set(),
    CompanyStage.LOST: {CompanyStage.MONITOR},
    CompanyStage.MONITOR: {CompanyStage.RESEARCHING, CompanyStage.ICP_APPROVED, CompanyStage.REJECT},
    CompanyStage.REJECT: {CompanyStage.MONITOR},
}

# --- Relationship stage transitions -------------------------------------------
_REL_PARK = {RelationshipStage.DORMANT, RelationshipStage.DISQUALIFIED}
_REACTIVATE = {
    RelationshipStage.OBSERVING,
    RelationshipStage.ENGAGED,
    RelationshipStage.FAMILIAR,
    RelationshipStage.CONNECTED,
    RelationshipStage.CONVERSATION_ACTIVE,
}
# A Lead can arise WITHOUT prior personal engagement — the spec explicitly
# allows referral/introduction leads, where a third party identifies the
# relevant need before the target person has ever been engaged directly. So
# LEAD is a reachable target from every non-terminal relationship stage, not
# only from Conversation Active. The evidence guard (a non-empty `reason`,
# enforced in relationships.py for COMMERCIAL_RELATIONSHIP_STAGES) is what
# keeps this honest, not the stage map.
_RELATIONSHIP: dict[RelationshipStage, set[RelationshipStage]] = {
    RelationshipStage.RESEARCHED: {RelationshipStage.OBSERVING, RelationshipStage.ENGAGED, RelationshipStage.CONNECTED, RelationshipStage.LEAD, *_REL_PARK},
    RelationshipStage.OBSERVING: {RelationshipStage.ENGAGED, RelationshipStage.CONNECTED, RelationshipStage.LEAD, *_REL_PARK},
    RelationshipStage.ENGAGED: {RelationshipStage.FAMILIAR, RelationshipStage.CONNECTED, RelationshipStage.LEAD, *_REL_PARK},
    RelationshipStage.FAMILIAR: {RelationshipStage.CONNECTED, RelationshipStage.CONVERSATION_ACTIVE, RelationshipStage.LEAD, *_REL_PARK},
    RelationshipStage.CONNECTED: {RelationshipStage.CONVERSATION_ACTIVE, RelationshipStage.FAMILIAR, RelationshipStage.LEAD, *_REL_PARK},
    RelationshipStage.CONVERSATION_ACTIVE: {RelationshipStage.LEAD, RelationshipStage.REFERRAL_PARTNER, *_REL_PARK},
    RelationshipStage.LEAD: {
        RelationshipStage.COMMERCIAL_NEED_CONFIRMED,
        RelationshipStage.REFERRAL_PARTNER,
        *_REL_PARK,
    },
    RelationshipStage.COMMERCIAL_NEED_CONFIRMED: {RelationshipStage.QUALIFIED_OPPORTUNITY, *_REL_PARK},
    RelationshipStage.QUALIFIED_OPPORTUNITY: {RelationshipStage.CLIENT, *_REL_PARK},
    RelationshipStage.CLIENT: {RelationshipStage.REFERRAL_PARTNER, RelationshipStage.DORMANT},
    RelationshipStage.REFERRAL_PARTNER: {RelationshipStage.DORMANT},
    RelationshipStage.DORMANT: set(_REACTIVATE),
    RelationshipStage.DISQUALIFIED: set(),
}

# Relationship stages that represent a real commercial escalation and therefore
# require supporting evidence to enter (enforced by relationships.advance_stage).
COMMERCIAL_RELATIONSHIP_STAGES = {
    RelationshipStage.LEAD,
    RelationshipStage.COMMERCIAL_NEED_CONFIRMED,
    RelationshipStage.QUALIFIED_OPPORTUNITY,
    RelationshipStage.CLIENT,
}

# --- Lead stage transitions ----------------------------------------------------
_LEAD: dict[LeadStage, set[LeadStage]] = {
    LeadStage.NEW: {LeadStage.EXPLORING, LeadStage.COMMERCIAL_NEED_CONFIRMED, LeadStage.DISQUALIFIED},
    LeadStage.EXPLORING: {LeadStage.COMMERCIAL_NEED_CONFIRMED, LeadStage.DISQUALIFIED},
    LeadStage.COMMERCIAL_NEED_CONFIRMED: {LeadStage.QUALIFIED, LeadStage.DISQUALIFIED},
    LeadStage.QUALIFIED: {LeadStage.CONVERTED, LeadStage.DISQUALIFIED},
    LeadStage.CONVERTED: set(),
    LeadStage.DISQUALIFIED: set(),
}

# --- Opportunity stage transitions --------------------------------------------
_OPP: dict[OpportunityStage, set[OpportunityStage]] = {
    OpportunityStage.QUALIFICATION: {OpportunityStage.DISCOVERY, OpportunityStage.LOST},
    OpportunityStage.DISCOVERY: {OpportunityStage.SOLUTION_DEVELOPMENT, OpportunityStage.LOST},
    OpportunityStage.SOLUTION_DEVELOPMENT: {OpportunityStage.PROPOSAL, OpportunityStage.LOST},
    OpportunityStage.PROPOSAL: {OpportunityStage.NEGOTIATION, OpportunityStage.WON, OpportunityStage.LOST},
    OpportunityStage.NEGOTIATION: {OpportunityStage.WON, OpportunityStage.LOST},
    OpportunityStage.WON: set(),
    OpportunityStage.LOST: set(),
}


def _assert(maps, current, target, label: str) -> None:
    if current == target:
        raise StageTransitionError(f"{label}: already in stage '{target}'.")
    allowed = maps.get(current, set())
    if target not in allowed:
        raise StageTransitionError(
            f"{label}: cannot move from '{current}' to '{target}'. "
            f"Allowed: {sorted(s.value for s in allowed) or 'none (terminal)'}"
        )


def assert_company_transition(current: CompanyStage, target: CompanyStage) -> None:
    _assert(_COMPANY, current, target, "Company stage")


def assert_relationship_transition(current: RelationshipStage, target: RelationshipStage) -> None:
    _assert(_RELATIONSHIP, current, target, "Relationship stage")


def assert_lead_transition(current: LeadStage, target: LeadStage) -> None:
    _assert(_LEAD, current, target, "Lead stage")


def assert_opportunity_transition(current: OpportunityStage, target: OpportunityStage) -> None:
    _assert(_OPP, current, target, "Opportunity stage")
