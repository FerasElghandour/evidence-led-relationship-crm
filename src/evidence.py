"""Evidence records. The critical rule enforced here: an Unsupported
Assumption or a Hypothesis can be stored (so the reasoning is preserved), but
`is_actionable_for_qualification` returns False for both — callers (leads.py,
opportunities.py, relationships.py) must check this before letting evidence
justify a stage advance.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .enums import EvidenceClassification
from .models import Evidence
from .schemas import EvidenceIn

# Only these classifications may support a qualification decision or a stage
# advance. Hypothesis, Unknown, and Unsupported Assumption never do.
QUALIFYING_CLASSIFICATIONS = {
    EvidenceClassification.CONFIRMED_FACT,
    EvidenceClassification.OBSERVED_BEHAVIOUR,
    EvidenceClassification.DERIVED_METRIC,
}


def is_actionable_for_qualification(classification: EvidenceClassification) -> bool:
    return classification in QUALIFYING_CLASSIFICATIONS


def add_evidence(session: Session, data: EvidenceIn) -> Evidence:
    record = Evidence(**data.model_dump())
    session.add(record)
    session.flush()
    return record


def list_evidence(
    session: Session, company_id: Optional[int] = None, person_id: Optional[int] = None
) -> list[Evidence]:
    stmt = select(Evidence)
    if company_id:
        stmt = stmt.where(Evidence.company_id == company_id)
    if person_id:
        stmt = stmt.where(Evidence.person_id == person_id)
    return list(session.execute(stmt.order_by(Evidence.created_at.desc())).scalars())


def has_icp_approval_evidence(session: Session, company_id: int) -> bool:
    """ICP Approved gate: at least one structured Evidence row exists for
    this company, of any classification EXCEPT Unsupported Assumption.

    This is deliberately a lower bar than `is_actionable_for_qualification`
    (which reserves Confirmed Fact / Observed Behaviour / Derived Metric for
    live commercial-qualification decisions on leads/opportunities). Company
    ICP fit is inherently a research judgment built from public, imperfect
    data — Inference and Hypothesis records legitimately support it. What
    they must NOT do is stand in for a source-dependent access-gate check
    (see activities.has_access_confirmed_evidence), and a bare
    classification/fit column with zero supporting Evidence rows never
    qualifies at all — that is the exact gap this function closes."""
    rows = list_evidence(session, company_id=company_id)
    return any(r.classification != EvidenceClassification.UNSUPPORTED_ASSUMPTION for r in rows)
