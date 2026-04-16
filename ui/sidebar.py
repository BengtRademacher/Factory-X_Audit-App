import streamlit as st

from core.llm_service import LLMService


def render_sidebar():
    if st.session_state.llm_service is None:
        st.session_state.llm_service = LLMService()

    llm_service = st.session_state.llm_service

    with st.sidebar:
        st.markdown("### Settings")

        with st.expander("\U0001F916 API Key", expanded=True):
            key_mode = st.pills(
                "API Key Source",
                options=["Use default API key", "Enter custom API key"],
                selection_mode="single",
                key="key_mode_pills",
            )
            st.session_state.use_custom_key = st.session_state.key_mode_pills == "Enter custom API key"

            if st.session_state.use_custom_key:
                st.session_state.custom_api_key = st.text_input(
                    "OpenRouter API Key",
                    value=st.session_state.custom_api_key,
                    type="password",
                    key="custom_key_input",
                )
                api_key = st.session_state.custom_api_key
                free_only = False
            else:
                api_key = st.secrets["openrouter"].get("api_key", "")
                free_only = True
                st.info("Using default key (Free models only)")

            if "openrouter" in llm_service.providers:
                llm_service.providers["openrouter"].api_key = api_key

            with st.spinner("Loading models..."):
                or_models = llm_service.get_openrouter_models(free_only=free_only)

            if not or_models:
                st.error("No suitable OpenRouter models found.")
                st.session_state.llm_model = None
            else:
                current_model = st.session_state.llm_model
                model_labels = list(or_models.keys())
                current_index = next(
                    (index for index, label in enumerate(model_labels) if or_models[label] == current_model),
                    0,
                )

                selected_model_label = st.selectbox(
                    "Model",
                    options=model_labels,
                    index=current_index,
                )
                st.session_state.llm_model = or_models[selected_model_label]
                st.session_state.llm_provider = "openrouter"

                st.caption(f"ID: `{st.session_state.llm_model}`")
                if free_only:
                    st.success("Free model selected.")
                else:
                    st.info("Full model access enabled.")

        st.divider()
        st.caption("Factory-X Audit-App v1.5")
