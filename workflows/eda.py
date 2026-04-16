import json
from typing import Any, Mapping

import pandas as pd

from workflows.measurement_profile import default_energy_component_columns, profile_measurement_dataframe


def build_numeric_summary(df: pd.DataFrame, profile: Mapping[str, Any] | None = None) -> pd.DataFrame:
    profile = profile or profile_measurement_dataframe(df)
    energy_like = set(default_energy_component_columns(profile))
    rows = []

    for column in profile.get("columns", []):
        name = column.get("name")
        if not name or not column.get("is_numeric"):
            continue
        values = pd.to_numeric(df[name], errors="coerce")
        valid = values.dropna()
        if valid.empty:
            continue
        rows.append({
            "column": name,
            "missing": int(values.isna().sum()),
            "min": round(float(valid.min()), 4),
            "max": round(float(valid.max()), 4),
            "mean": round(float(valid.mean()), 4),
            "median": round(float(valid.median()), 4),
            "std": round(float(valid.std()), 4) if len(valid) > 1 else 0.0,
            "energy_like": name in energy_like,
        })

    return pd.DataFrame(rows)


def build_eda_chat_context(
    filename: str,
    df: pd.DataFrame,
    profile: Mapping[str, Any],
    summary_df: pd.DataFrame,
    sample_size: int = 5,
) -> str:
    compact_columns = [
        {
            "name": column.get("name"),
            "dtype": column.get("dtype"),
            "missing": column.get("missing"),
            "is_numeric": column.get("is_numeric"),
            "suggested_unit": column.get("suggested_unit"),
            "min": column.get("min"),
            "max": column.get("max"),
            "mean": column.get("mean"),
            "std": column.get("std"),
        }
        for column in profile.get("columns", [])
    ]
    context = {
        "filename": filename,
        "row_count": profile.get("row_count"),
        "column_count": len(profile.get("columns", [])),
        "time_column": profile.get("time_column"),
        "sampling_rate_hz": profile.get("sampling_rate_hz"),
        "time_column_rationale": profile.get("time_column_rationale"),
        "columns": compact_columns,
        "numeric_summary": summary_df.to_dict(orient="records") if not summary_df.empty else [],
        "sample_rows": df.head(sample_size).where(pd.notna(df.head(sample_size)), None).to_dict(orient="records"),
    }
    return "### UPLOADED DATASET ###\n" + json.dumps(context, indent=2, default=str)
