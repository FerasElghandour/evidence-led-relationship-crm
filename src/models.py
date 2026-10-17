"""SQLAlchemy ORM models.

Design note: the separate commercial states from the spec (company ICP fit,
LinkedIn access fit, relationship stage, network quality, lead status,
opportunity stage) are stored as *distinct columns*. Nothing in the schema lets
one silently imply another — that separation is enforced in the business layer.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import enums
from .database import Base


def sa_enum(enum_cls) -> SAEnum:
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=64,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


def _utcnow() -> dt.datetime:
    """Naive UTC timestamp. SQLite has no timezone-aware datetime type and
    silently strips tzinfo on round-trip, so every timestamp in this app —
    both stored defaults and any 'now' computed later for a comparison — must
    be naive UTC. Mixing aware and naive datetimes raises TypeError on
    subtraction; using this helper everywhere avoids that class of bug."""
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class Company(Base):
    __tablename__ = "companies"

    company_id: Mapped[int] = mapped_column(primary_key=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_domain: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    website: Mapped[Optional[str]] = mapped_column(String(512))
    linkedin_company_url: Mapped[Optional[str]] = mapped_column(String(512))
    category: Mapped[Optional[str]] = mapped_column(String(128))
    country: Mapped[Optional[str]] = mapped_column(String(64))
    city: Mapped[Optional[str]] = mapped_column(String(128))
    estimated_revenue_min: Mapped[Optional[float]] = mapped_column(Float)
    estimated_revenue_max: Mapped[Optional[float]] = mapped_column(Float)
    revenue_estimation_basis: Mapped[Optional[str]] = mapped_column(Text)
    employee_range: Mapped[Optional[str]] = mapped_column(String(64))
    channels: Mapped[Optional[str]] = mapped_column(Text)  # comma-separated
    founder_led: Mapped[Optional[bool]] = mapped_column(Boolean)
    acquired: Mapped[Optional[bool]] = mapped_column(Boolean)
    company_icp_fit: Mapped[enums.FitLevel] = mapped_column(
        sa_enum(enums.FitLevel), default=enums.FitLevel.UNKNOWN
    )
    company_classification: Mapped[enums.CompanyClassification] = mapped_column(
        sa_enum(enums.CompanyClassification), default=enums.CompanyClassification.MONITOR
    )
    company_icp_reason: Mapped[Optional[str]] = mapped_column(Text)
    growth_stage: Mapped[Optional[str]] = mapped_column(String(128))
    commercial_trigger: Mapped[Optional[str]] = mapped_column(Text)
    trigger_type: Mapped[enums.TriggerType] = mapped_column(
        sa_enum(enums.TriggerType), default=enums.TriggerType.NONE
    )
    trigger_date: Mapped[Optional[dt.date]] = mapped_column()
    trigger_source_url: Mapped[Optional[str]] = mapped_column(String(512))
    visible_growth_opportunity: Mapped[Optional[str]] = mapped_column(Text)
    possible_growth_constraint: Mapped[Optional[str]] = mapped_column(Text)
    possible_external_support_reason: Mapped[Optional[str]] = mapped_column(Text)
    external_support_label: Mapped[enums.ExternalSupportLabel] = mapped_column(
        sa_enum(enums.ExternalSupportLabel), default=enums.ExternalSupportLabel.UNKNOWN
    )
    role_conflict_level: Mapped[enums.RoleConflict] = mapped_column(
        sa_enum(enums.RoleConflict), default=enums.RoleConflict.UNKNOWN
    )
    linkedin_access_fit: Mapped[enums.FitLevel] = mapped_column(
        sa_enum(enums.FitLevel), default=enums.FitLevel.UNKNOWN
    )
    current_stage: Mapped[enums.CompanyStage] = mapped_column(
        sa_enum(enums.CompanyStage), default=enums.CompanyStage.RESEARCHING
    )
    lead_source: Mapped[Optional[str]] = mapped_column(String(64))
    missing_evidence: Mapped[Optional[str]] = mapped_column(Text)
    next_action: Mapped[Optional[enums.NextAction]] = mapped_column(sa_enum(enums.NextAction))
    next_action_date: Mapped[Optional[dt.date]] = mapped_column()
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    people: Mapped[list["Person"]] = relationship(back_populates="company")
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="company")
    leads: Mapped[list["Lead"]] = relationship(back_populates="company")
    opportunities: Mapped[list["Opportunity"]] = relationship(back_populates="company")


class Person(Base):
    __tablename__ = "people"

    person_id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    linkedin_profile_url: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    current_title: Mapped[Optional[str]] = mapped_column(String(255))
    current_company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.company_id"))
    buyer_role: Mapped[enums.BuyerRole] = mapped_column(
        sa_enum(enums.BuyerRole), default=enums.BuyerRole.OTHER
    )
    authority_level: Mapped[enums.AuthorityLevel] = mapped_column(
        sa_enum(enums.AuthorityLevel), default=enums.AuthorityLevel.UNKNOWN
    )
    commercial_ownership: Mapped[Optional[str]] = mapped_column(Text)
    role_fit: Mapped[enums.FitLevel] = mapped_column(sa_enum(enums.FitLevel), default=enums.FitLevel.UNKNOWN)
    role_conflict_level: Mapped[enums.RoleConflict] = mapped_column(
        sa_enum(enums.RoleConflict), default=enums.RoleConflict.UNKNOWN
    )
    topics_discussed: Mapped[Optional[str]] = mapped_column(Text)
    last_visible_activity_date: Mapped[Optional[dt.date]] = mapped_column()
    linkedin_access_fit: Mapped[enums.FitLevel] = mapped_column(
        sa_enum(enums.FitLevel), default=enums.FitLevel.UNKNOWN
    )
    relationship_stage: Mapped[enums.RelationshipStage] = mapped_column(
        sa_enum(enums.RelationshipStage), default=enums.RelationshipStage.RESEARCHED
    )
    network_quality: Mapped[enums.NetworkQuality] = mapped_column(
        sa_enum(enums.NetworkQuality), default=enums.NetworkQuality.UNKNOWN
    )
    lead_status: Mapped[Optional[str]] = mapped_column(String(64), default="None")
    commercial_status: Mapped[Optional[str]] = mapped_column(String(64), default="None")
    date_first_discovered: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, default=_utcnow)
    date_first_engaged: Mapped[Optional[dt.datetime]] = mapped_column(DateTime)
    date_first_conversation: Mapped[Optional[dt.datetime]] = mapped_column(DateTime)
    date_became_lead: Mapped[Optional[dt.datetime]] = mapped_column(DateTime)
    date_became_qualified: Mapped[Optional[dt.datetime]] = mapped_column(DateTime)
    date_won: Mapped[Optional[dt.datetime]] = mapped_column(DateTime)
    date_lost: Mapped[Optional[dt.datetime]] = mapped_column(DateTime)
    date_last_engaged: Mapped[Optional[dt.datetime]] = mapped_column(DateTime)
    total_interactions: Mapped[int] = mapped_column(Integer, default=0)
    next_action: Mapped[Optional[enums.NextAction]] = mapped_column(sa_enum(enums.NextAction))
    next_action_date: Mapped[Optional[dt.date]] = mapped_column()
    status: Mapped[enums.PersonStatus] = mapped_column(
        sa_enum(enums.PersonStatus), default=enums.PersonStatus.ACTIVE
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    company: Mapped[Optional[Company]] = relationship(back_populates="people")
    employment: Mapped[list["EmploymentHistory"]] = relationship(
        back_populates="person", order_by="EmploymentHistory.is_current.desc()"
    )
    activities: Mapped[list["PublicActivity"]] = relationship(back_populates="person")
    actions: Mapped[list["EngagementAction"]] = relationship(back_populates="person")
    timeline: Mapped[list["TimelineEvent"]] = relationship(back_populates="person")


class EmploymentHistory(Base):
    __tablename__ = "employment_history"

    employment_id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.person_id"), nullable=False)
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.company_id"))
    title: Mapped[Optional[str]] = mapped_column(String(255))
    start_date: Mapped[Optional[dt.date]] = mapped_column()
    end_date: Mapped[Optional[dt.date]] = mapped_column()
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(512))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    person: Mapped[Person] = relationship(back_populates="employment")


class Evidence(Base):
    __tablename__ = "evidence"

    evidence_id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.company_id"))
    person_id: Mapped[Optional[int]] = mapped_column(ForeignKey("people.person_id"))
    evidence_type: Mapped[Optional[str]] = mapped_column(String(128))
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[enums.EvidenceClassification] = mapped_column(
        sa_enum(enums.EvidenceClassification), default=enums.EvidenceClassification.UNKNOWN
    )
    source_url: Mapped[Optional[str]] = mapped_column(String(512))
    source_name: Mapped[Optional[str]] = mapped_column(String(255))
    event_date: Mapped[Optional[dt.date]] = mapped_column()
    observation_date: Mapped[Optional[dt.date]] = mapped_column(default=lambda: _utcnow().date())
    reliability: Mapped[Optional[str]] = mapped_column(String(64))
    state_affected: Mapped[Optional[str]] = mapped_column(String(128))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    company: Mapped[Optional[Company]] = relationship(back_populates="evidence")


class PublicActivity(Base):
    __tablename__ = "public_activity"

    activity_id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.person_id"), nullable=False)
    activity_type: Mapped[enums.ActivityType] = mapped_column(
        sa_enum(enums.ActivityType), default=enums.ActivityType.POST
    )
    direct_url: Mapped[Optional[str]] = mapped_column(String(512))
    activity_date: Mapped[Optional[dt.date]] = mapped_column()
    topic: Mapped[Optional[str]] = mapped_column(String(255))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    commercial_relevance: Mapped[Optional[str]] = mapped_column(String(64))  # High/Medium/Low/None
    engagement_opportunity: Mapped[Optional[str]] = mapped_column(String(64))  # Strong/Moderate/None
    review_status: Mapped[str] = mapped_column(String(64), default="Pending")
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    person: Mapped[Person] = relationship(back_populates="activities")


class EngagementAction(Base):
    __tablename__ = "engagement_actions"

    action_id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.company_id"))
    person_id: Mapped[int] = mapped_column(ForeignKey("people.person_id"), nullable=False)
    action_type: Mapped[enums.ActionType] = mapped_column(sa_enum(enums.ActionType), nullable=False)
    related_activity_id: Mapped[Optional[int]] = mapped_column(ForeignKey("public_activity.activity_id"))
    related_activity_url: Mapped[Optional[str]] = mapped_column(String(512))
    action_date: Mapped[dt.date] = mapped_column(default=lambda: _utcnow().date())
    action_time: Mapped[Optional[str]] = mapped_column(String(16))
    timezone: Mapped[Optional[str]] = mapped_column(String(64))
    exact_text: Mapped[Optional[str]] = mapped_column(Text)
    reason_for_action: Mapped[Optional[str]] = mapped_column(Text)
    expected_outcome: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(64), default="Awaiting Outcome")
    time_spent_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    person: Mapped[Person] = relationship(back_populates="actions")
    outcomes: Mapped[list["Outcome"]] = relationship(back_populates="action")


class Outcome(Base):
    __tablename__ = "outcomes"

    outcome_id: Mapped[int] = mapped_column(primary_key=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("engagement_actions.action_id"), nullable=False)
    outcome_type: Mapped[enums.OutcomeType] = mapped_column(sa_enum(enums.OutcomeType), nullable=False)
    outcome_date: Mapped[dt.date] = mapped_column(default=lambda: _utcnow().date())
    outcome_notes: Mapped[Optional[str]] = mapped_column(Text)
    relationship_change: Mapped[Optional[str]] = mapped_column(String(128))
    network_change: Mapped[Optional[str]] = mapped_column(String(128))
    commercial_signal: Mapped[Optional[str]] = mapped_column(Text)
    next_action: Mapped[Optional[enums.NextAction]] = mapped_column(sa_enum(enums.NextAction))
    next_action_date: Mapped[Optional[dt.date]] = mapped_column()
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    action: Mapped[EngagementAction] = relationship(back_populates="outcomes")


class Lead(Base):
    __tablename__ = "leads"

    lead_id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.company_id"))
    person_id: Mapped[int] = mapped_column(ForeignKey("people.person_id"), nullable=False)
    lead_source: Mapped[enums.LeadSource] = mapped_column(
        sa_enum(enums.LeadSource), default=enums.LeadSource.OTHER
    )
    lead_created_date: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)
    lead_created_from_action_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("engagement_actions.action_id")
    )
    lead_reason: Mapped[Optional[str]] = mapped_column(Text)
    commercial_signal: Mapped[Optional[str]] = mapped_column(Text)
    problem_summary: Mapped[Optional[str]] = mapped_column(Text)
    authority_status: Mapped[Optional[str]] = mapped_column(String(128))
    urgency_status: Mapped[Optional[str]] = mapped_column(String(128))
    budget_status: Mapped[Optional[str]] = mapped_column(String(128))
    next_step: Mapped[Optional[str]] = mapped_column(Text)
    next_step_date: Mapped[Optional[dt.date]] = mapped_column()
    lead_stage: Mapped[enums.LeadStage] = mapped_column(
        sa_enum(enums.LeadStage), default=enums.LeadStage.NEW
    )
    lead_status: Mapped[enums.LeadStatus] = mapped_column(
        sa_enum(enums.LeadStatus), default=enums.LeadStatus.OPEN
    )
    disqualification_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    company: Mapped[Optional[Company]] = relationship(back_populates="leads")
    opportunities: Mapped[list["Opportunity"]] = relationship(back_populates="lead")


class Opportunity(Base):
    __tablename__ = "opportunities"

    opportunity_id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.lead_id"), nullable=False)
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.company_id"))
    primary_contact_id: Mapped[Optional[int]] = mapped_column(ForeignKey("people.person_id"))
    opportunity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    problem: Mapped[Optional[str]] = mapped_column(Text)
    desired_outcome: Mapped[Optional[str]] = mapped_column(Text)
    estimated_value: Mapped[Optional[float]] = mapped_column(Float)
    currency: Mapped[Optional[str]] = mapped_column(String(8), default="USD")
    probability: Mapped[Optional[float]] = mapped_column(Float)
    stage: Mapped[enums.OpportunityStage] = mapped_column(
        sa_enum(enums.OpportunityStage), default=enums.OpportunityStage.QUALIFICATION
    )
    qualified_date: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, default=_utcnow)
    expected_close_date: Mapped[Optional[dt.date]] = mapped_column()
    actual_close_date: Mapped[Optional[dt.datetime]] = mapped_column(DateTime)
    lost_reason: Mapped[Optional[str]] = mapped_column(Text)
    next_step: Mapped[Optional[str]] = mapped_column(Text)
    next_step_date: Mapped[Optional[dt.date]] = mapped_column()
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    lead: Mapped[Lead] = relationship(back_populates="opportunities")
    company: Mapped[Optional[Company]] = relationship(back_populates="opportunities")


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    timeline_id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.person_id"), nullable=False)
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.company_id"))
    event_date: Mapped[dt.date] = mapped_column(default=lambda: _utcnow().date())
    event_time: Mapped[Optional[str]] = mapped_column(String(16))
    event_type: Mapped[enums.TimelineEventType] = mapped_column(sa_enum(enums.TimelineEventType))
    related_url: Mapped[Optional[str]] = mapped_column(String(512))
    exact_text_used: Mapped[Optional[str]] = mapped_column(Text)
    their_response: Mapped[Optional[str]] = mapped_column(Text)
    interpretation: Mapped[Optional[str]] = mapped_column(Text)
    relationship_change: Mapped[Optional[str]] = mapped_column(String(128))
    commercial_signal: Mapped[Optional[str]] = mapped_column(Text)
    next_action: Mapped[Optional[str]] = mapped_column(String(128))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    person: Mapped[Person] = relationship(back_populates="timeline")


class ICPVersion(Base):
    __tablename__ = "icp_versions"
    __table_args__ = (UniqueConstraint("version_name", name="uq_icp_version_name"),)

    version_id: Mapped[int] = mapped_column(primary_key=True)
    version_name: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_date: Mapped[Optional[dt.date]] = mapped_column()
    company_definition: Mapped[Optional[str]] = mapped_column(Text)
    buyer_definition: Mapped[Optional[str]] = mapped_column(Text)
    revenue_bands: Mapped[Optional[str]] = mapped_column(Text)
    categories: Mapped[Optional[str]] = mapped_column(Text)
    triggers: Mapped[Optional[str]] = mapped_column(Text)
    disqualifiers: Mapped[Optional[str]] = mapped_column(Text)
    linkedin_access_rule: Mapped[Optional[str]] = mapped_column(Text)
    change_reason: Mapped[Optional[str]] = mapped_column(Text)
    supporting_outcomes: Mapped[Optional[str]] = mapped_column(Text)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)
