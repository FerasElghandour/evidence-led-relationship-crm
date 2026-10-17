"""ICP Relationship and Sales Learning CRM — Streamlit UI.

Every mutation goes through src/ domain modules (never a raw model write from
here), so the guards proven in tests/ apply to every click in this app too.
Streamlit reruns top-to-bottom on each interaction, so each render opens its
own short-lived DB session via session_scope().
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st
from sqlalchemy import select

from src import (
    actions,
    activities,
    companies,
    employment,
    evidence,
    icp_versions,
    leads,
    learning,
    metrics,
    opportunities,
    outcomes,
    people,
    relationships,
    sales_cycle,
)
from src.database import init_db, session_scope
from src.enums import (
    ActionType,
    ActivityType,
    AuthorityLevel,
    BuyerRole,
    CompanyClassification,
    CompanyStage,
    EvidenceClassification,
    ExternalSupportLabel,
    FitLevel,
    LeadSource,
    NetworkQuality,
    NextAction,
    OutcomeType,
    RelationshipStage,
    RoleConflict,
    TriggerType,
)
from src.models import Company, EngagementAction, Lead, Opportunity, Person, PublicActivity
from src.opportunities import QualificationError
from src.schemas import (
    ActionIn,
    ActivityIn,
    EvidenceIn,
    LeadCreateIn,
    OpportunityCreateIn,
    OutcomeIn,
)
from src.stages import StageTransitionError

st.set_page_config(page_title="ICP Relationship CRM", layout="wide")
init_db()

PAGES = [
    "Today",
    "Companies",
    "Company record",
    "People",
    "Person record",
    "Activity review",
    "Leads",
    "Opportunities",
    "Learning review",
]


def enum_options(enum_cls) -> list[str]:
    return [e.value for e in enum_cls]


def fmt_dt(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    return str(value)


def now_naive() -> dt.datetime:
    """Naive UTC 'now', matching src.models._utcnow — SQLite strips tzinfo on
    stored datetimes, so any 'now' compared against a DB value must also be
    naive or the subtraction raises TypeError."""
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def esc(value) -> str:
    """Escape markdown-sensitive characters in free text before st.write()/
    st.markdown(). Without this, two unescaped '$' in the same string (e.g.
    '$20M Series B; ... $30-40M spend') render as a broken LaTeX math span
    instead of plain text."""
    if value is None:
        return "Unknown"
    text = str(value)
    for ch in ("\\", "$", "*", "_", "`"):
        text = text.replace(ch, f"\\{ch}")
    return text


# --------------------------------------------------------------------------
# Today
# --------------------------------------------------------------------------

def page_today():
    st.title("Today")
    today = dt.date.today()

    with session_scope() as db:
        due_people = db.execute(
            select(Person).where(Person.next_action_date.is_not(None), Person.next_action_date <= today)
        ).scalars().all()
        due_companies = db.execute(
            select(Company).where(Company.next_action_date.is_not(None), Company.next_action_date <= today)
        ).scalars().all()
        pending_activity = db.execute(
            select(PublicActivity).where(PublicActivity.review_status == "Pending")
        ).scalars().all()
        ready_people = db.execute(
            select(Person).where(Person.linkedin_access_fit == FitLevel.STRONG.value)
        ).scalars().all()
        awaiting_outcome = actions.actions_awaiting_outcome(db)
        conversations = db.execute(
            select(Person).where(Person.relationship_stage == RelationshipStage.CONVERSATION_ACTIVE.value)
        ).scalars().all()
        open_leads = leads.list_leads(db)
        open_opps = [o for o in opportunities.list_opportunities(db) if o.stage.value not in ("Won", "Lost")]
        dormant = db.execute(
            select(Person).where(Person.relationship_stage == RelationshipStage.DORMANT.value)
        ).scalars().all()

        cols = st.columns(4)
        cols[0].metric("Next actions due", len(due_people) + len(due_companies))
        cols[1].metric("Activity to review", len(pending_activity))
        cols[2].metric("Actions awaiting outcome", len(awaiting_outcome))
        cols[3].metric("Conversations to follow up", len(conversations))

        st.subheader("Next actions due")
        if due_people or due_companies:
            for p in due_people:
                st.write(f"👤 **{esc(p.full_name)}** — {p.next_action.value if p.next_action else '—'} (due {p.next_action_date})")
            for c in due_companies:
                st.write(f"🏢 **{esc(c.company_name)}** — {c.next_action.value if c.next_action else '—'} (due {c.next_action_date})")
        else:
            st.caption("Nothing due.")

        st.subheader("People ready for engagement (strong LinkedIn access)")
        if ready_people:
            st.dataframe(
                pd.DataFrame(
                    [{"Person": p.full_name, "Company": p.company.company_name if p.company else "—",
                      "Relationship stage": p.relationship_stage.value} for p in ready_people]
                ),
                hide_index=True,
            )
        else:
            st.caption("None yet.")

        st.subheader("Actions awaiting outcome")
        if awaiting_outcome:
            st.dataframe(
                pd.DataFrame(
                    [{"Person": db.get(Person, a.person_id).full_name, "Action": a.action_type.value,
                      "Date": fmt_dt(a.action_date)} for a in awaiting_outcome]
                ),
                hide_index=True,
            )
        else:
            st.caption("None.")

        st.subheader("Leads requiring action")
        if open_leads:
            st.dataframe(
                pd.DataFrame(
                    [{"Person": db.get(Person, l.person_id).full_name, "Stage": l.lead_stage.value,
                      "Source": l.lead_source.value, "Created": fmt_dt(l.lead_created_date)} for l in open_leads]
                ),
                hide_index=True,
            )
        else:
            st.caption("None.")

        st.subheader("Opportunities requiring action")
        if open_opps:
            st.dataframe(
                pd.DataFrame(
                    [{"Opportunity": o.opportunity_name, "Stage": o.stage.value,
                      "Next step": o.next_step or "—"} for o in open_opps]
                ),
                hide_index=True,
            )
        else:
            st.caption("None.")

        st.subheader("Dormant relationships to review")
        if dormant:
            st.dataframe(pd.DataFrame([{"Person": p.full_name} for p in dormant]), hide_index=True)
        else:
            st.caption("None.")


# --------------------------------------------------------------------------
# Companies
# --------------------------------------------------------------------------

def page_companies():
    st.title("Companies")
    with session_scope() as db:
        classification_filter = st.selectbox(
            "Filter by classification", ["All"] + enum_options(CompanyClassification)
        )
        rows = companies.list_companies(db)
        if classification_filter != "All":
            rows = [c for c in rows if c.company_classification.value == classification_filter]

        table = []
        for c in rows:
            primary_person = next(iter(c.people), None)
            table.append(
                {
                    "Company": c.company_name,
                    "Category": c.category,
                    "Revenue band": _revenue_band(c),
                    "Company ICP fit": c.company_icp_fit.value,
                    "LinkedIn access fit": c.linkedin_access_fit.value,
                    "Classification": c.company_classification.value,
                    "Stage": c.current_stage.value,
                    "Trigger": c.commercial_trigger or "—",
                    "Primary person": primary_person.full_name if primary_person else "—",
                    "Next action": c.next_action.value if c.next_action else "—",
                    "Next action date": fmt_dt(c.next_action_date),
                }
            )
        st.dataframe(pd.DataFrame(table), hide_index=True, use_container_width=True)


def _revenue_band(c: Company) -> str:
    if c.estimated_revenue_min and c.estimated_revenue_max:
        return f"${c.estimated_revenue_min/1e6:.0f}M–${c.estimated_revenue_max/1e6:.0f}M"
    if c.estimated_revenue_max:
        return f"up to ${c.estimated_revenue_max/1e6:.0f}M"
    if c.estimated_revenue_min:
        return f"${c.estimated_revenue_min/1e6:.0f}M+"
    return "Unknown"


# --------------------------------------------------------------------------
# Company record
# --------------------------------------------------------------------------

def page_company_record():
    st.title("Company record")
    with session_scope() as db:
        all_companies = companies.list_companies(db)
        names = [c.company_name for c in all_companies]
        if not names:
            st.info("No companies yet.")
            return
        selected = st.selectbox("Company", names)
        company = next(c for c in all_companies if c.company_name == selected)

        st.subheader(company.company_name)
        c1, c2, c3 = st.columns(3)
        c1.metric("Company ICP fit", company.company_icp_fit.value)
        c2.metric("LinkedIn access fit", company.linkedin_access_fit.value)
        c3.metric("Classification", company.company_classification.value)

        st.write(f"**Category:** {esc(company.category)} · **Geography:** {esc(company.city or '—')}, {esc(company.country)}")
        st.write(f"**Revenue band:** {esc(_revenue_band(company))} — *{esc(company.revenue_estimation_basis)}*")
        st.write(f"**Channels:** {esc(company.channels)}")
        st.write(f"**Trigger:** {esc(company.commercial_trigger or 'None')} ({company.trigger_type.value})")
        st.write(f"**Growth opportunity:** {esc(company.visible_growth_opportunity)}")
        st.write(f"**Growth constraint:** {esc(company.possible_growth_constraint)}")
        st.write(
            f"**Possible external-support reason (hypothesis):** {esc(company.possible_external_support_reason or 'None recorded')} "
            f"— *{company.external_support_label.value}*"
        )
        st.write(f"**Role conflict level:** {company.role_conflict_level.value}")
        st.write(f"**Current stage:** {company.current_stage.value}")
        if company.missing_evidence:
            st.warning(f"**What remains unknown:** {esc(company.missing_evidence)}")

        st.divider()
        st.subheader("People")
        if company.people:
            st.dataframe(
                pd.DataFrame(
                    [{"Name": p.full_name, "Title": p.current_title, "Buyer role": p.buyer_role.value,
                      "Role conflict": p.role_conflict_level.value, "Access fit": p.linkedin_access_fit.value,
                      "Relationship stage": p.relationship_stage.value} for p in company.people]
                ),
                hide_index=True,
            )
        else:
            st.caption("No people recorded yet.")

        st.subheader("Evidence")
        ev_rows = evidence.list_evidence(db, company_id=company.company_id)
        if ev_rows:
            st.dataframe(
                pd.DataFrame(
                    [{"Text": e.evidence_text, "Classification": e.classification.value,
                      "Source": e.source_url or "—"} for e in ev_rows]
                ),
                hide_index=True,
            )
        else:
            st.caption("No evidence recorded yet.")
        with st.expander("Add evidence"):
            with st.form(f"evidence_form_{company.company_id}"):
                text = st.text_area("Evidence text")
                classification = st.selectbox("Classification", enum_options(EvidenceClassification))
                source_url = st.text_input("Source URL")
                submitted = st.form_submit_button("Save evidence")
                if submitted and text.strip():
                    with session_scope() as db2:
                        evidence.add_evidence(
                            db2,
                            EvidenceIn(
                                company_id=company.company_id,
                                evidence_text=text,
                                classification=EvidenceClassification(classification),
                                source_url=source_url or None,
                            ),
                        )
                    st.success("Evidence saved.")
                    st.rerun()

        st.subheader("Leads")
        company_leads = [l for l in leads.list_leads(db) if l.company_id == company.company_id]
        if company_leads:
            st.dataframe(
                pd.DataFrame(
                    [{"Person": db.get(Person, l.person_id).full_name, "Stage": l.lead_stage.value,
                      "Source": l.lead_source.value} for l in company_leads]
                ),
                hide_index=True,
            )
        else:
            st.caption("No leads yet.")

        st.subheader("Opportunities")
        company_opps = [o for o in opportunities.list_opportunities(db) if o.company_id == company.company_id]
        if company_opps:
            st.dataframe(
                pd.DataFrame(
                    [{"Name": o.opportunity_name, "Stage": o.stage.value, "Value": o.estimated_value} for o in company_opps]
                ),
                hide_index=True,
            )
        else:
            st.caption("No opportunities yet.")

        st.divider()
        st.subheader("One next action")
        with st.form(f"company_next_action_{company.company_id}"):
            next_action = st.selectbox(
                "Next action", enum_options(NextAction),
                index=enum_options(NextAction).index(company.next_action.value) if company.next_action else 0,
            )
            next_date = st.date_input("Next action date", value=company.next_action_date or dt.date.today())
            if st.form_submit_button("Save next action"):
                with session_scope() as db2:
                    co = companies.get_company(db2, company.company_id)
                    co.next_action = NextAction(next_action)
                    co.next_action_date = next_date
                st.success("Saved.")
                st.rerun()


# --------------------------------------------------------------------------
# People
# --------------------------------------------------------------------------

def page_people():
    st.title("People")
    with session_scope() as db:
        rows = people.list_people(db)
        table = []
        for p in rows:
            table.append(
                {
                    "Person": p.full_name,
                    "Company": p.company.company_name if p.company else "—",
                    "Title": p.current_title,
                    "Buyer role": p.buyer_role.value,
                    "Company ICP fit": p.company.company_icp_fit.value if p.company else "—",
                    "LinkedIn access fit": p.linkedin_access_fit.value,
                    "Relationship stage": p.relationship_stage.value,
                    "Network quality": p.network_quality.value,
                    "Lead status": p.lead_status or "—",
                    "Last engagement": fmt_dt(p.date_last_engaged),
                    "Interactions": p.total_interactions,
                    "Next action": p.next_action.value if p.next_action else "—",
                    "Next action date": fmt_dt(p.next_action_date),
                }
            )
        st.dataframe(pd.DataFrame(table), hide_index=True, use_container_width=True)


# --------------------------------------------------------------------------
# Person record — the core of the closed loop
# --------------------------------------------------------------------------

def page_person_record():
    st.title("Person record")
    with session_scope() as db:
        all_people = people.list_people(db)
        names = [f"{p.full_name} ({p.company.company_name if p.company else 'no company'})" for p in all_people]
        if not names:
            st.info("No people yet.")
            return
        idx = st.selectbox("Person", range(len(names)), format_func=lambda i: names[i])
        person = all_people[idx]

        st.subheader(person.full_name)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Relationship stage", person.relationship_stage.value)
        c2.metric("Network quality", person.network_quality.value)
        c3.metric("Lead status", person.lead_status or "None")
        c4.metric("LinkedIn access fit", person.linkedin_access_fit.value)

        st.write(f"**Company:** {esc(person.company.company_name) if person.company else 'Unknown'}")
        st.write(f"**Title:** {esc(person.current_title)} · **Buyer role:** {person.buyer_role.value}")
        st.write(f"**Role fit:** {person.role_fit.value} · **Role conflict:** {person.role_conflict_level.value}")
        st.write(f"**Topics discussed:** {esc(person.topics_discussed)}")
        st.write(f"**Last visible activity:** {fmt_dt(person.last_visible_activity_date)}")
        if person.notes:
            st.write(f"**Notes:** {esc(person.notes)}")

        hist = employment.get_employment_history(db, person.person_id)
        if len(hist) > 1:
            with st.expander(f"Employment history ({len(hist)} roles)"):
                st.dataframe(
                    pd.DataFrame(
                        [{"Company": h.company_id, "Title": h.title, "Current": h.is_current,
                          "Start": fmt_dt(h.start_date), "End": fmt_dt(h.end_date)} for h in hist]
                    ),
                    hide_index=True,
                )

        st.divider()
        st.subheader("Public activity")
        st.caption(
            "🔎 RESEARCH ACTIVITY — a post, comment, article, or public event you observed. "
            "This is not something you did. It is never counted as engagement."
        )
        acts = activities.list_activities(db, person.person_id)
        if acts:
            st.dataframe(
                pd.DataFrame(
                    [{"Date": fmt_dt(a.activity_date), "Type": a.activity_type.value, "Topic": a.topic,
                      "URL": a.direct_url, "Commercial relevance": a.commercial_relevance,
                      "Review status": a.review_status} for a in acts]
                ),
                hide_index=True,
            )
        passes, reason = activities.evaluate_access_gate(acts)
        st.caption(f"Access gate: {'PASSES' if passes else 'does not pass'} — {reason}")

        with st.expander("Save a public activity"):
            with st.form(f"activity_form_{person.person_id}"):
                a_type = st.selectbox("Type", enum_options(ActivityType))
                a_url = st.text_input("Direct post URL")
                a_date = st.date_input("Activity date", value=dt.date.today())
                a_topic = st.text_input("Topic")
                a_relevance = st.selectbox("Commercial relevance", ["High", "Medium", "Low", "None", "Unknown"])
                a_summary = st.text_area("Summary")
                if st.form_submit_button("Save activity"):
                    with session_scope() as db2:
                        activities.add_activity(
                            db2,
                            ActivityIn(
                                person_id=person.person_id, activity_type=ActivityType(a_type),
                                direct_url=a_url or None, activity_date=a_date, topic=a_topic or None,
                                commercial_relevance=a_relevance, summary=a_summary or None,
                            ),
                        )
                        activities.refresh_person_access_fit(db2, person.person_id)
                    st.success("Activity saved.")
                    st.rerun()

        st.divider()
        st.subheader("Record a manual action")
        st.caption("✋ MY ENGAGEMENT ACTION — something you personally performed. Nothing is recorded until you submit this form.")
        with st.form(f"action_form_{person.person_id}"):
            act_type = st.selectbox("Action type", enum_options(ActionType))
            act_url = st.text_input("Related activity URL (optional)")
            act_text = st.text_area("Exact text used (e.g. the comment you posted)")
            act_reason = st.text_area("Reason for this action")
            act_date = st.date_input("Action date", value=dt.date.today())
            if st.form_submit_button("Record action"):
                with session_scope() as db2:
                    actions.record_action(
                        db2,
                        ActionIn(
                            company_id=person.current_company_id, person_id=person.person_id,
                            action_type=ActionType(act_type), related_activity_url=act_url or None,
                            exact_text=act_text or None, reason_for_action=act_reason or None,
                            action_date=act_date,
                        ),
                    )
                st.success("Action recorded. Now record its outcome below once you observe one.")
                st.rerun()

        st.subheader("Actions and outcomes")
        st.caption("📩 OUTCOME — what happened after your action. Recorded separately, after the fact, never assumed.")
        person_actions = actions.list_actions(db, person.person_id)
        for a in person_actions:
            with st.container(border=True):
                st.write(f"**{a.action_type.value}** on {fmt_dt(a.action_date)} — status: {a.status}")
                if a.exact_text:
                    st.caption(esc(a.exact_text))
                a_outcomes = outcomes.list_outcomes(db, a.action_id)
                for o in a_outcomes:
                    st.write(f"→ Outcome: **{o.outcome_type.value}** on {fmt_dt(o.outcome_date)} — {esc(o.outcome_notes or '')}")
                if a.status == "Awaiting Outcome":
                    with st.form(f"outcome_form_{a.action_id}"):
                        o_type = st.selectbox("Outcome", enum_options(OutcomeType), key=f"otype_{a.action_id}")
                        o_notes = st.text_area("Notes / what they said", key=f"onotes_{a.action_id}")
                        o_signal = st.text_area(
                            "Commercial signal, if any (only if this outcome is lead-worthy)",
                            key=f"osignal_{a.action_id}",
                        )
                        if st.form_submit_button("Record outcome"):
                            with session_scope() as db2:
                                outcomes.record_outcome(
                                    db2,
                                    OutcomeIn(
                                        action_id=a.action_id, outcome_type=OutcomeType(o_type),
                                        outcome_notes=o_notes or None, commercial_signal=o_signal or None,
                                    ),
                                )
                            st.success("Outcome recorded.")
                            st.rerun()

        st.divider()
        st.subheader("Full relationship timeline")
        for ev in sorted(person.timeline, key=lambda e: (e.event_date or dt.date.min), reverse=True):
            st.write(
                f"`{fmt_dt(ev.event_date)}` **{ev.event_type.value if hasattr(ev.event_type, 'value') else ev.event_type}** "
                f"— {esc(ev.interpretation or ev.their_response or ev.commercial_signal or '')}"
            )

        st.divider()
        st.subheader("Update relationship stage")
        with st.form(f"relationship_form_{person.person_id}"):
            options = enum_options(RelationshipStage)
            target = st.selectbox("Target stage", options, index=options.index(person.relationship_stage.value))
            reason = st.text_area("Reason (required for commercial stages: Lead / Commercial Need Confirmed / Qualified Opportunity / Client)")
            if st.form_submit_button("Advance relationship stage"):
                try:
                    with session_scope() as db2:
                        relationships.advance_relationship_stage(
                            db2, person.person_id, RelationshipStage(target), reason=reason
                        )
                    st.success("Relationship stage updated.")
                    st.rerun()
                except StageTransitionError as e:
                    st.error(str(e))

        with st.form(f"network_form_{person.person_id}"):
            nq_options = enum_options(NetworkQuality)
            nq = st.selectbox("Network quality (human judgment)", nq_options, index=nq_options.index(person.network_quality.value))
            nq_note = st.text_input("Note")
            if st.form_submit_button("Set network quality"):
                with session_scope() as db2:
                    relationships.set_network_quality(db2, person.person_id, NetworkQuality(nq), note=nq_note or None)
                st.success("Network quality updated.")
                st.rerun()

        st.divider()
        st.subheader("Determine whether this person is now a lead")
        if person.lead_status in (None, "None"):
            with st.form(f"lead_form_{person.person_id}"):
                st.caption(
                    "Only create a lead for a real commercial signal: a business challenge discussed, "
                    "a question about your work, agreement to discuss further, a referral, or expressed "
                    "interest directly tied to your service. A like, connection, or generic reply is not enough."
                )
                source = st.selectbox("Lead source", enum_options(LeadSource))
                reason = st.text_area("Lead reason (required — the actual signal observed)")
                signal = st.text_area("Commercial signal detail")
                if st.form_submit_button("Create lead"):
                    if not reason.strip():
                        st.error("A lead reason is required.")
                    else:
                        with session_scope() as db2:
                            leads.create_lead(
                                db2,
                                LeadCreateIn(
                                    company_id=person.current_company_id, person_id=person.person_id,
                                    lead_source=LeadSource(source), lead_reason=reason,
                                    commercial_signal=signal or None,
                                ),
                            )
                        st.success("Lead created.")
                        st.rerun()
        else:
            st.info(f"Lead status: {person.lead_status}")
            person_lead = next((l for l in leads.list_leads(db) if l.person_id == person.person_id), None)
            if person_lead and person_lead.lead_status.value == "Open":
                with st.form(f"opportunity_form_{person.person_id}"):
                    st.caption(
                        "An opportunity requires ALL of: a relevant problem, confirmed authority, "
                        "confirmed potential value, and an agreed next step. Public research alone "
                        "is never enough."
                    )
                    name = st.text_input("Opportunity name")
                    problem = st.text_area("Problem")
                    next_step = st.text_area("Agreed next commercial step")
                    value = st.number_input("Estimated value (optional)", min_value=0.0, step=1000.0)
                    authority = st.checkbox("Authority confirmed (they own or can influence the decision)")
                    potential_value = st.checkbox("Potential commercial value confirmed")
                    if st.form_submit_button("Create qualified opportunity"):
                        try:
                            with session_scope() as db2:
                                opportunities.create_opportunity(
                                    db2,
                                    OpportunityCreateIn(
                                        lead_id=person_lead.lead_id, company_id=person.current_company_id,
                                        primary_contact_id=person.person_id, opportunity_name=name,
                                        problem=problem, next_step=next_step,
                                        estimated_value=value or None,
                                        authority_confirmed=authority, potential_value_confirmed=potential_value,
                                    ),
                                )
                            st.success("Opportunity created.")
                            st.rerun()
                        except QualificationError as e:
                            st.error(str(e))

        st.divider()
        st.subheader("One next action")
        with st.form(f"person_next_action_{person.person_id}"):
            na_options = enum_options(NextAction)
            na = st.selectbox(
                "Next action", na_options,
                index=na_options.index(person.next_action.value) if person.next_action else na_options.index("No Action"),
            )
            na_date = st.date_input("Next action date", value=person.next_action_date or dt.date.today())
            if st.form_submit_button("Save next action"):
                with session_scope() as db2:
                    people.set_next_action(db2, person.person_id, NextAction(na), na_date)
                st.success("Saved.")
                st.rerun()


# --------------------------------------------------------------------------
# Activity review
# --------------------------------------------------------------------------

def page_activity_review():
    st.title("Activity review")
    st.caption("🔎 This entire page is RESEARCH ACTIVITY — things observed publicly, not engagement you performed.")
    with session_scope() as db:
        pending = db.execute(select(PublicActivity)).scalars().all()
        for a in pending:
            person = db.get(Person, a.person_id)
            with st.container(border=True):
                st.write(f"**{esc(person.full_name)}** ({esc(person.company.company_name) if person.company else '—'})")
                st.write(f"{fmt_dt(a.activity_date)} · {a.activity_type.value} · {esc(a.topic or '')}")
                if a.direct_url:
                    st.write(a.direct_url)
                st.write(f"Commercial relevance: {a.commercial_relevance or 'Unknown'} · Engagement opportunity: {a.engagement_opportunity or 'Unknown'}")
                st.write(f"Last engagement with this person: {fmt_dt(person.date_last_engaged)}")
                cols = st.columns(3)
                if cols[0].button("Mark reviewed", key=f"rev_{a.activity_id}"):
                    with session_scope() as db2:
                        db2.get(PublicActivity, a.activity_id).review_status = "Reviewed"
                    st.rerun()
                if cols[1].button("Mark engagement-worthy", key=f"eng_{a.activity_id}"):
                    with session_scope() as db2:
                        row = db2.get(PublicActivity, a.activity_id)
                        row.review_status = "Reviewed"
                        row.engagement_opportunity = "Strong"
                    st.rerun()
                if cols[2].button("Skip", key=f"skip_{a.activity_id}"):
                    with session_scope() as db2:
                        row = db2.get(PublicActivity, a.activity_id)
                        row.review_status = "Reviewed"
                        row.engagement_opportunity = "None"
                    st.rerun()
        if not pending:
            st.caption("No activity recorded yet — save some from a Person record.")


# --------------------------------------------------------------------------
# Leads
# --------------------------------------------------------------------------

def page_leads():
    st.title("Leads")
    with session_scope() as db:
        rows = leads.list_leads(db)
        table = []
        for l in rows:
            person = db.get(Person, l.person_id)
            company = db.get(Company, l.company_id) if l.company_id else None
            age = sales_cycle.days_between(l.lead_created_date, now_naive())
            table.append(
                {
                    "Lead": f"{person.full_name}",
                    "Company": company.company_name if company else "—",
                    "Person": person.full_name,
                    "Source": l.lead_source.value,
                    "Created": fmt_dt(l.lead_created_date),
                    "Reason": l.lead_reason,
                    "Stage": l.lead_stage.value,
                    "Age (days)": age,
                    "Next step": l.next_step or "—",
                    "Next step date": fmt_dt(l.next_step_date),
                }
            )
        st.dataframe(pd.DataFrame(table), hide_index=True, use_container_width=True)


# --------------------------------------------------------------------------
# Opportunities
# --------------------------------------------------------------------------

def page_opportunities():
    st.title("Opportunities")
    with session_scope() as db:
        rows = opportunities.list_opportunities(db)
        table = []
        for o in rows:
            company = db.get(Company, o.company_id) if o.company_id else None
            contact = db.get(Person, o.primary_contact_id) if o.primary_contact_id else None
            days_open = sales_cycle.days_between(o.qualified_date, o.actual_close_date or now_naive())
            table.append(
                {
                    "Opportunity": o.opportunity_name,
                    "Company": company.company_name if company else "—",
                    "Primary contact": contact.full_name if contact else "—",
                    "Stage": o.stage.value,
                    "Estimated value": o.estimated_value,
                    "Days open": days_open,
                    "Expected close": fmt_dt(o.expected_close_date),
                    "Next step": o.next_step or "—",
                    "Outcome": o.stage.value if o.stage.value in ("Won", "Lost") else "Open",
                }
            )
        st.dataframe(pd.DataFrame(table), hide_index=True, use_container_width=True)

        if rows:
            st.divider()
            names = [o.opportunity_name for o in rows]
            idx = st.selectbox("Advance an opportunity", range(len(names)), format_func=lambda i: names[i])
            opp = rows[idx]
            from src.enums import OpportunityStage
            opts = enum_options(OpportunityStage)
            target = st.selectbox("Target stage", opts, index=opts.index(opp.stage.value))
            lost_reason = st.text_input("Lost reason (only if moving to Lost)")
            if st.button("Advance"):
                try:
                    with session_scope() as db2:
                        opportunities.advance_opportunity_stage(
                            db2, opp.opportunity_id, OpportunityStage(target), lost_reason=lost_reason or None
                        )
                    st.success("Opportunity advanced.")
                    st.rerun()
                except StageTransitionError as e:
                    st.error(str(e))


# --------------------------------------------------------------------------
# Learning review
# --------------------------------------------------------------------------

def page_learning_review():
    st.title("Learning review")
    with session_scope() as db:
        funnel = metrics.compute_funnel(db)
        rates = metrics.compute_conversion_rates(funnel)

        st.subheader("Funnel totals")
        cols = st.columns(4)
        cols[0].metric("Researched accounts", funnel.researched_accounts)
        cols[1].metric("People researched", funnel.people_researched)
        cols[2].metric("People engaged", funnel.people_engaged)
        cols[3].metric("Connections created", funnel.connections_created)
        cols = st.columns(4)
        cols[0].metric("Conversations started", funnel.conversations_started)
        cols[1].metric("Leads created", funnel.leads_created)
        cols[2].metric("Qualified opportunities", funnel.qualified_opportunities)
        cols[3].metric("Clients won", funnel.clients_won)

        st.subheader("Conversion rates")
        rate_rows = [
            ("Research → access", rates.research_to_access),
            ("Access → engagement", rates.access_to_engagement),
            ("Engagement response rate", rates.engagement_response),
            ("Conversation rate", rates.conversation),
            ("Lead creation rate", rates.lead_creation),
            ("Qualification rate", rates.qualification),
            ("Call-booking rate", rates.call_booking),
            ("Proposal rate", rates.proposal),
            ("Win rate", rates.win),
            ("Research → client", rates.research_to_client),
        ]
        st.dataframe(
            pd.DataFrame([{"Rate": name, "Display": r.display} for name, r in rate_rows]),
            hide_index=True,
        )

        st.subheader("Sales-cycle duration (average / median)")
        all_people = people.list_people(db)
        lead_cycles = [sales_cycle.compute_person_cycle_metrics(db, p).lead_cycle_days for p in all_people]
        complete_cycles = [sales_cycle.compute_person_cycle_metrics(db, p).complete_cycle_days for p in all_people]
        lc_avg, lc_med, lc_n = sales_cycle.average_and_median(lead_cycles)
        cc_avg, cc_med, cc_n = sales_cycle.average_and_median(complete_cycles)
        c1, c2 = st.columns(2)
        c1.metric("Lead → Qualified (avg / median days)", f"{lc_avg or 'n/a'} / {lc_med or 'n/a'} (n={lc_n})")
        c2.metric("Lead → Final decision (avg / median days)", f"{cc_avg or 'n/a'} / {cc_med or 'n/a'} (n={cc_n})")

        st.subheader("Results by category")
        st.dataframe(pd.DataFrame([vars(r) for r in learning.results_by_category(db)]), hide_index=True)
        st.subheader("Results by revenue band")
        st.dataframe(pd.DataFrame([vars(r) for r in learning.results_by_revenue_band(db)]), hide_index=True)
        st.subheader("Results by country")
        st.dataframe(pd.DataFrame([vars(r) for r in learning.results_by_country(db)]), hide_index=True)
        st.subheader("Results by buyer role")
        st.dataframe(pd.DataFrame([vars(r) for r in learning.results_by_buyer_role(db)]), hide_index=True)
        st.subheader("Results by trigger")
        st.dataframe(pd.DataFrame([vars(r) for r in learning.results_by_trigger(db)]), hide_index=True)
        st.subheader("Results by action type")
        st.dataframe(pd.DataFrame([vars(r) for r in learning.results_by_action_type(db)]), hide_index=True)
        st.subheader("Results by lead source")
        st.dataframe(pd.DataFrame([vars(r) for r in learning.results_by_lead_source(db)]), hide_index=True)
        st.subheader("Results by role-conflict level")
        st.dataframe(pd.DataFrame([vars(r) for r in learning.results_by_role_conflict(db)]), hide_index=True)

        st.divider()
        version = icp_versions.get_current_version(db)
        if version:
            st.subheader(f"Current ICP: {version.version_name}")
            st.caption(version.company_definition)


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

def sidebar_export():
    st.sidebar.divider()
    if st.sidebar.button("Export all data to CSV"):
        from src.imports import export_all
        with session_scope() as db:
            paths = export_all(db)
        st.sidebar.success(f"Exported {len(paths)} files to data/exports/")


def main():
    st.sidebar.title("ICP Relationship CRM")
    page = st.sidebar.radio("Go to", PAGES)
    sidebar_export()

    if page == "Today":
        page_today()
    elif page == "Companies":
        page_companies()
    elif page == "Company record":
        page_company_record()
    elif page == "People":
        page_people()
    elif page == "Person record":
        page_person_record()
    elif page == "Activity review":
        page_activity_review()
    elif page == "Leads":
        page_leads()
    elif page == "Opportunities":
        page_opportunities()
    elif page == "Learning review":
        page_learning_review()


if __name__ == "__main__":
    main()
