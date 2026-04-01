"""Custom exceptions for LLM client errors."""


class LLMError(Exception):
    """Base exception for LLM-related errors."""


class LLMTimeoutError(LLMError):
    """LLM request timed out."""


class LLMAPIError(LLMError):
    """LLM API returned an error status code."""


class LLMParseError(LLMError):
    """Failed to parse LLM response."""
