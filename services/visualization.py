import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Dict, Any, List, Optional

from config.settings import COLORS, COLORS_SEQUENCE

# Erweiterte Farb-Mappings fuer Charts
CHART_COLORS = {
    **COLORS,
    "electric": COLORS["primary"],     # Blau
    "pneumatic": COLORS["secondary"],   # Hellblau
    "background": "rgba(0,0,0,0)",
    "grid": "rgba(0,0,0,0.08)"         # Subtiles Grid fuer Light Mode
}

# Standard Layout-Konfiguration
LAYOUT_DEFAULTS = dict(
    font=dict(family="system-ui, -apple-system, sans-serif", size=12, color="#1A1A1A"),
    paper_bgcolor=CHART_COLORS["background"],
    plot_bgcolor=CHART_COLORS["background"],
    margin=dict(l=40, r=40, t=50, b=40),
    title_x=0.5,
    title_font_size=16,
)


class VisualizationService:
    """Service fuer die Erstellung von interaktiven Visualisierungen mit Plotly."""
    
    @staticmethod
    def _apply_layout(fig: go.Figure, title: str) -> go.Figure:
        """Wendet einheitliches Layout auf eine Figur an."""
        fig.update_layout(
            **LAYOUT_DEFAULTS,
            title=title
        )
        return fig
    
    @staticmethod
    def plot_energy_distribution(data: Dict[str, Any]) -> Optional[go.Figure]:
        """Erstellt ein Sunburst-Chart der Energieverteilung."""
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
            color='Group',
            color_discrete_map={
                "Elektrisch": CHART_COLORS["electric"],
                "Pneumatisch": CHART_COLORS["pneumatic"]
            }
        )
        fig = VisualizationService._apply_layout(fig, "Energieverteilung nach Komponenten")
        fig.update_traces(
            textinfo="label+percent entry",
            insidetextorientation='radial'
        )
        return fig

    @staticmethod
    def plot_kpi_comparison(audit_data: Dict[str, Any], benchmark_data: Dict[str, Any]) -> go.Figure:
        """Erstellt ein Bar-Chart zum Vergleich Audit vs Benchmark."""
        audit_total = audit_data.get("Overall Summary", {}).get("Total Energy (kWh)", 0)
        benchmark_total = benchmark_data.get("energy_data", {}).get("energy_usage", "0")
        
        # Benchmark-Wert extrahieren
        try:
            benchmark_val = float(str(benchmark_total).split()[0])
        except (ValueError, AttributeError):
            benchmark_val = 0.0
            
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=["Audit-Daten", "Benchmark"],
            y=[audit_total, benchmark_val],
            marker_color=[CHART_COLORS["primary"], CHART_COLORS["secondary"]],
            text=[f"{audit_total:.4f}", f"{benchmark_val:.4f}"],
            textposition='outside',
            name="Energie (kWh)"
        ))
        
        fig = VisualizationService._apply_layout(fig, "Energievergleich: Audit vs. Benchmark")
        fig.update_layout(
            yaxis_title="Energie (kWh)",
            showlegend=False,
            bargap=0.4
        )
        fig.update_yaxes(gridcolor=CHART_COLORS["grid"], zeroline=True, zerolinecolor=CHART_COLORS["grid"])
        return fig

    @staticmethod
    def plot_component_comparison(audit_details: Dict[str, Any], group_name: str = "Elektrisch") -> Optional[go.Figure]:
        """Bar-Chart fuer einzelne Komponenten innerhalb einer Gruppe."""
        if group_name not in audit_details or "Variables" not in audit_details[group_name]:
            return None
            
        vars_data = audit_details[group_name]["Variables"]
        df = pd.DataFrame.from_dict(vars_data, orient='index').reset_index()
        df.rename(columns={'index': 'Component'}, inplace=True)
        df = df.sort_values('total_energy_kWh', ascending=True)
        
        color = CHART_COLORS["electric"] if group_name == "Elektrisch" else CHART_COLORS["pneumatic"]
        
        fig = px.bar(
            df, 
            y='Component', 
            x='total_energy_kWh',
            orientation='h',
            labels={'total_energy_kWh': 'Energie (kWh)', 'Component': ''}
        )
        fig.update_traces(marker_color=color)
        fig = VisualizationService._apply_layout(fig, f"Energie pro Komponente ({group_name})")
        fig.update_xaxes(gridcolor=CHART_COLORS["grid"])
        return fig

