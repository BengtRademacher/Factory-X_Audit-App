import time

import streamlit as st

from database.literature_db import LiteratureDB
from database.working_store import WorkingStore
from services.export_service import ExportService
from services.visualization import VisualizationService
from ui.common import handle_llm_error, render_tab_header
from workflows.comparison import (
    build_comparison_prompt,
    build_report_data,
    prepare_comparison_payloads,
    should_summarize,
)


def render_comparison():
    render_tab_header("compare_arrows", "Comparison", "Compare stored audit data with literature benchmarks.")

    lit_db = LiteratureDB()
    work_store = WorkingStore()
    llm_service = st.session_state.llm_service
    provider_name = st.session_state.llm_provider
    provider = llm_service.get_provider(provider_name, model=st.session_state.llm_model) if provider_name else None

    col_audit, col_icon, col_benchmark = st.columns([5, 1, 5])

    with col_audit:
        st.subheader("1. Audit Data")
        audit_files = work_store.list_audits()
        selected_audit_files = st.multiselect("Select Audit JSONs", options=audit_files, key="comp_audit")

    with col_icon:
        st.markdown(
            """
            <div style='display:flex; justify-content:center; align-items:center; height:100px; margin-top:2rem;'>
                <span class='material-symbols-rounded' style='font-size:64px; color:#006DB9;'>compare_arrows</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_benchmark:
        st.subheader("2. Benchmarks")
        lit_entries = lit_db.get_all_entries()
        lit_options = {e["title"]: e["id"] for e in lit_entries}
        selected_lit_titles = st.multiselect("Select Literature Benchmarks", options=list(lit_options.keys()), key="comp_bench")
        selected_lit_ids = [lit_options.get(title) for title in selected_lit_titles]

    analysis_context = st.text_area(
        "Analysis focus",
        value=st.session_state.get("comparison_analysis_context", ""),
        placeholder="Example: Focus on auxiliary power, pneumatic losses, and practical retrofit measures.",
        help="Optional question or perspective for the benchmark comparison.",
    )
    st.session_state.comparison_analysis_context = analysis_context

    if selected_audit_files and selected_lit_ids:
        if st.button("Start Analysis", type="primary", width="stretch"):
            if not provider:
                st.error("Please configure an LLM provider.")
                return

            audits_data = {f: work_store.load_audit(f) for f in selected_audit_files}
            benchmarks_data = {title: lit_db.get_entry_by_id(lit_options[title]) for title in selected_lit_titles}

            use_summary = should_summarize(len(selected_audit_files), len(selected_lit_titles))
            audits_to_send, benchmarks_to_send = prepare_comparison_payloads(
                audits_data,
                benchmarks_data,
                use_summary,
            )

            start_time = time.time()
            with st.status("AI is analyzing the comparison...", expanded=True) as status:
                try:
                    if use_summary:
                        st.info("Large matrix detected: using summarized data to keep the analysis stable.")
                    else:
                        st.success("Small matrix: using full data for maximum analysis quality.")

                    prompt = build_comparison_prompt(audits_to_send, benchmarks_to_send, analysis_context)
                    assessment = provider.generate(prompt)
                    thinking_time = time.time() - start_time
                    status.update(label=f"Analysis completed ({thinking_time:.1f}s)", state="complete", expanded=False)
                except Exception as e:
                    handle_llm_error(e)
                    status.update(label="Analysis failed", state="error", expanded=False)
                    return

            st.divider()
            st.subheader("Analysis Results")
            st.markdown(assessment)

            st.divider()
            st.subheader("Visual Comparison")
            if len(selected_audit_files) == 1 and len(selected_lit_ids) == 1:
                fig = VisualizationService.plot_kpi_comparison(
                    audits_data[selected_audit_files[0]],
                    benchmarks_data[selected_lit_titles[0]],
                )
                if fig:
                    st.plotly_chart(fig, width="stretch")
            else:
                st.info("Visual comparison for multiple entries shows the overall energy comparison.")
                fig = VisualizationService.plot_multi_energy_comparison(audits_data, benchmarks_data)
                st.plotly_chart(fig, width="stretch")

            st.divider()
            st.subheader("Export")
            pdf_buffer = ExportService.create_pdf_report(build_report_data(audits_data))
            st.download_button(
                "Download PDF Report",
                data=pdf_buffer,
                file_name="comparison_report.pdf",
                mime="application/pdf",
                width="stretch",
            )


def render_json_comparison():
    render_comparison()
