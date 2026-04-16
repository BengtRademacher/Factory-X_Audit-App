import streamlit as st

from ui.audit_assistant import render_audit_assistant
from ui.chat_tab import render_chat_assistant
from ui.common import inject_custom_styles, render_main_title
from ui.comparison_tab import render_comparison
from ui.import_tab import render_import_tab
from ui.sidebar import render_sidebar
from ui.state import init_session_state


def main():
    st.set_page_config(
        page_title="Factory-X Audit-App",
        layout="wide",
    )

    st.logo("assets/FX_logo_top_left.png")
    inject_custom_styles()

    init_session_state()
    render_sidebar()

    render_main_title()

    tab0, tab1, tab2, tab3 = st.tabs([
        "Audit Assistant",
        "Import",
        "Comparison",
        "Ask about data",
    ])

    with tab0:
        render_audit_assistant()
    with tab1:
        render_import_tab()
    with tab2:
        render_comparison()
    with tab3:
        render_chat_assistant()


if __name__ == "__main__":
    main()
