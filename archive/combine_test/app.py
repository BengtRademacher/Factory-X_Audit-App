# ================================================================
# PART 1️⃣ — 📄 Batch Research Paper to JSON Extractor (Dynamic Prompt)
# ================================================================
import streamlit as st
import PyPDF2
import google.generativeai as genai
import json
import re
from io import BytesIO
import zipfile
import os

# ================================================================
# ⚙️ Setup Gemini API
# ================================================================
api_key = st.secrets["gemmini"]["api_key"] if "gemmini" in st.secrets else st.secrets["gemini"]["api_key"]
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.5-flash")

# ================================================================
# Streamlit Page Config
# ================================================================
st.set_page_config(layout="wide")
st.title("📄 Research Paper → JSON Extractor (Batch Mode)")

# ================================================================
# 🧠 Editable Prompt Template in UI with Confirm Button
# ================================================================
DEFAULT_PROMPT = """
Your task is to act as a meticulous data extraction agent. Extract structured information from the following scientific paper.

**Instructions:**
1. **Scan the entire document**, including all text, tables, and figure captions.  
2. **Populate the JSON schema below with precise, verbatim information**. Do not summarize or interpret the data.  
3. **For lists like `spindle_data` and `feeding_data`, meticulously parse the corresponding tables in the paper**.  
4. **If a specific piece of information is not found, use the string "not specified"**.  
5. **Return ONLY the raw JSON object** and nothing else.

**Schema to Populate:**
{
  "paper_metadata": {
    "title": "",
    "authors": [],
    "publication_date": "",
    "journal_or_conference": ""
  },
  "machine_info": {
    "machine_name": "",
    "machine_type": "",
    "axis": "",
    "control_unit": "",
    "material_processed": "",
    "process_parameters": {
      "spindle_speed": "",
      "feed_rate": "",
      "cutting_depth": "",
      "spindle_data": [
        { "spindle_speed_rpm": 0, "measured_power_w": 0 }
      ],
      "feeding_data": [
        { "feed_velocity_mm_min": 0, "x_axis_power_w": 0, "y_axis_power_w": 0, "z_axis_power_w_plus": 0, "z_axis_power_w_minus": 0 }
      ]
    }
  },
  "energy_data": {
    "energy_usage": "",
    "power_consumption": "",
    "measurement_method": ""
  },
  "kpi_metrics": {
    "specific_energy_consumption": "",
    "CO2_emissions": "",
    "efficiency": "",
    "other_kpis": []
  },
  "additional_notes": ""
}
"""

# Initialize prompt states
if "prompt_template" not in st.session_state:
    st.session_state.prompt_template = DEFAULT_PROMPT.strip()
if "prompt_edit_temp" not in st.session_state:
    st.session_state.prompt_edit_temp = st.session_state.prompt_template

with st.expander("🧠 Edit or Replace Extraction Prompt (Live)"):
    st.markdown("Edit the prompt below. Click **Apply Prompt** to make the changes active for subsequent analyses.")

    # Temporary editable area
    st.session_state.prompt_edit_temp = st.text_area(
        "Draft Prompt (edits here do not take effect until applied):",
        value=st.session_state.prompt_edit_temp,
        height=360,
        key="editable_prompt_temp"
    )

    cols = st.columns([1, 1, 1])
    with cols[0]:
        if st.button("✅ Apply Prompt"):
            st.session_state.prompt_template = st.session_state.prompt_edit_temp
            st.success("✅ Prompt applied. New prompt will be used for the next analyses.")
    with cols[1]:
        if st.button("↩️ Reset to Active Prompt"):
            st.session_state.prompt_edit_temp = st.session_state.prompt_template
            st.info("ℹ️ Draft reset to the currently active prompt.")
    with cols[2]:
        if st.button("🧱 Restore Default Prompt"):
            st.session_state.prompt_edit_temp = DEFAULT_PROMPT.strip()
            st.info("ℹ️ Draft replaced with default prompt. Click 'Apply Prompt' to make it active.")

    st.markdown("---")
    st.markdown("**Currently active prompt (used for analysis):**")
    st.code(st.session_state.prompt_template, language="text")

