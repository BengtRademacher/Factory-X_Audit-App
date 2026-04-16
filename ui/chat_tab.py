import pandas as pd
import plotly.express as px
import streamlit as st

from core.data_parser import DataParser
from database.working_store import WorkingStore
from ui.common import handle_llm_error, render_tab_header
from workflows.chat import build_chat_context_parts, build_chat_prompt
from workflows.eda import build_eda_chat_context, build_numeric_summary
from workflows.measurement_profile import profile_measurement_dataframe


def render_chat_assistant():
    render_tab_header("chat", "Ask about data", "Context-aware chat assistant and exploratory data analysis.")

    work_store = WorkingStore()
    llm_service = st.session_state.llm_service
    provider_name = st.session_state.llm_provider
    provider = llm_service.get_provider(provider_name, model=st.session_state.llm_model) if provider_name else None

    with st.expander("Configuration", expanded=False):
        col_p1, col_p2 = st.columns([2, 1])
        with col_p2:
            prompt_presets = {
                "Default Agent": "You are an expert for energy efficiency in manufacturing. Analyze the provided audit data and measurement context meticulously.",
                "Critical Auditor": "You are a critical energy auditor. Your goal is to find hidden inefficiencies and question every data point. Be strict and precise.",
                "Data Analyst": "You are a data scientist. Focus on statistical correlations, patterns in machine states, and numerical KPIs.",
            }

            def apply_preset_callback():
                preset_name = st.session_state.preset_selector
                st.session_state.system_prompt = prompt_presets[preset_name]
                st.session_state.last_applied_preset = preset_name

            preset_options = list(prompt_presets.keys())
            try:
                current_idx = preset_options.index(st.session_state.get("last_applied_preset", "Default Agent"))
            except ValueError:
                current_idx = 0

            selected_preset = st.selectbox(
                "Prompt Presets",
                options=preset_options,
                index=current_idx,
                key="preset_selector",
                on_change=apply_preset_callback,
            )

            if st.button("Update Preset"):
                st.session_state.system_prompt = prompt_presets[selected_preset]
                st.session_state.last_applied_preset = selected_preset
                st.rerun()

            st.session_state.enable_streaming = st.toggle("Enable Live Streaming", value=st.session_state.enable_streaming)

        with col_p1:
            st.session_state.system_prompt = st.text_area(
                "System Prompt",
                value=st.session_state.system_prompt,
                height=150,
                help="Defines the behavior and expertise of the AI.",
            )

    st.subheader("Chat")
    col_c1, col_c2 = st.columns([3, 1])
    with col_c1:
        audit_files = work_store.list_audits()
        selected_audits = st.multiselect("Include Audits as Context", options=audit_files)
    with col_c2:
        st.write("")
        st.write("")
        if st.button("Clear Chat History", width="stretch"):
            st.session_state.chat_history = []
            st.rerun()

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask a question about your data..."):
        if not provider:
            st.error("Please configure an LLM provider in the sidebar.")
            return

        audit_contexts = {f: work_store.load_audit(f) for f in selected_audits}
        uploaded_context = st.session_state.get("ask_data_context")
        context_parts = build_chat_context_parts(
            audit_contexts,
            {},
            [uploaded_context] if uploaded_context else [],
        )
        full_prompt = build_chat_prompt(prompt, context_parts)

        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            full_response = None
            try:
                if st.session_state.enable_streaming:
                    full_response = st.write_stream(
                        provider.generate_stream(full_prompt, system_instruction=st.session_state.system_prompt)
                    )
            except Exception:
                st.warning("Streaming failed, falling back to standard mode.")

            if _is_blank_response(full_response):
                try:
                    with st.spinner("Thinking..."):
                        full_response = provider.generate(full_prompt, system_instruction=st.session_state.system_prompt)
                        if _is_blank_response(full_response):
                            st.error("The model returned an empty response. Please try again or select a different model.")
                            full_response = None
                        else:
                            st.markdown(full_response)
                except Exception as e:
                    handle_llm_error(e)
                    full_response = None

        if not _is_blank_response(full_response):
            st.session_state.chat_history.append({"role": "assistant", "content": _response_to_text(full_response)})

    st.divider()
    _render_exploratory_upload()


