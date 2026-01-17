import abc
from typing import Optional, Dict, List
from google import genai
from google.genai import types
import streamlit as st

from core.providers.openrouter_provider import OpenRouterProvider


class BaseLLMProvider(abc.ABC):
    @abc.abstractmethod
    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        pass

    @abc.abstractmethod
    def generate_from_file(self, prompt: str, file_bytes: bytes, mime_type: str = "application/pdf") -> str:
        pass


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        config = None
        if system_instruction:
            config = types.GenerateContentConfig(system_instruction=system_instruction)

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config
        )
        return response.text.strip()

    def generate_from_file(self, prompt: str, file_bytes: bytes, mime_type: str = "application/pdf") -> str:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                prompt
            ]
        )
        return response.text.strip()


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model_name: str = "gpt-4-turbo"):
        self.api_key = api_key
        self.model_name = model_name

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        return "OpenAI Provider not fully implemented yet."

    def generate_from_file(self, prompt: str, file_bytes: bytes, mime_type: str = "application/pdf") -> str:
        return "OpenAI File analysis not implemented yet."


class OllamaProvider(BaseLLMProvider):
    def __init__(self, host: str = "http://localhost:11434", model_name: str = "mistral"):
        self.host = host
        self.model_name = model_name

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        import requests
        response = requests.post(
            f"{self.host}/api/generate",
            json={
                "model": self.model_name,
                "prompt": prompt,
                "system": system_instruction,
                "stream": False
            }
        )
        return response.json().get("response", "").strip()

    def generate_from_file(self, prompt: str, file_bytes: bytes, mime_type: str = "application/pdf") -> str:
        return "Ollama File analysis not supported."


class LLMService:
    def __init__(self):
        self.providers = {}
        self._init_providers()

    def _init_providers(self):
        secrets = st.secrets

        # Gemini
        if "gemini" in secrets:
            api_key = secrets["gemini"].get("api_key")
            if api_key:
                self.providers["gemini"] = GeminiProvider(api_key=api_key)

        # OpenAI
        if "openai" in secrets:
            api_key = secrets["openai"].get("api_key")
            if api_key and "OPTIONAL" not in api_key:
                self.providers["openai"] = OpenAIProvider(api_key=api_key)

        # Ollama
        if "ollama" in secrets:
            self.providers["ollama"] = OllamaProvider(
                host=secrets["ollama"].get("host", "http://localhost:11434"),
                model_name=secrets["ollama"].get("model", "mistral")
            )

        # OpenRouter (IMPORTANT)
        if "openrouter" in secrets:
            api_key = secrets["openrouter"].get("api_key")
            if api_key and api_key.startswith("sk-or-"):
                self.providers["openrouter"] = OpenRouterProvider(api_key=api_key)

    def list_providers(self):
        return list(self.providers.keys())

    def get_provider(self, name, model=None):
        provider = self.providers.get(name)
        if provider and model:
            provider.model = model
        return provider


