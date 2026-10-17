from __future__ import annotations

from src import actions, outcomes, people
from src.enums import ActionType, OutcomeType
from src.models import TimelineEvent
from src.schemas import ActionIn, OutcomeIn, PersonIn


def test_action_creates_a_timeline_entry(session):
    person, _ = people.create_or_get_person(
        session, PersonIn(full_name="Alex Kim", linkedin_profile_url="https://www.linkedin.com/in/alexkim/")
    )
    action = actions.record_action(
        session,
        ActionIn(
            person_id=person.person_id,
            action_type=ActionType.COMMENT,
            exact_text="Direct comment text.",
            reason_for_action="They posted about retail expansion.",
        ),
    )
    events = session.query(TimelineEvent).filter_by(person_id=person.person_id).all()
    assert len(events) == 1
    assert events[0].exact_text_used == "Direct comment text."


def test_outcome_updates_relationship_history_and_interaction_count(session):
    person, _ = people.create_or_get_person(
        session, PersonIn(full_name="Jordan Ray", linkedin_profile_url="https://www.linkedin.com/in/jordanray/")
    )
    action = actions.record_action(
        session, ActionIn(person_id=person.person_id, action_type=ActionType.FOLLOW)
    )
    assert person.total_interactions == 0

    outcomes.record_outcome(
        session, OutcomeIn(action_id=action.action_id, outcome_type=OutcomeType.FOLLOW)
    )
    session.refresh(person)
    assert person.total_interactions == 1
    assert person.date_last_engaged is not None
    assert person.date_first_engaged is not None

    events = session.query(TimelineEvent).filter_by(person_id=person.person_id).all()
    event_types = {e.event_type.value for e in events}
    assert "Followed" in event_types  # action's own timeline entry
    assert "Stage change" in event_types  # outcome's mechanical relationship advance


def test_conversation_started_outcome_sets_first_conversation_date(session):
    person, _ = people.create_or_get_person(
        session, PersonIn(full_name="Casey Fox", linkedin_profile_url="https://www.linkedin.com/in/caseyfox/")
    )
    action = actions.record_action(
        session, ActionIn(person_id=person.person_id, action_type=ActionType.DIRECT_MESSAGE)
    )
    assert person.date_first_conversation is None
    outcomes.record_outcome(
        session, OutcomeIn(action_id=action.action_id, outcome_type=OutcomeType.CONVERSATION_STARTED)
    )
    session.refresh(person)
    assert person.date_first_conversation is not None
