import json
from typing import Any, Dict, Iterable, Mapping, Optional

from core.json_extractor import extract_json_from_response


def build_audit_draft(
    audit_results: Mapping[str, Any],
    evidence_cards: Iterable[Mapping[str, Any]],
    manual_notes: str = "",
    provider: Optional[Any] = None,
) -> Dict[str, Any]:
    summary = audit_results.get("Overall Summary", {})
    evidence_cards = list(evidence_cards)
    data_quality = _grade_data_quality(audit_results)
    energy_level = _grade_energy_level(summary.get("Energy Rate (kWh/hour)", 0))
    benchmark_fit = _grade_benchmark_fit(evidence_cards)
    top_variables = summary.get("Top Variables", {})

    measures = _build_measures(audit_results, top_variables, data_quality, benchmark_fit)
    measures = _enhance_recommendations_with_ai(provider, audit_results, evidence_cards, measures)

    return {
        "title": "Machine Energy Audit",
        "executive_summary": _executive_summary(audit_results, data_quality, energy_level, benchmark_fit),
        "traffic_lights": {
            "Data Quality": data_quality,
            "Energy Level": energy_level,
            "Benchmark Fit": benchmark_fit,
        },
        "key_metrics": {
            "Total Energy (kWh)": summary.get("Total Energy (kWh)", 0),
            "Mean Power (W)": summary.get("Mean Power (W)", 0),
            "Energy Rate (kWh/hour)": summary.get("Energy Rate (kWh/hour)", 0),
            "Duration (s)": audit_results.get("metadata", {}).get("duration_seconds", 0),
        },
        "top_consumers": top_variables,
        "evidence_cards": evidence_cards,
        "recommended_measures": measures,
        "manual_notes": manual_notes,
        "data_basis": _data_basis(audit_results),
        "balance_summary": audit_results.get("balance", {}),
        "component_analysis": audit_results.get("component_analysis", {}),
    }


def _grade_data_quality(audit_results: Mapping[str, Any]) -> str:
    mapping = audit_results.get("mapping", {})
    channels = mapping.get("channels", [])
    if not channels:
        return "Red"
    avg_confidence = sum(float(ch.get("confidence", 0)) for ch in channels) / len(channels)
    if avg_confidence >= 0.75 and mapping.get("time_column"):
        return "Green"
    if avg_confidence >= 0.5:
        return "Yellow"
    return "Red"


def _grade_energy_level(energy_rate: Any) -> str:
    try:
        value = float(energy_rate)
    except (TypeError, ValueError):
        return "Yellow"
    if value <= 5:
        return "Green"
    if value <= 15:
        return "Yellow"
    return "Red"


def _grade_benchmark_fit(evidence_cards: Iterable[Mapping[str, Any]]) -> str:
    cards = list(evidence_cards)
    if len(cards) >= 5:
        return "Green"
    if cards:
        return "Yellow"
    return "Red"


def _build_measures(
    audit_results: Mapping[str, Any],
    top_variables: Mapping[str, Any],
    data_quality: str,
    benchmark_fit: str,
) -> list[Dict[str, str]]:
    measures = []
    component_analysis = audit_results.get("component_analysis", {})
    coverage = component_analysis.get("coverage_vs_main_supply_pct", {})
    for name in list(top_variables.keys())[:3]:
        measures.append({
            "category": "Betriebspotenzial",
            "priority": "High",
            "area": name,
            "measure": f"Review operating strategy and idle behavior for {name}.",
            "expected_effect": "Reduced runtime, idle demand, or leakage-related baseload.",
            "rationale": "This consumer is among the largest measured energy contributors.",
            "confidence": "Medium",
        })
    if any(value is not None and value < 80 for value in coverage.values()):
        measures.append({
            "category": "Retrofit-Potenzial",
            "priority": "Medium",
            "area": "Sub-metering coverage",
            "measure": "Add or recalibrate sub-metering for consumers not explained by measured components.",
            "expected_effect": "Improves allocation accuracy and exposes hidden consumers.",
            "rationale": "Measured sub-components explain only part of at least one main supply.",
            "confidence": "Medium",
        })
    if data_quality != "Green":
        measures.append({
            "category": "Betriebspotenzial",
            "priority": "High",
            "area": "Data quality",
            "measure": "Validate channel mapping, units, and sampling rate before final decisions.",
            "expected_effect": "Improves reliability of all quantified savings decisions.",
            "rationale": "Audit confidence depends on confirmed measurement semantics.",
            "confidence": "High",
        })
    if benchmark_fit != "Green":
        measures.append({
            "category": "Retrofit-Potenzial",
            "priority": "Medium",
            "area": "Benchmarking",
            "measure": "Add more process-specific literature evidence for the audited machine class.",
            "expected_effect": "Improves prioritization of retrofit cases and payback assumptions.",
            "rationale": "Current local evidence is limited for this audit context.",
            "confidence": "Medium",
        })
    if not any(measure["category"] == "Retrofit-Potenzial" for measure in measures):
        measures.append({
            "category": "Retrofit-Potenzial",
            "priority": "Medium",
            "area": "Auxiliary systems",
            "measure": "Assess demand-oriented drives, valves, and pump controls for the largest auxiliary consumers.",
            "expected_effect": "Potential reduction of baseload and standby losses.",
            "rationale": "Auxiliary consumers are common retrofit levers in machine-tool energy audits.",
            "confidence": "Medium",
        })
    return measures