# ================================================================
# 📖 Extract text from uploaded PDF
# ================================================================
def extract_pdf_text(pdf_file):
    """📄 Extract text content from an uploaded PDF file using PyPDF2."""
    try:
        pdf_file.seek(0)
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading PDF file '{pdf_file.name}': {e}")
        return None

# ================================================================
# 🤖 Analyze extracted text using Gemini
# ================================================================
def analyze_paper_with_gemini(text, prompt_template):
    """🤖 Send extracted PDF text to Gemini and return parsed JSON per schema."""
    if not text:
        return {"error": "Input text is empty. Cannot analyze."}

    prompt = f"{prompt_template}\n\n**Article text:**\n{text}"

    try:
        response = model.generate_content(prompt)
        raw_output = response.text.strip() if hasattr(response, "text") else ""

        if not raw_output:
            return {"error": "Model returned an empty response.", "raw_output": ""}

        cleaned = (
            raw_output.replace("```json", "")
            .replace("```", "")
            .replace("\r", "")
            .strip()
        )
        cleaned = re.sub(r"[\x00-\x1F]+", "", cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "error": "Gemini returned non-JSON text. Check 'raw_output' to debug.",
                "raw_output": cleaned[:1500],
            }

    except Exception as e:
        raw_output = response.text if "response" in locals() and hasattr(response, "text") else ""
        return {
            "error": f"Failed to get a valid JSON response. Details: {e}",
            "raw_output": raw_output[:1500],
        }

# ================================================================
# 🧩 Streamlit UI: PDF upload & processing
# ================================================================
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = []
if "rename_values" not in st.session_state:
    st.session_state.rename_values = {}

pdf_files = st.file_uploader(
    "📁 Upload one or more scientific papers (PDF):",
    type=["pdf"],
    accept_multiple_files=True,
)

if pdf_files:
    if st.button(f"🔍 Analyze {len(pdf_files)} Paper(s)", type="primary"):
        st.session_state.analysis_results = []
        st.session_state.rename_values = {}

        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, pdf_file in enumerate(pdf_files):
            progress_bar.progress((i + 1) / len(pdf_files))
            status_text.text(f"Processing file {i+1}/{len(pdf_files)}: {pdf_file.name}")

            text = extract_pdf_text(pdf_file)
            if text:
                result = analyze_paper_with_gemini(text, st.session_state.prompt_template)
            else:
                result = {"error": f"Could not extract text from {pdf_file.name}."}
            st.session_state.analysis_results.append((pdf_file.name, result))
            st.session_state.rename_values[str(i)] = pdf_file.name.replace(".pdf", "_data.json")

        progress_bar.empty()
        status_text.success(f"✅ Analysis complete for {len(pdf_files)} file(s)!")

