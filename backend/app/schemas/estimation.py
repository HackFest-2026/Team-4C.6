from typing import List, Dict, Any, Optional, Union
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
    target_platforms: Optional[List[str]] = None
    team_size: int = Field(default=4, ge=1, le=50)
    deadline_days: Optional[int] = Field(default=None, ge=1)
    working_hours_per_day: float = Field(default=8.0, ge=4.0, le=16.0)
    working_days_per_week: int = Field(default=5, ge=1, le=7)
    currency: str = "INR"
    currency_exchange_rate: Optional[float] = None
    rate_profile: str = "Professional"
    custom_rates: Optional[Dict[str, float]] = None
    custom_role_allocations: Optional[Dict[str, float]] = None
    role_headcounts: Optional[Dict[str, int]] = None
    contingency_pct: float = Field(default=0.15, ge=0.0, le=0.50)
    one_time_infra_inr: float = Field(default=25000.0, ge=0.0)
    tooling_setup_inr: float = Field(default=15000.0, ge=0.0)
    other_direct_costs_inr: float = Field(default=0.0, ge=0.0)
    infrastructure_items: Optional[List[Dict[str, Any]]] = None
    features: List[FeatureItem] = Field(default_factory=list)


class ScopeAnalyzeRequest(BaseModel):
    description: Optional[str] = ""
    project_type: Optional[str] = "SaaS Platform"
    project_name: Optional[str] = ""
    overall_complexity: Optional[str] = "Medium"
    complexity: Optional[str] = None
    target_platforms: List[str] = Field(default_factory=lambda: ["Web Application"])
    user_scale: Optional[str] = "1k-10k"
    tech_stack: Optional[Dict[str, Any]] = None
    existing_features: Optional[List[str]] = Field(default_factory=list)
    client_region: Optional[str] = "India"
    quality_requirement: Optional[str] = "Standard"
    realtime_requirement: Optional[str] = "None"
    security_compliance: Optional[str] = "Standard"
    deadline_days: Optional[int] = None
    budget_constraint: Optional[float] = None
    user_id: Optional[str] = None
    additional_notes: Optional[str] = ""


class CurrencyConvertRequest(BaseModel):
    amount_inr: Optional[float] = None
    amount: Optional[float] = None
    target_currency: str = "USD"
    custom_rate: Optional[float] = None
    budget: Optional[Dict[str, Any]] = None


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
    currency: Optional[str] = "INR"
    currency_code: Optional[str] = None
    canonical_currency: Optional[str] = "INR"
    canonical_amount_inr: Optional[float] = None
    exchange_rate: Optional[float] = None
    exchange_rate_source: Optional[str] = None
    exchange_rate_timestamp: Optional[str] = None
    final_budget_converted: Optional[float] = None
    estimate: Dict[str, Any]


class TechStackRecommendRequest(BaseModel):
    project_name: Optional[str] = ""
    project_type: str = "SaaS Platform"
    description: Optional[str] = ""
    overall_complexity: str = "Medium"
    complexity: Optional[str] = None
    target_platforms: List[str] = Field(default_factory=lambda: ["Web Application"])
    user_scale: Optional[str] = "1k-10k"
    expected_traffic: Optional[str] = None
    client_region: Optional[str] = "India"


class RoleRecommendRequest(BaseModel):
    features: List[FeatureItem] = Field(default_factory=list)
    project_type: Optional[str] = "SaaS Platform"
    overall_complexity: Optional[str] = "Medium"
    complexity: Optional[str] = None
    target_platforms: List[str] = Field(default_factory=list)
    rate_profile: Optional[str] = "Professional"
    currency: Optional[str] = "INR"


class InfraRecommendRequest(BaseModel):
    project_name: Optional[str] = ""
    project_type: Optional[str] = "SaaS Platform"
    overall_complexity: Optional[str] = "Medium"
    complexity: Optional[str] = None
    target_platforms: Union[List[str], str] = Field(default_factory=list)
    frontend_stack: Union[List[str], str] = Field(default_factory=list)
    backend_stack: Union[List[str], str] = Field(default_factory=list)
    database: Union[List[str], str] = Field(default_factory=list)
    hosting_cloud: Union[List[str], str] = Field(default_factory=list)
    cloud_platform: Optional[Union[List[str], str]] = None
    user_scale: Optional[str] = "1k-10k"
    expected_traffic: Optional[str] = None
    features_count: Optional[int] = 4
    features: Optional[List[FeatureItem]] = None
    integrations_count: Optional[int] = 1
    currency: Optional[str] = "INR"


class ProjectReconciliationRequest(BaseModel):
    actual_effort_hours: float = Field(..., ge=0.0)
    actual_duration_days: float = Field(..., ge=0.0)
    actual_cost: float = Field(..., ge=0.0)
    currency_code: Optional[str] = "INR"
    project_status: Optional[str] = "Completed"
    notes: Optional[str] = ""



