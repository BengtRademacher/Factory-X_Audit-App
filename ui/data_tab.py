import streamlit as st

from core.data_parser import DataParser
from database.working_store import WorkingStore
from services.visualization import VisualizationService
from ui.common import render_tab_header
from workflows.audit import calculate_audit_results
from workflows.operating_state import OPERATING_STATES, operating_state_to_machine_state


def render_data_to_json():
    render_tab_header("query_stats", "Data -> JSON", "Processing machine measurement data from Excel or CSV.")
    render_measurement_audit_json_section()


def render_measurement_audit_json_section():
    store = WorkingStore()

    st.subheader("Measurement Audit JSON")
    st.caption("Quick calculator for legacy measurement files with an `elapsedTime` column.")
    col_a, col_b = st.columns(2)
    with col_a:
        st.session_state.machine_name = st.text_input(
            "Machine Name",
            value=st.session_state.machine_name,
            key="input_machine_name",
        )
        st.session_state.operator = st.text_input(
            "Operator",
            value=st.session_state.operator,
            key="input_operator",
        )
    with col_b:
        operating_state = st.selectbox(
            "Operating State",
            OPERATING_STATES,
            index=OPERATING_STATES.index(st.session_state.operating_state)
            if st.session_state.operating_state in OPERATING_STATES
            else 0,
            key="input_operating_state",
        )
        st.session_state.operating_state = operating_state
        st.session_state.machine_state = operating_state_to_machine_state(operating_state)
        st.session_state.material = st.text_input(
            "Material",
            value=st.session_state.material,
            key="input_material",
        )

    uploaded_file = st.file_uploader("Upload Measurement Data", type=["xlsx", "xls", "csv"], key="data_uploader")

    if uploaded_file:
        try:
            df = DataParser.read_file(uploaded_file)
            st.toast(f"File loaded: {len(df)} rows")

            if "elapsedTime" not in df.columns:
                st.error("The file must contain an `elapsedTime` column.")
                return

            if st.button("Calculate Metrics", type="primary", width="stretch"):
                with st.spinner("Calculating KPIs..."):
                    results = calculate_audit_results(
                        df,
                        {
                            "machine_name": st.session_state.machine_name,
                            "operator": st.session_state.operator,
                            "machine_state": st.session_state.machine_state,
                            "operating_state": st.session_state.operating_state,
                            "material": st.session_state.material,
                        },
                    )
                    duration_sec = results["metadata"]["duration_seconds"]
                    total_energy = results["Overall Summary"]["Total Energy (kWh)"]
                    mean_power = results["Overall Summary"]["Mean Power (W)"]
                    energy_rate = results["Overall Summary"]["Energy Rate (kWh/hour)"]
                    duty_elek = results["Elektrisch"]["Duty Cycle (%)"]
                    duty_pneu = results["Pneumatisch"]["Duty Cycle (%)"]

                    filename = f"audit_{st.session_state.machine_name}_{uploaded_file.name.split('.')[0]}.json"
                    store.save_audit(results, filename)
                    st.session_state.last_audit_results = results
                    st.toast(f"Audit saved: {filename}")

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
                        st.plotly_chart(fig, width="stretch")

                    with st.expander("Show JSON result"):
                        st.json(results)

        except Exception as e:
            st.error(f"Error during processing: {e}")

    st.divider()
    st.subheader("Saved Audits (Working Store)")
    audits = store.list_audits()
    if audits:
        for audit in audits:
            with st.expander(audit):
                col_btn1, col_btn2 = st.columns([1, 1])
                if col_btn1.button("Load", key=f"load_{audit}"):
                    data = store.load_audit(audit)
                    st.json(data)
                if col_btn2.button("Delete", key=f"del_audit_{audit}"):
                    store.delete_audit(audit)
                    st.rerun()
    else:
        st.info("No audits in store yet.")
