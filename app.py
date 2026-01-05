import streamlit as st
import json
import time
from io import BytesIO
from core.llm_service import LLMService
from config.settings import settings
from config.prompts import PAPER_EXTRACTION_PROMPT, COMPARISON_PROMPT
from database.literature_db import LiteratureDB
from database.working_store import WorkingStore
from core.data_parser import DataParser
from services.visualization import VisualizationService
from services.export_service import ExportService

# --- Session State & UI Helpers ---
def init_session_state():
    """Initialisiert alle Session State Variablen mit Standardwerten."""
    defaults = {
        "llm_service": None,
        "llm_provider": None,
        # Form Inputs für Tab 2 (Data to JSON)
        "machine_name": "CNC_Milling_1",
        "operator": "Admin",
        "machine_state": "Idle",
        "material": "Aluminum",
        # Letzte Ergebnisse für Persistenz
        "last_audit_results": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_sidebar():
    """Rendert die Sidebar mit LLM-Konfiguration und App-Info."""
    st.sidebar.title("Einstellungen")
    
    # LLM Service initialisieren falls nötig
    if st.session_state.llm_service is None:
        st.session_state.llm_service = LLMService()
    
    llm_service = st.session_state.llm_service
    available_providers = llm_service.list_providers()
    
    st.sidebar.subheader("AI Backend")
    if not available_providers:
        st.sidebar.warning("Keine LLM-Provider konfiguriert. Bitte secrets.toml pruefen.")
    else:
        selected_provider = st.sidebar.radio(
            "Bevorzugter Provider",
            options=available_providers,
            index=0 if "gemini" in available_providers else 0
        )
        st.session_state.llm_provider = selected_provider
    
    st.sidebar.divider()
    st.sidebar.caption(f"Version: {settings.APP_NAME}")


def render_tab_header(icon: str, title: str, description: str):
    """Einheitlicher Header für jeden Tab."""
    st.header(f"{icon} {title}")
    st.caption(description)
    st.divider()


# --- Capability 1: Paper to JSON ---
def render_paper_to_json():
    render_tab_header("📄", "Paper to JSON Extractor", "Extraktion von strukturierten Daten aus wissenschaftlichen PDFs.")

    db = LiteratureDB()
    llm_service = st.session_state.llm_service
    provider_name = st.session_state.llm_provider
    provider = llm_service.get_provider(provider_name) if provider_name else None

    if not provider:
        st.error("Bitte konfigurieren Sie einen LLM-Provider in der Sidebar.")
        return

    uploaded_files = st.file_uploader(
        "PDF-Dateien hochladen", 
        type=["pdf"], 
        accept_multiple_files=True,
        key="paper_uploader"
    )

    if uploaded_files and st.button(f"Papers analysieren ({len(uploaded_files)})", type="primary", icon="🚀"):
        with st.status("Verarbeite Papers...", expanded=True) as status:
            results_container = st.container()
            
            for i, pdf_file in enumerate(uploaded_files):
                st.write(f"⏳ **{pdf_file.name}** ({i+1}/{len(uploaded_files)})")
                
                pdf_bytes = pdf_file.read()
                start_time = time.time()
                
                try:
                    response = provider.generate_from_file(
                        prompt=PAPER_EXTRACTION_PROMPT,
                        file_bytes=pdf_bytes,
                        mime_type="application/pdf"
                    )
                    thinking_time = time.time() - start_time
                    
                    # Bereinigung des JSON-Outputs
                    clean_json = response.strip()
                    if clean_json.startswith("```json"):
                        clean_json = clean_json[7:-3]
                    elif clean_json.startswith("```"):
                        clean_json = clean_json[3:-3]
                    
                    data = json.loads(clean_json)
                    db.add_entry(data, pdf_file=pdf_bytes, filename=pdf_file.name.replace(".pdf", ""))
                    
                    st.write(f"✅ Erfolgreich ({thinking_time:.1f}s)")
                    with results_container:
                        with st.expander(f"Details: {pdf_file.name}"):
                            st.json(data)
                    
                except Exception as e:
                    st.write(f"❌ Fehler: {e}")
                    with results_container:
                        with st.expander(f"Roh-Output: {pdf_file.name}"):
                            st.text(response if 'response' in locals() else "Kein Output")
            
            status.update(label="Verarbeitung abgeschlossen!", state="complete", expanded=False)
        st.toast("Alle Papers verarbeitet!", icon="🎉")

    # Anzeige der Datenbank
    st.divider()
    st.subheader("📚 Literaturdatenbank")
    entries = db.get_all_entries()
    if entries:
        for entry in entries:
            with st.expander(f"📄 {entry['title']} ({', '.join(entry['authors'][:2])}...)"):
                col_info, col_actions = st.columns([3, 1])
                with col_info:
                    st.write(f"**ID:** {entry['id']}")
                    st.write(f"**Datum:** {entry['date']}")
                with col_actions:
                    if st.button("👁️ JSON", key=f"details_{entry['id']}"):
                        full_data = db.get_entry_by_id(entry['id'])
                        st.json(full_data)
                    if st.button("🗑️ Löschen", key=f"del_{entry['id']}"):
                        db.delete_entry(entry['id'])
                        st.rerun()
    else:
        st.info("ℹ️ Noch keine Einträge in der Datenbank.")

# --- Capability 2: Data to JSON ---
def render_data_to_json():
    render_tab_header("📊", "Data to JSON", "Verarbeitung von Maschinen-Messdaten aus Excel oder CSV.")

    store = WorkingStore()
    
    # User Inputs mit Session State Persistenz
    st.subheader("Maschinen-Konfiguration")
    col_a, col_b = st.columns(2)
    with col_a:
        st.session_state.machine_name = st.text_input(
            "Maschinen-Name", 
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
            "Maschinen-Status", 
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
    uploaded_file = st.file_uploader("Messdaten hochladen", type=["xlsx", "csv"], key="data_uploader")

    if uploaded_file:
        try:
            df = DataParser.read_file(uploaded_file)
            st.toast(f"Datei geladen: {len(df)} Zeilen", icon="📂")
            
            if "elapsedTime" not in df.columns:
                st.error("Die Datei muss eine Spalte 'elapsedTime' enthalten.")
                return

            # Variablen-Gruppen
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

            if st.button("Metriken berechnen", type="primary", icon="⚙️"):
                with st.spinner("Berechne KPIs..."):
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
                    
                    # Speichern
                    filename = f"audit_{st.session_state.machine_name}_{uploaded_file.name.split('.')[0]}.json"
                    store.save_audit(results, filename)
                    st.session_state.last_audit_results = results
                    st.toast(f"Audit gespeichert: {filename}", icon="💾")
                    
                    # KPI Metriken Dashboard
                    st.divider()
                    st.subheader("Ergebnisse")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Gesamt-Energie", f"{total_energy:.4f} kWh")
                    col2.metric("Mittlere Leistung", f"{mean_power:.1f} W")
                    col3.metric("Energierate", f"{energy_rate:.4f} kWh/h")
                    col4.metric("Dauer", f"{duration_sec:.0f} s")
                    
                    # Duty Cycle Metriken
                    col_e, col_p = st.columns(2)
                    col_e.metric("Duty Cycle Elektrisch", f"{duty_elek:.1f} %")
                    col_p.metric("Duty Cycle Pneumatisch", f"{duty_pneu:.1f} %")
                    
                    # Visualisierung
                    st.divider()
                    st.subheader("Visualisierung")
                    fig = VisualizationService.plot_energy_distribution(results)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with st.expander("JSON-Resultat anzeigen"):
                        st.json(results)

        except Exception as e:
            st.error(f"Fehler bei der Verarbeitung: {e}")

    # Liste existierender Audits
    st.divider()
    st.subheader("📂 Gespeicherte Audits (Working Store)")
    audits = store.list_audits()
    if audits:
        for audit in audits:
            with st.expander(f"📊 {audit}"):
                col_btn1, col_btn2 = st.columns([1, 1])
                if col_btn1.button("👁️ Laden", key=f"load_{audit}"):
                    data = store.load_audit(audit)
                    st.json(data)
                if col_btn2.button("🗑️ Löschen", key=f"del_audit_{audit}"):
                    store.delete_audit(audit)
                    st.rerun()
    else:
        st.info("ℹ️ Noch keine Audits im Store.")

# --- Capability 3: JSON Comparison ---
def render_json_comparison():
    render_tab_header("🔍", "JSON Comparison", "Vergleich von Audit-Daten mit Literatur-Benchmarks via LLM.")

    lit_db = LiteratureDB()
    work_store = WorkingStore()
    llm_service = st.session_state.llm_service
    provider_name = st.session_state.llm_provider
    provider = llm_service.get_provider(provider_name) if provider_name else None

    col_audit, col_benchmark = st.columns(2)
    
    with col_audit:
        st.subheader("1. Audit Daten")
        audit_files = work_store.list_audits()
        selected_audit_file = st.selectbox("Audit JSON auswaehlen", options=audit_files, key="comp_audit")
        
    with col_benchmark:
        st.subheader("2. Benchmark")
        lit_entries = lit_db.get_all_entries()
        lit_options = {e['title']: e['id'] for e in lit_entries}
        selected_lit_title = st.selectbox("Literatur Benchmark auswaehlen", options=list(lit_options.keys()), key="comp_bench")
        selected_lit_id = lit_options.get(selected_lit_title)

    if selected_audit_file and selected_lit_id:
        if st.button("Analyse starten", type="primary", icon="🚀"):
            if not provider:
                st.error("Bitte LLM-Provider konfigurieren.")
                return
                
            audit_data = work_store.load_audit(selected_audit_file)
            benchmark_data = lit_db.get_entry_by_id(selected_lit_id)
            
            start_time = time.time()
            with st.status("AI analysiert den Vergleich...", expanded=True) as status:
                prompt = COMPARISON_PROMPT.format(
                    audit_json=json.dumps(audit_data, indent=2),
                    benchmark_json=json.dumps(benchmark_data, indent=2)
                )
                assessment = provider.generate(prompt)
                thinking_time = time.time() - start_time
                status.update(label=f"Analyse abgeschlossen ({thinking_time:.1f}s)", state="complete", expanded=False)
            
            st.divider()
            st.subheader("Analyse-Ergebnis")
            st.markdown(assessment)
            
            # Visualisierung
            st.divider()
            st.subheader("Visueller Vergleich")
            fig = VisualizationService.plot_kpi_comparison(audit_data, benchmark_data)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
                
            # Export
            st.divider()
            st.subheader("Export")
            report_data = [{
                "filename": selected_audit_file,
                "machine_name": audit_data.get("metadata", {}).get("machine_name", "N/A"),
                "machine_state": audit_data.get("metadata", {}).get("machine_state", "N/A"),
                "total_energy_combined": audit_data.get("Overall Summary", {}).get("Total Energy (kWh)", 0),
                "assessment": assessment
            }]
            
            pdf_buffer = ExportService.create_pdf_report(report_data)
            st.download_button(
                "PDF Bericht herunterladen",
                data=pdf_buffer,
                file_name=f"comparison_{selected_audit_file.replace('.json', '')}.pdf",
                mime="application/pdf",
                icon="⬇️"
            )

# --- Main App ---
def main():
    st.set_page_config(
        page_title=settings.APP_NAME,
        page_icon="🔍",
        layout="wide"
    )
    
    # Session State initialisieren (muss zuerst passieren)
    init_session_state()
    
    # Sidebar rendern
    render_sidebar()

    # Tabs for main content
    tab1, tab2, tab3 = st.tabs([
        "📄 Paper to JSON", 
        "📊 Data to JSON", 
        "🔍 JSON Comparison"
    ])

    with tab1:
        render_paper_to_json()

    with tab2:
        render_data_to_json()

    with tab3:
        render_json_comparison()


if __name__ == "__main__":
    main()