# ================================================================
# 📊 Display Extracted JSON Results (checkbox selection)
# ================================================================
if st.session_state.analysis_results:
    st.subheader("📊 Extracted Data")

    # Render each result
    for i, (orig_filename, result) in enumerate(st.session_state.analysis_results):
        rename_key = f"rename_{i}"
        checkbox_key = f"select_{i}"

        # JSON preview inside expander
        with st.expander(f"📄 Results for: **{orig_filename}**", expanded=False):
            st.json(result, expanded=True)

        cols = st.columns([4, 1])
        with cols[0]:
            new_name = st.text_input(
                f"✏️ Rename file for '{orig_filename}'",
                value=st.session_state.rename_values.get(str(i), orig_filename.replace(".pdf", "_data.json")),
                key=rename_key,
            )
            if not new_name.endswith(".json"):
                new_name += ".json"
            st.session_state.rename_values[str(i)] = new_name
        with cols[1]:
            st.checkbox("✅ Select", key=checkbox_key)

        st.markdown("---")

    # Determine which files are selected
    selected_indices = [i for i in range(len(st.session_state.analysis_results)) if st.session_state.get(f"select_{i}", False)]
    selected_count = len(selected_indices)

    st.markdown(f"**📦 You selected {selected_count} file(s).**")

    if selected_count > 0:
        st.markdown("---")
        st.subheader("📥 Batch Actions for Selected Files")

        save_dir = st.text_input("📂 Enter folder path to save selected files:", "outputs")

        # --- Download Selected as ZIP ---
        if st.button("⬇️ Download Selected as ZIP"):
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for i in selected_indices:
                    filename = st.session_state.rename_values[str(i)]
                    data = st.session_state.analysis_results[i][1]
                    zip_file.writestr(filename, json.dumps(data, indent=2))
            zip_buffer.seek(0)

            st.download_button(
                label=f"📥 Download {selected_count} Selected JSON(s) as ZIP",
                data=zip_buffer.getvalue(),
                file_name="selected_results.zip",
                mime="application/zip",
                key="download_selected_zip"
            )

        # --- Save Selected to Folder ---
        if st.button("💾 Save Selected to Folder"):
            os.makedirs(save_dir, exist_ok=True)
            saved_files = []
            for i in selected_indices:
                filename = st.session_state.rename_values[str(i)]
                data = st.session_state.analysis_results[i][1]
                save_path = os.path.join(save_dir, filename)
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                saved_files.append(save_path)

            st.success(f"✅ Saved {len(saved_files)} file(s) to: {os.path.abspath(save_dir)}")
            for path in saved_files:
                st.write(f"- `{os.path.basename(path)}`")
    else:
        st.info("☑️ Select at least one file above to enable download or save options.")



# ================================================================
# PART 2️⃣ — XLSX/CSV → JSON Conversion (Multi-File Version with Editable JSON Name)
# ================================================================

import pandas as pd
import numpy as np
import streamlit as st
import json
import plotly.graph_objects as go

st.title("2️⃣📘 XLSX/CSV → JSON Conversion")

# --- Metadata Inputs ---
maschine_name = st.text_input("Maschine Name")
operator_name = st.text_input("Operator Name")
maschine_state = st.text_input("Maschine State (e.g. Idle, Cutting, Cooling)")
material = st.text_input("Material Used (e.g. Aluminum, Steel, Plastic)")
json_title = st.text_input("Default JSON File Title", value="energy_summary")

# --- File Uploader (multi-file) ---
uploaded_files = st.file_uploader(
    "Upload one or more .xlsx or .csv files",
    type=["xlsx", "csv"],
    accept_multiple_files=True,
    key="datafiles"
)

# --- Initialize Session States ---
if "generated_jsons" not in st.session_state:
    st.session_state["generated_jsons"] = {}
if "selected_ranges" not in st.session_state:
    st.session_state["selected_ranges"] = {}
if "temp_ranges" not in st.session_state:
    st.session_state["temp_ranges"] = {}
if "confirmed" not in st.session_state:
    st.session_state["confirmed"] = {}
if "time_limits" not in st.session_state:
    st.session_state["time_limits"] = {}
if "json_names" not in st.session_state:
    st.session_state["json_names"] = {}

