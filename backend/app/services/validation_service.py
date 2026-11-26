import re
from typing import Optional

from backend.app.models.meeting_schema import (
    ActionItem,
    ActionItemExtraction,
    Decision,
    DecisionExtraction,
    MeetingSummary,
    MeetingSummaryExtraction,
    Overview,
    OverviewExtraction,
    PendingDiscussion,
    PendingDiscussionExtraction,
    Topic,
    TopicExtraction,
)

SUGGESTION_CUES = (
    "should we",
    "we should",
    "maybe",
    "perhaps",
    "i suggest",
    "we could",
    "could we",
    "what if",
    "propose",
    "proposal",
    "might want",
    "consider",
    "how about",
)
CONFIRMATION_CUES = (
    "we decided",
    "it was decided",
    "we agreed",
    "agreed to",
    "approved",
    "we will",
    "we'll",
    "confirmed",
    "the decision is",
    "going with",
    "finalized",
    "signed off",
)


def normalize_text(value: str) -> str:
    collapsed = re.sub(r"\s+", " ", value or "")
    return collapsed.strip().lower()


def evidence_in_transcript(evidence: Optional[str], transcript: str) -> bool:
    if not evidence:
        return False
    haystack = normalize_text(transcript)
    needle = normalize_text(evidence)
    if len(needle) < 8:
        return False
    return needle in haystack


def text_in_transcript(value: Optional[str], transcript: str) -> bool:
    if not value:
        return False
    return normalize_text(value) in normalize_text(transcript)


def looks_like_suggestion(evidence: str) -> bool:
    text = normalize_text(evidence)
    has_suggestion = any(cue in text for cue in SUGGESTION_CUES)
    has_confirmation = any(cue in text for cue in CONFIRMATION_CUES)
    return has_suggestion and not has_confirmation


def _reviewable(needs_review: bool, reasons: list[str]) -> tuple[bool, list[str]]:
    unique = list(dict.fromkeys(reason for reason in reasons if reason))
    return bool(needs_review or unique), unique


def validate_overview(overview: OverviewExtraction, transcript: str) -> Overview:
    reasons: list[str] = []
    evidence = overview.evidence
    if evidence and not evidence_in_transcript(evidence, transcript):
        reasons.append("Overview evidence was not found in the transcript.")
    needs_review, reasons = _reviewable(bool(reasons), reasons)
    return Overview(text=overview.text.strip(), evidence=evidence, needs_review=needs_review, review_reasons=reasons)


def validate_topics(topics: list[TopicExtraction], transcript: str) -> list[Topic]:
    validated: list[Topic] = []
    for topic in topics:
        if not topic.title or not topic.evidence:
            continue
        reasons: list[str] = []
        if not evidence_in_transcript(topic.evidence, transcript):
            reasons.append("Topic evidence was not found in the transcript.")
        needs_review, reasons = _reviewable(bool(reasons), reasons)
        validated.append(
            Topic(
                title=topic.title,
                explanation=topic.explanation,
                evidence=topic.evidence,
                needs_review=needs_review,
                review_reasons=reasons,
            )
        )
    return validated


def validate_decisions(decisions: list[DecisionExtraction], transcript: str) -> list[Decision]:
    validated: list[Decision] = []
    for decision in decisions:
        if not decision.statement or not decision.evidence:
            continue
        reasons: list[str] = []
        if not evidence_in_transcript(decision.evidence, transcript):
            reasons.append("Decision evidence was not found in the transcript.")
        if looks_like_suggestion(decision.evidence) or looks_like_suggestion(decision.statement):
            reasons.append("This looks like a suggestion rather than a confirmed decision.")
        needs_review, reasons = _reviewable(bool(reasons), reasons)
        validated.append(
            Decision(
                statement=decision.statement,
                evidence=decision.evidence,
                needs_review=needs_review,
                review_reasons=reasons,
            )
        )
    return validated


def validate_action_items(items: list[ActionItemExtraction], transcript: str) -> list[ActionItem]:
    validated: list[ActionItem] = []
    for item in items:
        if not item.task or not item.evidence:
            continue
        reasons: list[str] = []
        owner = item.owner
        due_date = item.due_date
        if not evidence_in_transcript(item.evidence, transcript):
            reasons.append("Action item evidence was not found in the transcript.")
        if owner and not text_in_transcript(owner, transcript):
            reasons.append("Assigned owner was not found in the transcript and was cleared.")
            owner = None
        if due_date and not text_in_transcript(due_date, transcript):
            reasons.append("Due date was not found in the transcript and was cleared.")
            due_date = None
        needs_review, reasons = _reviewable(bool(reasons), reasons)
        validated.append(
            ActionItem(
                task=item.task,
                owner=owner,
                due_date=due_date,
                evidence=item.evidence,
                needs_review=needs_review,
                review_reasons=reasons,
            )
        )
    return validated


def validate_pending(items: list[PendingDiscussionExtraction], transcript: str) -> list[PendingDiscussion]:
    validated: list[PendingDiscussion] = []
    for item in items:
        if not item.item or not item.evidence:
            continue
        reasons: list[str] = []
        if not evidence_in_transcript(item.evidence, transcript):
            reasons.append("Pending discussion evidence was not found in the transcript.")
        needs_review, reasons = _reviewable(bool(reasons), reasons)
        validated.append(
            PendingDiscussion(
                item=item.item,
                evidence=item.evidence,
                needs_review=needs_review,
                review_reasons=reasons,
            )
        )
    return validated


def is_insufficient(summary: MeetingSummary) -> bool:
    has_overview = bool(summary.overview.text.strip())
    has_content = any(
        [
            has_overview,
            summary.topics,
            summary.decisions,
            summary.action_items,
            summary.pending_discussions,
        ]
    )
    return not has_content


def validate_summary(extraction: MeetingSummaryExtraction, transcript: str) -> MeetingSummary:
    summary = MeetingSummary(
        overview=validate_overview(extraction.overview, transcript),
        topics=validate_topics(extraction.topics, transcript),
        decisions=validate_decisions(extraction.decisions, transcript),
        action_items=validate_action_items(extraction.action_items, transcript),
        pending_discussions=validate_pending(extraction.pending_discussions, transcript),
    )
    summary.insufficient_information = is_insufficient(summary)
    return summary
