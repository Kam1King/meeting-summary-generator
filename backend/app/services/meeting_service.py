from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.models.database_models import Meeting
from backend.app.models.meeting_schema import (
    MeetingListItem,
    MeetingResponse,
    MeetingSummary,
    MeetingSummaryExtraction,
    OverviewExtraction,
    SectionName,
)
from backend.app.services.llm_service import LLMService
from backend.app.services.validation_service import validate_summary


def derive_title(transcript: str, requested_title: Optional[str] = None) -> str:
    if requested_title and requested_title.strip():
        return requested_title.strip()[:255]
    for line in transcript.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned[:255]
    return "Untitled meeting"


def _iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat() + "Z"


def meeting_to_response(meeting: Meeting) -> MeetingResponse:
    return MeetingResponse(
        id=meeting.id,
        title=meeting.title,
        transcript=meeting.transcript,
        summary=MeetingSummary.model_validate(meeting.summary_json),
        created_at=_iso(meeting.created_at),
        updated_at=_iso(meeting.updated_at),
    )


class MeetingService:
    """Coordinates transcript processing, validation, and persistence.

    Future audio transcription should call process_transcript() with a
    normalized transcript string instead of reaching Gemini or the database
    directly.
    """

    def __init__(self, db: Session, llm: Optional[LLMService] = None):
        self.db = db
        self.llm = llm or LLMService()

    def process_transcript(self, transcript: str) -> MeetingSummary:
        extraction = self.llm.generate_summary(transcript)
        return validate_summary(extraction, transcript)

    def create_meeting(self, transcript: str, title: Optional[str] = None) -> MeetingResponse:
        summary = self.process_transcript(transcript)
        meeting = Meeting(
            title=derive_title(transcript, title),
            transcript=transcript,
            summary_json=summary.model_dump(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(meeting)
        self.db.commit()
        self.db.refresh(meeting)
        return meeting_to_response(meeting)

    def list_meetings(self) -> list[MeetingListItem]:
        rows = self.db.query(Meeting).order_by(Meeting.created_at.desc()).all()
        return [
            MeetingListItem(id=row.id, title=row.title, created_at=_iso(row.created_at))
            for row in rows
        ]

    def get_meeting(self, meeting_id: int) -> Optional[MeetingResponse]:
        meeting = self.db.get(Meeting, meeting_id)
        if meeting is None:
            return None
        return meeting_to_response(meeting)

    def update_meeting(
        self,
        meeting_id: int,
        summary: MeetingSummary,
        title: Optional[str] = None,
    ) -> Optional[MeetingResponse]:
        meeting = self.db.get(Meeting, meeting_id)
        if meeting is None:
            return None
        if title and title.strip():
            meeting.title = title.strip()[:255]
        meeting.summary_json = summary.model_dump()
        meeting.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(meeting)
        return meeting_to_response(meeting)

    def regenerate_section(self, meeting_id: int, section: SectionName) -> Optional[MeetingResponse]:
        meeting = self.db.get(Meeting, meeting_id)
        if meeting is None:
            return None

        current = MeetingSummary.model_validate(meeting.summary_json)
        section_payload = self.llm.generate_section(meeting.transcript, section)
        current_dump = current.model_dump()
        merged_extraction = MeetingSummaryExtraction(
            overview=OverviewExtraction.model_validate(
                section_payload["overview"] if section == SectionName.overview else current_dump["overview"]
            ),
            topics=section_payload["topics"] if section == SectionName.topics else current_dump["topics"],
            decisions=section_payload["decisions"] if section == SectionName.decisions else current_dump["decisions"],
            action_items=(
                section_payload["action_items"]
                if section == SectionName.action_items
                else current_dump["action_items"]
            ),
            pending_discussions=(
                section_payload["pending_discussions"]
                if section == SectionName.pending_discussions
                else current_dump["pending_discussions"]
            ),
        )
        validated = validate_summary(merged_extraction, meeting.transcript)

        # Preserve already-saved sections exactly; only replace the requested one.
        if section == SectionName.overview:
            current.overview = validated.overview
        elif section == SectionName.topics:
            current.topics = validated.topics
        elif section == SectionName.decisions:
            current.decisions = validated.decisions
        elif section == SectionName.action_items:
            current.action_items = validated.action_items
        elif section == SectionName.pending_discussions:
            current.pending_discussions = validated.pending_discussions

        current.insufficient_information = not any(
            [
                bool(current.overview.text.strip()),
                current.topics,
                current.decisions,
                current.action_items,
                current.pending_discussions,
            ]
        )
        meeting.summary_json = current.model_dump()
        meeting.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(meeting)
        return meeting_to_response(meeting)
