from backend.app.models.meeting_schema import (
    ActionItemExtraction,
    DecisionExtraction,
    MeetingSummaryExtraction,
    OverviewExtraction,
    PendingDiscussionExtraction,
    TopicExtraction,
)
from backend.app.services.validation_service import (
    evidence_in_transcript,
    looks_like_suggestion,
    validate_action_items,
    validate_decisions,
    validate_summary,
)


TRANSCRIPT = (
    "Weekly product meeting. Priya said the onboarding flow is still confusing for new users. "
    "We decided to ship the simplified checkout this Friday. "
    "Alex will update the release notes by Thursday. "
    "We should maybe consider a new pricing page. "
    "Open question: should we hire a contractor for design support?"
)


def test_missing_owner_returns_null():
    items = validate_action_items(
        [
            ActionItemExtraction(
                task="Update the release notes",
                owner=None,
                due_date="Thursday",
                evidence="Alex will update the release notes by Thursday.",
            )
        ],
        TRANSCRIPT,
    )
    assert items[0].owner is None
    assert items[0].due_date == "Thursday"


def test_missing_due_date_returns_null():
    items = validate_action_items(
        [
            ActionItemExtraction(
                task="Update the release notes",
                owner="Alex",
                due_date=None,
                evidence="Alex will update the release notes by Thursday.",
            )
        ],
        TRANSCRIPT,
    )
    assert items[0].owner == "Alex"
    assert items[0].due_date is None


def test_invented_owner_is_cleared_and_flagged():
    items = validate_action_items(
        [
            ActionItemExtraction(
                task="Update the release notes",
                owner="Morgan",
                due_date="Thursday",
                evidence="Alex will update the release notes by Thursday.",
            )
        ],
        TRANSCRIPT,
    )
    assert items[0].owner is None
    assert items[0].needs_review is True
    assert any("owner" in reason.lower() for reason in items[0].review_reasons)


def test_evidence_not_in_transcript_is_flagged():
    assert evidence_in_transcript("this quote is not in the notes", TRANSCRIPT) is False
    decisions = validate_decisions(
        [
            DecisionExtraction(
                statement="We will acquire a competitor",
                evidence="We will acquire a competitor next quarter.",
            )
        ],
        TRANSCRIPT,
    )
    assert decisions[0].needs_review is True
    assert any("not found" in reason.lower() for reason in decisions[0].review_reasons)


def test_suggestion_versus_confirmed_decision():
    suggestion_evidence = "We should maybe consider a new pricing page."
    assert looks_like_suggestion(suggestion_evidence) is True
    decisions = validate_decisions(
        [
            DecisionExtraction(
                statement="Consider a new pricing page",
                evidence=suggestion_evidence,
            ),
            DecisionExtraction(
                statement="Ship the simplified checkout this Friday",
                evidence="We decided to ship the simplified checkout this Friday.",
            ),
        ],
        TRANSCRIPT,
    )
    flagged = next(item for item in decisions if "pricing" in item.statement.lower())
    confirmed = next(item for item in decisions if "checkout" in item.statement.lower())
    assert flagged.needs_review is True
    assert any("suggestion" in reason.lower() for reason in flagged.review_reasons)
    assert confirmed.needs_review is False


def test_empty_extraction_is_insufficient():
    summary = validate_summary(
        MeetingSummaryExtraction(
            overview=OverviewExtraction(text="", evidence=None),
            topics=[],
            decisions=[],
            action_items=[],
            pending_discussions=[],
        ),
        TRANSCRIPT,
    )
    assert summary.insufficient_information is True


def test_supported_extraction_is_not_insufficient():
    summary = validate_summary(
        MeetingSummaryExtraction(
            overview=OverviewExtraction(
                text="The team discussed onboarding and decided to ship simplified checkout.",
                evidence="We decided to ship the simplified checkout this Friday.",
            ),
            topics=[
                TopicExtraction(
                    title="Onboarding",
                    explanation="New users still find onboarding confusing.",
                    evidence="Priya said the onboarding flow is still confusing for new users.",
                )
            ],
            decisions=[
                DecisionExtraction(
                    statement="Ship simplified checkout this Friday",
                    evidence="We decided to ship the simplified checkout this Friday.",
                )
            ],
            action_items=[
                ActionItemExtraction(
                    task="Update the release notes",
                    owner="Alex",
                    due_date="Thursday",
                    evidence="Alex will update the release notes by Thursday.",
                )
            ],
            pending_discussions=[
                PendingDiscussionExtraction(
                    item="Whether to hire a contractor for design support",
                    evidence="Open question: should we hire a contractor for design support?",
                )
            ],
        ),
        TRANSCRIPT,
    )
    assert summary.insufficient_information is False
    assert summary.action_items[0].owner == "Alex"
