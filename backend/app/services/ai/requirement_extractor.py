import json
import logging
import os
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)


class ExtractedFeature(BaseModel):
    name: str
    category: str
    complexity: str = "Medium"
    description: str = ""
    dependencies: List[str] = Field(default_factory=list)
    integration_requirements: List[str] = Field(default_factory=list)
    priority: str = "Must-Have"


class RequirementExtractionResult(BaseModel):
    project_type: str = "SaaS Web Application"
    overall_complexity: str = "Medium"
    features: List[ExtractedFeature]
    recommended_tech_stack: Dict[str, str] = Field(default_factory=dict)
    missing_requirements: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    is_ai_generated: bool = False
    provider_used: str = "rule_based_offline"


# Archetype domain features for offline/fallback extraction
DOMAIN_ARCHETYPES = {
    "food delivery": [
        ExtractedFeature(name="Customer Authentication & Profiles", category="Authentication", complexity="Medium", description="JWT login, social sign-in, address book"),
        ExtractedFeature(name="Restaurant & Menu Catalog", category="CRUD/data module", complexity="Medium", description="Browse restaurants, menus, dishes, modifiers, pricing"),
        ExtractedFeature(name="Search & Geospatial Filters", category="Search/filter", complexity="High", description="Filter by cuisine, rating, delivery time, distance"),
        ExtractedFeature(name="Shopping Cart & Checkout", category="CRUD/data module", complexity="Medium", description="Cart state, coupons, tax calculation"),
        ExtractedFeature(name="Payment Gateway Integration", category="Payment integration", complexity="High", description="Razorpay/Stripe, card, UPI, refunds", integration_requirements=["Payment Gateway"]),
        ExtractedFeature(name="Live Order Tracking & Geolocation", category="Real-time features", complexity="Very High", description="WebSockets, driver GPS location updates, map rendering", integration_requirements=["Google Maps API"]),
        ExtractedFeature(name="Driver Dispatch & Assignment", category="Booking/scheduling", complexity="High", description="Order queue, driver proximity matching"),
        ExtractedFeature(name="SMS & Push Notifications", category="Email/SMS notifications", complexity="Medium", description="Order status updates to customer and driver", integration_requirements=["Twilio/Firebase"]),
        ExtractedFeature(name="Admin & Restaurant Portal", category="Admin dashboard", complexity="High", description="Menu management, order fulfillment, payout reports"),
    ],
    "fintech": [
        ExtractedFeature(name="Identity & KYC Verification", category="Security/compliance", complexity="Very High", description="Document upload, biometric check, regulatory compliance", integration_requirements=["KYC Verification API"]),
        ExtractedFeature(name="MFA & Secure Authentication", category="Authentication", complexity="High", description="Multi-factor auth, biometrics, hardware token support"),
        ExtractedFeature(name="Account & Balance Ledger", category="CRUD/data module", complexity="Very High", description="Double-entry financial accounting ledger, ACID guarantees"),
        ExtractedFeature(name="Money Transfers & Payments", category="Payment integration", complexity="Very High", description="ACH, IMPS/NEFT, wire transfers, fraud detection", integration_requirements=["Banking Core API"]),
        ExtractedFeature(name="Transaction History & Statements", category="Analytics/reporting", complexity="Medium", description="Searchable statement export, PDF generation"),
        ExtractedFeature(name="Role-Based Permissions & Approvals", category="Role-based permissions", complexity="High", description="Maker-checker approval workflow, hierarchical privileges"),
        ExtractedFeature(name="Comprehensive Audit Logging", category="Audit logs", complexity="High", description="Immutable tamper-evident event streaming"),
    ],
    "ecommerce": [
        ExtractedFeature(name="User Registration & Account Management", category="Authentication", complexity="Low", description="Email sign-up, password reset, order history"),
        ExtractedFeature(name="Product Catalog & Inventory", category="CRUD/data module", complexity="Medium", description="SKUs, variants, categories, inventory stock levels"),
        ExtractedFeature(name="Faceted Search & Filtering", category="Search/filter", complexity="Medium", description="Price ranges, categories, brand filters, sorting"),
        ExtractedFeature(name="Shopping Cart & Promotions", category="CRUD/data module", complexity="Medium", description="Persistent cart, discount codes, bundles"),
        ExtractedFeature(name="Secure Payment Integration", category="Payment integration", complexity="High", description="Stripe/Razorpay, card validation, webhook listener", integration_requirements=["Stripe API"]),
        ExtractedFeature(name="Order Management & Shipping", category="Booking/scheduling", complexity="High", description="Order fulfillment, shipping label generation", integration_requirements=["Shipment Tracking API"]),
        ExtractedFeature(name="Customer Reviews & Ratings", category="CRUD/data module", complexity="Low", description="Verified purchaser reviews, star ratings"),
        ExtractedFeature(name="Merchant Admin Dashboard", category="Admin dashboard", complexity="Medium", description="Sales analytics, inventory restocking, order dispatch"),
    ],
    "saas": [
        ExtractedFeature(name="Authentication & SSO", category="Authentication", complexity="Medium", description="Google/GitHub OAuth, session management"),
        ExtractedFeature(name="Organization Multi-Tenancy", category="Multi-tenancy", complexity="Very High", description="Isolated tenant workspaces, custom domains"),
        ExtractedFeature(name="Role-Based Access Control (RBAC)", category="Role-based permissions", complexity="High", description="Admin, editor, viewer permission tiers"),
        ExtractedFeature(name="Subscription Billing & Invoicing", category="Subscription/billing", complexity="High", description="Tiered pricing, Stripe Billing, recurring invoices", integration_requirements=["Stripe Billing"]),
        ExtractedFeature(name="Core Business Logic Workflow", category="CRUD/data module", complexity="High", description="Application specific operations and state machine"),
        ExtractedFeature(name="REST API & Webhooks", category="Third-party API integration", complexity="Medium", description="Developer public API with rate limiting"),
        ExtractedFeature(name="Analytics & Usage Metrics", category="Analytics/reporting", complexity="Medium", description="Tenant usage counters, activity reports"),
    ],
}


