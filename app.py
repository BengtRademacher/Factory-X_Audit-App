import streamlit as st
import json
import time
import base64
import re
import pandas as pd
from pathlib import Path
from io import BytesIO

from core.llm_service import LLMService
from config.settings import settings, COLORS
from config.prompts import PAPER_EXTRACTION_PROMPT, COMPARISON_PROMPT
from database.literature_db import LiteratureDB
from database.working_store import WorkingStore
from core.data_parser import DataParser
from core.json_extractor import extract_json_from_response
from services.visualization import VisualizationService
from services.export_service import ExportService


# --- Session State & UI Helpers ---
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
        "material": "Aluminum",
        "last_audit_results": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _get_base64(path: Path) -> str:
    if not path.exists():
        return ""
    with path.open("rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def inject_custom_styles():
    logo_path = Path("assets/FX_logo_top_left.png")
    svg_style_path = Path("assets/FX_style_top_right.svg")
    bg_color_hex = COLORS.get("Blau", "#006DB9")
    bg_opacity = 0.25

    h = bg_color_hex.lstrip('#')
    r, g, b = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    rgba_bg = f"rgba({r}, {g}, {b}, {bg_opacity})"

    style_base64 = _get_base64(svg_style_path)
    bg_style = ""
    if style_base64:
        bg_style = f"""
        [data-testid="stAppViewContainer"]::before {{
            content: "";
            position: fixed;
            top: -5px;
            right: -5px;
            width: 400px;
            height: 400px;
            background-image: url('data:image/svg+xml;base64,{style_base64}');
            background-size: contain;
            background-repeat: no-repeat;
            background-position: top right;
            opacity: 0.4;
            transform: rotate(180deg);
            pointer-events: none;
            z-index: 0;
        }}
        """

    st.markdown(f"""
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0" />
    <style>
        [data-testid="stAppViewContainer"] {{
            background: radial-gradient(
                circle at top left,
                {rgba_bg} 0%,
                rgba(255, 255, 255, 0) 70%
            ) !important;
            background-attachment: fixed !important;
        }}
        {bg_style}
        [data-testid="stSidebarHeader"] {{
            height: 120px !important;
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
        }}
        [data-testid="stSidebarHeader"] img {{
            height: 100px !important;
            width: auto !important;
        }}
        [data-testid="stMainBlockContainer"] {{
            padding-top: 2rem !important;
        }}
        header[data-testid="stHeader"], [data-testid="stToolbar"] {{
            background-color: transparent !important;
        }}
        .material-symbols-rounded {{
            font-family: 'Material Symbols Rounded';
            vertical-align: middle;
            margin-right: 8px;
            font-variation-settings: 'opsz' 24;
        }}
    </style>
    """, unsafe_allow_html=True)


def render_sidebar():
    if st.session_state.llm_service is None:
        st.session_state.llm_service = LLMService()

    llm_service = st.session_state.llm_service

    with st.sidebar:
        st.markdown("### Settings")

        with st.expander("🤖 AI Backend", expanded=True):
            # API Key Selection
            key_mode = st.radio(
                "API Key Source",
                options=["Use default API key", "Enter custom API key"],
                index=1 if st.session_state.use_custom_key else 0,
                key="key_mode_radio"
            )
            st.session_state.use_custom_key = (key_mode == "Enter custom API key")

            if st.session_state.use_custom_key:
                st.session_state.custom_api_key = st.text_input(
                    "OpenRouter API Key",
                    value=st.session_state.custom_api_key,
                    type="password",
                    key="custom_key_input"
                )
                api_key = st.session_state.custom_api_key
                free_only = False
            else:
                api_key = st.secrets["openrouter"].get("api_key", "")
                free_only = True
                st.info("Using default key (Free models only)")

            # Update provider with current key
            if "openrouter" in llm_service.providers:
                llm_service.providers["openrouter"].api_key = api_key

            # Model Selection
            with st.spinner("Loading models..."):
                or_models = llm_service.get_openrouter_models(free_only=free_only, vision_only=False)
            
            if not or_models:
                st.error("No suitable OpenRouter models found.")
                st.session_state.llm_model = "openrouter/auto"
            else:
                # Legend for capability tags
                st.markdown("""
                <div style='background-color: rgba(0, 109, 185, 0.1); padding: 10px; border-radius: 5px; margin-bottom: 10px;'>
                    <small><b>Model Capabilities:</b><br/>
                    👁️ Vision (PDF, Images)<br/>
                    📝 Text Only (CSV, Excel, JSON)</small>
                </div>
                """, unsafe_allow_html=True)

                # Ensure previously selected model is still in the list, otherwise pick first
                current_model = st.session_state.llm_model
                model_labels = list(or_models.keys())
                
                # Find index of current model label if it exists
                current_index = 0
                for i, label in enumerate(model_labels):
                    if or_models[label] == current_model:
                        current_index = i
                        break

                selected_model_label = st.selectbox(
                    "OpenRouter Model",
                    options=model_labels,
                    index=current_index
                )
                st.session_state.llm_model = or_models[selected_model_label]
                
                # Ensure a model is always selected even if selectbox hasn't updated yet
                if st.session_state.llm_model is None and model_labels:
                    st.session_state.llm_model = or_models[model_labels[0]]
                st.session_state.llm_provider = "openrouter" # Force openrouter for now
                
                # Model Details
                with st.expander("ℹ️ Model Info", expanded=False):
                    st.caption(f"ID: `{st.session_state.llm_model}`")
                    if free_only:
                        st.success("Free document model selected.")
                    else:
                        st.info("Full model access enabled.")

        st.divider()
        st.caption("Factory-X Audit-App v1.4")



def render_tab_header(icon_name: str, title: str, description: str):
    st.markdown(
        f"""
        <div style='display:flex; align-items:center; gap:16px; margin-top:0.5rem;'>
            <span class='material-symbols-rounded' style='font-size:32px;'>{icon_name}</span>
            <h2 style='margin:0;'>{title}</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(description)
    st.divider()


def handle_llm_error(e):
    """Consolidated LLM error handling."""
    error_msg = str(e)
    if "429" in error_msg or "quota" in error_msg.lower():
        st.error("❌ Quota exceeded or rate limit reached. Please try another model or wait a moment.")
    else:
        st.error(f"❌ Error: {e}")

def render_paper_to_json():
    render_tab_header("description", "Document ➔ JSON Extractor", "Extraction of structured data from PDFs, CSV, Excel or JSON.")

    db = LiteratureDB()
    llm_service = st.session_state.llm_service
    provider_name = st.session_state.llm_provider
    provider = llm_service.get_provider(provider_name, model=st.session_state.llm_model) if provider_name else None

    # Check for vision capability if model is selected
    is_vision_model = False
    if st.session_state.llm_model:
        model_id = st.session_state.llm_model.lower()
        is_vision_model = any(kw in model_id for kw in ["vision", "gemini", "claude-3", "pixtral", "llava"])

    if not provider:
        st.error("Please configure an LLM provider in the sidebar.")
        return

    uploaded_files = st.file_uploader(
        "Upload Documents",
        type=["pdf", "csv", "xlsx", "json"],
        accept_multiple_files=True,
        key="paper_uploader"
    )

    if uploaded_files:
        # Warning if PDF is uploaded but model has no vision
        has_pdf = any(f.name.lower().endswith(".pdf") for f in uploaded_files)
        if has_pdf and not is_vision_model:
            st.warning("⚠️ Warning: You have uploaded a PDF, but the selected model might not support vision/PDF analysis. This could lead to errors.")

        if st.button(
            f"Analyze Documents ({len(uploaded_files)})",
            type="primary",
            icon="🚀",
            use_container_width=True
        ):
            with st.status("Processing documents...", expanded=True) as status:
                results_container = st.container()

            for i, doc_file in enumerate(uploaded_files):
                st.write(f"⏳ **{doc_file.name}** ({i+1}/{len(uploaded_files)})")

                doc_bytes = doc_file.read()
                start_time = time.time()
                file_ext = doc_file.name.split('.')[-1].lower()

                try:
                    if file_ext == "pdf":
                        response = provider.generate_from_file(
                            prompt=PAPER_EXTRACTION_PROMPT,
                            file_bytes=doc_bytes,
                            mime_type="application/pdf"
                        )
                    else:
                        # Text-based formats (CSV, JSON, XLSX)
                        if file_ext == "csv":
                            content = doc_bytes.decode("utf-8", errors="ignore")
                        elif file_ext == "json":
                            content = doc_bytes.decode("utf-8", errors="ignore")
                        elif file_ext == "xlsx":
                            df_xlsx = pd.read_excel(BytesIO(doc_bytes))
                            content = df_xlsx.to_csv(index=False)
                        else:
                            content = ""

                        full_prompt = f"{PAPER_EXTRACTION_PROMPT}\n\n### FILE CONTENT ({file_ext.upper()}):\n{content}"
                        response = provider.generate(full_prompt)

                    thinking_time = time.time() - start_time

                    # Robust JSON extraction via utility
                    try:
                        data = extract_json_from_response(response)
                    except ValueError as e:
                        st.error(f"Could not parse JSON: {e}")
                        raise e

                    db.add_entry(data, pdf_file=doc_bytes, filename=doc_file.name.rsplit(".", 1)[0])

                    st.write(f"✅ Success ({thinking_time:.1f}s)")
                    with results_container:
                        with st.expander(f"Details: {doc_file.name}"):
                            st.json(data)

                except Exception as e:
                    handle_llm_error(e)
                    with results_container:
                        with st.expander(f"Error Details: {doc_file.name}"):
                            st.exception(e)

            status.update(label="Processing complete!", state="complete", expanded=False)
        st.toast("All documents processed!", icon="🎉")

    st.divider()
    st.subheader("📚 Literature Database")
    entries = db.get_all_entries()
    if entries:
        for entry in entries:
            with st.expander(f"📄 {entry['title']} ({', '.join(entry['authors'][:2])}...)"):
                col_info, col_actions = st.columns([3, 1])
                with col_info:
                    st.write(f"**ID:** {entry['id']}")
                    st.write(f"**Date:** {entry['date']}")
                with col_actions:
                    if st.button("👁️ JSON", key=f"details_{entry['id']}"):
                        full_data = db.get_entry_by_id(entry['id'])
                        st.json(full_data)
                    if st.button("🗑️ Delete", key=f"del_{entry['id']}"):
                        db.delete_entry(entry['id'])
                        st.rerun()
    else:
        st.info("ℹ️ No entries in database yet.")


def render_data_to_json():
    render_tab_header("query_stats", "Data ➔ JSON", "Processing machine measurement data from Excel or CSV.")

    store = WorkingStore()

    st.subheader("Machine Configuration")
    col_a, col_b = st.columns(2)
    with col_a:
        st.session_state.machine_name = st.text_input(
            "Machine Name",
            value=st.session_state.machine_name,
            key="input_machine_name"
        )
        st.session_state.operator = st.text_input(
            "Operator",
            value=st.session_state.operator,
            key="input_operator"
        )
    with col_b:
        state_options = ["Idle", "Cutting", "Cooling", "Maintenance"]
        st.session_state.machine_state = st.selectbox(
            "Machine State",
            state_options,
            index=state_options.index(st.session_state.machine_state),
            key="input_machine_state"
        )
        st.session_state.material = st.text_input(
            "Material",
            value=st.session_state.material,
            key="input_material"
        )

    st.divider()
    uploaded_file = st.file_uploader("Upload Measurement Data", type=["xlsx", "csv"], key="data_uploader")

    if uploaded_file:
        try:
            df = DataParser.read_file(uploaded_file)
            st.toast(f"File loaded: {len(df)} rows", icon="📂")

            if "elapsedTime" not in df.columns:
                st.error("The file must contain an 'elapsedTime' column.")
                return

            vars_elektrisch = [
                'Hauptversorgung', '24V-Versorgung', 'Antriebe', 'Bandfilteranlage',
                'Hebepumpe', 'Kühlung', 'KühlungSchaltschrank', 'Späneförderer'
            ]
            vars_pneumatisch = [
                'AirPower_Hauptversorgung', 'AirPower_Blum', 'AirPower_Hauptventilblock',
                'AirPower_BlasluftKegelreinigung', 'AirPower_KlemmungTisch',
                'AirPower_NPS', 'AirPower_Werkzeugkühlung', 'AirPower_ÖlLuftschmierungSpindel',
                'AirPower_Sperrluft', 'AirPower_BlasluftSpindelMitte'
            ]

            if st.button("Calculate Metrics", type="primary", icon="⚙️", use_container_width=True):
                with st.spinner("Calculating KPIs..."):
                    elek_details, elek_total = DataParser.compute_metrics(df, vars_elektrisch)
                    pneu_details, pneu_total = DataParser.compute_metrics(df, vars_pneumatisch)

                    duty_elek = DataParser.calculate_duty_cycle(df, vars_elektrisch, elek_total.get("mean", 0))
                    duty_pneu = DataParser.calculate_duty_cycle(df, vars_pneumatisch, pneu_total.get("mean", 0))

                    duration_sec = df["elapsedTime"].iloc[-1] - df["elapsedTime"].iloc[0]
                    total_energy = round(elek_total.get("total_energy_kWh", 0) + pneu_total.get("total_energy_kWh", 0), 4)
                    mean_power = round((elek_total.get("mean", 0) + pneu_total.get("mean", 0)) / 2, 2)
                    energy_rate = round(total_energy / (duration_sec / 3600), 4) if duration_sec > 0 else 0

                    results = {
                        "metadata": {
                            "machine_name": st.session_state.machine_name,
                            "operator": st.session_state.operator,
                            "machine_state": st.session_state.machine_state,
                            "material": st.session_state.material,
                            "duration_seconds": round(float(duration_sec), 2),
                            "unit_power": "W",
                            "unit_energy": "kWh"
                        },
                        "Elektrisch": {
                            "Variables": elek_details,
                            "Total Elektrisch": elek_total,
                            "Duty Cycle (%)": duty_elek
                        },
                        "Pneumatisch": {
                            "Variables": pneu_details,
                            "Total Pneumatisch": pneu_total,
                            "Duty Cycle (%)": duty_pneu
                        },
                        "Overall Summary": {
                            "Total Energy (kWh)": total_energy,
                            "Mean Power (W)": mean_power,
                            "Energy Rate (kWh/hour)": energy_rate,
                            "Top Variables": {}
                        }
                    }

                    filename = f"audit_{st.session_state.machine_name}_{uploaded_file.name.split('.')[0]}.json"
                    store.save_audit(results, filename)
                    st.session_state.last_audit_results = results
                    st.toast(f"Audit saved: {filename}", icon="💾")

                    st.divider()
                    st.subheader("Results")

                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Energy", f"{total_energy:.4f} kWh")
                    col2.metric("Mean Power", f"{mean_power:.1f} W")
                    col3.metric("Energy Rate", f"{energy_rate:.4f} kWh/h")
                    col4.metric("Duration", f"{duration_sec:.0f} s")

                    col_e, col_p = st.columns(2)
                    col_e.metric("Duty Cycle Electric", f"{duty_elek:.1f} %")
                    col_p.metric("Duty Cycle Pneumatic", f"{duty_pneu:.1f} %")

                    st.divider()
                    st.subheader("Visualization")
                    fig = VisualizationService.plot_energy_distribution(results)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)

                    with st.expander("Show JSON result"):
                        st.json(results)

        except Exception as e:
            st.error(f"Error during processing: {e}")

    st.divider()
    st.subheader("📂 Saved Audits (Working Store)")
    audits = store.list_audits()
    if audits:
        for audit in audits:
            with st.expander(f"📊 {audit}"):
                col_btn1, col_btn2 = st.columns([1, 1])
                if col_btn1.button("👁️ Load", key=f"load_{audit}"):
                    data = store.load_audit(audit)
                    st.json(data)
                if col_btn2.button("🗑️ Delete", key=f"del_audit_{audit}"):
                    store.delete_audit(audit)
                    st.rerun()
    else:
        st.info("ℹ️ No audits in store yet.")


def render_json_comparison():
    render_tab_header("compare_arrows", "JSON Comparison", "Comparison of audit data with literature benchmarks via LLM.")

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
            unsafe_allow_html=True
        )

    with col_benchmark:
        st.subheader("2. Benchmarks")
        lit_entries = lit_db.get_all_entries()
        lit_options = {e['title']: e['id'] for e in lit_entries}
        selected_lit_titles = st.multiselect("Select Literature Benchmarks", options=list(lit_options.keys()), key="comp_bench")
        selected_lit_ids = [lit_options.get(title) for title in selected_lit_titles]

    if selected_audit_files and selected_lit_ids:
        if st.button("Start Analysis", type="primary", icon="🚀", use_container_width=True):
            if not provider:
                st.error("Please configure an LLM provider.")
                return

            # Load all data
            audits_data = {f: work_store.load_audit(f) for f in selected_audit_files}
            benchmarks_data = {title: lit_db.get_entry_by_id(lit_options[title]) for title in selected_lit_titles}

            # Matrix size check for adaptive summarization (to maintain quality vs token limits)
            matrix_size = len(selected_audit_files) * len(selected_lit_titles)
            use_summary = matrix_size > 4

            def summarize_for_llm(data, is_benchmark=False):
                if not use_summary:
                    return data # Full data for best quality when matrix is small
                
                summary = {
                    "metadata": data.get("metadata", {}),
                    "Overall Summary": data.get("Overall Summary", {}),
                }
                if is_benchmark:
                    summary["energy_data"] = data.get("energy_data", {})
                else:
                    summary["Electrical Total"] = data.get("Elektrisch", {}).get("Total Elektrisch", {})
                    summary["Pneumatic Total"] = data.get("Pneumatisch", {}).get("Total Pneumatisch", {})
                return summary

            audits_to_send = {f: summarize_for_llm(d) for f, d in audits_data.items()}
            benchmarks_to_send = {t: summarize_for_llm(d, True) for t, d in benchmarks_data.items()}

            start_time = time.time()
            with st.status("AI is analyzing the comparison...", expanded=True) as status:
                try:
                    # Construct matrix prompt
                    audit_json_str = json.dumps(audits_to_send, indent=2)
                    benchmark_json_str = json.dumps(benchmarks_to_send, indent=2)
                    
                    if use_summary:
                        st.info("Large matrix detected: Using summarized data to ensure stability.")
                    else:
                        st.success("Small matrix: Using full data for maximum analysis quality.")
                    
                    prompt = COMPARISON_PROMPT.format(
                        audit_json=audit_json_str,
                        benchmark_json=benchmark_json_str
                    )
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
            # For now, we take the first audit and first benchmark for the visual comparison if multiple are selected,
            # or we could iterate. The plan suggested expanding for grouped bar charts.
            # Let's check if VisualizationService can handle multiple.
            # If not, we might need to update it too.
            if len(selected_audit_files) == 1 and len(selected_lit_ids) == 1:
                fig = VisualizationService.plot_kpi_comparison(
                    audits_data[selected_audit_files[0]], 
                    benchmarks_data[selected_lit_titles[0]]
                )
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Visual comparison for multiple entries will show the overall energy comparison.")
                # Simple matrix bar chart
                rows = []
                for f, a_data in audits_data.items():
                    rows.append({
                        "Source": f,
                        "Energy (kWh)": a_data.get("Overall Summary", {}).get("Total Energy (kWh)", 0),
                        "Type": "Audit"
                    })
                for title, b_data in benchmarks_data.items():
                    benchmark_val = 0.0
                    try:
                        benchmark_val = float(str(b_data.get("energy_data", {}).get("energy_usage", "0")).split()[0])
                    except: pass
                    rows.append({
                        "Source": title,
                        "Energy (kWh)": benchmark_val,
                        "Type": "Benchmark"
                    })
                
                import plotly.express as px
                df_comp = pd.DataFrame(rows)
                fig = px.bar(df_comp, x="Source", y="Energy (kWh)", color="Type", barmode="group",
                             color_discrete_map={"Audit": COLORS["primary"], "Benchmark": COLORS["secondary"]})
                st.plotly_chart(fig, use_container_width=True)

            st.divider()
            st.subheader("Export")
            report_data = []
            for f, a_data in audits_data.items():
                report_data.append({
                    "filename": f,
                    "machine_name": a_data.get("metadata", {}).get("machine_name", "N/A"),
                    "machine_state": a_data.get("metadata", {}).get("machine_state", "N/A"),
                    "total_energy_combined": a_data.get("Overall Summary", {}).get("Total Energy (kWh)", 0),
                    "assessment": "See full report for matrix analysis."
                })

            pdf_buffer = ExportService.create_pdf_report(report_data)
            st.download_button(
                "Download PDF Report",
                data=pdf_buffer,
                file_name=f"comparison_report.pdf",
                mime="application/pdf",
                icon="⬇️",
                use_container_width=True
            )


def main():
    st.set_page_config(
        page_title="Factory-X Audit-App",
        layout="wide"
    )

    st.logo("assets/FX_logo_top_left.png")
    inject_custom_styles()

    init_session_state()
    render_sidebar()

    st.markdown(
        """
        <div style='display:flex; align-items:center; gap:24px; margin-bottom:1rem;'>
            <span class='material-symbols-rounded' style='font-size:48px;'>analytics</span>
            <span style='font-size:48px; font-weight:700; letter-spacing:0.8px;'>
                Factory-X Audit-App
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3 = st.tabs([
        "Document ➔ JSON",
        "Data ➔ JSON",
        "JSON Comparison"
    ])

    with tab1:
        render_paper_to_json()
    with tab2:
        render_data_to_json()
    with tab3:
        render_json_comparison()


if __name__ == "__main__":
    main()
