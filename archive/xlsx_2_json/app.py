import streamlit as st
import pandas as pd
import numpy as np
import json

st.title("Machine Energy Data → JSON Summary")

# --- User inputs ---
maschine_name = st.text_input("Maschine Name")
operator_name = st.text_input("Operator Name")
maschine_state = st.text_input("Maschine State (e.g. Idle, Cutting, Cooling)")
material = st.text_input("Material Used (e.g. Aluminum, Steel, Plastic)")  # ✅ NEW
json_title = st.text_input("JSON File Title", value="energy_summary")

uploaded_file = st.file_uploader("Upload your .xlsx file", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # --- Validate time column ---
    if "elapsedTime" not in df.columns:
        st.error("The file must contain a column named 'elapsedTime'.")
        st.stop()

    time = df["elapsedTime"].to_numpy()
    duration_sec = time[-1] - time[0]
    duration_hr = duration_sec / 3600.0
    sampling_rate = 1 / np.mean(np.diff(time)) if len(time) > 1 else None

    # --- Define variable groups ---
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

    # --- Helper: round to 2 decimals ---
    def r(value):
        return round(float(value), 2)

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
            total_energy_kWh = np.trapz(values, time) / 3_600_000.0  # W·s → kWh
            time_of_peak = float(time[np.argmax(values)]) if len(values) > 0 else None

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

        # Group totals
        group_mean = np.mean(df[valid_vars].mean(axis=1))
        group_total_energy = np.trapz(df[valid_vars].sum(axis=1), time) / 3_600_000.0
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

    # --- Compute for each group ---
    elektrisch_details, elektrisch_total = compute_metrics(vars_elektrisch)
    pneumatisch_details, pneumatisch_total = compute_metrics(vars_pneumatisch)

    # --- Combine all variables for overall analysis ---
    all_vars_combined = []
    for var_name, metrics in elektrisch_details.items():
        all_vars_combined.append({
            "name": var_name,
            "group": "Elektrisch",
            **metrics
        })
    for var_name, metrics in pneumatisch_details.items():
        all_vars_combined.append({
            "name": var_name,
            "group": "Pneumatisch",
            **metrics
        })

    # --- Identify top-performing variables ---
    def find_top_variable(key):
        if not all_vars_combined:
            return None
        top_var = max(all_vars_combined, key=lambda x: x.get(key, 0))
        return {
            "name": top_var["name"],
            "group": top_var["group"],
            key: r(top_var[key])
        }

    top_mean = find_top_variable("mean")
    top_energy = find_top_variable("total_energy_kWh")
    top_peak = find_top_variable("max")

    # --- Duty cycle estimation ---
    def duty_cycle(vars_group, mean_value):
        if mean_value == 0 or not vars_group:
            return 0
        group_mean = df[vars_group].mean(axis=1)
        active = np.sum(group_mean > 0.1 * mean_value)
        return r(active / len(df) * 100)

    duty_elektrisch = duty_cycle(vars_elektrisch, elektrisch_total.get("mean", 0))
    duty_pneumatisch = duty_cycle(vars_pneumatisch, pneumatisch_total.get("mean", 0))

    # --- Create final JSON structure ---
    results = {
        "metadata": {
            "machine_name": maschine_name or "Unknown",
            "operator": operator_name or "Unknown",
            "machine_state": maschine_state or "Not specified",
            "material": material or "Not specified",  # ✅ added material
            "recording_start": r(time[0]),
            "recording_end": r(time[-1]),
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
            "Total Energy (kWh)": r(
                elektrisch_total.get("total_energy_kWh", 0)
                + pneumatisch_total.get("total_energy_kWh", 0)
            ),
            "Mean Power (W)": r(
                (elektrisch_total.get("mean", 0)
                 + pneumatisch_total.get("mean", 0)) / 2
            ),
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

    # --- Display and download ---
    st.subheader("Generated JSON Summary")
    st.json(results)

    json_str = json.dumps(results, indent=4)
    st.download_button(
        label="Download JSON",
        data=json_str,
        file_name=f"{json_title or 'energy_summary'}.json",
        mime="application/json"
    )
