import math
import logging
from typing import Dict, Any, List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class RoleRecommender:
    """
    Analyzes Step 3 Approved Features, complexity, and technical requirements
    to generate project-specific team roles, headcounts, allocations, and justifications.
    """

    def recommend(
        self,
        features: List[Dict[str, Any]],
        project_type: str = "SaaS Platform",
        overall_complexity: str = "Medium",
        target_platforms: Optional[List[str]] = None,
        rate_profile: str = "Professional",
        currency: str = "INR",
    ) -> Dict[str, Any]:
        platforms = target_platforms or ["Web Application"]
        p_text = f"{project_type} " + " ".join([f.get("name", "") + " " + f.get("category", "") for f in features]).lower()
        platforms_lower = " ".join(platforms).lower()
        feature_count = max(1, len(features))

        # Check rates
        rates_map = settings.RATE_PROFILES.get(rate_profile, settings.RATE_PROFILES["Professional"])
        cur_info = settings.SUPPORTED_CURRENCIES.get(currency.upper(), settings.SUPPORTED_CURRENCIES["INR"])
        rate_conv = float(cur_info.get("rate_to_inr", 1.0))
        cur_symbol = cur_info.get("symbol", "₹")

        # Determine feature categories present
        has_ui = any("ui" in f.get("category", "").lower() or "page" in f.get("category", "").lower() or "dashboard" in f.get("category", "").lower() or "cart" in f.get("name", "").lower() for f in features) or True
        has_mobile = "mobile" in platforms_lower or "android" in platforms_lower or "ios" in platforms_lower or "cross-platform" in platforms_lower
        has_ai = any(w in p_text for w in ["ai", "ml", "machine learning", "nlp", "llm", "predict", "model", "extract"])
        has_high_security = any("security" in f.get("category", "").lower() or "kyc" in f.get("name", "").lower() or "mfa" in f.get("name", "").lower() for f in features) or "fintech" in p_text or overall_complexity in ("High", "Very High")
        has_cloud = feature_count >= 4 or overall_complexity in ("High", "Very High")

        # Headcount determination based on scope scale
        dev_scale = 1 if feature_count <= 4 else 2 if feature_count <= 8 else 3

        roles = []

        # 1. UI/UX Designer
        ui_count = 1 if has_ui else 0
        roles.append({
            "role": "UI/UX Designer",
            "headcount": ui_count,
            "allocation_pct": 12.0,
            "responsibilities": "Design system, responsive component wireframes, user journeys, and interactive prototypes.",
            "hourly_rate_inr": rates_map.get("UI/UX Designer", 1100.0),
            "hourly_rate_converted": round(rates_map.get("UI/UX Designer", 1100.0) / rate_conv, 2),
            "reason": "Crucial for user-facing workflows, navigation ergonomics, and client onboarding journeys.",
            "is_required": True,
        })

        # 2. Frontend Developer
        fe_count = 2 if dev_scale >= 2 else 1
        roles.append({
            "role": "Frontend Developer",
            "headcount": fe_count,
            "allocation_pct": 28.0,
            "responsibilities": "Client-side SPA/SSR pages, state stores, form validation, and responsive CSS theme styling.",
            "hourly_rate_inr": rates_map.get("Frontend Developer", 1200.0),
            "hourly_rate_converted": round(rates_map.get("Frontend Developer", 1200.0) / rate_conv, 2),
            "reason": f"Required to build the {feature_count} features across client views.",
            "is_required": True,
        })

        # 3. Backend Developer
        be_count = 2 if dev_scale >= 2 else 1
        roles.append({
            "role": "Backend Developer",
            "headcount": be_count,
            "allocation_pct": 32.0,
            "responsibilities": "REST APIs, database schemas, transactional integrity, authentication tokens, and integrations.",
            "hourly_rate_inr": rates_map.get("Backend Developer", 1400.0),
            "hourly_rate_converted": round(rates_map.get("Backend Developer", 1400.0) / rate_conv, 2),
            "reason": "Implements core business logic, database migrations, and third-party webhooks.",
            "is_required": True,
        })

        # 4. Mobile Developer (if mobile targets selected)
        if has_mobile:
            mob_count = 1 if dev_scale <= 2 else 2
            roles.append({
                "role": "Mobile Developer",
                "headcount": mob_count,
                "allocation_pct": 20.0,
                "responsibilities": "Cross-platform Flutter / React Native client, offline storage, push notifications, native bridging.",
                "hourly_rate_inr": rates_map.get("Frontend Developer", 1200.0) * 1.1,
                "hourly_rate_converted": round((rates_map.get("Frontend Developer", 1200.0) * 1.1) / rate_conv, 2),
                "reason": "Dedicated mobile engineering required for iOS and Android deployment targets.",
                "is_required": True,
            })

        # 5. QA / Test Engineer
        qa_count = 1 if feature_count >= 3 else 0
        roles.append({
            "role": "QA/Test Engineer",
            "headcount": qa_count,
            "allocation_pct": 14.0,
            "responsibilities": "Test case design, automated regression scripts, API validation, and load testing.",
            "hourly_rate_inr": rates_map.get("QA/Test Engineer", 900.0),
            "hourly_rate_converted": round(rates_map.get("QA/Test Engineer", 900.0) / rate_conv, 2),
            "reason": "Guarantees feature regression prevention and defect containment before production.",
            "is_required": True,
        })

        # 6. DevOps / Cloud Engineer
        devops_count = 1 if has_cloud else 0
        roles.append({
            "role": "DevOps/Cloud Engineer",
            "headcount": devops_count,
            "allocation_pct": 8.0,
            "responsibilities": "Infrastructure as Code (Terraform), CI/CD pipelines, container orchestration, and monitoring.",
            "hourly_rate_inr": rates_map.get("DevOps/Cloud Engineer", 1500.0),
            "hourly_rate_converted": round(rates_map.get("DevOps/Cloud Engineer", 1500.0) / rate_conv, 2),
            "reason": "Required for automated deployment pipelines and production cloud infrastructure reliability.",
            "is_required": has_cloud,
        })

        # 7. AI/ML Engineer (if AI/ML features detected)
        if has_ai:
            roles.append({
                "role": "Data/ML Engineer",
                "headcount": 1,
                "allocation_pct": 16.0,
                "responsibilities": "ML model pipelines, feature engineering, vector indexing, and inference API optimization.",
                "hourly_rate_inr": rates_map.get("Data/ML Engineer", 1800.0),
                "hourly_rate_converted": round(rates_map.get("Data/ML Engineer", 1800.0) / rate_conv, 2),
                "reason": "Specialized engineering required for machine learning algorithms and inference integration.",
                "is_required": True,
            })

        # 8. Project Manager
        pm_count = 1
        roles.append({
            "role": "Project Manager",
            "headcount": pm_count,
            "allocation_pct": 6.0,
            "responsibilities": "Sprint ceremonies, backlog grooming, critical-path dependency tracking, and stakeholder reporting.",
            "hourly_rate_inr": rates_map.get("Project Manager", 1500.0),
            "hourly_rate_converted": round(rates_map.get("Project Manager", 1500.0) / rate_conv, 2),
            "reason": "Ensures delivery alignment, milestones pacing, and cross-role coordination.",
            "is_required": True,
        })

        # Calculate total team size strictly as the sum of headcounts across active role rows
        total_team_size = sum(r["headcount"] for r in roles)
        for r in roles:
            r["role_name"] = r["role"]
            r["name"] = r["role"]
            r["recommended_headcount"] = r["headcount"]
            r["hourly_rate"] = r["hourly_rate_converted"] if currency.upper() != "INR" else r["hourly_rate_inr"]

        return {
            "roles": roles,
            "recommended_roles": roles,
            "total_team_size": total_team_size,
            "currency": currency.upper(),
            "currency_symbol": cur_symbol,
            "rate_profile": rate_profile,
            "feature_count_analyzed": feature_count,
            "rationale": f"Team of {total_team_size} specialists recommended to deliver {feature_count} features across {len(platforms)} platform(s).",
        }


role_recommender = RoleRecommender()
