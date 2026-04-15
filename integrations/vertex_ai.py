"""
Vertex AI (Gemini) integration for MOH claim management.

Adapted from the Apps Script ``VertexAi.js`` in
https://github.com/googleworkspace/google-chat-samples/tree/62dd4336f/
apps-script/issue-management-app/4-inclusivity-help

Provides:
* ``summarize_space`` – Gemini-powered summarisation of a Chat space conversation.
* ``get_inclusivity_feedback`` – flag words that go against inclusivity.
"""

from __future__ import annotations

import httpx

DEFAULT_LOCATION = "us-central1"
GEMINI_MODEL = "gemini-1.0-pro"


class VertexAIClient:
    """Async Vertex AI client for Gemini text generation."""

    def __init__(
        self,
        project_id: str = "",
        location_id: str = DEFAULT_LOCATION,
    ) -> None:
        self.project_id = project_id
        self.location_id = location_id

    def _endpoint(self) -> str:
        return (
            f"https://{self.location_id}-aiplatform.googleapis.com/v1"
            f"/projects/{self.project_id}/locations/{self.location_id}"
            f"/publishers/google/models/{GEMINI_MODEL}:generateContent"
        )

    @staticmethod
    def _build_request(prompt: str) -> dict:
        return {
            "contents": {
                "role": "user",
                "parts": {"text": prompt},
            },
            "safetySettings": {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_LOW_AND_ABOVE",
            },
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.8,
                "topK": 40,
            },
        }

    async def _generate(self, prompt: str, oauth_token: str) -> str:
        """Call the Gemini generateContent endpoint and return the text."""
        headers = {
            "Authorization": f"Bearer {oauth_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self._endpoint(),
                headers=headers,
                json=self._build_request(prompt),
                timeout=30.0,
            )
            resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

    async def summarize_space(self, history: str, oauth_token: str = "") -> str:
        """
        Summarise a Google Chat space conversation.

        Mirrors ``summarizeSpace`` from the Apps Script VertexAi.js.

        Args:
            history: Newline-separated "SenderName: message" history.
            oauth_token: Bearer token for the Vertex AI API.

        Returns:
            A short summary string.
        """
        prompt = (
            "Summarize the following conversation between engineers resolving an issue"
            " in a few sentences.\n\n" + history
        )
        return await self._generate(prompt, oauth_token)

    async def get_inclusivity_feedback(
        self, text: str, oauth_token: str = ""
    ) -> str:
        """
        Check *text* for words that go against inclusivity.

        Mirrors ``getInclusivityFeedback`` from the Apps Script VertexAi.js.

        Returns:
            ``"It's inclusive!"`` when no issues are found, otherwise a
            comma-separated list of problematic words.
        """
        prompt = (
            "Are there any words that obviously go against inclusivity in this text:"
            f"\n\n----------\n{text}\n----------\n\n"
            "If there are not, answer \"It's inclusive!\" "
            "otherwise answer by listing them separated by commas. "
            "Do not answer with any explanation."
        )
        return await self._generate(prompt, oauth_token)
