from typing import Any, Dict, Mapping, Optional

import pandas as pd

from config.machine_variables import ELECTRIC_VARIABLES, PNEUMATIC_VARIABLES
from core.data_parser import DataParser


def calculate_audit_results(df: pd.DataFrame, metadata: Mapping[str, Any]) -> Dict[str, Any]:
    elek_details, elek_total = DataParser.compute_metrics(df, ELECTRIC_VARIABLES)
    pneu_details, pneu_total = DataParser.compute_metrics(df, PNEUMATIC_VARIABLES)

    duty_elek = DataParser.calculate_duty_cycle(df, ELECTRIC_VARIABLES, elek_total.get("mean", 0))
    duty_pneu = DataParser.calculate_duty_cycle(df, PNEUMATIC_VARIABLES, pneu_total.get("mean", 0))

    duration_sec = df["elapsedTime"].iloc[-1] - df["elapsedTime"].iloc[0]
    total_energy = round(elek_total.get("total_energy_kWh", 0) + pneu_total.get("total_energy_kWh", 0), 4)
    mean_power = round((elek_total.get("mean", 0) + pneu_total.get("mean", 0)) / 2, 2)
    energy_rate = round(total_energy / (duration_sec / 3600), 4) if duration_sec > 0 else 0

    return {
        "metadata": {
            "machine_name": metadata["machine_name"],
            "operator": metadata["operator"],
            "machine_state": metadata["machine_state"],
            "operating_state": metadata.get("operating_state", "not specified"),
            "material": metadata["material"],
            "duration_seconds": round(float(duration_sec), 2),
            "unit_power": "W",
            "unit_energy": "kWh"
        },
        "Elektrisch": {
            "Variables": elek_details,
            "Total Elektrisch": elek_total,
            "Duty Cycle (%)": duty_elek
        },
        "Pneumatisch": {
            "Variables": pneu_details,
            "Total Pneumatisch": pneu_total,
            "Duty Cycle (%)": duty_pneu
        },
        "Overall Summary": {
            "Total Energy (kWh)": total_energy,
            "Mean Power (W)": mean_power,
            "Energy Rate (kWh/hour)": energy_rate,
            "Top Variables": {}
        }
    }