class RequirementExtractor:
    """
    Extracts structured software specifications from free-text descriptions.
    Supports real AI providers if configured, or deterministic domain rule-based extraction.
    """

    def extract(self, description: str, project_type: Optional[str] = None) -> RequirementExtractionResult:
        desc_lower = description.lower()

        # If external AI is enabled and configured, attempt extraction
        if settings.AI_PROVIDER != "offline" and settings.AI_API_KEY:
            try:
                # LLM call placeholder / implementation
                # If it succeeds, return validated Pydantic model with is_ai_generated=True
                pass
            except Exception as e:
                logger.warning(f"External AI extraction failed: {e}. Falling back to rule-based engine.")

        # Offline domain-driven fallback
        matched_archetype = None
        for key in DOMAIN_ARCHETYPES.keys():
            if key in desc_lower or (project_type and key in project_type.lower()):
                matched_archetype = key
                break

        if matched_archetype:
            features = DOMAIN_ARCHETYPES[matched_archetype]
            derived_type = {
                "food delivery": "Booking Platform",
                "fintech": "Fintech Application",
                "ecommerce": "E-commerce",
                "saas": "SaaS Web Application",
            }.get(matched_archetype, project_type or "SaaS Web Application")
        else:
            # Generic multi-tier feature decomposition
            derived_type = project_type or "SaaS Web Application"
            features = [
                ExtractedFeature(name="User Authentication & Profiles", category="Authentication", complexity="Medium", description="User login, signup, password reset"),
                ExtractedFeature(name="Responsive Web UI", category="Responsive UI/page", complexity="Medium", description="Modern responsive frontend pages"),
                ExtractedFeature(name="Core Business Data Module", category="CRUD/data module", complexity="Medium", description="Primary entity management and operations"),
                ExtractedFeature(name="Search & Filter Interface", category="Search/filter", complexity="Low", description="Locate and filter core records"),
                ExtractedFeature(name="Admin & Analytics Dashboard", category="Admin dashboard", complexity="High", description="Operational metrics and administrative tools"),
                ExtractedFeature(name="Email Notifications", category="Email/SMS notifications", complexity="Low", description="Transactional alerts and emails"),
            ]

        # Determine recommended tech stack
        tech_stack = {
            "frontend_stack": "React",
            "backend_stack": "Node.js_Express" if "javascript" in desc_lower or "node" in desc_lower else "Django" if "python" in desc_lower else "Node.js_Express",
            "database": "PostgreSQL",
            "hosting_platform": "AWS",
        }

        # Calculate overall complexity from features
        comp_scores = {"Low": 1, "Medium": 2, "High": 3, "Very High": 4}
        avg_comp = sum(comp_scores.get(f.complexity, 2) for f in features) / max(1, len(features))
        overall_comp = "Low" if avg_comp < 1.7 else "Medium" if avg_comp < 2.7 else "High" if avg_comp < 3.5 else "Very High"

        return RequirementExtractionResult(
            project_type=derived_type,
            overall_complexity=overall_comp,
            features=features,
            recommended_tech_stack=tech_stack,
            missing_requirements=[
                "Confirm target concurrent active user volume and burst traffic expectations.",
                "Verify compliance standards (e.g., GDPR, SOC2, PCI-DSS) if handling sensitive payments or data.",
                "Specify target deployment regions and multi-region availability needs.",
            ],
            assumptions=[
                "Standard cloud infrastructure (AWS/GCP) with managed relational database.",
                "Single primary web frontend target unless cross-platform mobile apps are explicitly added.",
                "Third-party managed services for transactional emails and standard SMS.",
            ],
            is_ai_generated=False,
            provider_used="rule_based_offline",
        )


requirement_extractor = RequirementExtractor()