def _enhance_recommendations_with_ai(
    provider: Optional[Any],
    audit_results: Mapping[str, Any],
    evidence_cards: list[Mapping[str, Any]],
    fallback_measures: list[Dict[str, str]],
) -> list[Dict[str, str]]:
    if provider is None:
        return fallback_measures
    prompt = f"""
You are refining energy-saving recommendations for a concrete machine-tool audit.

Return ONLY JSON with this shape:
{{
  "recommended_measures": [
    {{
      "category": "Retrofit-Potenzial|Betriebspotenzial",
      "priority": "High|Medium|Low",
      "area": "component or process area",
      "measure": "specific recommendation",
      "expected_effect": "qualitative or calculated indication",
      "rationale": "why this applies to this machine",
      "confidence": "High|Medium|Low"
    }}
  ]
}}

Rules:
- Keep recommendations specific to the measured machine and its top consumers.
- Include both Retrofit-Potenzial and Betriebspotenzial.
- Do not invent quantified savings percentages unless they are directly supported.
- Preserve the fallback recommendations when they are already useful.

Audit summary:
{json.dumps(_compact_audit_context(audit_results), indent=2, ensure_ascii=False)}

Evidence cards:
{json.dumps(evidence_cards[:8], indent=2, ensure_ascii=False)}

Fallback recommendations:
{json.dumps(fallback_measures, indent=2, ensure_ascii=False)}
""".strip()
    try:
        parsed = extract_json_from_response(provider.generate(prompt))
    except ValueError:
        return fallback_measures
    measures = parsed.get("recommended_measures")
    if not isinstance(measures, list):
        return fallback_measures
    normalized = [_normalize_measure(measure) for measure in measures if isinstance(measure, Mapping)]
    categories = {measure.get("category") for measure in normalized}
    if {"Retrofit-Potenzial", "Betriebspotenzial"}.issubset(categories):
        return normalized
    return fallback_measures


def _normalize_measure(measure: Mapping[str, Any]) -> Dict[str, str]:
    category = measure.get("category") if measure.get("category") in {"Retrofit-Potenzial", "Betriebspotenzial"} else "Betriebspotenzial"
    priority = measure.get("priority") if measure.get("priority") in {"High", "Medium", "Low"} else "Medium"
    confidence = measure.get("confidence") if measure.get("confidence") in {"High", "Medium", "Low"} else "Medium"
    return {
        "category": category,
        "priority": priority,
        "area": str(measure.get("area", "")),
        "measure": str(measure.get("measure", "")),
        "expected_effect": str(measure.get("expected_effect", "")),
        "rationale": str(measure.get("rationale", "")),
        "confidence": confidence,
    }


def _compact_audit_context(audit_results: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "metadata": audit_results.get("metadata", {}),
        "balance": audit_results.get("balance", {}),
        "component_analysis": audit_results.get("component_analysis", {}),
        "overall_summary": audit_results.get("Overall Summary", {}),
        "electric_total": audit_results.get("Elektrisch", {}).get("Total Elektrisch", {}),
        "pneumatic_total": audit_results.get("Pneumatisch", {}).get("Total Pneumatisch", {}),
    }


def _data_basis(audit_results: Mapping[str, Any]) -> Dict[str, Any]:
    mapping = audit_results.get("mapping", {})
    metadata = audit_results.get("metadata", {})
    channels = mapping.get("channels", [])
    confidences = [float(channel.get("confidence", 0) or 0) for channel in channels]
    selected = metadata.get("selected_component_columns") or mapping.get("component_selection", {}).get("selected_component_columns", [])
    excluded = metadata.get("excluded_numeric_columns") or mapping.get("component_selection", {}).get("excluded_numeric_columns", [])
    return {
        "time_column": mapping.get("time_column"),
        "sampling_rate_hz": mapping.get("sampling_rate_hz"),
        "channel_count": len(channels),
        "selected_energy_components": len(selected),
        "excluded_numeric_columns": ", ".join(excluded) if excluded else "none",
        "selection_note": "Excluded numeric columns were not mapped, calculated, charted, or included in the energy balance.",
        "average_mapping_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0,
        "mapping_notes": audit_results.get("metadata", {}).get("mapping_notes", ""),
    }


def _executive_summary(
    audit_results: Mapping[str, Any],
    data_quality: str,
    energy_level: str,
    benchmark_fit: str,
) -> str:
    metadata = audit_results.get("metadata", {})
    summary = audit_results.get("Overall Summary", {})
    return (
        f"Audit for {metadata.get('machine_name', 'the machine')} over "
        f"{metadata.get('duration_seconds', 0)} seconds. Total measured energy is "
        f"{summary.get('Total Energy (kWh)', 0)} kWh with an energy rate of "
        f"{summary.get('Energy Rate (kWh/hour)', 0)} kWh/hour. "
        f"Traffic lights: data quality {data_quality}, energy level {energy_level}, "
        f"benchmark fit {benchmark_fit}."
    )
