import re
import json
from typing import Dict, Any, Optional

def extract_json_from_response(response: str) -> Dict[str, Any]:
    """
    Robustly extract and parse JSON from an LLM response.
    Supports markdown code blocks and raw JSON strings.
    """
    clean_json = response.strip()
    
    # Try to find JSON in markdown blocks
    json_match = re.search(r"```json\s*([\s\S]*?)\s*```", clean_json)
    if json_match:
        clean_json = json_match.group(1)
    else:
        # Fallback: find any code block
        code_match = re.search(r"```\s*([\s\S]*?)\s*```", clean_json)
        if code_match:
            clean_json = code_match.group(1)
        else:
            # Last resort: find first { and last }
            struct_match = re.search(r"(\{[\s\S]*\})", clean_json)
            if struct_match:
                clean_json = struct_match.group(1)

    if not clean_json or clean_json.strip() == "":
        raise ValueError("AI returned no valid JSON data (empty response).")

    try:
        return json.loads(clean_json)
    except json.JSONDecodeError as je:
        raise ValueError(f"Invalid JSON format received from AI: {je}")
