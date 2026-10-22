"""Unit tests for the Google Gemini AI Copilot service."""

import unittest
import uuid
from unittest.mock import AsyncMock, patch

from app.services.copilot_service import CopilotService


class TestCopilotService(unittest.IsolatedAsyncioTestCase):
    """Test suite for Gemini-powered CopilotService."""

    def test_history_conversion(self) -> None:
        """Verify conversion of internal conversation history to Gemini Content objects."""
        history = [
            {"role": "assistant", "content": "Initial assistant greeting to drop"},
            {"role": "user", "content": "Hello AYE Vision"},
            {"role": "assistant", "content": "Hello! How can I assist you with surveillance today?"},
            {"role": "user", "content": "How many cameras are online?"},
        ]

        contents = CopilotService._history_to_gemini_contents(history)
        # The first message must be a user turn
        self.assertEqual(len(contents), 3)
        self.assertEqual(contents[0].role, "user")
        self.assertEqual(contents[0].parts[0].text, "Hello AYE Vision")
        self.assertEqual(contents[1].role, "model")
        self.assertEqual(contents[1].parts[0].text, "Hello! How can I assist you with surveillance today?")
        self.assertEqual(contents[2].role, "user")
        self.assertEqual(contents[2].parts[0].text, "How many cameras are online?")

    def test_history_consecutive_merge(self) -> None:
        """Verify consecutive messages with the same role are merged cleanly."""
        history = [
            {"role": "user", "content": "First line"},
            {"role": "user", "content": "Second line"},
            {"role": "assistant", "content": "Answer part 1"},
            {"role": "assistant", "content": "Answer part 2"},
        ]

        contents = CopilotService._history_to_gemini_contents(history)
        self.assertEqual(len(contents), 2)
        self.assertEqual(contents[0].role, "user")
        self.assertIn("First line\n\nSecond line", contents[0].parts[0].text)
        self.assertEqual(contents[1].role, "model")
        self.assertIn("Answer part 1\n\nAnswer part 2", contents[1].parts[0].text)

    async def test_copilot_service_unconfigured(self) -> None:
        """Ensure CopilotService returns graceful message when GEMINI_API_KEY is not set."""
        with patch("app.services.copilot_service.get_settings") as mock_settings:
            mock_settings.return_value.GEMINI_API_KEY = ""
            mock_settings.return_value.ANTHROPIC_API_KEY = ""
            mock_settings.return_value.GEMINI_MODEL = "gemini-3.6-flash"

            service = CopilotService()
            self.assertIsNone(service._client)

            mock_redis = AsyncMock()
            mock_redis.get.return_value = None
            mock_redis.set.return_value = True
            service._redis = mock_redis

            mock_db = AsyncMock()
            res = await service.chat(
                db=mock_db,
                org_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                message="Check all cameras",
            )

            self.assertIn("response_text", res)
            self.assertIn("conversation_id", res)
            self.assertIn("data_cards", res)
            self.assertIn("suggested_followups", res)
            self.assertTrue(
                "not configured" in res["response_text"].lower()
                or "gemini_api_key" in res["response_text"].lower()
            )


if __name__ == "__main__":
    unittest.main()
