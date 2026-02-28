"""
LLM Client Wrapper
==================
Abstracts away the specific LLM API (Google Vertex AI or OpenAI).
Allows easy switching for demo purposes.
"""

import os
import asyncio


class LLMClient:
    def __init__(self):
        self.google_key = os.getenv("GOOGLE_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        
        if self.google_key:
            self.provider = "google"
            self._init_google()
        elif self.openai_key:
            self.provider = "openai"
            self._init_openai()
        else:
            raise ValueError("No API key found. Set GOOGLE_API_KEY or OPENAI_API_KEY in .env")
    
    def _init_google(self):
        import google.generativeai as genai
        genai.configure(api_key=self.google_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    def _init_openai(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=self.openai_key)
        self.model_name = "gpt-4o"
    
    async def complete(self, prompt: str, max_tokens: int = 500) -> str:
        """Asynchronously call the LLM and return the string response."""
        if self.provider == "google":
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
            )
            return response.text or ""

        if self.provider == "openai":
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return (response.choices[0].message.content or "").strip()

        return "ERROR: No provider configured"