# --- Process Each Uploaded File ---
if uploaded_files:
    for uploaded_file in uploaded_files:
        file_name = uploaded_file.name
        st.header(f"📂 File: {file_name}")

        # --- Load data ---
        try:
            if file_name.lower().endswith(".xlsx"):
                df = pd.read_excel(uploaded_file)
            elif file_name.lower().endswith(".csv"):
                df = pd.read_csv(uploaded_file, sep=None, engine="python")
            else:
                st.error("Unsupported file type. Please upload .xlsx or .csv")
                continue
        except Exception as e:
            st.error(f"❌ Failed to read {file_name}: {e}")
            continue

        # --- Check required column ---
        if "elapsedTime" not in df.columns:
            st.error(f"⚠️ File '{file_name}' must contain a column named 'elapsedTime'.")
            continue

        # --- Determine time range ---
        time_arr = df["elapsedTime"].to_numpy(dtype=float)
        t_min, t_max = float(time_arr.min()), float(time_arr.max())
        st.session_state["time_limits"][file_name] = (t_min, t_max)
        st.info(f"📆 Available time range: {round(t_min,2)} s → {round(t_max,2)} s")

        # --- Slider Setup ---
        st.write("🕒 Adjust time range (won’t update until confirmed):")

        if file_name not in st.session_state["temp_ranges"]:
            st.session_state["temp_ranges"][file_name] = (t_min, t_max)

        slider_key = f"temp_slider_{file_name}"

        temp_range = st.slider(
            f"Select time range for {file_name}:",
            min_value=float(t_min),
            max_value=float(t_max),
            value=st.session_state["temp_ranges"][file_name],
            step=0.1,
            key=slider_key
        )
        st.session_state["temp_ranges"][file_name] = temp_range

        # --- Buttons ---
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button(f"✅ Confirm Selection for {file_name}"):
                st.session_state["selected_ranges"][file_name] = temp_range
                st.session_state["confirmed"][file_name] = True
                st.success(f"{file_name}: confirmed range {temp_range[0]:.2f}s → {temp_range[1]:.2f}s")

        with col2:
            if st.button(f"🔄 Reset Timestamp for {file_name}"):
                st.session_state["selected_ranges"][file_name] = (t_min, t_max)
                st.session_state["temp_ranges"][file_name] = (t_min, t_max)
                st.session_state["confirmed"][file_name] = True
                st.success(f"{file_name}: reset to full range.")
                st.rerun()

        # --- Plot Hauptversorgung ---
        if "Hauptversorgung" in df.columns:
            st.subheader(f"📈 Hauptversorgung Power vs Time — {file_name}")

            temp_start, temp_end = st.session_state["temp_ranges"][file_name]
            full_df = df.copy()
            selected_df = df[(df["elapsedTime"] >= temp_start) & (df["elapsedTime"] <= temp_end)]

            # Full range plot
            fig_full = go.Figure()
            fig_full.add_trace(go.Scatter(
                x=full_df["elapsedTime"], y=full_df["Hauptversorgung"],
                mode="lines", name="Full Range",
                line=dict(width=1.2, color="royalblue")
            ))
            fig_full.add_vrect(
                x0=temp_start, x1=temp_end,
                fillcolor="lightgreen", opacity=0.3,
                layer="below", line_width=0,
                annotation_text="Selected range",
                annotation_position="top left"
            )
            fig_full.update_layout(
                title="Full Range: Hauptversorgung vs Elapsed Time",
                xaxis_title="Elapsed Time (s)",
                yaxis_title="Power (W)",
                height=300,
                template="plotly_white",
                hovermode="x unified"
            )

            # Zoomed plot
            fig_zoom = go.Figure()
            fig_zoom.add_trace(go.Scatter(
                x=full_df["elapsedTime"],
                y=[None] * len(full_df),
                mode="lines", showlegend=False
            ))
            fig_zoom.add_trace(go.Scatter(
                x=selected_df["elapsedTime"],
                y=selected_df["Hauptversorgung"],
                mode="lines", line=dict(width=2.2, color="firebrick"),
                showlegend=False
            ))
            fig_zoom.update_layout(
                title=f"Selected Range Overlay ({temp_start:.2f}s → {temp_end:.2f}s)",
                xaxis_title="Elapsed Time (s)",
                yaxis_title="Power (W)",
                height=300,
                template="plotly_white",
                hovermode="x unified",
                showlegend=False,
                xaxis=dict(range=[full_df["elapsedTime"].min(), full_df["elapsedTime"].max()])
            )
            st.plotly_chart(fig_full, use_container_width=True)
            st.plotly_chart(fig_zoom, use_container_width=True)
        else:
            st.warning(f"⚠️ File '{file_name}' has no 'Hauptversorgung' column.")

        # --- Main Processing ---
        if st.session_state["confirmed"].get(file_name) and st.session_state["selected_ranges"].get(file_name):
            start_time, end_time = st.session_state["selected_ranges"][file_name]
            df = df[(df["elapsedTime"] >= start_time) & (df["elapsedTime"] <= end_time)]
            time_arr = df["elapsedTime"].to_numpy(dtype=float)
            duration_sec = time_arr[-1] - time_arr[0]
            duration_hr = duration_sec / 3600.0
            sampling_rate = 1 / np.mean(np.diff(time_arr)) if len(time_arr) > 1 else None

            # --- Variable groups ---
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
            def r(v): return round(float(v), 2)

            # --- Compute metrics ---
            def compute_metrics(vars_group):
                details = {}
                valid_vars = [v for v in vars_group if v in df.columns]
                if not valid_vars:
                    return {}, {}
                for var in valid_vars:
                    values = df[var].to_numpy(dtype=float)
                    mean_val = np.mean(values)
                    median_val = np.median(values)
                    max_val = np.max(values)
                    min_val = np.min(values)
                    std_val = np.std(values)
                    range_val = max_val - min_val
                    total_energy_kWh = np.trapz(values, time_arr) / 3_600_000.0
                    time_of_peak = float(time_arr[np.argmax(values)]) if len(values) > 0 else None
                    details[var] = {
                        "mean": r(mean_val),
                        "median": r(median_val),
                        "max": r(max_val),
                        "min": r(min_val),
                        "std_dev": r(std_val),
                        "range": r(range_val),
                        "total_energy_kWh": r(total_energy_kWh),
                        "time_of_peak": r(time_of_peak) if time_of_peak is not None else None
                    }
                group_mean = np.mean(df[valid_vars].mean(axis=1))
                group_total_energy = np.trapz(df[valid_vars].sum(axis=1), time_arr) / 3_600_000.0
                group_max = df[valid_vars].sum(axis=1).max()
                group_min = df[valid_vars].sum(axis=1).min()
                group_std = df[valid_vars].sum(axis=1).std()
                group_range = group_max - group_min
                group_summary = {
                    "mean": r(group_mean),
                    "max": r(group_max),
                    "min": r(group_min),
                    "std_dev": r(group_std),
                    "range": r(group_range),
                    "total_energy_kWh": r(group_total_energy)
                }
                return details, group_summary

            elektrisch_details, elektrisch_total = compute_metrics(vars_elektrisch)
            pneumatisch_details, pneumatisch_total = compute_metrics(vars_pneumatisch)

            all_vars_combined = []
            for var_name, metrics in elektrisch_details.items():
                all_vars_combined.append({"name": var_name, "group": "Elektrisch", **metrics})
            for var_name, metrics in pneumatisch_details.items():
                all_vars_combined.append({"name": var_name, "group": "Pneumatisch", **metrics})

            def find_top_variable(key):
                if not all_vars_combined:
                    return None
                top_var = max(all_vars_combined, key=lambda x: x.get(key, 0))
                return {"name": top_var["name"], "group": top_var["group"], key: r(top_var[key])}

            top_mean = find_top_variable("mean")
            top_energy = find_top_variable("total_energy_kWh")
            top_peak = find_top_variable("max")

            def duty_cycle(vars_group, mean_value):
                if mean_value == 0 or not vars_group:
                    return 0
                group_mean = df[vars_group].mean(axis=1)
                active = np.sum(group_mean > 0.1 * mean_value)
                return r(active / len(df) * 100)

            duty_elektrisch = duty_cycle(vars_elektrisch, elektrisch_total.get("mean", 0))
            duty_pneumatisch = duty_cycle(vars_pneumatisch, pneumatisch_total.get("mean", 0))

            # --- Combine results ---
            results = {
                "metadata": {
                    "machine_name": maschine_name or "Unknown",
                    "operator": operator_name or "Unknown",
                    "machine_state": maschine_state or "Not specified",
                    "material": material or "Not specified",
                    "recording_start": r(time_arr[0]),
                    "recording_end": r(time_arr[-1]),
                    "selected_range_start": r(start_time),
                    "selected_range_end": r(end_time),
                    "duration_seconds": r(duration_sec),
                    "duration_hours": r(duration_hr),
                    "sampling_rate_Hz": r(sampling_rate) if sampling_rate else None,
                    "unit_power": "W",
                    "unit_energy": "kWh"
                },
                "Elektrisch": {
                    "Variables": elektrisch_details,
                    "Total Elektrisch": elektrisch_total,
                    "Duty Cycle (%)": duty_elektrisch
                },
                "Pneumatisch": {
                    "Variables": pneumatisch_details,
                    "Total Pneumatisch": pneumatisch_total,
                    "Duty Cycle (%)": duty_pneumatisch
                },
                "Overall Summary": {
                    "Total Energy (kWh)": r(elektrisch_total.get("total_energy_kWh", 0)
                                           + pneumatisch_total.get("total_energy_kWh", 0)),
                    "Mean Power (W)": r((elektrisch_total.get("mean", 0)
                                        + pneumatisch_total.get("mean", 0)) / 2),
                    "Energy Rate (kWh/hour)": r(
                        (elektrisch_total.get("total_energy_kWh", 0)
                         + pneumatisch_total.get("total_energy_kWh", 0)) / duration_hr
                        if duration_hr > 0 else 0
                    ),
                    "Top Variables": {
                        "Highest Average Power": top_mean,
                        "Highest Total Energy": top_energy,
                        "Highest Peak Power": top_peak
                    }
                }
            }

            # --- Store JSON ---
            st.session_state["generated_jsons"][file_name] = results

            # --- Display JSON ---
            st.subheader(f"Generated JSON Summary — {file_name}")
            with st.expander(f"📦 Show Generated JSON for {file_name}"):
                st.json(results)

            # --- Editable JSON File Name ---
            default_name = st.session_state["json_names"].get(file_name, f"{json_title}_{file_name}")
            new_name = st.text_input(f"✏️ JSON file name for {file_name} (without .json):", value=default_name, key=f"json_name_{file_name}")
            st.session_state["json_names"][file_name] = new_name

            # --- Download ---
            json_str = json.dumps(results, indent=4)
            st.download_button(
                label=f"💾 Download JSON ({file_name})",
                data=json_str,
                file_name=f"{new_name}.json",
                mime="application/json"
            )

