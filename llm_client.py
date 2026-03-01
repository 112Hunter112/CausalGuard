"""
LLM Client Wrapper
==================
Dual-client architecture:
- Claude (Vertex AI) or Gemini for agent reasoning
- Gemini (Vertex AI) for Google Search grounding

Authenticate via gcloud CLI: gcloud auth application-default login
Configure via .env: GOOGLE_CLOUD_PROJECT, VERTEX_REGION, ANTHROPIC_MODEL (optional).
"""

import os
from anthropic import AsyncAnthropicVertex
from google import genai
from google.genai import types

# Env: project and region for Vertex AI
_VERTEX_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("VERTEX_PROJECT_ID") or os.getenv("GCP_PROJECT")
_VERTEX_REGION = os.getenv("VERTEX_REGION", "us-east5")
# Claude model: use short ID without @date (e.g. claude-sonnet-4-6). Enable in Vertex AI Model Garden if you get 404.
_ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")


class LLMClient:
    def __init__(self):
        if not _VERTEX_PROJECT:
            raise ValueError(
                "Set GOOGLE_CLOUD_PROJECT (or VERTEX_PROJECT_ID) in .env or in your environment. "
                "Use the project ID where Vertex AI is enabled (e.g. from gcloud config get-value project)."
            )
        self._project = _VERTEX_PROJECT
        self._region = _VERTEX_REGION
        self.claude_model = _ANTHROPIC_MODEL

        # Claude for agent reasoning (Vertex AI)
        self.claude = AsyncAnthropicVertex(
            region=self._region,
            project_id=self._project,
        )

        # Gemini for Search grounding and as fallback if Claude is unavailable
        self.gemini = genai.Client(
            vertexai=True,
            project=self._project,
            location=self._region,
        )
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    async def complete(self, prompt: str, max_tokens: int = 2048) -> str:
        """Call Claude for agent reasoning; fall back to Gemini if Claude is unavailable."""
        try:
            # Many Vertex Claude versions don't support extended thinking; use simple message call
            response = await self.claude.messages.create(
                model=self.claude_model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            parts = []
            for block in response.content:
                if getattr(block, "type", None) == "text":
                    parts.append(block.text)
            return "\n".join(parts) or ""
        except Exception as e:
            if "404" in str(e) or "NOT_FOUND" in str(e):
                # Claude model/region not available — fall back to Gemini
                return await self._complete_gemini(prompt, max_tokens)
            raise

    async def _complete_gemini(self, prompt: str, max_tokens: int) -> str:
        """Fallback: use Gemini for agent reasoning when Claude is not available."""
        response = await self.gemini.aio.models.generate_content(
            model=self.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=max_tokens),
        )
        return response.text or ""

    async def complete_with_search(self, prompt: str, max_tokens: int = 2048) -> str:
        """Call Gemini with Google Search grounding (when available)."""
        try:
            search_tool = types.Tool(google_search=types.GoogleSearch())
            response = await self.gemini.aio.models.generate_content(
                model=self.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[search_tool],
                    max_output_tokens=max_tokens,
                ),
            )
            return response.text or ""
        except Exception:
            # If Search grounding isn't available, call Gemini without tools
            return await self._complete_gemini(prompt, max_tokens)
