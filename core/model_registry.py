from typing import Any, Dict, List

import requests
import streamlit as st


class OpenRouterModelRegistry:
    """Service zum dynamischen Abrufen und Filtern von OpenRouter Modellen."""

    API_URL = "https://openrouter.ai/api/v1/models"
    CACHE_TTL = 600  # 10 Minuten

    MULTIMODAL_INPUT_MODALITIES = {"image", "file", "pdf", "video"}
    EXCLUDED_MODEL_IDS = {
        "openrouter/free",
    }
    EXCLUDED_MODEL_KEYWORDS = (
        "guard",
        "moderation",
        "safety",
        "lyria",
    )

    @staticmethod
    @st.cache_data(ttl=600)
    def fetch_models() -> List[Dict[str, Any]]:
        """Holt die aktuelle Modell-Liste von OpenRouter."""
        try:
            response = requests.get(OpenRouterModelRegistry.API_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except (requests.RequestException, ValueError) as e:
            st.error(f"Fehler beim Laden der OpenRouter Modelle: {e}")
            return []

    @classmethod
    def get_models(
        cls,
        free_only: bool = False,
        vision_only: bool = False,
        search_term: str = "",
    ) -> List[Dict[str, Any]]:
        """Gibt gefilterte Modelle zurueck."""
        filtered = []
        for model in cls.fetch_models():
            if not cls.is_supported_audit_model(model):
                continue
            if free_only and not cls.is_free_model(model):
                continue
            if vision_only and not cls.has_vision(model):
                continue

            model_id = model.get("id", "").lower()
            model_name = model.get("name", "").lower()
            if search_term and search_term.lower() not in model_name and search_term.lower() not in model_id:
                continue

            filtered.append(model)
        return filtered

    @classmethod
    def get_model_options(cls, free_only: bool = True, vision_only: bool = False) -> Dict[str, str]:
        """Gibt ein Dictionary {Anzeigename: ID} fuer Streamlit Selectboxen zurueck."""
        models = cls.get_models(free_only=free_only, vision_only=vision_only)
        options = {}

        for model in cls.order_models_for_selection(models):
            options[cls.model_label(model)] = model.get("id")
        return options

    @classmethod
    def get_model_metadata(cls, model_id: str) -> Dict[str, Any]:
        for model in cls.fetch_models():
            if model.get("id") == model_id:
                return model
        return {}

    @staticmethod
    def price_as_float(value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def is_free_model(model: Dict[str, Any]) -> bool:
        pricing = model.get("pricing", {}) or {}
        return (
            OpenRouterModelRegistry.price_as_float(pricing.get("prompt")) == 0
            and OpenRouterModelRegistry.price_as_float(pricing.get("completion")) == 0
        )

    @staticmethod
    def input_modalities(model: Dict[str, Any]) -> set[str]:
        architecture = model.get("architecture", {}) or {}
        modalities = architecture.get("input_modalities") or model.get("input_modalities") or []
        return {str(item).lower() for item in modalities}

    @staticmethod
    def output_modalities(model: Dict[str, Any]) -> set[str]:
        architecture = model.get("architecture", {}) or {}
        modalities = architecture.get("output_modalities") or model.get("output_modalities") or []
        return {str(item).lower() for item in modalities}

    @classmethod
    def has_multimodal_input(cls, model: Dict[str, Any]) -> bool:
        return bool(cls.MULTIMODAL_INPUT_MODALITIES & cls.input_modalities(model))

    @classmethod
    def has_text_only_output(cls, model: Dict[str, Any]) -> bool:
        return cls.output_modalities(model) == {"text"}

    @classmethod
    def is_specialized_model(cls, model: Dict[str, Any]) -> bool:
        model_id = str(model.get("id", "")).lower()
        model_name = str(model.get("name", "")).lower()
        searchable = f"{model_id} {model_name}"
        return model_id in cls.EXCLUDED_MODEL_IDS or any(
            keyword in searchable for keyword in cls.EXCLUDED_MODEL_KEYWORDS
        )

    @classmethod
    def is_supported_audit_model(cls, model: Dict[str, Any]) -> bool:
        return (
            cls.has_multimodal_input(model)
            and cls.has_text_only_output(model)
            and not cls.is_specialized_model(model)
        )

    @classmethod
    def has_vision(cls, model: Dict[str, Any]) -> bool:
        modalities = cls.input_modalities(model)
        model_id = model.get("id", "").lower()
        return bool({"image", "vision", "file", "pdf", "video"} & modalities) or any(
            keyword in model_id for keyword in ["vision", "gemini", "pixtral", "llava"]
        )

    @staticmethod
    def supports_reasoning(model: Dict[str, Any]) -> bool:
        supported = set(model.get("supported_parameters", []) or [])
        return bool({"reasoning", "reasoning_effort", "include_reasoning"} & supported)

    @classmethod
    def order_models_for_selection(cls, models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(models, key=cls.model_sort_key, reverse=True)

    @classmethod
    def model_label(cls, model: Dict[str, Any]) -> str:
        name = model.get("name", model.get("id"))
        parts = [str(name)]

        context = model.get("context_length")
        if isinstance(context, int) and context:
            parts.append(f"{int(context / 1000)}k")

        if cls.supports_reasoning(model):
            parts.append("reasoning")

        price_label = cls.price_label(model)
        if price_label:
            parts.append(price_label)

        return " | ".join(parts)

    @classmethod
    def price_label(cls, model: Dict[str, Any]) -> str:
        pricing = model.get("pricing", {}) or {}
        prompt_price = cls.price_as_float(pricing.get("prompt")) * 1_000_000
        if prompt_price <= 0:
            return ""
        return f"~${prompt_price:.2f}/M input"

    @classmethod
    def model_sort_key(cls, model: Dict[str, Any]) -> tuple[int, int, int, float, str]:
        pricing = model.get("pricing", {}) or {}
        prompt_price = cls.price_as_float(pricing.get("prompt"))
        return (
            1 if cls.supports_reasoning(model) else 0,
            int(model.get("context_length") or 0),
            len(cls.MULTIMODAL_INPUT_MODALITIES & cls.input_modalities(model)),
            -prompt_price,
            model.get("name", model.get("id", "")),
        )
