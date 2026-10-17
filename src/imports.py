"""Seed data: optional caller-provided seed records, and CSV
import/export helpers for everything that follows.

Seeding is idempotent — if any companies already exist, seed_initial_data()
is a no-op. Missing values are stored as None/Unknown, never invented.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from .companies import advance_company_stage, create_or_get_company, set_classification
from .database import PROJECT_ROOT, session_scope
from .employment import add_employment
from .enums import (
    BuyerRole,
    CompanyClassification,
    CompanyStage,
    EvidenceClassification,
    ExternalSupportLabel,
    FitLevel,
    RoleConflict,
    TriggerType,
)
from .evidence import add_evidence
from .icp_versions import create_initial_version
from .models import (
    Company,
    EmploymentHistory,
    EngagementAction,
    Evidence,
    ICPVersion,
    Lead,
    Opportunity,
    Outcome,
    Person,
    PublicActivity,
)
from .people import create_or_get_person
from .schemas import CompanyIn, EmploymentIn, EvidenceIn, PersonIn
from .stages import StageTransitionError

EXPORT_DIR = PROJECT_ROOT / "data" / "exports"
IMPORT_DIR = PROJECT_ROOT / "data" / "imports"

# The originally-named 5-company execution cohort (spec §18/§19). Informational
# only — membership here does NOT advance a company's stage. A company's real
# stage is earned by its own stored evidence (see
# companies.advance_company_stage / _assert_ready_for_engagement_evidence),
# never assigned because it's on this list.
ACTIVE_COHORT = set()

# --- Seed data -------------------------------------------------------------
# Fields not confirmed on LinkedIn are left as None (revenue) or "Unknown"
# (labels) rather than guessed. Use authorized source records
# for full source links; this seed carries the structured summary only.

_C = dict  # shorthand for the literal company dicts below


COMPANIES = []


def seed_initial_data(session: Optional[Session] = None) -> int:
    """Seed caller-provided records. Idempotent —
    returns 0 and does nothing if any company already exists.
    """
    if session is not None:
        return _seed(session)
    with session_scope() as s:
        return _seed(s)


def _seed(session: Session) -> int:
    existing_count = session.execute(select(Company.company_id)).first()
    if existing_count is not None:
        return 0

    create_initial_version(session)

    created = 0
    for row in COMPANIES:
        row = dict(row)  # local copy — don't mutate the module-level literal
        people = row.pop("people", [])
        classification = row.pop("company_classification")

        company_fields = {k: v for k, v in row.items() if k in CompanyIn.model_fields}
        company, was_created = create_or_get_company(session, CompanyIn(**company_fields))
        if was_created:
            created += 1
        set_classification(session, company.company_id, classification)
        row["company_classification"] = classification  # restore for the stage helper below

        # Structured Evidence rows FIRST — a classification/fit column alone
        # never satisfies the ICP Approved gate; see _import_company_evidence.
        _import_company_evidence(session, company, row)

        # Stage progression, guarded — only advance as far as the evidence allows.
        _advance_company_stage_safely(session, company, row)

        for p in people:
            person_in = PersonIn(
                full_name=p["full_name"],
                linkedin_profile_url=p["linkedin_profile_url"] or f"unknown://{company.company_name}/{p['full_name']}",
                current_title=p.get("current_title"),
                current_company_id=company.company_id,
                buyer_role=p.get("buyer_role", BuyerRole.OTHER),
                role_conflict_level=p.get("role_conflict_level", RoleConflict.UNKNOWN),
                linkedin_access_fit=p.get("linkedin_access_fit", FitLevel.UNKNOWN),
                topics_discussed=p.get("topics_discussed"),
                last_visible_activity_date=p.get("last_visible_activity_date"),
            )
            person, _ = create_or_get_person(session, person_in)
            _import_person_evidence(session, person, p)
            add_employment(
                session,
                EmploymentIn(
                    person_id=person.person_id,
                    company_id=company.company_id,
                    title=p.get("current_title"),
                    is_current=True,
                    source_url=p.get("linkedin_profile_url"),
                ),
            )

    session.flush()
    return created


def _import_company_evidence(session: Session, company: Company, row: dict) -> None:
    """Convert the seed's flat research-summary fields into structured
    Evidence rows. This is historical research gathered during the ICP
    validation run that was never captured as per-fact source URLs at the
    time, so every row here uses the spec's explicit "original source
    unavailable" fallback: Inference or Hypothesis classification, Low or
    Medium reliability, source_name "Previous ICP research", source_url left
    empty, and a note explaining why. None of this can ever satisfy Access
    Confirmed (which requires a SOURCED record — see
    activities.has_access_confirmed_evidence) — it exists to give ICP
    Approved a real evidentiary basis instead of a bare imported
    classification column, and to preserve research history and
    uncertainty rather than invent precision that was never captured."""

    def _add(
        text: Optional[str],
        classification: EvidenceClassification,
        reliability: str,
        state_affected: str,
        evidence_type: str,
    ) -> None:
        if not text:
            return
        add_evidence(
            session,
            EvidenceIn(
                company_id=company.company_id,
                evidence_type=evidence_type,
                evidence_text=text,
                classification=classification,
                source_url=None,
                source_name="Previous ICP research",
                event_date=None,
                reliability=reliability,
                state_affected=state_affected,
                notes=(
                    "Imported from the prior ICP validation research summary. The "
                    "original direct source URL was not preserved in structured form "
                    "at research time, so this record cannot satisfy a source-dependent "
                    "access gate."
                ),
            ),
        )

    profile_bits = []
    if row.get("category"):
        profile_bits.append(f"Category: {row['category']}.")
    geo = row.get("country") or ""
    if row.get("city"):
        geo = f"{row['city']}, {geo}" if geo else row["city"]
    if geo:
        profile_bits.append(f"Geography: {geo}.")
    rev_min, rev_max, rev_basis = row.get("estimated_revenue_min"), row.get("estimated_revenue_max"), row.get("revenue_estimation_basis")
    if rev_min or rev_max or rev_basis:
        if rev_min and rev_max:
            rev_range = f"${rev_min:,.0f}-${rev_max:,.0f}"
        elif rev_max:
            rev_range = f"up to ${rev_max:,.0f}"
        elif rev_min:
            rev_range = f"${rev_min:,.0f}+"
        else:
            rev_range = "Unknown"
        profile_bits.append(f"Revenue estimate: {rev_range} (basis: {rev_basis or 'not established'}).")
    if row.get("channels"):
        profile_bits.append(f"Channels: {row['channels']}.")
    if row.get("founder_led") is not None:
        profile_bits.append(f"Founder-led: {row['founder_led']}.")
    _add(
        " ".join(profile_bits) or None,
        EvidenceClassification.INFERENCE,
        "Medium",
        "company_icp_fit",
        "Company profile research",
    )

    _add(
        row.get("company_icp_reason"),
        EvidenceClassification.INFERENCE,
        "Medium",
        "company_classification",
        "Classification rationale",
    )

    trigger_text = row.get("commercial_trigger")
    if trigger_text:
        trigger_type = row.get("trigger_type")
        label = (
            f"[{trigger_type.value}] {trigger_text}"
            if trigger_type and trigger_type != TriggerType.NONE
            else trigger_text
        )
        _add(label, EvidenceClassification.INFERENCE, "Medium", "commercial_trigger", "Commercial trigger research")

    _add(
        row.get("possible_external_support_reason"),
        EvidenceClassification.HYPOTHESIS,
        "Low",
        "external_support_label",
        "External-support hypothesis",
    )


def _import_person_evidence(session: Session, person: Person, p: dict) -> None:
    """Same fallback rule, scoped to a person: their researched topics are a
    real research finding, but were never captured as a dated, sourced
    activity record — so this is Inference/Low-reliability history, and it
    can never satisfy Access Confirmed on its own."""
    topics = p.get("topics_discussed")
    if not topics:
        return
    add_evidence(
        session,
        EvidenceIn(
            person_id=person.person_id,
            evidence_type="Person research summary",
            evidence_text=topics,
            classification=EvidenceClassification.INFERENCE,
            source_url=None,
            source_name="Previous ICP research",
            event_date=None,
            reliability="Low",
            state_affected="buyer_role",
            notes=(
                "Imported from the prior ICP validation research summary of this "
                "person's observed public topics. Not a dated, sourced activity "
                "record — cannot satisfy the Access Confirmed gate."
            ),
        ),
    )


def _advance_company_stage_safely(session: Session, company: Company, row: dict) -> None:
    """Move a company forward through Researching -> ICP Approved -> Access
    Confirmed only as far as its own fit/access data AND supporting evidence
    allows, or straight to Monitor/Reject for those classifications.

    Stops at Access Confirmed on purpose. Ready for Engagement additionally
    requires a stored, current public activity (direct URL, date, commercial
    relevance, engagement opportunity, Reviewed status) — evidence that
    cannot exist at seed time, since seeding only carries research summaries,
    not logged posts/comments. Advancing further than Access Confirmed here
    would be the exact "strong fit implies ready" shortcut this rule exists
    to prevent; see companies.advance_company_stage for the enforced gates.
    """
    classification = row["company_classification"]
    if classification == CompanyClassification.REJECT:
        _try_transition(session, company, CompanyStage.REJECT)
        return
    if classification == CompanyClassification.MONITOR:
        _try_transition(session, company, CompanyStage.MONITOR)
        return

    if row.get("company_icp_fit") == FitLevel.STRONG:
        _try_transition(session, company, CompanyStage.ICP_APPROVED)
        if row.get("linkedin_access_fit") == FitLevel.STRONG:
            _try_transition(session, company, CompanyStage.ACCESS_CONFIRMED)


def _try_transition(session: Session, company: Company, target: CompanyStage) -> None:
    """Route through the REAL guarded transition (companies.advance_company_stage)
    rather than mutating current_stage directly, so seeding is held to the exact
    same evidence gates as the running application — including the ICP Approved
    and Access Confirmed evidence checks, not just the raw stage-graph shape."""
    try:
        advance_company_stage(session, company.company_id, target)
    except StageTransitionError:
        return


# --- CSV import / export ----------------------------------------------------

def export_table_to_csv(session: Session, model, filename: str, out_dir: Optional[Path] = None) -> Path:
    """Export every row of `model` to CSV. Columns are always taken from the
    table schema (not inferred from the row data), so an empty table still
    exports with the correct header row instead of a blank file."""
    out_dir = out_dir or EXPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    columns = [c.name for c in model.__table__.columns]
    rows = session.execute(select(model)).scalars().all()
    records = [{c: getattr(row, c) for c in columns} for row in rows]
    df = pd.DataFrame(records, columns=columns)
    path = out_dir / filename
    df.to_csv(path, index=False)
    return path


# Full table set per the data model (spec §12): every entity gets a CSV, in
# both the default export (data/exports/) and the baseline snapshot.
EXPORT_TABLES: dict[str, type] = {
    "companies.csv": Company,
    "people.csv": Person,
    "employment.csv": EmploymentHistory,
    "evidence.csv": Evidence,
    "activities.csv": PublicActivity,
    "actions.csv": EngagementAction,
    "outcomes.csv": Outcome,
    "leads.csv": Lead,
    "opportunities.csv": Opportunity,
    "icp_versions.csv": ICPVersion,
}


def export_all(session: Session, out_dir: Optional[Path] = None) -> dict[str, Path]:
    return {
        name: export_table_to_csv(session, model, name, out_dir=out_dir)
        for name, model in EXPORT_TABLES.items()
    }


def import_companies_csv(session: Session, path: Path) -> int:
    df = pd.read_csv(path)
    created = 0
    for _, raw in df.iterrows():
        data = {k: (None if pd.isna(v) else v) for k, v in raw.to_dict().items()}
        company_in = CompanyIn(**{k: v for k, v in data.items() if k in CompanyIn.model_fields})
        _, was_created = create_or_get_company(session, company_in)
        created += int(was_created)
    return created
