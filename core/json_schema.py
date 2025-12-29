from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# --- Paper Metadata ---
class PaperMetadata(BaseModel):
    title: str = Field(..., description="The title of the scientific paper")
    authors: List[str] = Field(default_factory=list, description="List of authors")
    publication_date: Optional[str] = Field(None, description="Date of publication")
    journal_or_conference: Optional[str] = Field(None, description="Journal or conference name")

# --- Machine Info ---
class SpindleData(BaseModel):
    spindle_speed_rpm: float
    measured_power_w: float

class FeedingData(BaseModel):
    feed_velocity_mm_min: float
    x_axis_power_w: float
    y_axis_power_w: float
    z_axis_power_w_plus: float
    z_axis_power_w_minus: float

class ProcessParameters(BaseModel):
    spindle_speed: Optional[str] = None
    feed_rate: Optional[str] = None
    cutting_depth: Optional[str] = None
    spindle_data: List[SpindleData] = Field(default_factory=list)
    feeding_data: List[FeedingData] = Field(default_factory=list)

class MachineInfo(BaseModel):
    machine_name: str
    machine_type: Optional[str] = None
    axis: Optional[str] = None
    control_unit: Optional[str] = None
    material_processed: Optional[str] = None
    process_parameters: ProcessParameters

# --- Energy Data ---
class EnergyData(BaseModel):
    energy_usage: str = Field(..., description="Estimated and measured values")
    power_consumption: str = Field(..., description="Specific power values for components")
    measurement_method: Optional[str] = None

# --- KPI Metrics ---
class KPIMetrics(BaseModel):
    specific_energy_consumption: Optional[str] = None
    CO2_emissions: Optional[str] = None
    efficiency: Optional[str] = None
    other_kpis: List[str] = Field(default_factory=list)

# --- Main Paper Schema ---
class PaperJSON(BaseModel):
    paper_metadata: PaperMetadata
    machine_info: MachineInfo
    energy_data: EnergyData
    kpi_metrics: KPIMetrics
    additional_notes: Optional[str] = None

# --- Audit / Working Data Schema ---
class VariableMetrics(BaseModel):
    mean: float
    median: float
    max: float
    min: float
    std_dev: float
    range: float
    total_energy_kWh: float
    time_of_peak: Optional[float] = None

class GroupSummary(BaseModel):
    mean: float
    max: float
    min: float
    std_dev: float
    range: float
    total_energy_kWh: float

class ComponentGroup(BaseModel):
    Variables: Dict[str, VariableMetrics]
    Total_Group: GroupSummary = Field(..., alias="Total Elektrisch") # Or "Total Pneumatisch"
    Duty_Cycle_Percent: float = Field(..., alias="Duty Cycle (%)")

class OverallSummary(BaseModel):
    Total_Energy_kWh: float = Field(..., alias="Total Energy (kWh)")
    Mean_Power_W: float = Field(..., alias="Mean Power (W)")
    Energy_Rate_kWh_hour: float = Field(..., alias="Energy Rate (kWh/hour)")
    Top_Variables: Dict[str, Any]

class AuditJSON(BaseModel):
    metadata: Dict[str, Any]
    Elektrisch: Optional[Dict[str, Any]] = None
    Pneumatisch: Optional[Dict[str, Any]] = None
    Overall_Summary: OverallSummary = Field(..., alias="Overall Summary")

# --- Comparison Results ---
class ComparisonResult(BaseModel):
    audit_filename: str
    benchmark_filename: str
    comparison_text: str
    kpi_comparison: Dict[str, Any]
    timestamp: str

