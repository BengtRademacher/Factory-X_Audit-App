import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple

class DataParser:
    """Extrahiert und verarbeitet Daten aus Excel- und CSV-Dateien."""
    
    @staticmethod
    def read_file(file) -> pd.DataFrame:
        """Liest eine Excel- oder CSV-Datei ein."""
        if file.name.endswith('.xlsx') or file.name.endswith('.xls'):
            return pd.read_excel(file)
        elif file.name.endswith('.csv'):
            return pd.read_csv(file)
        else:
            raise ValueError("Unsupported file format. Please upload .xlsx, .xls or .csv")

    @staticmethod
    def compute_metrics(df: pd.DataFrame, vars_group: List[str], time_col: str = "elapsedTime") -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Berechnet Metriken für eine Gruppe von Variablen."""
        if time_col not in df.columns:
            raise ValueError(f"Time column '{time_col}' not found in data.")

        time = df[time_col].to_numpy()
        duration_sec = time[-1] - time[0]
        
        details = {}
        valid_vars = [v for v in vars_group if v in df.columns]
        
        if not valid_vars:
            return {}, {}

        for var in valid_vars:
            values = df[var].to_numpy(dtype=float)
            mean_val = np.mean(values)
            max_val = np.max(values)
            min_val = np.min(values)
            std_val = np.std(values)
            
            # W·s → kWh (trapz nutzt die Zeitachse korrekt für unregelmäßige Abtastung)
            total_energy_kWh = np.trapz(values, time) / 3_600_000.0
            
            details[var] = {
                "mean": round(float(mean_val), 2),
                "median": round(float(np.median(values)), 2),
                "max": round(float(max_val), 2),
                "min": round(float(min_val), 2),
                "std_dev": round(float(std_val), 2),
                "range": round(float(max_val - min_val), 2),
                "total_energy_kWh": round(float(total_energy_kWh), 4),
                "time_of_peak": round(float(time[np.argmax(values)]), 2)
            }

        # Group totals
        combined_values = df[valid_vars].sum(axis=1).to_numpy()
        group_total_energy = np.trapz(combined_values, time) / 3_600_000.0
        
        group_summary = {
            "mean": round(float(np.mean(combined_values)), 2),
            "max": round(float(np.max(combined_values)), 2),
            "min": round(float(np.min(combined_values)), 2),
            "std_dev": round(float(np.std(combined_values)), 2),
            "range": round(float(np.max(combined_values) - np.min(combined_values)), 2),
            "total_energy_kWh": round(float(group_total_energy), 4)
        }

        return details, group_summary

    @staticmethod
    def calculate_duty_cycle(df: pd.DataFrame, vars_group: List[str], mean_power: float) -> float:
        """Berechnet den Duty Cycle basierend auf einer Schwelle."""
        if not vars_group or mean_power == 0:
            return 0.0
        
        valid_vars = [v for v in vars_group if v in df.columns]
        if not valid_vars:
            return 0.0
            
        group_mean = df[valid_vars].mean(axis=1)
        active_samples = np.sum(group_mean > 0.1 * mean_power)
        return round(float(active_samples / len(df) * 100), 2)

