import streamlit as st
import PyPDF2
import google.generativeai as genai
import json
from io import BytesIO

# Setup Gemini API
# It's recommended to use st.secrets for your API key in a deployed app
# genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
genai.configure(api_key="AIzaSyBnI8QXT7tDSO7Do0j0URBfEw9xP1gNTxQ") # Replace with your key

# Gemini model
model = genai.GenerativeModel("gemini-2.0-flash-001") # Updated to a newer recommended model

def extract_pdf_text(pdf_file):
    """Extracts text from an uploaded PDF file."""
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading PDF file: {e}")
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
        # Clean up the response from markdown code blocks if they exist
        clean_response = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_response)
    except Exception as e:
        st.error(f"Error analyzing with Gemini or parsing JSON: {e}")
        # Try to show the raw response for debugging if available
        raw_output = "No raw output captured."
        if 'response' in locals() and hasattr(response, 'text'):
            raw_output = response.text
        return {"error": "Failed to get a valid JSON response from the model.", "raw_output": raw_output}

# --- THIS IS THE MODIFIED FUNCTION ---
def download_json(data):
    """Converts a dictionary to a pretty-printed JSON file for download."""
    # Using indent=2 makes the JSON file human-readable
    json_string = json.dumps(data, indent=2)
    return BytesIO(json_string.encode("utf-8"))

# Streamlit App
st.set_page_config(layout="wide")
st.title("📄 Research Paper to JSON Extractor")
st.write("Upload a scientific paper in PDF format to extract key information into a structured JSON file.")

pdf_file = st.file_uploader("Upload a Research Paper (PDF)", type=["pdf"])

if pdf_file is not None:
    if st.button("Analyze Paper", type="primary"):
        # Display spinners while processing
        with st.spinner("Step 1/2: Extracting text from PDF..."):
            text = extract_pdf_text(pdf_file)
        
        if text:
            with st.spinner("Step 2/2: Analyzing with Gemini AI..."):
                result = analyze_paper_with_gemini(text)
            
            st.success("Analysis complete!")
            
            # Display results
            st.subheader("Extracted Data")
            st.json(result, expanded=True)

            if "error" not in result:
                # 👉 Let user type custom filename (default suggestion provided)
                default_filename = f"{pdf_file.name.replace('.pdf', '')}_data.json"
                custom_filename = st.text_input(
                    "Enter JSON filename", 
                    value=default_filename
                )

                # Download button with user-provided filename
                st.download_button(
                    label="⬇️ Download JSON",
                    data=download_json(result),
                    file_name=custom_filename if custom_filename.strip() else default_filename,
                    mime="application/json"
                )
