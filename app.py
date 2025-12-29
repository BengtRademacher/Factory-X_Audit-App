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

# --- Capability 1: Paper to JSON ---
def render_paper_to_json():
    st.header("📄 Paper to JSON Extractor")
    st.write("Extraktion von strukturierten Daten aus wissenschaftlichen PDFs.")
    st.divider()

    db = LiteratureDB()
    llm_service = st.session_state.get("llm_service")
    provider_name = st.session_state.get("llm_provider")
    provider = llm_service.get_provider(provider_name) if provider_name else None

    if not provider:
        st.error("❌ Bitte konfigurieren Sie einen LLM-Provider in der Sidebar.")
        return

    uploaded_files = st.file_uploader(
        "PDF-Dateien hochladen", 
        type=["pdf"], 
        accept_multiple_files=True
    )

    if uploaded_files and st.button(f"🚀 {len(uploaded_files)} Papers analysieren", type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, pdf_file in enumerate(uploaded_files):
            status_text.text(f"⏳ Verarbeite: {pdf_file.name} ({i+1}/{len(uploaded_files)})")
            
            # PDF direkt als Bytes einlesen
            pdf_bytes = pdf_file.read()
            
            start_time = time.time()
            try:
                with st.spinner(f"🤖 KI analysiert {pdf_file.name}..."):
                    # Direkte Übergabe der PDF-Bytes an das Modell
                    response = provider.generate_from_file(
                        prompt=PAPER_EXTRACTION_PROMPT,
                        file_bytes=pdf_bytes,
                        mime_type="application/pdf"
                    )
                
                thinking_time = time.time() - start_time
                
                # Bereinigung des JSON-Outputs vom LLM
                clean_json = response.strip()
                if clean_json.startswith("```json"):
                    clean_json = clean_json[7:-3]
                elif clean_json.startswith("```"):
                    clean_json = clean_json[3:-3]
                
                data = json.loads(clean_json)
                
                # In DB speichern
                db.add_entry(data, pdf_file=pdf_bytes, filename=pdf_file.name.replace(".pdf", ""))
                st.success(f"✅ Erfolgreich extrahiert: {pdf_file.name} (🕒 {thinking_time:.2f}s)")
                
                with st.expander(f"🔍 Details für {pdf_file.name}"):
                    st.json(data)
                
            except Exception as e:
                st.error(f"❌ Fehler bei {pdf_file.name}: {e}")
                with st.expander("📝 Roh-Output anzeigen"):
                    st.text(response if 'response' in locals() else "Kein Output verfügbar")
            
            progress_bar.progress((i + 1) / len(uploaded_files))
        
        status_text.success("🏁 Alle Dateien verarbeitet!")

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
    st.header("📊 Data to JSON")
    st.write("Verarbeitung von Maschinen-Messdaten aus Excel oder CSV.")
    st.divider()

    store = WorkingStore()
    
    # User Inputs in Columns
    st.subheader("🛠️ Maschinen-Konfiguration")
    col_a, col_b = st.columns(2)
    with col_a:
        machine_name = st.text_input("Maschinen-Name", value="CNC_Milling_1")
        operator = st.text_input("Operator", value="Admin")
    with col_b:
        machine_state = st.selectbox("Maschinen-Status", ["Idle", "Cutting", "Cooling", "Maintenance"])
        material = st.text_input("Material", value="Aluminum")

    st.divider()
    uploaded_file = st.file_uploader("📂 Messdaten hochladen (.xlsx, .csv)", type=["xlsx", "csv"])

    if uploaded_file:
        try:
            df = DataParser.read_file(uploaded_file)
            st.success(f"✅ Datei geladen: {uploaded_file.name} ({len(df)} Zeilen)")
            
            if "elapsedTime" not in df.columns:
                st.error("❌ Die Datei muss eine Spalte 'elapsedTime' enthalten.")
                return

            # Definition der Variablen-Gruppen
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

            if st.button("⚙️ Metriken berechnen", type="primary"):
                with st.spinner("🔢 Berechne KPIs..."):
                    elek_details, elek_total = DataParser.compute_metrics(df, vars_elektrisch)
                    pneu_details, pneu_total = DataParser.compute_metrics(df, vars_pneumatisch)
                    
                    duty_elek = DataParser.calculate_duty_cycle(df, vars_elektrisch, elek_total.get("mean", 0))
                    duty_pneu = DataParser.calculate_duty_cycle(df, vars_pneumatisch, pneu_total.get("mean", 0))
                    
                    duration_sec = df["elapsedTime"].iloc[-1] - df["elapsedTime"].iloc[0]
                    
                    results = {
                        "metadata": {
                            "machine_name": machine_name,
                            "operator": operator,
                            "machine_state": machine_state,
                            "material": material,
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
                            "Total Energy (kWh)": round(elek_total.get("total_energy_kWh", 0) + pneu_total.get("total_energy_kWh", 0), 4),
                            "Mean Power (W)": round((elek_total.get("mean", 0) + pneu_total.get("mean", 0)) / 2, 2),
                            "Energy Rate (kWh/hour)": round((elek_total.get("total_energy_kWh", 0) + pneu_total.get("total_energy_kWh", 0)) / (duration_sec / 3600), 4) if duration_sec > 0 else 0,
                            "Top Variables": {}
                        }
                    }
                    
                    # Speichern
                    filename = f"audit_{machine_name}_{uploaded_file.name.split('.')[0]}.json"
                    store.save_audit(results, filename)
                    st.success(f"✅ Audit gespeichert als {filename}")
                    
                    # Visualisierung
                    st.divider()
                    st.subheader("📈 Visualisierung")
                    fig = VisualizationService.plot_energy_distribution(results)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with st.expander("📄 JSON-Resultat anzeigen"):
                        st.json(results)

        except Exception as e:
            st.error(f"❌ Fehler bei der Verarbeitung: {e}")

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
    st.header("🔍 JSON Comparison")
    st.write("Vergleich von Audit-Daten mit Literatur-Benchmarks via LLM.")
    st.divider()

    lit_db = LiteratureDB()
    work_store = WorkingStore()
    llm_service = st.session_state.get("llm_service")
    provider_name = st.session_state.get("llm_provider")
    provider = llm_service.get_provider(provider_name) if provider_name else None

    col_audit, col_benchmark = st.columns(2)
    
    with col_audit:
        st.subheader("1. 📊 Audit Daten wählen")
        audit_files = work_store.list_audits()
        selected_audit_file = st.selectbox("Audit JSON auswählen", options=audit_files)
        
    with col_benchmark:
        st.subheader("2. 📚 Benchmark wählen")
        lit_entries = lit_db.get_all_entries()
        lit_options = {e['title']: e['id'] for e in lit_entries}
        selected_lit_title = st.selectbox("Literatur Benchmark auswählen", options=list(lit_options.keys()))
        selected_lit_id = lit_options.get(selected_lit_title)

    if selected_audit_file and selected_lit_id:
        if st.button("🚀 Analyse starten", type="primary"):
            if not provider:
                st.error("❌ Bitte LLM-Provider konfigurieren.")
                return
                
            audit_data = work_store.load_audit(selected_audit_file)
            benchmark_data = lit_db.get_entry_by_id(selected_lit_id)
            
            start_time = time.time()
            with st.spinner("🤖 AI analysiert den Vergleich..."):
                prompt = COMPARISON_PROMPT.format(
                    audit_json=json.dumps(audit_data, indent=2),
                    benchmark_json=json.dumps(benchmark_data, indent=2)
                )
                assessment = provider.generate(prompt)
            
            thinking_time = time.time() - start_time
                
            st.divider()
            st.subheader(f"📝 Analyse-Ergebnis (🕒 {thinking_time:.2f}s)")
            st.markdown(assessment)
            
            # Visualisierung
            st.divider()
            st.subheader("📊 Visueller Vergleich")
            fig = VisualizationService.plot_kpi_comparison(audit_data, benchmark_data)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
                
            # Export
            st.divider()
            st.subheader("📤 Export")
            report_data = [{
                "filename": selected_audit_file,
                "machine_name": audit_data.get("metadata", {}).get("machine_name", "N/A"),
                "machine_state": audit_data.get("metadata", {}).get("machine_state", "N/A"),
                "total_energy_combined": audit_data.get("Overall Summary", {}).get("Total Energy (kWh)", 0),
                "assessment": assessment
            }]
            
            pdf_buffer = ExportService.create_pdf_report(report_data)
            st.download_button(
                "⬇️ PDF Bericht herunterladen",
                data=pdf_buffer,
                file_name=f"comparison_{selected_audit_file.replace('.json', '')}.pdf",
                mime="application/pdf"
            )

# --- Main App ---
def main():
    st.set_page_config(
        page_title=settings.APP_NAME,
        page_icon="🔍",
        layout="wide"
    )

    # Sidebar: AI Configuration
    st.sidebar.title("🛠️ Einstellungen")
    
    llm_service = st.session_state.get("llm_service")
    if not llm_service:
        llm_service = LLMService()
        st.session_state["llm_service"] = llm_service
        
    available_providers = llm_service.list_providers()
    
    st.sidebar.subheader("🤖 AI Backend")
    if not available_providers:
        st.sidebar.warning("⚠️ Keine LLM-Provider konfiguriert. Bitte secrets.toml prüfen.")
        selected_provider = None
    else:
        # Prominente Backend-Auswahl via Radio
        selected_provider = st.sidebar.radio(
            "Bevorzugter Provider",
            options=available_providers,
            index=0 if "gemini" in available_providers else 0
        )
        st.session_state["llm_provider"] = selected_provider

    st.sidebar.divider()
    st.sidebar.markdown(f"**App Version:** {settings.APP_NAME}")

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
