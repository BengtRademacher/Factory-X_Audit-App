import json
from typing import Any, Dict, Mapping

from config.prompts import COMPARISON_PROMPT


def should_summarize(selected_audit_count: int, selected_benchmark_count: int) -> bool:
    return selected_audit_count * selected_benchmark_count > 4


def summarize_for_llm(data: Mapping[str, Any], is_benchmark: bool = False) -> Dict[str, Any]:
    summary = {
        "metadata": data.get("metadata", {}),
        "Overall Summary": data.get("Overall Summary", {}),
    }
    if is_benchmark:
        summary["energy_data"] = data.get("energy_data", {})
    else:
        summary["Electrical Total"] = data.get("Elektrisch", {}).get("Total Elektrisch", {})
        summary["Pneumatic Total"] = data.get("Pneumatisch", {}).get("Total Pneumatisch", {})
    return summary


def prepare_comparison_payloads(
    audits_data: Mapping[str, Mapping[str, Any]],
    benchmarks_data: Mapping[str, Mapping[str, Any]],
    use_summary: bool,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    if not use_summary:
        return dict(audits_data), dict(benchmarks_data)

    audits_to_send = {filename: summarize_for_llm(data) for filename, data in audits_data.items()}
    benchmarks_to_send = {
        title: summarize_for_llm(data, is_benchmark=True)
        for title, data in benchmarks_data.items()
    }
    return audits_to_send, benchmarks_to_send


def build_comparison_prompt(
    audits_payload: Mapping[str, Any],
    benchmarks_payload: Mapping[str, Any],
    analysis_context: str = "",
) -> str:
    prompt = COMPARISON_PROMPT.format(
        audit_json=json.dumps(audits_payload, indent=2),
        benchmark_json=json.dumps(benchmarks_payload, indent=2),
    )
    if analysis_context.strip():
        prompt += f"\n\nAdditional analysis focus:\n{analysis_context.strip()}"
    return prompt


def build_report_data(audits_data: Mapping[str, Mapping[str, Any]]) -> list[Dict[str, Any]]:
    report_data = []
    for filename, audit_data in audits_data.items():
        report_data.append({
            "filename": filename,
            "machine_name": audit_data.get("metadata", {}).get("machine_name", "N/A"),
            "machine_state": audit_data.get("metadata", {}).get("machine_state", "N/A"),
            "operating_state": audit_data.get("metadata", {}).get("operating_state"),
            "total_energy_combined": audit_data.get("Overall Summary", {}).get("Total Energy (kWh)", 0),
            "assessment": "See full report for matrix analysis."
        })
    return report_data
