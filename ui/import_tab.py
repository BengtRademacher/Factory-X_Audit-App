import streamlit as st

from ui.common import render_tab_header
from ui.data_tab import render_measurement_audit_json_section
from ui.document_tab import render_document_import_section


def render_import_tab():
    render_tab_header("input", "Import", "Bring benchmark documents and measurement JSONs into the local workspace.")

    render_document_import_section()
    st.divider()
    render_measurement_audit_json_section()
