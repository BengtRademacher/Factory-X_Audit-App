import abc
from typing import Optional, Dict, List, Any
import streamlit as st

from core.providers.openrouter_provider import OpenRouterProvider
from core.model_registry import OpenRouterModelRegistry


class BaseLLMProvider(abc.ABC):
    @abc.abstractmethod
    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        pass

    @abc.abstractmethod
    def generate_from_file(self, prompt: str, file_bytes: bytes, mime_type: str = "application/pdf") -> str:
        pass


class LLMService:
    def __init__(self):
        self.providers = {}
        self._init_providers()

    def _init_providers(self):
        # We initialize with a placeholder if no key is found.
        # The app.py sidebar will update the key dynamically.
        secrets = getattr(st, "secrets", {})
        
        # OpenRouter (Primary Provider)
        api_key = None
        if "openrouter" in secrets:
            api_key = secrets["openrouter"].get("api_key")
        
        # Even if api_key is None, we create the provider. 
        # It will be updated by the sidebar.
        self.providers["openrouter"] = OpenRouterProvider(api_key=api_key if api_key else "")

    def list_providers(self) -> List[str]:
        return list(self.providers.keys())

    def get_provider(self, name: str, model: Optional[str] = None) -> Optional[BaseLLMProvider]:
        provider = self.providers.get(name)
        if provider and model:
            provider.model_name = model
        return provider

    def get_openrouter_models(self, free_only: bool = False, vision_only: bool = False) -> Dict[str, str]:
        """Returns the model options for OpenRouter."""
        return OpenRouterModelRegistry.get_model_options(free_only=free_only, vision_only=vision_only)
