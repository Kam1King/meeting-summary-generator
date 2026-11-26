from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class SectionName(str, Enum):
    overview = "overview"
    topics = "topics"
    decisions = "decisions"
    action_items = "action_items"
    pending_discussions = "pending_discussions"


def _strip_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned or cleaned.lower() in {"null", "none", "n/a", "na", "unknown", "not specified"}:
        return None
    return cleaned


class OverviewExtraction(BaseModel):
    text: str = Field(default="", description="Concise factual overview of the meeting.")
    evidence: Optional[str] = Field(
        default=None,
        description="Optional short quotation from the transcript that supports the overview.",
    )

    @field_validator("text", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("evidence", mode="before")
    @classmethod
    def normalize_evidence(cls, value: object) -> Optional[str]:
        return _strip_optional(str(value) if value is not None else None)


class TopicExtraction(BaseModel):
    title: str
    explanation: str
    evidence: str

    @field_validator("title", "explanation", "evidence", mode="before")
    @classmethod
    def strip_required(cls, value: object) -> str:
        return str(value or "").strip()


class DecisionExtraction(BaseModel):
    statement: str
    evidence: str

    @field_validator("statement", "evidence", mode="before")
    @classmethod
    def strip_required(cls, value: object) -> str:
        return str(value or "").strip()


class ActionItemExtraction(BaseModel):
    task: str
    owner: Optional[str] = None
    due_date: Optional[str] = None
    evidence: str

    @field_validator("task", "evidence", mode="before")
    @classmethod
    def strip_required(cls, value: object) -> str:
        return str(value or "").strip()

    @field_validator("owner", "due_date", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> Optional[str]:
        if value is None:
            return None
        return _strip_optional(str(value))


class PendingDiscussionExtraction(BaseModel):
    item: str
    evidence: str

    @field_validator("item", "evidence", mode="before")
    @classmethod
    def strip_required(cls, value: object) -> str:
        return str(value or "").strip()


class MeetingSummaryExtraction(BaseModel):
    overview: OverviewExtraction = Field(default_factory=OverviewExtraction)
    topics: list[TopicExtraction] = Field(default_factory=list)
    decisions: list[DecisionExtraction] = Field(default_factory=list)
    action_items: list[ActionItemExtraction] = Field(default_factory=list)
    pending_discussions: list[PendingDiscussionExtraction] = Field(default_factory=list)


class OverviewSectionExtraction(BaseModel):
    overview: OverviewExtraction = Field(default_factory=OverviewExtraction)


class TopicsSectionExtraction(BaseModel):
    topics: list[TopicExtraction] = Field(default_factory=list)


class DecisionsSectionExtraction(BaseModel):
    decisions: list[DecisionExtraction] = Field(default_factory=list)


class ActionItemsSectionExtraction(BaseModel):
    action_items: list[ActionItemExtraction] = Field(default_factory=list)


class PendingDiscussionsSectionExtraction(BaseModel):
    pending_discussions: list[PendingDiscussionExtraction] = Field(default_factory=list)


class ReviewableMixin(BaseModel):
    needs_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)


class Overview(ReviewableMixin):
    text: str = ""
    evidence: Optional[str] = None


class Topic(ReviewableMixin):
    title: str
    explanation: str
    evidence: str


class Decision(ReviewableMixin):
    statement: str
    evidence: str


class ActionItem(ReviewableMixin):
    task: str
    owner: Optional[str] = None
    due_date: Optional[str] = None
    evidence: str


class PendingDiscussion(ReviewableMixin):
    item: str
    evidence: str


class MeetingSummary(BaseModel):
    overview: Overview = Field(default_factory=Overview)
    topics: list[Topic] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    pending_discussions: list[PendingDiscussion] = Field(default_factory=list)
    insufficient_information: bool = False


class CreateMeetingRequest(BaseModel):
    transcript: str = Field(..., min_length=1)
    title: Optional[str] = None

    @field_validator("transcript")
    @classmethod
    def transcript_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Transcript cannot be empty.")
        if len(cleaned) < 20:
            raise ValueError("Transcript is too short to summarize. Paste the meeting notes or transcript.")
        return cleaned


class UpdateMeetingRequest(BaseModel):
    title: Optional[str] = None
    summary: MeetingSummary


class RegenerateRequest(BaseModel):
    section: SectionName


class MeetingListItem(BaseModel):
    id: int
    title: str
    created_at: str


class MeetingResponse(BaseModel):
    id: int
    title: str
    transcript: str
    summary: MeetingSummary
    created_at: str
    updated_at: str


class HealthResponse(BaseModel):
    status: str
    gemini_configured: bool
    model: str


SECTION_SCHEMAS: dict[SectionName, type[BaseModel]] = {
    SectionName.overview: OverviewSectionExtraction,
    SectionName.topics: TopicsSectionExtraction,
    SectionName.decisions: DecisionsSectionExtraction,
    SectionName.action_items: ActionItemsSectionExtraction,
    SectionName.pending_discussions: PendingDiscussionsSectionExtraction,
}
