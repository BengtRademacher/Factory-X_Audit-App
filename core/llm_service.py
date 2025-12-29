import abc
from typing import Optional, Dict, Any, List
import google.generativeai as genai
import streamlit as st

class BaseLLMProvider(abc.ABC):
    """Abstrakte Basisklasse für LLM-Provider."""
    
    @abc.abstractmethod
    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """Generiert eine Antwort basierend auf dem Prompt."""
        pass

    @abc.abstractmethod
    def generate_from_file(self, prompt: str, file_bytes: bytes, mime_type: str = "application/pdf") -> str:
        """Generiert eine Antwort basierend auf einem Prompt und einer Datei."""
        pass

class GeminiProvider(BaseLLMProvider):
    """Implementierung für Google Gemini."""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        
    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        try:
            full_prompt = prompt
            if system_instruction:
                full_prompt = f"{system_instruction}\n\n{prompt}"
                
            response = self.model.generate_content(full_prompt)
            return response.text.strip()
        except Exception as e:
            return f"Error with Gemini: {str(e)}"

    def generate_from_file(self, prompt: str, file_bytes: bytes, mime_type: str = "application/pdf") -> str:
        try:
            # Gemini unterstützt Inline-Daten für PDFs
            content = [
                prompt,
                {
                    "mime_type": mime_type,
                    "data": file_bytes
                }
            ]
            response = self.model.generate_content(content)
            return response.text.strip()
        except Exception as e:
            return f"Error with Gemini (File): {str(e)}"

class OpenAIProvider(BaseLLMProvider):
    """Implementierung für OpenAI (placeholder)."""
    
    def __init__(self, api_key: str, model_name: str = "gpt-4-turbo"):
        self.api_key = api_key
        self.model_name = model_name
        
    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        return "OpenAI Provider not fully implemented yet."

    def generate_from_file(self, prompt: str, file_bytes: bytes, mime_type: str = "application/pdf") -> str:
        return "OpenAI File analysis not implemented yet."

class OllamaProvider(BaseLLMProvider):
    """Implementierung für lokale Modelle via Ollama."""
    
    def __init__(self, host: str = "http://localhost:11434", model_name: str = "mistral"):
        self.host = host
        self.model_name = model_name
        
    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        try:
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
        except Exception as e:
            return f"Error with Ollama: {str(e)}"

    def generate_from_file(self, prompt: str, file_bytes: bytes, mime_type: str = "application/pdf") -> str:
        return "Ollama File analysis not supported in this basic implementation."

class LLMService:
    """Zentraler Service zur Verwaltung verschiedener LLM-Provider."""
    
    def __init__(self):
        self.providers: Dict[str, BaseLLMProvider] = {}
        self._initialize_from_secrets()
        
    def _initialize_from_secrets(self):
        """Initialisiert verfügbare Provider aus Streamlit Secrets."""
        try:
            # Versuche auf st.secrets zuzugreifen. Wenn die Datei fehlt oder leer ist,
            # fangen wir den Fehler ab oder arbeiten mit einem leeren Dict.
            secrets = st.secrets
            
            if "gemini" in secrets:
                api_key = secrets["gemini"].get("api_key")
                if api_key and "HIER_EINTRAGEN" not in api_key:
                    self.providers["gemini"] = GeminiProvider(api_key=api_key)
            
            if "openai" in secrets:
                api_key = secrets["openai"].get("api_key")
                if api_key and "OPTIONAL" not in api_key:
                    self.providers["openai"] = OpenAIProvider(api_key=api_key)
                
            if "ollama" in secrets:
                self.providers["ollama"] = OllamaProvider(
                    host=secrets["ollama"].get("host", "http://localhost:11434"),
                    model_name=secrets["ollama"].get("model", "mistral")
                )
        except Exception as e:
            # Wenn secrets.toml komplett fehlt oder ein Parsing-Fehler vorliegt
            st.warning(f"Hinweis: secrets.toml konnte nicht geladen werden oder ist unvollständig. ({e})")
            pass
            
    def get_provider(self, name: str) -> Optional[BaseLLMProvider]:
        return self.providers.get(name.lower())

    def list_providers(self) -> List[str]:
        return list(self.providers.keys())