def _render_exploratory_upload():
    st.subheader("Exploratory Data Analysis")
    uploaded_file = st.file_uploader(
        "Upload data for exploration",
        type=["csv", "xlsx", "xls"],
        key="ask_data_uploader",
    )

    if not uploaded_file:
        st.info("Upload a measurement file to explore it and add it to the chat context.")
        return

    file_key = (uploaded_file.name, getattr(uploaded_file, "size", None))
    if st.session_state.get("ask_data_file_key") != file_key:
        try:
            df = DataParser.read_file(uploaded_file)
            profile = profile_measurement_dataframe(df)
            summary_df = build_numeric_summary(df, profile)
            st.session_state.ask_data_file_key = file_key
            st.session_state.ask_data_df = df
            st.session_state.ask_data_profile = profile
            st.session_state.ask_data_summary = summary_df
            st.session_state.ask_data_context = build_eda_chat_context(uploaded_file.name, df, profile, summary_df)
        except Exception as e:
            st.error(f"Error during processing: {e}")
            return

    df = st.session_state.get("ask_data_df")
    profile = st.session_state.get("ask_data_profile")
    summary_df = st.session_state.get("ask_data_summary")
    if df is None or profile is None or summary_df is None:
        return

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("Rows", f"{profile.get('row_count', len(df))}")
    col_m2.metric("Columns", f"{len(profile.get('columns', []))}")
    col_m3.metric("Time Column", profile.get("time_column") or "not detected")
    sampling_rate = profile.get("sampling_rate_hz")
    col_m4.metric("Sampling Rate", f"{sampling_rate} Hz" if sampling_rate else "not detected")

    with st.expander("Measurement Profile", expanded=False):
        st.dataframe(pd.DataFrame(profile.get("columns", [])), width="stretch")

    st.subheader("Important Values")
    if summary_df.empty:
        st.info("No numeric columns detected.")
    else:
        st.dataframe(summary_df, width="stretch")
        st.download_button(
            "Download summary CSV",
            data=summary_df.to_csv(index=False).encode("utf-8"),
            file_name=f"{uploaded_file.name.rsplit('.', 1)[0]}_summary.csv",
            mime="text/csv",
            width="stretch",
        )

    numeric_columns = summary_df["column"].tolist() if not summary_df.empty else []
    if numeric_columns:
        st.subheader("Line Plot")
        default_columns = [col for col in numeric_columns if col != profile.get("time_column")][:5]
        selected_line_columns = st.multiselect(
            "Columns for line plot",
            options=numeric_columns,
            default=default_columns,
            key="ask_line_columns",
        )
        if selected_line_columns:
            plot_df, x_axis = _plot_frame(df, profile.get("time_column"), selected_line_columns)
            fig = px.line(plot_df.head(5000), x=x_axis, y=selected_line_columns, title="Measurement Trends")
            st.plotly_chart(fig, width="stretch")

        st.subheader("Histogram")
        histogram_column = st.selectbox("Histogram column", options=numeric_columns, key="ask_histogram_column")
        hist_values = pd.to_numeric(df[histogram_column], errors="coerce").dropna()
        fig = px.histogram(hist_values, nbins=40, title=f"Distribution: {histogram_column}")
        st.plotly_chart(fig, width="stretch")

    if len(numeric_columns) >= 2:
        st.subheader("Correlation")
        corr_df = df[numeric_columns].apply(pd.to_numeric, errors="coerce").corr()
        fig = px.imshow(corr_df, text_auto=True, title="Numeric Correlation Matrix")
        st.plotly_chart(fig, width="stretch")

    st.subheader("Data Preview")
    st.dataframe(df.head(200), width="stretch")


def _plot_frame(df: pd.DataFrame, time_column: str | None, selected_columns: list[str]) -> tuple[pd.DataFrame, str]:
    if time_column and time_column in df.columns:
        columns = [time_column] + [column for column in selected_columns if column != time_column]
        plot_df = df[columns].copy()
        x_axis = time_column
    else:
        plot_df = df[selected_columns].copy()
        plot_df.insert(0, "row_index", range(len(plot_df)))
        x_axis = "row_index"

    for column in selected_columns:
        if column in plot_df.columns:
            plot_df[column] = pd.to_numeric(plot_df[column], errors="coerce")
    return plot_df, x_axis


def _is_blank_response(response) -> bool:
    return not _response_to_text(response).strip()


def _response_to_text(response) -> str:
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, list):
        return "".join(str(item) for item in response)
    return str(response)