# --- JSON Selection for Part 3 ---
if st.session_state["generated_jsons"]:
    st.divider()
    st.subheader("📁 Select JSONs for Part 3")
    available_jsons = list(st.session_state["generated_jsons"].keys())
    selected = st.multiselect("Select JSONs to pass to Part 3:", available_jsons)
    if selected:
        st.session_state["selected_jsons"] = selected
        st.success(f"✅ Selected for Part 3: {', '.join(selected)}")



# ================================================================
# Part 3️⃣ — JSON Analysis + AI Report (Separate PDF per file)
# ================================================================
import streamlit as st
import json
import time
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import google.generativeai as genai

# --- Title ---
st.header("3️⃣🤖 JSON Analysis and AI Efficiency Report")

# --- API Key Configuration ---
api_key = st.secrets["gemmini"]["api_key"] if "gemmini" in st.secrets else st.secrets["gemini"]["api_key"]
genai.configure(api_key=api_key)
MODEL_NAME = "gemini-2.5-flash"

# --- Optional Local LLM (Ollama) ---
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

backend = st.radio("Select AI Backend:", ["Gemini (online)", "Local LLM (Ollama)"])
if backend == "Local LLM (Ollama)" and not OLLAMA_AVAILABLE:
    st.warning("⚠️ Ollama not installed. Install it from https://ollama.ai to use local models.")
    st.stop()

