import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Dict, Any, List

class VisualizationService:
    """Service für die Erstellung von interaktiven Visualisierungen mit Plotly."""
    
    @staticmethod
    def plot_energy_distribution(data: Dict[str, Any]):
        """Erstellt ein Sunburst- oder Pie-Chart der Energieverteilung."""
        rows = []
        
        # Elektrische Daten
        if "Elektrisch" in data and "Variables" in data["Elektrisch"]:
            for var, metrics in data["Elektrisch"]["Variables"].items():
                rows.append({
                    "Group": "Elektrisch",
                    "Component": var,
                    "Energy (kWh)": metrics.get("total_energy_kWh", 0)
                })
                
        # Pneumatische Daten
        if "Pneumatisch" in data and "Variables" in data["Pneumatisch"]:
            for var, metrics in data["Pneumatisch"]["Variables"].items():
                rows.append({
                    "Group": "Pneumatisch",
                    "Component": var,
                    "Energy (kWh)": metrics.get("total_energy_kWh", 0)
                })
                
        if not rows:
            return None
            
        df = pd.DataFrame(rows)
        fig = px.sunburst(
            df, 
            path=['Group', 'Component'], 
            values='Energy (kWh)',
            title="Energy Consumption Distribution"
        )
        return fig

    @staticmethod
    def plot_kpi_comparison(audit_data: Dict[str, Any], benchmark_data: Dict[str, Any]):
        """Erstellt ein Radar-Chart oder Bar-Chart zum Vergleich mit Benchmarks."""
        # Beispiel: Vergleich der Gesamtenergie
        audit_total = audit_data.get("Overall Summary", {}).get("Total Energy (kWh)", 0)
        benchmark_total = benchmark_data.get("energy_data", {}).get("energy_usage", "0")
        
        # Da Benchmark oft Text ist, versuchen wir eine Zahl zu extrahieren oder nutzen Platzhalter
        try:
            benchmark_val = float(benchmark_total.split()[0]) # Sehr simple Heuristik
        except:
            benchmark_val = 0.0
            
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=["Audit", "Benchmark"],
            y=[audit_total, benchmark_val],
            marker_color=['blue', 'lightgrey'],
            name="Total Energy (kWh)"
        ))
        fig.update_layout(title="Total Energy Comparison")
        return fig

    @staticmethod
    def plot_component_comparison(audit_details: Dict[str, Any], group_name: str = "Elektrisch"):
        """Bar-Chart für einzelne Komponenten innerhalb einer Gruppe."""
        if group_name not in audit_details or "Variables" not in audit_details[group_name]:
            return None
            
        vars_data = audit_details[group_name]["Variables"]
        df = pd.DataFrame.from_dict(vars_data, orient='index').reset_index()
        df.rename(columns={'index': 'Component'}, inplace=True)
        
        fig = px.bar(
            df, 
            x='Component', 
            y='total_energy_kWh',
            title=f"Energy per Component ({group_name})",
            labels={'total_energy_kWh': 'Energy (kWh)'}
        )
        return fig

