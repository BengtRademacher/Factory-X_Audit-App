import streamlit as st

from workflows.operating_state import default_operating_state


def init_session_state():
    defaults = {
        "llm_service": None,
        "llm_provider": "openrouter",
        "llm_model": None,
        "use_custom_key": False,
        "custom_api_key": st.secrets["openrouter"].get("api_key", "") if "openrouter" in st.secrets else "",
        "machine_name": "CNC_Milling_1",
        "operator": "Admin",
        "machine_state": "Idle",
        "operating_state": None,
        "material": "Aluminum",
        "last_audit_results": None,
        "key_mode_pills": "Use default API key",
        "chat_history": [],
        "system_prompt": "You are an expert for energy efficiency in manufacturing. Analyze the provided audit data and benchmarks meticulously.",
        "last_applied_preset": "Default Agent",
        "enable_streaming": True,
        "audit_profile": None,
        "audit_measurement_context": None,
        "audit_time_ai_key": None,
        "audit_time_ai_result": None,
        "audit_supply_ai_key": None,
        "audit_supply_ai_result": None,
        "audit_selected_component_columns": None,
        "audit_component_selection_key": None,
        "audit_mapping": None,
        "audit_mapping_guidance": "",
        "audit_mapping_chat": [],
        "audit_uploaded_file_key": None,
        "audit_results": None,
        "audit_evidence_cards": [],
        "audit_manual_notes": "",
        "audit_draft": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if not st.session_state.get("operating_state"):
        st.session_state.operating_state = default_operating_state(st.session_state.get("machine_state"))
