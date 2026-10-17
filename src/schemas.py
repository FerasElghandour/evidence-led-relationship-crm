"""Pydantic input schemas. These validate data entering the domain modules;
the ORM models in models.py are the persisted shape. Keeping them separate
means a bad CSV row fails validation before it ever touches the database.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    ActionType,
    ActivityType,
    AuthorityLevel,
    BuyerRole,
    EvidenceClassification,
    ExternalSupportLabel,
    FitLevel,
    LeadSource,
    OutcomeType,
    RoleConflict,
    TriggerType,
)


class CompanyIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    company_name: str
    normalized_domain: Optional[str] = None
    website: Optional[str] = None
    linkedin_company_url: Optional[str] = None
    category: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    estimated_revenue_min: Optional[float] = None
    estimated_revenue_max: Optional[float] = None
    revenue_estimation_basis: Optional[str] = None
    employee_range: Optional[str] = None
    channels: Optional[str] = None
    founder_led: Optional[bool] = None
    acquired: Optional[bool] = None
    company_icp_fit: FitLevel = FitLevel.UNKNOWN
    company_icp_reason: Optional[str] = None
    growth_stage: Optional[str] = None
    commercial_trigger: Optional[str] = None
    trigger_type: TriggerType = TriggerType.NONE
    trigger_date: Optional[dt.date] = None
    trigger_source_url: Optional[str] = None
    visible_growth_opportunity: Optional[str] = None
    possible_growth_constraint: Optional[str] = None
    possible_external_support_reason: Optional[str] = None
    external_support_label: ExternalSupportLabel = ExternalSupportLabel.UNKNOWN
    role_conflict_level: RoleConflict = RoleConflict.UNKNOWN
    linkedin_access_fit: FitLevel = FitLevel.UNKNOWN
    missing_evidence: Optional[str] = None


class PersonIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str
    linkedin_profile_url: str
    current_title: Optional[str] = None
    current_company_id: Optional[int] = None
    buyer_role: BuyerRole = BuyerRole.OTHER
    authority_level: AuthorityLevel = AuthorityLevel.UNKNOWN
    commercial_ownership: Optional[str] = None
    role_fit: FitLevel = FitLevel.UNKNOWN
    role_conflict_level: RoleConflict = RoleConflict.UNKNOWN
    topics_discussed: Optional[str] = None
    last_visible_activity_date: Optional[dt.date] = None
    linkedin_access_fit: FitLevel = FitLevel.UNKNOWN
    notes: Optional[str] = None


class EmploymentIn(BaseModel):
    person_id: int
    company_id: Optional[int] = None
    title: Optional[str] = None
    start_date: Optional[dt.date] = None
    end_date: Optional[dt.date] = None
    is_current: bool = True
    source_url: Optional[str] = None
    notes: Optional[str] = None


class EvidenceIn(BaseModel):
    company_id: Optional[int] = None
    person_id: Optional[int] = None
    evidence_type: Optional[str] = None
    evidence_text: str
    classification: EvidenceClassification = EvidenceClassification.UNKNOWN
    source_url: Optional[str] = None
    source_name: Optional[str] = None
    event_date: Optional[dt.date] = None
    reliability: Optional[str] = None
    state_affected: Optional[str] = None
    notes: Optional[str] = None


class ActivityIn(BaseModel):
    person_id: int
    activity_type: ActivityType = ActivityType.POST
    direct_url: Optional[str] = None
    activity_date: Optional[dt.date] = None
    topic: Optional[str] = None
    summary: Optional[str] = None
    commercial_relevance: Optional[str] = None
    engagement_opportunity: Optional[str] = None
    notes: Optional[str] = None


class ActionIn(BaseModel):
    company_id: Optional[int] = None
    person_id: int
    action_type: ActionType
    related_activity_id: Optional[int] = None
    related_activity_url: Optional[str] = None
    action_date: Optional[dt.date] = None
    action_time: Optional[str] = None
    timezone: Optional[str] = None
    exact_text: Optional[str] = None
    reason_for_action: Optional[str] = None
    expected_outcome: Optional[str] = None
    time_spent_minutes: Optional[int] = None


class OutcomeIn(BaseModel):
    action_id: int
    outcome_type: OutcomeType
    outcome_date: Optional[dt.date] = None
    outcome_notes: Optional[str] = None
    commercial_signal: Optional[str] = None


class LeadCreateIn(BaseModel):
    company_id: Optional[int] = None
    person_id: int
    lead_source: LeadSource = LeadSource.OTHER
    lead_created_from_action_id: Optional[int] = None
    lead_reason: str = Field(..., min_length=1)
    commercial_signal: Optional[str] = None


class OpportunityCreateIn(BaseModel):
    lead_id: int
    company_id: Optional[int] = None
    primary_contact_id: Optional[int] = None
    opportunity_name: str
    problem: str = Field(..., min_length=1)
    desired_outcome: Optional[str] = None
    estimated_value: Optional[float] = None
    currency: str = "USD"
    next_step: str = Field(..., min_length=1)
    next_step_date: Optional[dt.date] = None
    authority_confirmed: bool
    potential_value_confirmed: bool
