class LLMError(Exception):
    """Base class for LLM integration failures."""


class LLMConfigurationError(LLMError):
    """Missing or invalid Gemini configuration."""


class LLMRateLimitError(LLMError):
    """Gemini rate limit reached."""


class LLMResponseError(LLMError):
    """Empty, invalid, or unexpected Gemini output."""
