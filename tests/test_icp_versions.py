from __future__ import annotations

import pytest

from src.icp_versions import (
    create_initial_version,
    get_version,
    list_versions,
    propose_change,
    approve_version,
)


def test_initial_version_is_created_and_idempotent(session):
    v1 = create_initial_version(session)
    v1_again = create_initial_version(session)
    assert v1.version_id == v1_again.version_id
    assert len(list_versions(session)) == 1


def test_propose_change_does_not_write_to_database(session):
    create_initial_version(session)
    proposal = propose_change(
        existing_rule="Core band $8M-$30M",
        proposed_rule="Core band $8M-$40M",
        evidence="3 of 4 core-fit companies were above $20M",
        companies_involved=4,
        people_involved=4,
        actions_involved=0,
        observed_outcomes="No conversions yet — too early to tell.",
    )
    # Nothing persisted by propose_change alone.
    assert len(list_versions(session)) == 1
    assert proposal.companies_involved == 4


def test_new_version_requires_explicit_human_approval(session):
    create_initial_version(session)
    proposal = propose_change(
        existing_rule="x", proposed_rule="y", evidence="z",
        companies_involved=1, people_involved=1, actions_involved=1, observed_outcomes="n/a",
    )
    with pytest.raises(ValueError):
        approve_version(session, version_name="ICP Version 1.1", proposal=proposal, approved=False)
    assert len(list_versions(session)) == 1


def test_approved_new_version_is_persisted_and_prior_version_untouched(session):
    v1 = create_initial_version(session)
    original_definition = v1.company_definition

    proposal = propose_change(
        existing_rule="Core band $8M-$30M",
        proposed_rule="Core band $8M-$40M",
        evidence="Observed outcomes across 22 companies",
        companies_involved=22, people_involved=24, actions_involved=0,
        observed_outcomes="4 Core, 3 Secondary, 6 Monitor, 9 Reject",
    )
    v1_1 = approve_version(
        session,
        version_name="ICP Version 1.1",
        proposal=proposal,
        approved=True,
        company_definition="Core band $8M-$40M",
    )
    assert v1_1.version_name == "ICP Version 1.1"
    assert len(list_versions(session)) == 2

    session.refresh(v1)
    assert v1.company_definition == original_definition  # immutable, not mutated in place


def test_versions_are_immutable_cannot_recreate_same_name(session):
    create_initial_version(session)
    proposal = propose_change(
        existing_rule="a", proposed_rule="b", evidence="c",
        companies_involved=0, people_involved=0, actions_involved=0, observed_outcomes="n/a",
    )
    with pytest.raises(ValueError):
        approve_version(session, version_name="ICP Version 1", proposal=proposal, approved=True)
