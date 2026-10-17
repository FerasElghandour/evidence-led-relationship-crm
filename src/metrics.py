"""Funnel counts and conversion rates. Every rate carries its numerator and
denominator alongside the percentage, and a zero denominator returns None
(displayed as "n/a") rather than a misleading number.

EXPERIMENT_START_DATE gates every engagement/outcome-based count. The current
ICP engagement loop began with the real Julie Sawaya comment on 2026-07-14.
Sales Navigator reconciliation imported real historical outreach (messages
sent, connections requested, replies) that predates the experiment — genuine
relationship context, but not clean experimental observations. Counting it
would silently inflate response/conversion rates with pre-experiment data,
so every funnel query below excludes EngagementAction rows dated before this
constant. See tests/test_metrics_experiment_boundary.py.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from .enums import MEANINGFUL_RESPONSE_OUTCOMES, OpportunityStage
from .models import (
    Company,
    EngagementAction,
    Lead,
    Opportunity,
    Outcome,
    Person,
)

EXPERIMENT_START_DATE = dt.date(2026, 7, 14)

@dataclass
class Rate:
    numerator: int
    denominator: int

    @property
    def percentage(self) -> Optional[float]:
        if self.denominator == 0:
            return None
        return round(100 * self.numerator / self.denominator, 1)

    @property
    def display(self) -> str:
        if self.denominator == 0:
            return f"{self.numerator} of {self.denominator} — n/a"
        return f"{self.numerator} of {self.denominator} — {self.percentage}%"


def rate(numerator: int, denominator: int) -> Rate:
    return Rate(numerator=numerator, denominator=denominator)


@dataclass
class FunnelCounts:
    researched_accounts: int
    access_confirmed_accounts: int
    engaged_accounts: int
    people_researched: int
    people_engaged: int
    people_responded: int
    connections_created: int
    conversations_started: int
    leads_created: int
    qualified_opportunities: int
    calls_booked: int
    proposals_sent: int
    clients_won: int


def compute_funnel(session: Session) -> FunnelCounts:
    researched_accounts = session.execute(select(func.count(Company.company_id))).scalar_one()

    access_confirmed_accounts = session.execute(
        select(func.count(Company.company_id)).where(
            Company.linkedin_access_fit == "Strong"
        )
    ).scalar_one()

    engaged_accounts = session.execute(
        select(func.count(distinct(EngagementAction.company_id))).where(
            EngagementAction.company_id.is_not(None),
            EngagementAction.action_date >= EXPERIMENT_START_DATE,
        )
    ).scalar_one()

    people_researched = session.execute(select(func.count(Person.person_id))).scalar_one()

    people_engaged = session.execute(
        select(func.count(distinct(EngagementAction.person_id))).where(
            EngagementAction.action_date >= EXPERIMENT_START_DATE
        )
    ).scalar_one()

    people_responded = session.execute(
        select(func.count(distinct(EngagementAction.person_id)))
        .join(Outcome, Outcome.action_id == EngagementAction.action_id)
        .where(
            Outcome.outcome_type.in_([o.value for o in MEANINGFUL_RESPONSE_OUTCOMES]),
            EngagementAction.action_date >= EXPERIMENT_START_DATE,
        )
    ).scalar_one()

    connections_created = session.execute(
        select(func.count(distinct(EngagementAction.person_id)))
        .join(Outcome, Outcome.action_id == EngagementAction.action_id)
        .where(
            Outcome.outcome_type == "Connection Accepted",
            EngagementAction.action_date >= EXPERIMENT_START_DATE,
        )
    ).scalar_one()

    conversations_started = session.execute(
        select(func.count(Person.person_id)).where(
            Person.date_first_conversation.is_not(None),
            Person.date_first_conversation >= dt.datetime.combine(EXPERIMENT_START_DATE, dt.time.min),
        )
    ).scalar_one()

    leads_created = session.execute(
        select(func.count(Lead.lead_id)).where(
            Lead.lead_created_date >= dt.datetime.combine(EXPERIMENT_START_DATE, dt.time.min)
        )
    ).scalar_one()

    qualified_opportunities = session.execute(
        select(func.count(Opportunity.opportunity_id)).where(
            Opportunity.qualified_date >= dt.datetime.combine(EXPERIMENT_START_DATE, dt.time.min)
        )
    ).scalar_one()

    calls_booked = session.execute(
        select(func.count(distinct(EngagementAction.person_id)))
        .join(Outcome, Outcome.action_id == EngagementAction.action_id)
        .where(
            Outcome.outcome_type == "Call Booked",
            EngagementAction.action_date >= EXPERIMENT_START_DATE,
        )
    ).scalar_one()

    proposals_sent = session.execute(
        select(func.count(Opportunity.opportunity_id)).where(
            Opportunity.stage.in_(
                [OpportunityStage.PROPOSAL.value, OpportunityStage.NEGOTIATION.value,
                 OpportunityStage.WON.value, OpportunityStage.LOST.value]
            ),
            Opportunity.qualified_date >= dt.datetime.combine(EXPERIMENT_START_DATE, dt.time.min),
        )
    ).scalar_one()

    clients_won = session.execute(
        select(func.count(Opportunity.opportunity_id)).where(
            Opportunity.stage == OpportunityStage.WON.value,
            Opportunity.qualified_date >= dt.datetime.combine(EXPERIMENT_START_DATE, dt.time.min),
        )
    ).scalar_one()

    return FunnelCounts(
        researched_accounts=researched_accounts,
        access_confirmed_accounts=access_confirmed_accounts,
        engaged_accounts=engaged_accounts,
        people_researched=people_researched,
        people_engaged=people_engaged,
        people_responded=people_responded,
        connections_created=connections_created,
        conversations_started=conversations_started,
        leads_created=leads_created,
        qualified_opportunities=qualified_opportunities,
        calls_booked=calls_booked,
        proposals_sent=proposals_sent,
        clients_won=clients_won,
    )


@dataclass
class ConversionRates:
    research_to_access: Rate
    access_to_engagement: Rate
    engagement_response: Rate
    conversation: Rate
    lead_creation: Rate
    qualification: Rate
    call_booking: Rate
    proposal: Rate
    win: Rate
    research_to_client: Rate


def compute_conversion_rates(f: FunnelCounts) -> ConversionRates:
    closed_opportunities = f.clients_won  # WON count; LOST tracked separately via opportunities query
    return ConversionRates(
        research_to_access=rate(f.access_confirmed_accounts, f.researched_accounts),
        access_to_engagement=rate(f.engaged_accounts, f.access_confirmed_accounts),
        engagement_response=rate(f.people_responded, f.people_engaged),
        conversation=rate(f.conversations_started, f.people_engaged),
        lead_creation=rate(f.leads_created, f.conversations_started),
        qualification=rate(f.qualified_opportunities, f.leads_created),
        call_booking=rate(f.calls_booked, f.leads_created),
        proposal=rate(f.proposals_sent, f.qualified_opportunities),
        win=rate(f.clients_won, f.proposals_sent),
        research_to_client=rate(f.clients_won, f.researched_accounts),
    )
