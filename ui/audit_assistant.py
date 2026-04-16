import pandas as pd
import streamlit as st

from core.data_parser import DataParser
from database.literature_db import LiteratureDB
from database.working_store import WorkingStore
from services.export_service import ExportService
from services.visualization import VisualizationService
from ui.common import handle_llm_error, render_tab_header
from workflows.audit import calculate_audit_results_from_mapping
from workflows.audit_draft import build_audit_draft
from workflows.evidence import build_evidence_cards_from_literature, select_relevant_evidence_cards
from workflows.measurement_profile import (
    apply_time_column_selection,
    build_measurement_context,
    default_energy_component_columns,
    enhance_mapping_with_supply_ai,
    filter_profile_for_selected_components,
    generate_mapping_with_llm,
    infer_time_column_with_ai,
    normalize_mapping,
    profile_measurement_dataframe,
    should_infer_time_column_with_ai,
)
from workflows.operating_state import OPERATING_STATES, operating_state_to_machine_state


def render_audit_assistant():
    render_tab_header("assignment", "Audit Assistant", "Guided audit workflow from measurement data to management report.")

    store = WorkingStore()
    lit_db = LiteratureDB()
    llm_service = st.session_state.llm_service
    provider_name = st.session_state.llm_provider
    provider = llm_service.get_provider(provider_name, model=st.session_state.llm_model) if provider_name else None

    st.subheader("1. Machine and Measurement Data")
    col_meta_1, col_meta_2 = st.columns(2)
    with col_meta_1:
        machine_name = st.text_input("Machine Name", value=st.session_state.machine_name, key="assistant_machine_name")
        operator = st.text_input("Operator", value=st.session_state.operator, key="assistant_operator")
    with col_meta_2:
        operating_state = st.selectbox(
            "Operating State",
            OPERATING_STATES,
            index=OPERATING_STATES.index(st.session_state.operating_state)
            if st.session_state.operating_state in OPERATING_STATES
            else 0,
            key="assistant_operating_state",
        )
        st.session_state.operating_state = operating_state
        machine_state = operating_state_to_machine_state(operating_state)
        st.session_state.machine_state = machine_state
        material = st.text_input("Material", value=st.session_state.material, key="assistant_material")

    uploaded_file = st.file_uploader("Upload Measurement Data", type=["xlsx", "csv"], key="assistant_data_uploader")
    if not uploaded_file:
        st.info("Upload a measurement file to start the guided audit.")
        return

    file_key = (uploaded_file.name, getattr(uploaded_file, "size", None))
    if st.session_state.get("audit_uploaded_file_key") != file_key:
        st.session_state.audit_uploaded_file_key = file_key
        st.session_state.audit_mapping = None
        st.session_state.audit_results = None
        st.session_state.audit_draft = None
        st.session_state.audit_evidence_cards = []
        st.session_state.audit_mapping_chat = []
        st.session_state.audit_measurement_context = None
        st.session_state.audit_time_ai_key = None
        st.session_state.audit_time_ai_result = None
        st.session_state.audit_supply_ai_key = None
        st.session_state.audit_supply_ai_result = None
        st.session_state.audit_selected_component_columns = None
        st.session_state.audit_component_selection_key = None

    try:
        df = DataParser.read_file(uploaded_file)
    except Exception as e:
        st.error(f"Error during processing: {e}")
        return

    profile = profile_measurement_dataframe(df)
    measurement_context = build_measurement_context(df, profile)
    if provider and should_infer_time_column_with_ai(profile) and st.session_state.get("audit_time_ai_key") != file_key:
        with st.spinner("Inferring time column from measurement context..."):
            try:
                st.session_state.audit_time_ai_result = infer_time_column_with_ai(provider, profile, measurement_context)
                st.session_state.audit_time_ai_key = file_key
            except Exception as e:
                st.warning(f"Time-column AI fallback failed: {e}")
                st.session_state.audit_time_ai_key = file_key
    ai_time_result = st.session_state.get("audit_time_ai_result")
    if ai_time_result and ai_time_result.get("source") == "ai" and ai_time_result.get("time_column"):
        profile = apply_time_column_selection(
            profile,
            df,
            ai_time_result["time_column"],
            source="ai",
            confidence=ai_time_result.get("confidence"),
            rationale=ai_time_result.get("rationale", ""),
        )
    st.session_state.audit_profile = profile
    measurement_context = build_measurement_context(df, profile)
    st.session_state.audit_measurement_context = measurement_context
    st.caption(f"Rows: {profile['row_count']} | Time column: {profile.get('time_column')} | Sampling rate: {profile.get('sampling_rate_hz')} Hz")

    column_options = [""] + [column["name"] for column in profile.get("columns", [])]
    selected_time_column = st.selectbox(
        "Time column",
        options=column_options,
        index=column_options.index(profile["time_column"]) if profile.get("time_column") in column_options else 0,
        help="Automatically detected time axis. You can change it before calculating the audit.",
        key="assistant_time_column",
    ) if column_options else None
    if selected_time_column and selected_time_column != profile.get("time_column"):
        profile = apply_time_column_selection(
            profile,
            df,
            selected_time_column,
            source="manual",
            confidence=1.0,
            rationale="User selected the time column in the Audit Assistant.",
        )
        st.session_state.audit_profile = profile
        measurement_context = build_measurement_context(df, profile)
        st.session_state.audit_measurement_context = measurement_context
        if st.session_state.get("audit_mapping"):
            st.session_state.audit_mapping["time_column"] = selected_time_column
            st.session_state.audit_mapping["sampling_rate_hz"] = profile.get("sampling_rate_hz")
    if profile.get("time_column_source") == "ai":
        st.info(
            f"AI selected `{profile.get('time_column')}` as time column "
            f"(confidence {profile.get('time_column_confidence', 0):.2f}): "
            f"{profile.get('time_column_rationale', '')}"
        )
    elif profile.get("time_column_source") != "local_name_hint":
        st.warning(
            f"Time column detection is uncertain: {profile.get('time_column_rationale', 'No rationale available.')}"
        )

    with st.expander("Measurement Profile", expanded=False):
        st.dataframe(pd.DataFrame(profile["columns"]), width="stretch")

    st.divider()
    st.subheader("2. AI-assisted Channel Mapping")
    numeric_component_options = [
        column["name"]
        for column in profile.get("columns", [])
        if column.get("is_numeric") and column.get("name") != profile.get("time_column")
    ]
    selected_component_columns = st.session_state.get("audit_selected_component_columns")
    if selected_component_columns is None:
        selected_component_columns = default_energy_component_columns(profile)
        st.session_state.audit_selected_component_columns = selected_component_columns
    selected_component_columns = [
        column for column in selected_component_columns
        if column in numeric_component_options
    ]
    st.session_state.audit_selected_component_columns = selected_component_columns
    selected_component_columns = st.multiselect(
        "Energy component selection",
        options=numeric_component_options,
        help="Only selected columns are mapped, calculated, charted, and included in the PDF energy balance.",
        key="audit_selected_component_columns",
    )
    selection_key = tuple(selected_component_columns)
    if st.session_state.get("audit_component_selection_key") is None:
        st.session_state.audit_component_selection_key = selection_key
    elif st.session_state.audit_component_selection_key != selection_key:
        st.session_state.audit_component_selection_key = selection_key
        st.session_state.audit_mapping = None
        st.session_state.audit_results = None
        st.session_state.audit_draft = None
        st.session_state.audit_supply_ai_key = None
    excluded_components = [
        column for column in numeric_component_options
        if column not in selected_component_columns
    ]
    if excluded_components:
        excluded_preview = ", ".join(excluded_components[:8])
        suffix = " ..." if len(excluded_components) > 8 else ""
        st.info(
            "Excluded numeric columns stay visible in the measurement profile but are not included in the energy audit: "
            f"{excluded_preview}{suffix}"
        )
    mapping_profile = filter_profile_for_selected_components(profile, selected_component_columns)
    mapping_context = build_measurement_context(df, mapping_profile)
    mapping_guidance = st.text_area(
        "Mapping guidance",
        value=st.session_state.get("audit_mapping_guidance", ""),
        help="Optional instruction for the AI, e.g. 'AirPower columns are pneumatic and all values are kW'.",
    )
    st.session_state.audit_mapping_guidance = mapping_guidance
    with st.expander("Mapping chat", expanded=False):
        for message in st.session_state.get("audit_mapping_chat", []):
            st.write(f"**{message['role']}:** {message['content']}")
        chat_instruction = st.text_input(
            "Tell the mapping assistant what to change",
            key="audit_mapping_chat_input",
            placeholder="Example: Treat every AirPower column as pneumatic and values as kW.",
        )
        if st.button("Apply Mapping Chat Update", width="stretch"):
            if chat_instruction:
                st.session_state.audit_mapping_chat.append({"role": "user", "content": chat_instruction})
                combined_guidance = "\n".join(
                    [mapping_guidance] + [msg["content"] for msg in st.session_state.audit_mapping_chat]
                )
                with st.spinner("Updating mapping proposal..."):
                    try:
                        mapping = generate_mapping_with_llm(provider, mapping_profile, combined_guidance)
                        st.session_state.audit_mapping = _enhance_mapping_once(provider, mapping, mapping_profile, mapping_context, file_key)
                        st.session_state.audit_mapping_chat.append({"role": "assistant", "content": "Mapping proposal updated."})
                    except Exception as e:
                        handle_llm_error(e)
                        return

    if st.button("Suggest / Update Mapping", type="primary", width="stretch"):
        with st.spinner("Generating mapping proposal..."):
            try:
                mapping = generate_mapping_with_llm(provider, mapping_profile, mapping_guidance)
                st.session_state.audit_mapping = _enhance_mapping_once(provider, mapping, mapping_profile, mapping_context, file_key)
            except Exception as e:
                handle_llm_error(e)
                return

    mapping = st.session_state.get("audit_mapping")
    if mapping is None:
        mapping = generate_mapping_with_llm(None, mapping_profile, "")
        mapping = _enhance_mapping_once(provider, mapping, mapping_profile, mapping_context, file_key)
        st.session_state.audit_mapping = mapping
    else:
        mapping["time_column"] = mapping_profile.get("time_column")
        mapping["sampling_rate_hz"] = mapping_profile.get("sampling_rate_hz")
        mapping = normalize_mapping(mapping, mapping_profile)
        st.session_state.audit_mapping = mapping

    mapping_df = _mapping_to_dataframe(mapping)
    edited_mapping_df = st.data_editor(
        mapping_df,
        num_rows="dynamic",
        width="stretch",
        key="assistant_mapping_editor",
        column_config={
            "medium": st.column_config.SelectboxColumn("medium", options=["electric", "pneumatic", "other"]),
            "unit": st.column_config.SelectboxColumn("unit", options=["W", "kW", "unknown"]),
            "include_in_audit": st.column_config.CheckboxColumn("include_in_audit"),
            "supply_role": st.column_config.SelectboxColumn("supply_role", options=["main_supply", "component", "other"]),
            "is_balance_source": st.column_config.CheckboxColumn("is_balance_source"),
            "confidence": st.column_config.NumberColumn("confidence", min_value=0.0, max_value=1.0, step=0.05),
        },
    )

    if st.button("Approve Mapping and Calculate Audit", width="stretch"):
        approved_mapping = _dataframe_to_mapping(edited_mapping_df, mapping, mapping_profile)
        approved_mapping = normalize_mapping(approved_mapping, mapping_profile)
        metadata = {
            "machine_name": machine_name,
            "operator": operator,
            "machine_state": machine_state,
            "operating_state": operating_state,
            "material": material,
            "selected_component_columns": selected_component_columns,
            "excluded_numeric_columns": excluded_components,
        }
        try:
            audit_results = calculate_audit_results_from_mapping(df, approved_mapping, metadata)
        except Exception as e:
            st.error(f"Error during processing: {e}")
            return
        st.session_state.audit_mapping = approved_mapping
        st.session_state.audit_results = audit_results
        st.session_state.last_audit_results = audit_results
        store.save_audit(audit_results, f"audit_{machine_name}_{uploaded_file.name.rsplit('.', 1)[0]}_assistant.json")
        st.toast("Audit metrics calculated and saved.")

    audit_results = st.session_state.get("audit_results")
    if not audit_results:
        return

    st.divider()
    st.subheader("3. Metrics and Local Literature Evidence")
    _render_metrics(audit_results)

    entries = []
    for entry in lit_db.get_all_entries():
        data = lit_db.get_entry_by_id(entry["id"])
        if data:
            entries.append(data)
    evidence_cards = build_evidence_cards_from_literature(entries)
    selected_evidence = select_relevant_evidence_cards(audit_results, evidence_cards)
    st.session_state.audit_evidence_cards = selected_evidence

    with st.expander("Selected Evidence Cards", expanded=True):
        if selected_evidence:
            st.dataframe(pd.DataFrame(selected_evidence), width="stretch")
        else:
            st.info("No local evidence cards matched the current audit context.")

    st.divider()
    st.subheader("4. Editable Audit Draft")
    manual_notes = st.text_area("Manual notes and assumptions", value=st.session_state.get("audit_manual_notes", ""), height=120)
    st.session_state.audit_manual_notes = manual_notes

    if st.button("Build / Refresh Audit Draft", width="stretch"):
        st.session_state.audit_draft = build_audit_draft(audit_results, selected_evidence, manual_notes, provider=provider)

    draft = st.session_state.get("audit_draft")
    if not draft:
        return

    draft["executive_summary"] = st.text_area("Executive Summary", value=draft.get("executive_summary", ""), height=140)
    traffic = draft.get("traffic_lights", {})
    cols = st.columns(len(traffic) or 1)
    for idx, (area, rating) in enumerate(traffic.items()):
        with cols[idx]:
            traffic[area] = st.selectbox(area, ["Green", "Yellow", "Red"], index=["Green", "Yellow", "Red"].index(rating), key=f"traffic_{area}")
    draft["traffic_lights"] = traffic

    measures_df = pd.DataFrame(draft.get("recommended_measures", []))
    edited_measures = st.data_editor(measures_df, num_rows="dynamic", width="stretch", key="assistant_measures_editor")
    draft["recommended_measures"] = edited_measures.fillna("").to_dict(orient="records")
    draft["manual_notes"] = manual_notes
    st.session_state.audit_draft = draft

    st.divider()
    st.subheader("5. Management Report")
    pdf_buffer = ExportService.create_management_audit_report(audit_results, draft)
    st.download_button(
        "Download Management Audit PDF",
        data=pdf_buffer,
        file_name=f"management_audit_{machine_name}.pdf",
        mime="application/pdf",
        width="stretch",
    )


