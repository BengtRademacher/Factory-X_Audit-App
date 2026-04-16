import time
from io import BytesIO

import pandas as pd
import streamlit as st

from config.prompts import PAPER_EXTRACTION_PROMPT
from core.json_extractor import extract_json_from_response
from database.literature_db import LiteratureDB
from ui.common import handle_llm_error, render_tab_header


def render_paper_to_json():
    render_tab_header("description", "Document -> JSON Extractor", "Extraction of structured data from PDFs, CSV, Excel or JSON.")
    render_document_import_section()


def render_document_import_section():
    db = LiteratureDB()
    llm_service = st.session_state.llm_service
    provider_name = st.session_state.llm_provider
    provider = llm_service.get_provider(provider_name, model=st.session_state.llm_model) if provider_name else None

    st.subheader("Benchmark / Document Import")
    st.caption("Import papers, tables, JSON, CSV, or Excel files into the local benchmark database.")

    is_vision_model = False
    if st.session_state.llm_model:
        model_id = st.session_state.llm_model.lower()
        is_vision_model = any(kw in model_id for kw in ["vision", "gemini", "claude-3", "pixtral", "llava"])

    if provider:
        uploaded_files = st.file_uploader(
            "Upload Documents",
            type=["pdf", "csv", "xlsx", "json"],
            accept_multiple_files=True,
            key="paper_uploader",
        )

        if uploaded_files:
            has_pdf = any(f.name.lower().endswith(".pdf") for f in uploaded_files)
            if has_pdf and not is_vision_model:
                st.warning("Warning: the selected model might not support PDF or vision analysis.")

            if st.button(f"Analyze Documents ({len(uploaded_files)})", type="primary", width="stretch"):
                with st.status("Processing documents...", expanded=True) as status:
                    results_container = st.container()

                    for i, doc_file in enumerate(uploaded_files):
                        st.write(f"Processing **{doc_file.name}** ({i + 1}/{len(uploaded_files)})")

                        doc_bytes = doc_file.read()
                        start_time = time.time()
                        file_ext = doc_file.name.split(".")[-1].lower()

                        try:
                            if file_ext == "pdf":
                                response = provider.generate_from_file(
                                    prompt=PAPER_EXTRACTION_PROMPT,
                                    file_bytes=doc_bytes,
                                    mime_type="application/pdf",
                                )
                            else:
                                if file_ext in {"csv", "json"}:
                                    content = doc_bytes.decode("utf-8", errors="ignore")
                                elif file_ext == "xlsx":
                                    df_xlsx = pd.read_excel(BytesIO(doc_bytes))
                                    content = df_xlsx.to_csv(index=False)
                                else:
                                    content = ""

                                full_prompt = f"{PAPER_EXTRACTION_PROMPT}\n\n### FILE CONTENT ({file_ext.upper()}):\n{content}"
                                response = provider.generate(full_prompt)

                            thinking_time = time.time() - start_time
                            try:
                                data = extract_json_from_response(response)
                            except ValueError as e:
                                st.error(f"Could not parse JSON: {e}")
                                raise e

                            db.add_entry(data, pdf_file=doc_bytes, filename=doc_file.name.rsplit(".", 1)[0])

                            st.write(f"Success ({thinking_time:.1f}s)")
                            with results_container:
                                with st.expander(f"Details: {doc_file.name}"):
                                    st.json(data)

                        except Exception as e:
                            handle_llm_error(e)
                            with results_container:
                                with st.expander(f"Error Details: {doc_file.name}"):
                                    st.exception(e)

                    status.update(label="Processing complete", state="complete", expanded=False)
                st.toast("All documents processed.")
    else:
        st.error("Please configure an LLM provider in the sidebar to import benchmark documents.")

    st.divider()
    st.subheader("Literature Database")
    entries = db.get_all_entries()
    if entries:
        for entry in entries:
            authors = entry.get("authors") or []
            title = entry.get("title") or entry.get("id")
            with st.expander(f"{title} ({', '.join(authors[:2])}...)"):
                col_info, col_actions = st.columns([3, 1])
                with col_info:
                    st.write(f"**ID:** {entry['id']}")
                    st.write(f"**Date:** {entry.get('date')}")
                with col_actions:
                    if st.button("JSON", key=f"details_{entry['id']}"):
                        full_data = db.get_entry_by_id(entry["id"])
                        st.json(full_data)
                    if st.button("Delete", key=f"del_{entry['id']}"):
                        db.delete_entry(entry["id"])
                        st.rerun()
    else:
        st.info("No entries in database yet.")
