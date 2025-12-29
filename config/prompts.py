# --- LLM Prompts ---

PAPER_EXTRACTION_PROMPT = """
Your task is to act as a meticulous data extraction agent. Extract structured information from the provided scientific paper (PDF).

**Instructions:**
1. **Scan the entire document**, including all text, tables, and figure captions.
2. **Populate the JSON schema below with precise, verbatim information**. Do not summarize or interpret the data.
3. **For lists like `spindle_data` and `feeding_data`, meticulously parse the corresponding tables in the paper**. Each row in a data table should become a separate JSON object in the list.
4. **If a specific piece of information is not found, use the string "not specified"**. For numerical lists that are empty, use an empty list `[]`.
5. **Return ONLY the raw JSON object** and nothing else. Do not wrap it in markdown backticks or add any explanations.
"""

COMPARISON_PROMPT = """
You are an expert in machine energy efficiency.

--- Audit Data ---
{audit_json}

--- Literature Benchmark ---
{benchmark_json}

Task:
1. Evaluate the overall energy efficiency of the audit machine based on the benchmark.
2. Identify significant differences in power consumption and KPIs.
3. Suggest specific energy optimization strategies for the audit machine.
4. Provide a structured summary.
"""

