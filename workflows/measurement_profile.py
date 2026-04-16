import json
import math
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional

import pandas as pd

from config.machine_variables import ELECTRIC_VARIABLES, PNEUMATIC_VARIABLES
from core.json_extractor import extract_json_from_response


TIME_COLUMN_HINTS = ("time", "timestamp", "elapsed", "zeit", "seconds", "sekunde", "sec")
ELECTRIC_HINTS = (
    "versorgung",
    "antrieb",
    "pumpe",
    "kuhl",
    "filter",
    "forder",
    "spane",
    "power",
    "leistung",
)
PNEUMATIC_HINTS = ("air", "luft", "pneum", "blum", "ventil", "klemm", "nps", "druck")
MAIN_SUPPLY_HINTS = (
    "hauptversorgung",
    "haupt versorgung",
    "main supply",
    "mainsupply",
    "main",
    "total",
    "gesamt",
    "versorgung gesamt",
)
PNEUMATIC_MAIN_HINTS = (
    "airpower hauptversorgung",
    "compressed air",
    "main valve",
    "hauptventilblock",
    "druckluft haupt",
)
NON_ENERGY_HINTS = (
    "temp",
    "temperatur",
    "temperature",
    "celsius",
    "status",
    "state",
    "zustand",
    "id",
    "index",
    "counter",
    "zaehler",
    "zähler",
    "cycle",
    "program",
    "programm",
    "position",
    "axis",
    "achse",
)
ENERGY_COMPONENT_HINTS = ELECTRIC_HINTS + PNEUMATIC_HINTS + (
    "energy",
    "energie",
    "kw",
    "watt",
    "strom",
    "current",
    "main supply",
    "total",
)


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _infer_unit(column_name: str, values: pd.Series) -> str:
    name = column_name.lower()
    if "kw" in name:
        return "kW"
    if "w" in name or "power" in name or "leistung" in name:
        return "W"
    numeric = _numeric_measurement_values(values)
    if not numeric.empty and numeric.quantile(0.95) < 100:
        return "kW"
    return "W" if not numeric.empty else "unknown"