def _mapping_to_dataframe(mapping):
    columns = [
        "source_column",
        "canonical_name",
        "medium",
        "unit",
        "scale_to_watts",
        "sampling_rate_hz",
        "include_in_audit",
        "supply_role",
        "is_balance_source",
        "parent_supply",
        "confidence",
        "rationale",
    ]
    data = mapping.get("channels", [])
    if not data:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(data)
    for column in columns:
        if column not in df.columns:
            if column == "is_balance_source":
                df[column] = False
            elif column == "include_in_audit":
                df[column] = True
            else:
                df[column] = ""
    return df[columns]


def _dataframe_to_mapping(mapping_df, base_mapping, profile):
    return {
        "time_column": base_mapping.get("time_column") or profile.get("time_column"),
        "sampling_rate_hz": base_mapping.get("sampling_rate_hz") or profile.get("sampling_rate_hz"),
        "channels": mapping_df.fillna("").to_dict(orient="records"),
        "notes": base_mapping.get("notes", ""),
        "component_selection": profile.get("component_selection", base_mapping.get("component_selection", {})),
    }


def _enhance_mapping_once(provider, mapping, profile, measurement_context, file_key):
    if provider and st.session_state.get("audit_supply_ai_key") != file_key:
        try:
            enhanced = enhance_mapping_with_supply_ai(provider, mapping, profile, measurement_context)
            st.session_state.audit_supply_ai_key = file_key
            st.session_state.audit_supply_ai_result = enhanced.get("main_supplies")
            return enhanced
        except Exception as e:
            st.warning(f"Main-supply AI fallback failed: {e}")
            st.session_state.audit_supply_ai_key = file_key
    return enhance_mapping_with_supply_ai(None, mapping, profile, measurement_context)


def _render_metrics(audit_results):
    summary = audit_results.get("Overall Summary", {})
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Energy", f"{summary.get('Total Energy (kWh)', 0):.4f} kWh")
    col2.metric("Mean Power", f"{summary.get('Mean Power (W)', 0):.1f} W")
    col3.metric("Energy Rate", f"{summary.get('Energy Rate (kWh/hour)', 0):.4f} kWh/h")
    col4.metric("Duration", f"{audit_results.get('metadata', {}).get('duration_seconds', 0):.0f} s")

    fig = VisualizationService.plot_energy_distribution(audit_results)
    balance_fig = VisualizationService.plot_balanced_energy_pie(audit_results)
    if balance_fig:
        st.plotly_chart(balance_fig, width="stretch")
    if fig:
        st.plotly_chart(fig, width="stretch")
