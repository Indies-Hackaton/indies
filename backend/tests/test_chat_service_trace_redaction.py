import unittest

from app.services.chat_service import _redact_llm_request_for_client


class ChatServiceTraceRedactionTests(unittest.TestCase):
    def test_system_prompt_is_redacted_without_mutating_original(self) -> None:
        request_json = {
            "model": "minimax-test",
            "messages": [
                {"role": "system", "content": "secret prompt"},
                {"role": "user", "content": "analiza asesores marzo 2026"},
            ],
        }

        redacted = _redact_llm_request_for_client(request_json)

        self.assertEqual(
            redacted["messages"][0]["content"],
            "[redacted: internal system prompt]",
        )
        self.assertEqual(
            redacted["messages"][1]["content"],
            "analiza asesores marzo 2026",
        )
        self.assertEqual(request_json["messages"][0]["content"], "secret prompt")


if __name__ == "__main__":
    unittest.main()