def calculate_audit_results_from_mapping(
    df: pd.DataFrame,
    mapping: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> Dict[str, Any]:
    time_column = mapping.get("time_column") or "elapsedTime"
    if time_column not in df.columns:
        raise ValueError(f"Time column '{time_column}' not found in data.")

    normalized = pd.DataFrame({"elapsedTime": pd.to_numeric(df[time_column], errors="coerce")})
    channel_lookup = {}
    electric_vars = []
    pneumatic_vars = []
    electric_balance_var = None
    pneumatic_balance_var = None

    for channel in mapping.get("channels", []):
        if channel.get("include_in_audit") is False:
            continue
        source_column = channel.get("source_column")
        if source_column not in df.columns:
            continue
        canonical_name = _unique_name(channel.get("canonical_name") or source_column, normalized.columns)
        medium = channel.get("medium", "other")
        scale_to_watts = float(channel.get("scale_to_watts", 1.0) or 1.0)
        normalized[canonical_name] = pd.to_numeric(df[source_column], errors="coerce").fillna(0) * scale_to_watts
        channel_lookup[canonical_name] = dict(channel)
        channel_lookup[canonical_name]["normalized_name"] = canonical_name
        if medium == "pneumatic":
            pneumatic_vars.append(canonical_name)
            if channel.get("is_balance_source") and pneumatic_balance_var is None:
                pneumatic_balance_var = canonical_name
        elif medium == "electric":
            electric_vars.append(canonical_name)
            if channel.get("is_balance_source") and electric_balance_var is None:
                electric_balance_var = canonical_name

    elek_details, elek_total = DataParser.compute_metrics(normalized, electric_vars)
    pneu_details, pneu_total = DataParser.compute_metrics(normalized, pneumatic_vars)
    electric_balance_vars = [electric_balance_var] if electric_balance_var else electric_vars
    pneumatic_balance_vars = [pneumatic_balance_var] if pneumatic_balance_var else pneumatic_vars
    _, electric_balance_total = DataParser.compute_metrics(normalized, electric_balance_vars)
    _, pneumatic_balance_total = DataParser.compute_metrics(normalized, pneumatic_balance_vars)

    electric_component_vars = [name for name in electric_vars if name != electric_balance_var]
    pneumatic_component_vars = [name for name in pneumatic_vars if name != pneumatic_balance_var]
    _, electric_component_total = DataParser.compute_metrics(normalized, electric_component_vars)
    _, pneumatic_component_total = DataParser.compute_metrics(normalized, pneumatic_component_vars)

    duty_elek = DataParser.calculate_duty_cycle(normalized, electric_balance_vars, electric_balance_total.get("mean", 0))
    duty_pneu = DataParser.calculate_duty_cycle(normalized, pneumatic_balance_vars, pneumatic_balance_total.get("mean", 0))

    duration_sec = normalized["elapsedTime"].iloc[-1] - normalized["elapsedTime"].iloc[0]
    total_energy = round(
        electric_balance_total.get("total_energy_kWh", 0) + pneumatic_balance_total.get("total_energy_kWh", 0),
        4,
    )
    mean_power = round(electric_balance_total.get("mean", 0) + pneumatic_balance_total.get("mean", 0), 2)
    energy_rate = round(total_energy / (duration_sec / 3600), 4) if duration_sec > 0 else 0
    top_variables = _top_variables_for_recommendations(
        elek_details | pneu_details,
        {name for name in (electric_balance_var, pneumatic_balance_var) if name},
    )
    balance = {
        "electric_source": _source_column(channel_lookup, electric_balance_var),
        "pneumatic_source": _source_column(channel_lookup, pneumatic_balance_var),
        "electric_total_kWh": electric_balance_total.get("total_energy_kWh", 0),
        "pneumatic_total_kWh": pneumatic_balance_total.get("total_energy_kWh", 0),
        "total_energy_kWh": total_energy,
        "mean_power_W": mean_power,
        "double_counting_prevented": bool(electric_balance_var or pneumatic_balance_var),
    }
    component_analysis = {
        "electric_component_sum_kWh": electric_component_total.get("total_energy_kWh", 0),
        "pneumatic_component_sum_kWh": pneumatic_component_total.get("total_energy_kWh", 0),
        "coverage_vs_main_supply_pct": {
            "electric": _coverage_pct(electric_component_total, electric_balance_total),
            "pneumatic": _coverage_pct(pneumatic_component_total, pneumatic_balance_total),
        },
        "electric_component_count": len(electric_component_vars),
        "pneumatic_component_count": len(pneumatic_component_vars),
    }

    return {
        "metadata": {
            "machine_name": metadata["machine_name"],
            "operator": metadata["operator"],
            "machine_state": metadata["machine_state"],
            "operating_state": metadata.get("operating_state", "not specified"),
            "material": metadata["material"],
            "duration_seconds": round(float(duration_sec), 2),
            "unit_power": "W",
            "unit_energy": "kWh",
            "mapping_notes": mapping.get("notes", ""),
            "selected_component_columns": metadata.get("selected_component_columns", []),
            "excluded_numeric_columns": metadata.get("excluded_numeric_columns", []),
        },
        "mapping": mapping,
        "balance": balance,
        "component_analysis": component_analysis,
        "Elektrisch": {
            "Variables": _attach_mapping(elek_details, channel_lookup),
            "Total Elektrisch": electric_balance_total,
            "Component Total Elektrisch": electric_component_total,
            "Duty Cycle (%)": duty_elek
        },
        "Pneumatisch": {
            "Variables": _attach_mapping(pneu_details, channel_lookup),
            "Total Pneumatisch": pneumatic_balance_total,
            "Component Total Pneumatisch": pneumatic_component_total,
            "Duty Cycle (%)": duty_pneu
        },
        "Overall Summary": {
            "Total Energy (kWh)": total_energy,
            "Mean Power (W)": mean_power,
            "Energy Rate (kWh/hour)": energy_rate,
            "Top Variables": top_variables
        }
    }


def _attach_mapping(details: Dict[str, Any], channel_lookup: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    enriched = {}
    for name, metrics in details.items():
        enriched[name] = dict(metrics)
        if name in channel_lookup:
            enriched[name]["source_column"] = channel_lookup[name].get("source_column")
            enriched[name]["mapping_confidence"] = channel_lookup[name].get("confidence")
            enriched[name]["mapping_rationale"] = channel_lookup[name].get("rationale")
            enriched[name]["supply_role"] = channel_lookup[name].get("supply_role")
            enriched[name]["is_balance_source"] = channel_lookup[name].get("is_balance_source")
            enriched[name]["parent_supply"] = channel_lookup[name].get("parent_supply")
    return enriched


def _unique_name(name: str, existing_columns) -> str:
    if name not in existing_columns:
        return name
    index = 2
    candidate = f"{name} ({index})"
    while candidate in existing_columns:
        index += 1
        candidate = f"{name} ({index})"
    return candidate


def _top_variables(details: Mapping[str, Mapping[str, Any]], limit: int = 5) -> Dict[str, float]:
    ranked = sorted(
        (
            (name, metrics.get("total_energy_kWh", 0))
            for name, metrics in details.items()
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    return {name: value for name, value in ranked[:limit]}


def _top_variables_for_recommendations(
    details: Mapping[str, Mapping[str, Any]],
    balance_sources: set[str],
    limit: int = 5,
) -> Dict[str, float]:
    component_details = {
        name: metrics
        for name, metrics in details.items()
        if name not in balance_sources
    }
    return _top_variables(component_details or details, limit=limit)


def _coverage_pct(component_total: Mapping[str, Any], balance_total: Mapping[str, Any]) -> Optional[float]:
    balance_energy = float(balance_total.get("total_energy_kWh", 0) or 0)
    if balance_energy <= 0:
        return None
    component_energy = float(component_total.get("total_energy_kWh", 0) or 0)
    return round(component_energy / balance_energy * 100, 1)


def _source_column(channel_lookup: Mapping[str, Mapping[str, Any]], normalized_name: Optional[str]) -> Optional[str]:
    if not normalized_name:
        return None
    return channel_lookup.get(normalized_name, {}).get("source_column")
