from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class FeatureItem(BaseModel):
    id: Optional[str] = None
    name: str
    category: Optional[str] = None
    complexity: Optional[str] = "Medium"
    description: Optional[str] = ""
    dependencies: List[str] = Field(default_factory=list)
    reuse_level_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    integration_count: int = Field(default=0, ge=0)
    factor_scores: Optional[Dict[str, float]] = None


class EstimateRequest(BaseModel):
    project_name: Optional[str] = "New Software Project"
    project_type: str = "SaaS Web Application"
    overall_complexity: str = "Medium"
    description: Optional[str] = ""
    hosting_platform: str = "Web"
    team_size: int = Field(default=4, ge=1, le=50)
    deadline_days: Optional[int] = Field(default=None, ge=1)
    rate_profile: str = "Professional"
    custom_rates: Optional[Dict[str, float]] = None
    custom_role_allocations: Optional[Dict[str, float]] = None
    contingency_pct: float = Field(default=0.15, ge=0.0, le=0.50)
    one_time_infra_inr: float = Field(default=25000.0, ge=0.0)
    tooling_setup_inr: float = Field(default=15000.0, ge=0.0)
    other_direct_costs_inr: float = Field(default=0.0, ge=0.0)
    features: List[FeatureItem] = Field(default_factory=list)


class ScopeAnalyzeRequest(BaseModel):
    description: str
    project_type: Optional[str] = None


class BatchFeatureEffortRequest(BaseModel):
    features: List[FeatureItem]


class RecalculateRequest(BaseModel):
    base_estimate: Dict[str, Any]
    overrides: Dict[str, Any]


class CompareRequest(BaseModel):
    scenarios: List[EstimateRequest]


class ProjectSaveRequest(BaseModel):
    project_name: str
    description: Optional[str] = ""
    estimate: Dict[str, Any]
