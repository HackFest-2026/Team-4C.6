import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)

# Fallback generic base hours by complexity for completely novel features
GENERIC_BASE_HOURS = {
    "Low": 8.0,
    "Medium": 16.0,
    "High": 32.0,
    "Very High": 64.0,
}

# Category normalization keywords mapping
SYNONYM_MAPPINGS = {
    "Authentication": ["auth", "login", "signup", "register", "sso", "oauth", "password", "session", "jwt", "mfa", "2fa"],
    "Responsive UI/page": ["ui", "page", "screen", "frontend", "responsive", "landing", "layout", "view", "component"],
    "CRUD/data module": ["crud", "module", "catalog", "products", "items", "records", "table", "inventory", "management", "data"],
    "Search/filter": ["search", "filter", "query", "indexing", "autocomplete", "sort", "faceted"],
    "Admin dashboard": ["admin", "dashboard", "backoffice", "portal", "control panel", "console"],
    "Email/SMS notifications": ["notification", "email", "sms", "alert", "message", "push", "mailer"],
    "Payment integration": ["payment", "checkout", "stripe", "razorpay", "paypal", "gateway", "billing", "invoice", "refund"],
    "Booking/scheduling": ["booking", "schedule", "calendar", "appointment", "reservation", "slot"],
    "Analytics/reporting": ["analytics", "reporting", "reports", "metrics", "charts", "kpi", "telemetry"],
    "Third-party API integration": ["api", "integration", "webhook", "external", "third-party", "sync"],
    "File upload/storage": ["upload", "storage", "s3", "files", "documents", "media", "attachment"],
    "Role-based permissions": ["rbac", "permissions", "roles", "access control", "authorization", "user roles"],
    "Real-time features": ["realtime", "websocket", "chat", "live", "messaging", "presence", "streaming"],
    "AI API feature": ["ai", "llm", "openai", "gpt", "gemini", "claude", "nlp", "chatbot", "vision"],
    "Custom ML pipeline": ["custom ml", "training pipeline", "model training", "deep learning", "recommendation engine"],
    "Multi-tenancy": ["multitenant", "multi-tenant", "tenancy", "organizations", "workspaces"],
    "Security/compliance": ["security", "compliance", "gdpr", "hipaa", "audit log", "encryption", "pentest"],
    "Data migration": ["migration", "etl", "legacy data", "import", "export"],
    "SEO/content setup": ["seo", "meta tags", "sitemap", "content setup", "cms"],
    "Deployment/CI-CD": ["deployment", "ci/cd", "pipeline", "docker", "kubernetes", "infra"],
    "Performance/load optimization": ["performance", "optimization", "caching", "redis", "load testing"],
    "Mobile-specific workflow": ["mobile", "offline sync", "push notifications", "camera", "gps"],
    "Subscription/billing": ["subscription", "tier", "plans", "recurring", "credits"],
    "Maps/geolocation": ["maps", "location", "geo", "geocoding", "tracking"],
    "Audit logs": ["audit", "activity log", "history", "changelog"],
}


