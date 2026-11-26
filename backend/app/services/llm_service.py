from typing import Any, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from backend.app.config import Settings, get_settings
from backend.app.models.meeting_schema import (
    SECTION_SCHEMAS,
    MeetingSummaryExtraction,
    SectionName,
)
from backend.app.services.llm_errors import LLMConfigurationError, LLMRateLimitError, LLMResponseError
from backend.app.services.prompt_service import SYSTEM_INSTRUCTION, build_section_prompt, build_summary_prompt


class LLMService:
    """Gemini-backed extractor. Swap this class to replace the AI provider."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        if not self.settings.gemini_configured:
            raise LLMConfigurationError(
                "Gemini API key is not configured. Add GEMINI_API_KEY to backend/.env "
                "and restart the server. Get a key from Google AI Studio."
            )
        if self._client is None:
            self._client = genai.Client(api_key=self.settings.gemini_api_key)
        return self._client

    def generate_summary(self, transcript: str) -> MeetingSummaryExtraction:
        payload = self._generate(
            prompt=build_summary_prompt(transcript),
            schema=MeetingSummaryExtraction,
        )
        try:
            return MeetingSummaryExtraction.model_validate(payload)
        except ValidationError as exc:
            raise LLMResponseError("Gemini returned a summary that did not match the expected structure.") from exc

    def generate_section(self, transcript: str, section: SectionName) -> dict[str, Any]:
        schema = SECTION_SCHEMAS[section]
        payload = self._generate(
            prompt=build_section_prompt(transcript, section),
            schema=schema,
        )
        try:
            parsed = schema.model_validate(payload)
        except ValidationError as exc:
            raise LLMResponseError(
                f"Gemini returned an invalid {section.value} section."
            ) from exc
        return parsed.model_dump()

    def _generate(self, prompt: str, schema: type[BaseModel]) -> Any:
        try:
            response = self.client.models.generate_content(
                model=self.settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
        except Exception as exc:
            self._raise_mapped_error(exc)

        if response is None:
            raise LLMResponseError("Gemini returned an empty response.")

        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            if isinstance(parsed, BaseModel):
                return parsed.model_dump()
            if isinstance(parsed, dict):
                return parsed
            if hasattr(parsed, "model_dump"):
                return parsed.model_dump()

        text = (getattr(response, "text", None) or "").strip()
        if not text:
            raise LLMResponseError("Gemini returned an empty JSON payload.")
        try:
            return schema.model_validate_json(text).model_dump()
        except ValidationError as exc:
            raise LLMResponseError("Gemini returned invalid JSON for the meeting summary.") from exc

    def _raise_mapped_error(self, exc: Exception) -> None:
        message = str(exc).lower()
        status = getattr(exc, "status_code", None) or getattr(exc, "code", None)

        if status in {401, 403} or "api key" in message or "permission" in message or "unauthenticated" in message:
            raise LLMConfigurationError(
                "The Gemini API key is invalid or unauthorized. Check GEMINI_API_KEY in backend/.env."
            ) from exc
        if status == 429 or "resource exhausted" in message or "rate" in message or "quota" in message:
            raise LLMRateLimitError(
                "Gemini rate limit reached. Wait a moment and try again."
            ) from exc
        if status == 404 or "not found" in message or "is not found" in message:
            raise LLMConfigurationError(
                f"Gemini model '{self.settings.gemini_model}' is not available for this API key. "
                "Set GEMINI_MODEL in backend/.env to a model your account can access."
            ) from exc
        if "json" in message:
            raise LLMResponseError("Gemini returned output that could not be parsed as JSON.") from exc
        raise LLMResponseError("The Gemini service could not generate a summary. Try again.") from exc
