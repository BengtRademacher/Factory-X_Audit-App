import streamlit as st
import PyPDF2
import google.generativeai as genai
import json
from io import BytesIO
import zipfile # Import necessary for zipping files

# Setup Gemini API
# It's recommended to use st.secrets for your API key in a deployed app
# genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
genai.configure(api_key="AIzaSyBnI8QXT7tDSO7Do0j0URBfEw9xP1gNTxQ") # Replace with your key

# Gemini model
model = genai.GenerativeModel("gemini-2.0-flash")

def extract_pdf_text(pdf_file):
    """Extracts text from an uploaded PDF file."""
    try:
        # pdf_file is now a file-like object from st.file_uploader, not a path
        pdf_file.seek(0) # Go to the start of the file
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

def analyze_paper_with_gemini(text):
    """Sends the extracted text to Gemini for analysis based on a structured prompt."""
    if not text:
        return {"error": "Input text is empty. Cannot analyze."}

    prompt = f"""
Your task is to act as a meticulous data extraction agent. Extract structured information from the following scientific paper.

**Instructions:**
1.  **Scan the entire document**, including all text, tables, and figure captions.
2.  **Populate the JSON schema below with precise, verbatim information**. Do not summarize or interpret the data.
3.  **For lists like `spindle_data` and `feeding_data`, meticulously parse the corresponding tables in the paper**. Each row in a data table should become a separate JSON object in the list.
4.  **If a specific piece of information is not found, use the string "not specified"**. For numerical lists that are empty, use an empty list `[]`.
5.  **Return ONLY the raw JSON object** and nothing else. Do not wrap it in markdown backticks or add any explanations.

**Schema to Populate:**
{{
  "paper_metadata": {{
    "title": "",
    "authors": [],
    "publication_date": "",
    "journal_or_conference": ""
  }},
  "machine_info": {{
    "machine_name": "",
    "machine_type": "",
    "axis": "",
    "control_unit": "",
    "material_processed": "",
    "process_parameters": {{
      "spindle_speed": "**The specific speed used in the experiment, not the machine's full range.**",
      "feed_rate": "**The specific feed rates used in the experiment, detailing different axes if possible.**",
      "cutting_depth": "",
      "spindle_data": [
        {{ "spindle_speed_rpm": 0, "measured_power_w": 0 }}
      ],
      "feeding_data": [
        {{ "feed_velocity_mm_min": 0, "x_axis_power_w": 0, "y_axis_power_w": 0, "z_axis_power_w_plus": 0, "z_axis_power_w_minus": 0 }}
      ]
    }}
  }},
  "energy_data": {{
    "energy_usage": "**Provide both estimated and measured values if available.**",
    "power_consumption": "**List the specific power values for each component: Standby, Spindle, and each Axis.**",
    "measurement_method": ""
  }},
  "kpi_metrics": {{
    "specific_energy_consumption": "",
    "CO2_emissions": "",
    "efficiency": "**Extract concrete error percentages or other efficiency metrics.**",
    "other_kpis": [
        "**List any other key numerical results, like time estimations or energy proportions.**"
    ]
  }},
  "additional_notes": "**Briefly summarize the main focus or unique contribution of the paper in one or two sentences.**"
}}

**Article text:**
{text}
"""

    try:
        response = model.generate_content(prompt)
        clean_response = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_response)
    except Exception as e:
        st.error(f"Error analyzing with Gemini or parsing JSON: {e}")
        raw_output = "No raw output captured."
        if 'response' in locals() and hasattr(response, 'text'):
            raw_output = response.text
        return {"error": "Failed to get a valid JSON response from the model.", "raw_output": raw_output}

def create_zip_of_json_files(results):
    """Creates a zip file in memory containing multiple JSON files."""
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        # The `results` is a list of tuples: (filename, json_data)
        for filename, data in results:
            json_string = json.dumps(data, indent=2)
            # Create a .json filename from the original PDF filename
            json_filename = filename.replace('.pdf', '_data.json')
            zip_file.writestr(json_filename, json_string.encode("utf-8"))
    
    zip_buffer.seek(0)
    return zip_buffer

# =================================================================
# Streamlit App - MODIFIED FOR BATCH PROCESSING
# =================================================================

st.set_page_config(layout="wide")
st.title("📄 Batch Research Paper to JSON Extractor")
st.write("Upload one or more scientific papers (PDF) to extract key information into structured JSON files.")

# Initialize session_state to hold a LIST of analysis results
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = []

# MODIFICATION 1: Accept multiple files
pdf_files = st.file_uploader(
    "Upload Research Papers (PDF)", 
    type=["pdf"],
    accept_multiple_files=True
)

if pdf_files:
    if st.button(f"Analyze {len(pdf_files)} Papers", type="primary"):
        st.session_state.analysis_results = [] # Clear previous results
        all_results = []
        
        # MODIFICATION 2: Loop through each file and show progress
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, pdf_file in enumerate(pdf_files):
            progress = (i + 1) / len(pdf_files)
            progress_bar.progress(progress)
            status_text.text(f"Processing file {i+1}/{len(pdf_files)}: {pdf_file.name}")

            text = extract_pdf_text(pdf_file)
            if text:
                result = analyze_paper_with_gemini(text)
                # Store a tuple of (original_filename, result_dict)
                all_results.append((pdf_file.name, result))
            else:
                # Handle extraction failure for one file
                all_results.append((pdf_file.name, {"error": f"Could not extract text from {pdf_file.name}."}))

        # Store all results in the session state at once
        st.session_state.analysis_results = all_results
        status_text.success(f"Analysis complete for all {len(pdf_files)} files!")
        progress_bar.empty()

# MODIFICATION 3: Display all results from the session state
if st.session_state.analysis_results:
    st.subheader("Extracted Data")

    # Display results for each file in an expander
    for filename, result in st.session_state.analysis_results:
        with st.expander(f"Results for: **{filename}**"):
            st.json(result, expanded=True)

    # MODIFICATION 4: Add a button to download all results as a single ZIP file
    st.download_button(
        label="⬇️ Download All as ZIP",
        data=create_zip_of_json_files(st.session_state.analysis_results),
        file_name="analysis_results.zip",
        mime="application/zip"
    )