class FeatureEffortEngine:
    """
    Authoritative Feature-Level Effort Estimator using:
    1. Historical Empirical Bayes Shrinkage from Feature_Level_Data
    2. Catalog Priors from Feature_Effort_Priors
    3. Rule-Based Fallback
    4. Clearly Labeled Generic Fallback
    """

    def __init__(self, catalog_path: Optional[str] = None):
        self.catalog_path = Path(catalog_path or f"{settings.ARTIFACTS_DIR}/feature_catalog_stats.json")
        self.priors: Dict[str, Dict[str, Any]] = {}
        self.historical_stats: Dict[str, Dict[str, Any]] = {}
        self._load_catalog()

    def _load_catalog(self) -> None:
        if self.catalog_path.exists():
            try:
                with open(self.catalog_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.priors = data.get("priors", {})
                    self.historical_stats = data.get("historical_stats", {})
                    logger.info(f"Loaded {len(self.priors)} priors and {len(self.historical_stats)} historical stats.")
            except Exception as e:
                logger.error(f"Failed to load feature catalog from {self.catalog_path}: {e}")

    def normalize_feature_category(self, name: str, category: Optional[str] = None) -> Tuple[str, bool]:
        """
        Normalizes category using known names or synonym keyword matching.
        Returns (normalized_name, is_matched_exact_or_synonym).
        """
        text = f"{category or ''} {name}".lower()

        # Direct match in catalog priors
        for prior_name in self.priors.keys():
            if prior_name.lower() in text or text in prior_name.lower():
                return prior_name, True

        # Check synonym patterns
        for prior_name, keywords in SYNONYM_MAPPINGS.items():
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", text):
                    return prior_name, True

        # Generic fallback
        return category or name or "Custom Feature", False

    def estimate_feature(
        self,
        name: str,
        category: Optional[str] = None,
        complexity: str = "Medium",
        reuse_level_pct: float = 0.0,
        integration_count: int = 0,
        notes: str = "",
    ) -> Dict[str, Any]:
        """
        Calculates PERT Three-Point estimate (O, M, P) for a single feature.
        Ensures non-negativity and transparent provenance.
        """
        if complexity not in ("Low", "Medium", "High", "Very High"):
            complexity = "Medium"

        reuse_pct = max(0.0, min(90.0, float(reuse_level_pct)))  # Cap reuse at 90%
        integrations = max(0, int(integration_count))

        matched_name, is_matched = self.normalize_feature_category(name, category)
        key = f"{matched_name}::{complexity}"

        most_likely_raw: float = 0.0
        method: str = "generic_fallback"
        matched_records: int = 0
        assumptions: List[str] = []
        needs_review: bool = False

        if is_matched and key in self.historical_stats:
            stat = self.historical_stats[key]
            hist_median = stat["median_hours"]
            matched_records = stat["count"]
            prior_val = self.priors.get(matched_name, {}).get(complexity, hist_median)

            # Empirical Bayes Shrinkage toward catalog prior
            # alpha = n / (n + 15)
            alpha = matched_records / (matched_records + 15.0)
            most_likely_raw = (alpha * hist_median) + ((1.0 - alpha) * prior_val)
            method = "historical_shrinkage"
            assumptions.append(
                f"Matched {matched_records} simulated records in '{matched_name}' ({complexity}). "
                f"Shrunk historical median ({hist_median:.1f}h) toward catalog prior ({prior_val:.1f}h) with weight {alpha:.2f}."
            )
        elif is_matched and matched_name in self.priors:
            prior_val = self.priors[matched_name].get(complexity, 16.0)
            most_likely_raw = float(prior_val)
            method = "catalog_prior"
            assumptions.append(f"Used planning prior baseline for '{matched_name}' at {complexity} complexity ({prior_val}h).")
        elif is_matched:
            most_likely_raw = GENERIC_BASE_HOURS.get(complexity, 16.0)
            method = "rule_based_fallback"
            assumptions.append(f"Derived base effort via rule-based category heuristic for '{matched_name}'.")
        else:
            most_likely_raw = GENERIC_BASE_HOURS.get(complexity, 16.0)
            method = "generic_fallback"
            needs_review = True
            assumptions.append(
                f"Unmatched feature '{name}'. Applied generic default planning base ({most_likely_raw}h). User review recommended."
            )

        # Apply reuse adjustment (capped at 50% effort reduction to preserve core wiring/testing)
        reuse_discount = (reuse_pct / 100.0) * 0.50
        effort_after_reuse = most_likely_raw * (1.0 - reuse_discount)
        if reuse_pct > 0:
            assumptions.append(f"Applied {reuse_pct}% component reuse (effort discount factor: {1.0 - reuse_discount:.2f}x).")

        # Apply feature integration overhead (+10% per external dependency)
        integration_multiplier = 1.0 + (0.10 * integrations)
        if integrations > 0:
            effort_after_reuse *= integration_multiplier
            assumptions.append(f"Added {integrations} external integrations (+{int(integrations * 10)}% integration overhead).")

        most_likely = max(1.0, round(effort_after_reuse, 1))

        # PERT 3-point:
        # Optimistic: ~75% of Most Likely
        # Pessimistic: ~150% of Most Likely
        optimistic = max(0.5, round(most_likely * 0.75, 1))
        pessimistic = max(optimistic + 1.0, round(most_likely * 1.50, 1))
        expected = max(0.5, round((optimistic + 4.0 * most_likely + pessimistic) / 6.0, 1))
        std_dev = max(0.1, round((pessimistic - optimistic) / 6.0, 2))

        return {
            "feature_name": name,
            "normalized_category": matched_name,
            "complexity": complexity,
            "reuse_level_pct": reuse_pct,
            "integration_count": integrations,
            "optimistic_effort_hours": optimistic,
            "most_likely_effort_hours": most_likely,
            "pessimistic_effort_hours": pessimistic,
            "expected_effort_hours": expected,
            "standard_deviation_hours": std_dev,
            "estimation_method": method,
            "matched_record_count": matched_records,
            "relevant_assumptions": assumptions,
            "needs_user_review": needs_review,
        }

    def estimate_features_list(self, features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            self.estimate_feature(
                name=f.get("name", f.get("feature_name", "Untitled Feature")),
                category=f.get("category", f.get("feature_category")),
                complexity=f.get("complexity", f.get("feature_complexity", "Medium")),
                reuse_level_pct=f.get("reuse_level_pct", 0.0),
                integration_count=f.get("integration_count", f.get("feature_integration_count", 0)),
                notes=f.get("notes", ""),
            )
            for f in features
        ]


feature_effort_engine = FeatureEffortEngine()