def _numeric_measurement_values(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return pd.Series(dtype="float64")
    numeric = pd.to_numeric(values, errors="coerce")
    if pd.api.types.is_bool_dtype(numeric):
        return pd.Series(dtype="float64")
    return numeric.astype("float64").dropna()


def _detect_time_column_details(df: pd.DataFrame) -> Dict[str, Any]:
    for column in df.columns:
        normalized = _normalize_text(str(column))
        if any(hint in normalized for hint in TIME_COLUMN_HINTS):
            return {
                "time_column": str(column),
                "source": "local_name_hint",
                "confidence": 0.9,
                "rationale": "Column name contains a time-related keyword.",
            }

    numeric_candidates = []
    for column in df.columns:
        values = _numeric_measurement_values(df[column])
        if len(values) >= 3 and values.is_monotonic_increasing:
            numeric_candidates.append(str(column))
    if numeric_candidates:
        return {
            "time_column": numeric_candidates[0],
            "source": "local_monotonic_numeric",
            "confidence": 0.55,
            "rationale": "No time-name hint found; selected first monotonic numeric column.",
        }

    return {
        "time_column": None,
        "source": "not_detected",
        "confidence": 0.0,
        "rationale": "No time-name hint or monotonic numeric time candidate found.",
    }


def _detect_time_column(df: pd.DataFrame) -> Optional[str]:
    return _detect_time_column_details(df).get("time_column")


def estimate_sampling_rate_hz(df: pd.DataFrame, time_column: Optional[str]) -> Optional[float]:
    if not time_column or time_column not in df.columns:
        return None
    time_values = pd.to_numeric(df[time_column], errors="coerce").dropna()
    deltas = time_values.diff().dropna()
    deltas = deltas[deltas > 0]
    if deltas.empty:
        return None
    median_delta = float(deltas.median())
    if median_delta <= 0:
        return None
    return round(1 / median_delta, 4)


def profile_measurement_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    time_detection = _detect_time_column_details(df)
    time_column = time_detection.get("time_column")
    sampling_rate_hz = estimate_sampling_rate_hz(df, time_column)
    columns = []

    for column in df.columns:
        series = df[column]
        valid = _numeric_measurement_values(series)
        entry = {
            "name": str(column),
            "dtype": str(series.dtype),
            "non_null": int(series.notna().sum()),
            "missing": int(series.isna().sum()),
            "is_numeric": bool(not valid.empty),
            "suggested_unit": _infer_unit(str(column), series) if str(column) != time_column else "s",
        }
        if not valid.empty:
            entry.update({
                "min": round(float(valid.min()), 4),
                "max": round(float(valid.max()), 4),
                "mean": round(float(valid.mean()), 4),
                "std": round(float(valid.std()), 4) if len(valid) > 1 else 0.0,
                "is_monotonic_increasing": bool(valid.is_monotonic_increasing),
            })
        columns.append(entry)

    return {
        "row_count": int(len(df)),
        "time_column": time_column,
        "sampling_rate_hz": sampling_rate_hz,
        "time_column_source": time_detection["source"],
        "time_column_confidence": time_detection["confidence"],
        "time_column_rationale": time_detection["rationale"],
        "columns": columns,
    }


def build_measurement_context(
    df: pd.DataFrame,
    profile: Mapping[str, Any],
    sample_size: int = 5,
) -> Dict[str, Any]:
    """Build a compact LLM context from profile plus representative rows."""
    row_count = len(df)
    sample_indexes: list[int] = []
    if row_count:
        sample_indexes.extend(range(min(sample_size, row_count)))
        middle_start = max(0, row_count // 2 - sample_size // 2)
        sample_indexes.extend(range(middle_start, min(middle_start + sample_size, row_count)))
        sample_indexes.extend(range(max(0, row_count - sample_size), row_count))

    return {
        "profile": profile,
        "column_names": [str(column) for column in df.columns],
        "representative_rows": [
            _serialize_row(index, df.iloc[index].to_dict())
            for index in sorted(set(sample_indexes))
        ],
    }


def default_energy_component_columns(profile: Mapping[str, Any]) -> List[str]:
    """Return numeric non-time columns that look like energy or utility channels."""
    selected = []
    time_column = profile.get("time_column")
    for column in profile.get("columns", []):
        name = column.get("name")
        if name == time_column or not column.get("is_numeric"):
            continue
        if _is_default_energy_component(column):
            selected.append(name)
    return selected


def filter_profile_for_selected_components(
    profile: Mapping[str, Any],
    selected_component_columns: Iterable[str],
) -> Dict[str, Any]:
    selected = {str(column) for column in selected_component_columns}
    time_column = profile.get("time_column")
    numeric_columns = {
        column.get("name")
        for column in profile.get("columns", [])
        if column.get("is_numeric") and column.get("name") != time_column
    }
    allowed = set(selected)
    if time_column:
        allowed.add(str(time_column))
    filtered = dict(profile)
    filtered["columns"] = [
        dict(column)
        for column in profile.get("columns", [])
        if column.get("name") in allowed
    ]
    filtered["component_selection"] = {
        "selected_component_columns": [column for column in profile_column_names(profile) if column in selected],
        "excluded_numeric_columns": sorted(numeric_columns - selected),
        "excluded_note": "Excluded numeric columns were not mapped, calculated, charted, or included in the energy balance.",
    }
    return filtered


def profile_column_names(profile: Mapping[str, Any]) -> List[str]:
    return [column.get("name") for column in profile.get("columns", [])]


def _is_default_energy_component(column: Mapping[str, Any]) -> bool:
    name = str(column.get("name", ""))
    normalized = _normalize_text(name)
    tokens = set(normalized.split())
    unit = column.get("suggested_unit")
    if any((hint in tokens if len(hint) <= 2 else hint in normalized) for hint in NON_ENERGY_HINTS):
        return False
    if unit not in {"W", "kW", "unknown"}:
        return False
    if any(_normalize_text(hint) in normalized for hint in ENERGY_COMPONENT_HINTS):
        return True
    if unit in {"W", "kW"} and column.get("max", 0) not in (None, 0):
        return True
    return False


def _serialize_row(index: int, row: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "row_index": int(index),
        "values": {str(key): _json_safe(value) for key, value in row.items()},
    }


def _json_safe(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _best_channel_name(column_name: str, candidates: Iterable[str]) -> Optional[str]:
    normalized_column = _normalize_text(column_name)
    best = None
    best_score = 0
    for candidate in candidates:
        candidate_tokens = _normalize_text(candidate).split()
        score = sum(1 for token in candidate_tokens if token and token in normalized_column)
        if score > best_score:
            best = candidate
            best_score = score
    return best if best_score else None


def suggest_mapping_locally(profile: Mapping[str, Any]) -> Dict[str, Any]:
    time_column = profile.get("time_column")
    sampling_rate_hz = profile.get("sampling_rate_hz")
    channels = []

    for column in profile.get("columns", []):
        source_column = column["name"]
        if source_column == time_column or not column.get("is_numeric"):
            continue

        normalized = _normalize_text(source_column)
        medium = "pneumatic" if any(hint in normalized for hint in PNEUMATIC_HINTS) else "electric"
        candidates = PNEUMATIC_VARIABLES if medium == "pneumatic" else ELECTRIC_VARIABLES
        canonical = _best_channel_name(source_column, candidates)
        if canonical is None:
            canonical = source_column
            confidence = 0.45
            rationale = "Fallback: no known channel name matched clearly."
        else:
            confidence = 0.75
            rationale = "Matched from known machine channel names."

        if any(hint in normalized for hint in ELECTRIC_HINTS + PNEUMATIC_HINTS):
            confidence = max(confidence, 0.65)

        channels.append({
            "source_column": source_column,
            "canonical_name": canonical,
            "medium": medium,
            "unit": column.get("suggested_unit", "W"),
            "scale_to_watts": 1000.0 if column.get("suggested_unit") == "kW" else 1.0,
            "sampling_rate_hz": sampling_rate_hz,
            "confidence": confidence,
            "rationale": rationale,
            "include_in_audit": True,
            "supply_role": "component",
            "is_balance_source": False,
            "parent_supply": None,
        })

    mapping = {
        "time_column": time_column,
        "sampling_rate_hz": sampling_rate_hz,
        "channels": channels,
        "notes": "Local heuristic mapping. Review before audit calculation.",
    }
    return apply_main_supply_detection(mapping)


def apply_main_supply_detection(
    mapping: Mapping[str, Any],
    supply_hints: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    normalized = dict(mapping)
    channels = [dict(channel) for channel in normalized.get("channels", [])]

    for channel in channels:
        channel["supply_role"] = channel.get("supply_role") or "component"
        channel["is_balance_source"] = bool(channel.get("is_balance_source", False))
        channel["parent_supply"] = channel.get("parent_supply") or None
        channel["supply_confidence"] = channel.get("supply_confidence", channel.get("confidence", 0.5))
        channel["supply_rationale"] = channel.get("supply_rationale", "")

    selected = _select_main_supplies(channels, supply_hints or {})
    for channel in channels:
        medium = channel.get("medium")
        source_column = channel.get("source_column")
        main_source = selected.get(medium)
        if main_source and source_column == main_source.get("source_column"):
            channel["supply_role"] = "main_supply"
            channel["is_balance_source"] = True
            channel["parent_supply"] = None
            channel["supply_confidence"] = main_source.get("confidence", channel.get("supply_confidence", 0.5))
            channel["supply_rationale"] = main_source.get("rationale", "Detected as main supply.")
        elif medium in {"electric", "pneumatic"}:
            channel["is_balance_source"] = False
            if main_source:
                channel["supply_role"] = "component"
                channel["parent_supply"] = main_source.get("source_column")
            elif channel.get("supply_role") == "main_supply":
                channel["supply_role"] = "component"

    normalized["channels"] = channels
    normalized["main_supplies"] = {
        "electric": selected.get("electric"),
        "pneumatic": selected.get("pneumatic"),
    }
    return normalized


def _select_main_supplies(
    channels: list[Dict[str, Any]],
    supply_hints: Mapping[str, Any],
) -> Dict[str, Optional[Dict[str, Any]]]:
    selected: Dict[str, Optional[Dict[str, Any]]] = {"electric": None, "pneumatic": None}
    for medium, hint_key in (("electric", "electric_main_supply"), ("pneumatic", "pneumatic_main_supply")):
        hinted = supply_hints.get(hint_key) or {}
        hinted_source = hinted.get("source_column") if isinstance(hinted, Mapping) else None
        if hinted_source and any(ch.get("source_column") == hinted_source and ch.get("medium") == medium for ch in channels):
            selected[medium] = {
                "source_column": hinted_source,
                "confidence": _bounded_float(hinted.get("confidence", 0.65), 0.65),
                "rationale": hinted.get("rationale", "AI selected this channel as the main supply."),
            }
            continue

        existing = [
            ch for ch in channels
            if ch.get("medium") == medium and (ch.get("is_balance_source") or ch.get("supply_role") == "main_supply")
        ]
        if existing:
            channel = existing[0]
            selected[medium] = {
                "source_column": channel.get("source_column"),
                "confidence": _bounded_float(channel.get("supply_confidence", channel.get("confidence", 0.65)), 0.65),
                "rationale": channel.get("supply_rationale") or "Selected from existing mapping metadata.",
            }
            continue

        scored = [
            (_main_supply_score(ch), ch)
            for ch in channels
            if ch.get("medium") == medium
        ]
        scored = [(score, channel) for score, channel in scored if score > 0]
        if scored:
            score, channel = sorted(scored, key=lambda item: item[0], reverse=True)[0]
            selected[medium] = {
                "source_column": channel.get("source_column"),
                "confidence": min(0.95, 0.55 + score * 0.1),
                "rationale": "Name matches a main supply pattern.",
            }
    return selected


def _main_supply_score(channel: Mapping[str, Any]) -> int:
    text = _normalize_text(f"{channel.get('source_column', '')} {channel.get('canonical_name', '')}")
    hints = list(MAIN_SUPPLY_HINTS)
    if channel.get("medium") == "pneumatic":
        hints.extend(PNEUMATIC_MAIN_HINTS)
    score = sum(1 for hint in hints if _normalize_text(hint) in text)
    if "hauptversorgung" in text:
        score += 3
    if channel.get("medium") == "pneumatic" and "airpower hauptversorgung" in text:
        score += 4
    return score


def build_mapping_prompt(profile: Mapping[str, Any], user_instruction: str = "") -> str:
    return f"""
You are mapping machine tool energy measurement data for an audit.

Return ONLY JSON with this shape:
{{
  "time_column": "column name",
  "sampling_rate_hz": 2.0,
  "channels": [
    {{
      "source_column": "raw column",
      "canonical_name": "human readable component",
      "medium": "electric|pneumatic|other",
      "unit": "W|kW|unknown",
      "scale_to_watts": 1.0,
      "sampling_rate_hz": 2.0,
      "confidence": 0.0,
      "include_in_audit": true,
      "supply_role": "main_supply|component|other",
      "is_balance_source": true,
      "parent_supply": "source column or null",
      "rationale": "short reason"
    }}
  ],
  "notes": "mapping caveats"
}}

Rules:
- Map only measured consumer/power columns, not metadata columns.
- Map only source columns present in the provided measurement profile.
- Prefer electric or pneumatic medium when plausible.
- If values look like kW, use scale_to_watts 1000.0; if values look like W, use 1.0.
- Keep all source_column names exactly as provided.
- Mark exactly one electric and one pneumatic main supply as supply_role main_supply when identifiable.
- Do not mark sub-components as balance sources when they are measured downstream of a main supply.
- Use the user's instruction when it conflicts with heuristics.

User instruction:
{user_instruction or "No additional instruction."}

Measurement profile:
{json.dumps(profile, indent=2, ensure_ascii=False)}
""".strip()


def normalize_mapping(mapping: Mapping[str, Any], profile: Mapping[str, Any]) -> Dict[str, Any]:
    source_columns = {column["name"] for column in profile.get("columns", [])}
    time_column = mapping.get("time_column") or profile.get("time_column")
    channels = []

    for channel in mapping.get("channels", []):
        source_column = channel.get("source_column")
        if source_column not in source_columns or source_column == time_column:
            continue
        unit = channel.get("unit", "W") or "W"
        scale = channel.get("scale_to_watts")
        if scale is None:
            scale = 1000.0 if unit == "kW" else 1.0
        try:
            scale = float(scale)
        except (TypeError, ValueError):
            scale = 1000.0 if unit == "kW" else 1.0
        try:
            confidence = float(channel.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        supply_role = channel.get("supply_role") if channel.get("supply_role") in {"main_supply", "component", "other"} else "component"
        channels.append({
            "source_column": source_column,
            "canonical_name": channel.get("canonical_name") or source_column,
            "medium": channel.get("medium") if channel.get("medium") in {"electric", "pneumatic", "other"} else "other",
            "unit": unit,
            "scale_to_watts": scale,
            "sampling_rate_hz": channel.get("sampling_rate_hz") or profile.get("sampling_rate_hz"),
            "confidence": min(max(confidence, 0.0), 1.0),
            "rationale": channel.get("rationale", ""),
            "include_in_audit": _as_bool(channel.get("include_in_audit", True)),
            "supply_role": supply_role,
            "is_balance_source": _as_bool(channel.get("is_balance_source", supply_role == "main_supply")),
            "parent_supply": channel.get("parent_supply") or None,
            "supply_confidence": _bounded_float(channel.get("supply_confidence", confidence), confidence),
            "supply_rationale": channel.get("supply_rationale", ""),
        })

    normalized = {
        "time_column": time_column,
        "sampling_rate_hz": mapping.get("sampling_rate_hz") or profile.get("sampling_rate_hz"),
        "channels": channels,
        "notes": mapping.get("notes", ""),
        "component_selection": profile.get("component_selection", mapping.get("component_selection", {})),
    }
    return apply_main_supply_detection(normalized)


def generate_mapping_with_llm(provider: Any, profile: Mapping[str, Any], user_instruction: str = "") -> Dict[str, Any]:
    fallback = suggest_mapping_locally(profile)
    if provider is None:
        return fallback

    prompt = build_mapping_prompt(profile, user_instruction)
    response = provider.generate(prompt)
    try:
        mapping = extract_json_from_response(response)
    except ValueError:
        fallback["notes"] = f"{fallback['notes']} LLM mapping could not be parsed; fallback used."
        return fallback
    return normalize_mapping(mapping, profile)


def should_infer_time_column_with_ai(profile: Mapping[str, Any]) -> bool:
    return profile.get("time_column_source") != "local_name_hint" or not profile.get("time_column")


def infer_time_column_with_ai(
    provider: Any,
    profile: Mapping[str, Any],
    measurement_context: Mapping[str, Any],
) -> Dict[str, Any]:
    if provider is None:
        return {
            "time_column": profile.get("time_column"),
            "confidence": profile.get("time_column_confidence", 0.0),
            "rationale": "No LLM provider configured; kept local time column candidate.",
            "source": "local",
            "error": None,
        }

    prompt = f"""
You are selecting the best time column for machine measurement data.

Return ONLY JSON with this shape:
{{
  "time_column": "column name",
  "confidence": 0.0,
  "rationale": "short reason"
}}

Rules:
- Pick exactly one existing column name from the provided context.
- Prefer elapsed-time, timestamp, seconds, or monotonic numeric columns.
- Do not choose power, pressure, current, energy, or component-consumption columns.
- If uncertain, choose the most plausible monotonic acquisition axis and lower confidence.

Measurement context:
{json.dumps(measurement_context, indent=2, ensure_ascii=False)}
""".strip()
    try:
        parsed = extract_json_from_response(provider.generate(prompt))
    except ValueError:
        return {
            "time_column": profile.get("time_column"),
            "confidence": profile.get("time_column_confidence", 0.0),
            "rationale": "LLM time-column response could not be parsed; kept local candidate.",
            "source": "ai_parse_failed",
            "error": "parse_failed",
        }

    valid_columns = {column.get("name") for column in profile.get("columns", [])}
    time_column = parsed.get("time_column")
    if time_column not in valid_columns:
        return {
            "time_column": profile.get("time_column"),
            "confidence": profile.get("time_column_confidence", 0.0),
            "rationale": "LLM selected a column not present in the data; kept local candidate.",
            "source": "ai_invalid_column",
            "error": "invalid_column",
        }
    return {
        "time_column": time_column,
        "confidence": _bounded_float(parsed.get("confidence", 0.65), 0.65),
        "rationale": parsed.get("rationale", "LLM selected the most plausible time column."),
        "source": "ai",
        "error": None,
    }


def apply_time_column_selection(
    profile: Mapping[str, Any],
    df: pd.DataFrame,
    time_column: Optional[str],
    source: str = "manual",
    confidence: Optional[float] = None,
    rationale: str = "",
) -> Dict[str, Any]:
    updated = dict(profile)
    updated["time_column"] = time_column
    updated["sampling_rate_hz"] = estimate_sampling_rate_hz(df, time_column)
    updated["time_column_source"] = source
    updated["time_column_confidence"] = _bounded_float(confidence, 1.0 if source == "manual" else 0.0)
    updated["time_column_rationale"] = rationale or ("User selected the time column." if source == "manual" else "")
    columns = []
    for column in updated.get("columns", []):
        item = dict(column)
        if item.get("name") == time_column:
            item["suggested_unit"] = "s"
        elif item.get("suggested_unit") == "s":
            item["suggested_unit"] = "W" if item.get("is_numeric") else "unknown"
        columns.append(item)
    updated["columns"] = columns
    return updated


def missing_main_supply_media(mapping: Mapping[str, Any]) -> List[str]:
    media = {"electric": False, "pneumatic": False}
    present = {"electric": False, "pneumatic": False}
    for channel in mapping.get("channels", []):
        medium = channel.get("medium")
        if medium in present:
            present[medium] = True
        if medium in media and channel.get("is_balance_source"):
            media[medium] = True
    return [medium for medium, found in media.items() if present[medium] and not found]


def infer_main_supplies_with_ai(
    provider: Any,
    mapping: Mapping[str, Any],
    profile: Mapping[str, Any],
    measurement_context: Mapping[str, Any],
) -> Dict[str, Any]:
    if provider is None or not missing_main_supply_media(mapping):
        return {}
    prompt = f"""
You are identifying main utility supply channels in machine measurement data.

Return ONLY JSON with this shape:
{{
  "electric_main_supply": {{"source_column": "...", "confidence": 0.0, "rationale": "..."}},
  "pneumatic_main_supply": {{"source_column": "...", "confidence": 0.0, "rationale": "..."}}
}}

Rules:
- source_column must exactly match an existing mapped channel source_column.
- Pick at most one electric main supply and at most one pneumatic main supply.
- A main supply is the upstream total feed for that medium; downstream components must not be double counted with it.
- If a medium has no plausible main supply, return null for that medium.

Current mapping:
{json.dumps(mapping, indent=2, ensure_ascii=False)}

Measurement context:
{json.dumps(measurement_context, indent=2, ensure_ascii=False)}
""".strip()
    try:
        parsed = extract_json_from_response(provider.generate(prompt))
    except ValueError:
        return {
            "error": "parse_failed",
            "rationale": "LLM main-supply response could not be parsed; kept local supply roles.",
        }

    valid_by_medium = {
        channel.get("source_column"): channel.get("medium")
        for channel in mapping.get("channels", [])
    }
    result: Dict[str, Any] = {}
    for medium, key in (("electric", "electric_main_supply"), ("pneumatic", "pneumatic_main_supply")):
        value = parsed.get(key)
        if not isinstance(value, Mapping):
            result[key] = None
            continue
        source_column = value.get("source_column")
        if source_column and valid_by_medium.get(source_column) == medium:
            result[key] = {
                "source_column": source_column,
                "confidence": _bounded_float(value.get("confidence", 0.65), 0.65),
                "rationale": value.get("rationale", "LLM selected this channel as the main supply."),
            }
        else:
            result[key] = None
    return result


def enhance_mapping_with_supply_ai(
    provider: Any,
    mapping: Mapping[str, Any],
    profile: Mapping[str, Any],
    measurement_context: Mapping[str, Any],
) -> Dict[str, Any]:
    normalized = apply_main_supply_detection(mapping)
    if provider is None or not missing_main_supply_media(normalized):
        return normalized
    supply_hints = infer_main_supplies_with_ai(provider, normalized, profile, measurement_context)
    if supply_hints.get("error"):
        notes = normalized.get("notes", "")
        normalized["notes"] = f"{notes} Main-supply AI fallback failed; local supply roles used.".strip()
        return normalized
    return apply_main_supply_detection(normalized, supply_hints)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _bounded_float(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return min(max(number, 0.0), 1.0)