# --- Load Benchmarks ---
@st.cache_resource
def load_benchmarks():
    import os, json, numpy as np, faiss
    from sentence_transformers import SentenceTransformer

    benchmarks, names = [], []
    folder = "benchmark"
    if not os.path.exists(folder):
        st.warning(f"⚠️ Benchmark folder not found: {os.path.abspath(folder)}")
        return [], [], None, None

    for filename in sorted(os.listdir(folder)):
        if filename.lower().endswith(".json") and filename.startswith("Milling"):
            try:
                with open(os.path.join(folder, filename), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    benchmarks.append(json.dumps(data))
                    names.append(filename)
            except Exception as e:
                st.error(f"Failed to read {filename}: {e}")

    if not benchmarks:
        st.warning(f"⚠️ No benchmark JSONs found in '{folder}/'.")
        return [], [], None, None

    model = SentenceTransformer("all-MiniLM-L6-v2")
    emb = model.encode(benchmarks)
    index = faiss.IndexFlatL2(emb.shape[1])
    index.add(emb)
    return benchmarks, names, model, index

benchmarks, benchmark_names, embed_model, index = load_benchmarks()

# --- Show Benchmarks ---
if benchmark_names:
    with st.expander("📂 Show Loaded Benchmarks"):
        for i, name in enumerate(benchmark_names):
            with st.expander(f"🔸 {i+1}. {name}"):
                try:
                    st.json(json.loads(benchmarks[i]))
                except Exception:
                    st.write("(Could not display JSON content)")
else:
    st.warning("⚠️ No benchmark files found. Place files like Milling1_benchmark.json etc. in 'benchmark/' folder.")

# --- Input Selection ---
use_generated_checkbox = st.checkbox("Use JSONs generated from Section 2️⃣")

uploaded_files_json = None
if use_generated_checkbox and st.session_state.get("generated_jsons"):
    selected_jsons = st.session_state.get("selected_jsons", list(st.session_state["generated_jsons"].keys()))
    if selected_jsons:
        uploaded_files_json = [(name, st.session_state["generated_jsons"][name]) for name in selected_jsons]
        st.info(f"Using {len(selected_jsons)} JSON(s) generated in Section 2.")
    else:
        st.warning("No JSON selected in Section 2. Please select one first.")
else:
    uploaded_files = st.file_uploader("Upload one or more JSON files", type="json", accept_multiple_files=True)
    if uploaded_files:
        uploaded_files_json = uploaded_files

# --- Process Each File ---
if uploaded_files_json:
    for item in uploaded_files_json:
        # Load file data
        if isinstance(item, tuple):
            file_name, data = item
        else:
            file_name = item.name
            try:
                data = json.load(item)
            except Exception as e:
                st.error(f"❌ Failed to read {file_name}: {e}")
                continue

        st.divider()
        st.subheader(f"📄 File: {file_name}")

        metadata = data.get("metadata", {})
        elektrisch = data.get("Elektrisch", {})
        pneumatisch = data.get("Pneumatisch", {})
        summary = data.get("Overall Summary", {})

        machine_name = metadata.get("machine_name", "Unknown")
        machine_state = metadata.get("machine_state", "Unknown")
        material_used = metadata.get("material", "Unknown")

        st.write(f"**Machine Name:** {machine_name}")
        st.write(f"**State:** {machine_state}")
        st.write(f"**Material:** {material_used}")

        # --- Metrics Extraction ---
        avg_elektrisch_dict = {k: v.get("mean", 0) for k, v in elektrisch.get("Variables", {}).items()}
        avg_pneumatisch_dict = {k: v.get("mean", 0) for k, v in pneumatisch.get("Variables", {}).items()}
        energy_elektrisch_dict = {k: v.get("total_energy_kWh", 0) for k, v in elektrisch.get("Variables", {}).items()}
        energy_pneumatisch_dict = {k: v.get("total_energy_kWh", 0) for k, v in pneumatisch.get("Variables", {}).items()}

        total_energy_elektrisch = sum(energy_elektrisch_dict.values())
        total_energy_pneumatisch = sum(energy_pneumatisch_dict.values())
        total_energy_combined = total_energy_elektrisch + total_energy_pneumatisch

        avg_elektrisch = elektrisch.get("Total Elektrisch", {}).get("mean", 0) / 1000
        avg_pneumatisch = pneumatisch.get("Total Pneumatisch", {}).get("mean", 0) / 1000

        # --- Expanders for details ---
        with st.expander("⚡ Electrical Components Details"):
            st.json(elektrisch)
        with st.expander("💨 Pneumatic Components Details"):
            st.json(pneumatisch)

        st.info(f"🔋 Combined Energy Consumption: **{total_energy_combined:.3f} kWh**")

        # --- AI Analysis ---
        st.info(f"Analyzing {file_name} with {backend}...")
        prompt = f"""
        You are an expert in machine energy efficiency.

        Machine name: {machine_name}
        Machine state: {machine_state}
        Material used: {material_used}

        --- Summary ---
        Average Electrical Power: {avg_elektrisch:.2f} kW
        Average Pneumatic Power: {avg_pneumatisch:.2f} kW
        Total Electrical Energy: {total_energy_elektrisch:.3f} kWh
        Total Pneumatic Energy: {total_energy_pneumatisch:.3f} kWh
        Combined Energy: {total_energy_combined:.3f} kWh
        """

        try:
            start = time.time()
            if backend == "Gemini (online)":
                model = genai.GenerativeModel(MODEL_NAME)
                response = model.generate_content(prompt)
                assessment = response.text
            else:
                response = ollama.chat(model="mistral", messages=[
                    {"role": "system", "content": "You are an expert in machine energy efficiency."},
                    {"role": "user", "content": prompt}
                ])
                assessment = response["message"]["content"]
            duration = time.time() - start

            with st.expander("🧠 Show AI Analysis"):
                st.write(assessment)
            st.success(f"🕒 Thinking time: {duration:.2f}s")

        except Exception as e:
            st.error(f"AI request failed: {e}")
            assessment = f"Error generating AI analysis: {e}"

        # --- Checkbox for Export ---
        export_check = st.checkbox(f"📥 Export {file_name} as PDF")

        if export_check:
            pdf_name = st.text_input(f"Enter PDF name for {file_name} (without .pdf):", file_name.replace(".json", ""), key=f"pdfname_{file_name}")

            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
            styles = getSampleStyleSheet()
            story = [
                Paragraph("<b>Machine Efficiency Analysis Report</b>", styles["Title"]),
                Spacer(1, 12),
                Paragraph(f"<b>File:</b> {file_name}", styles["Heading2"]),
                Paragraph(f"Machine Name: {machine_name}", styles["Normal"]),
                Paragraph(f"Machine State: {machine_state}", styles["Normal"]),
                Paragraph(f"Material Used: {material_used}", styles["Normal"]),
                Paragraph(f"Average Electrical Power: {avg_elektrisch:.2f} kW", styles["Normal"]),
                Paragraph(f"Average Pneumatic Power: {avg_pneumatisch:.2f} kW", styles["Normal"]),
                Paragraph(f"Total Electrical Energy: {total_energy_elektrisch:.3f} kWh", styles["Normal"]),
                Paragraph(f"Total Pneumatic Energy: {total_energy_pneumatisch:.3f} kWh", styles["Normal"]),
                Paragraph(f"Combined Energy: {total_energy_combined:.3f} kWh", styles["Normal"]),
                Spacer(1, 8),
                Paragraph("<b>AI Analysis:</b>", styles["Heading3"]),
                Paragraph(assessment.replace("\n", "<br/>"), styles["Normal"]),
                Spacer(1, 12)
            ]
            doc.build(story)
            buffer.seek(0)
            st.download_button(
                label=f"📤 Download {pdf_name}.pdf",
                data=buffer.getvalue(),
                file_name=f"{pdf_name}.pdf",
                mime="application/pdf",
                key=f"download_{file_name}"
            )


# END OF APP
