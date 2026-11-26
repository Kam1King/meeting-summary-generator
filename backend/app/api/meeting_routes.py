from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database.database import get_db
from backend.app.models.meeting_schema import (
    CreateMeetingRequest,
    HealthResponse,
    MeetingListItem,
    MeetingResponse,
    RegenerateRequest,
    UpdateMeetingRequest,
)
from backend.app.services.llm_errors import LLMConfigurationError, LLMRateLimitError, LLMResponseError
from backend.app.services.meeting_service import MeetingService

router = APIRouter()


def get_meeting_service(db: Session = Depends(get_db)) -> MeetingService:
    return MeetingService(db)


def _http_for_llm_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LLMConfigurationError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    if isinstance(exc, LLMRateLimitError):
        return HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc))
    if isinstance(exc, LLMResponseError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected server error.")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        gemini_configured=settings.gemini_configured,
        model=settings.gemini_model,
    )


@router.post("/api/meetings", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
def create_meeting(
    payload: CreateMeetingRequest,
    service: MeetingService = Depends(get_meeting_service),
) -> MeetingResponse:
    try:
        return service.create_meeting(payload.transcript, payload.title)
    except (LLMConfigurationError, LLMRateLimitError, LLMResponseError) as exc:
        raise _http_for_llm_error(exc) from exc


@router.get("/api/meetings", response_model=list[MeetingListItem])
def list_meetings(service: MeetingService = Depends(get_meeting_service)) -> list[MeetingListItem]:
    return service.list_meetings()


@router.get("/api/meetings/{meeting_id}", response_model=MeetingResponse)
def get_meeting(
    meeting_id: int,
    service: MeetingService = Depends(get_meeting_service),
) -> MeetingResponse:
    meeting = service.get_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found.")
    return meeting


@router.put("/api/meetings/{meeting_id}", response_model=MeetingResponse)
def update_meeting(
    meeting_id: int,
    payload: UpdateMeetingRequest,
    service: MeetingService = Depends(get_meeting_service),
) -> MeetingResponse:
    meeting = service.update_meeting(meeting_id, payload.summary, payload.title)
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found.")
    return meeting


@router.post("/api/meetings/{meeting_id}/regenerate", response_model=MeetingResponse)
def regenerate_section(
    meeting_id: int,
    payload: RegenerateRequest,
    service: MeetingService = Depends(get_meeting_service),
) -> MeetingResponse:
    try:
        meeting = service.regenerate_section(meeting_id, payload.section)
    except (LLMConfigurationError, LLMRateLimitError, LLMResponseError) as exc:
        raise _http_for_llm_error(exc) from exc
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found.")
    return meeting
