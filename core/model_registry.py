import requests
import streamlit as st
import time
from typing import List, Dict, Any, Optional

class OpenRouterModelRegistry:
    """Service zum dynamischen Abrufen und Filtern von OpenRouter Modellen."""
    
    API_URL = "https://openrouter.ai/api/v1/models"
    CACHE_TTL = 600  # 10 Minuten

    @staticmethod
    @st.cache_data(ttl=600)
    def fetch_models() -> List[Dict[str, Any]]:
        """Holt die aktuelle Modell-Liste von OpenRouter."""
        try:
            response = requests.get(OpenRouterModelRegistry.API_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception as e:
            st.error(f"Fehler beim Laden der OpenRouter Modelle: {e}")
            return []

    @classmethod
    def get_models(cls, 
                   free_only: bool = False, 
                   vision_only: bool = False,
                   search_term: str = "") -> List[Dict[str, Any]]:
        """Gibt gefilterte Modelle zurueck."""
        models = cls.fetch_models()
        
        filtered = []
        for m in models:
            # Free Filter: Pruefe prompt und completion pricing
            pricing = m.get("pricing", {})
            is_free = pricing.get("prompt") == "0" and pricing.get("completion") == "0"
            
            if free_only and not is_free:
                continue
                
            # Vision / Document Filter
            # OpenRouter Modelle mit Vision haben oft 'vision' in der ID oder entsprechende Architektur-Flags.
            # Wir suchen hier nach Modellen, die fuer PDF/Bildanalyse bekannt sind (Gemini, Claude-3, Vision-Modelle).
            model_id = m.get("id", "").lower()
            has_vision = any(keyword in model_id for keyword in ["vision", "gemini", "claude-3", "pixtral", "llava"])
            
            if vision_only and not has_vision:
                continue
                
            # Search Term
            if search_term and search_term.lower() not in m.get("name", "").lower() and search_term.lower() not in model_id:
                continue
                
            filtered.append(m)
            
        return filtered

    @classmethod
    def get_model_options(cls, free_only: bool = True, vision_only: bool = True) -> Dict[str, str]:
        """Gibt ein Dictionary {Anzeigename: ID} fuer Streamlit Selectboxen zurueck."""
        models = cls.get_models(free_only=free_only, vision_only=vision_only)
        options = {}
        for m in models:
            name = m.get("name", m.get("id"))
            pricing = m.get("pricing", {})
            p_prompt = float(pricing.get("prompt", 0)) * 1000000
            
            # Anzeige-Label bereinigt (keine Emojis, kein (Free) Suffix fuer kostenlose Modelle)
            if p_prompt == 0:
                label = name
            else:
                label = f"💰 {name} (~${p_prompt:.2f}/M tokens)"
                
            options[label] = m.get("id")
            
        # Sortieren: Alphabetisch
        sorted_keys = sorted(options.keys())
        return {k: options[k] for k in sorted_keys}
