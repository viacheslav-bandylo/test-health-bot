"""Tests for per-user rate limiter."""

import asyncio
import time

import pytest

from hea.bot.rate_limiter import RateLimiter


class TestRateLimiter:
    def test_first_request_allowed(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        assert limiter.is_allowed(chat_id=123) is True

    def test_requests_within_limit_allowed(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        assert limiter.is_allowed(123) is True
        assert limiter.is_allowed(123) is True
        assert limiter.is_allowed(123) is True

    def test_exceeding_limit_denied(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        assert limiter.is_allowed(123) is True
        assert limiter.is_allowed(123) is True
        assert limiter.is_allowed(123) is False

    def test_different_users_independent(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.is_allowed(1) is True
        assert limiter.is_allowed(2) is True
        assert limiter.is_allowed(1) is False
        assert limiter.is_allowed(2) is False

    def test_window_expiry_resets_count(self):
        limiter = RateLimiter(max_requests=1, window_seconds=0.1)
        assert limiter.is_allowed(123) is True
        assert limiter.is_allowed(123) is False
        time.sleep(0.15)
        assert limiter.is_allowed(123) is True


class TestMessageLengthValidation:
    def test_message_within_limit(self):
        from hea.bot.rate_limiter import validate_message_length

        text = "Hello, I'm 35 years old"
        result = validate_message_length(text, max_length=500)
        assert result == text

    def test_message_exceeding_limit_truncated(self):
        from hea.bot.rate_limiter import validate_message_length

        text = "x" * 1000
        result = validate_message_length(text, max_length=500)
        assert len(result) == 500

    def test_empty_message(self):
        from hea.bot.rate_limiter import validate_message_length

        result = validate_message_length("", max_length=500)
        assert result == ""
