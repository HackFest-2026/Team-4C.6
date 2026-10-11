import logging
from typing import Dict, Any, List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class InfraRecommender:
    """
    Analyzes Steps 1, 2, and 3 (Domain, Platform, Complexity, Scale, Tech Stack, Features, Integrations)
    and produces an itemized, defensible Infrastructure and Tooling recommendation catalog for Step 5.
    """

    def recommend(
        self,
        project_name: str = "",
        project_type: str = "SaaS Platform",
        overall_complexity: str = "Medium",
        target_platforms: Optional[List[str]] = None,
        frontend_stack: Optional[List[str]] = None,
        backend_stack: Optional[List[str]] = None,
        database: Optional[List[str]] = None,
        hosting_cloud: Optional[List[str]] = None,
        user_scale: str = "1k-10k",
        features_count: int = 4,
        integrations_count: int = 1,
        currency: str = "INR",
    ) -> Dict[str, Any]:
        cur_code = (currency or "INR").upper()
        cur_info = settings.SUPPORTED_CURRENCIES.get(cur_code, settings.SUPPORTED_CURRENCIES["INR"])
        rate_conv = float(cur_info.get("rate_to_inr", 1.0))
        cur_symbol = cur_info.get("symbol", "₹")

        clouds = hosting_cloud or ["AWS"]
        primary_cloud = clouds[0] if clouds else "AWS"
        dbs = database or ["PostgreSQL"]
        db_primary = dbs[0] if dbs else "PostgreSQL"
        p_text = f"{project_name} {project_type}".lower()

        is_high_scale = user_scale in ("100k-1M", "1M+")
        is_critical = overall_complexity in ("High", "Very High")

        items = []

        # 1. Compute & Application Hosting
        if primary_cloud == "Vercel_Supabase":
            items.append({
                "name": "Vercel Pro Team Hosting",
                "category": "Compute / Hosting",
                "purpose": "Serverless edge functions and static asset hosting with global anycast routing.",
                "is_required": True,
                "billing_period": "monthly",
                "cost_inr": 2500.0,
                "pricing_source": "Vercel Pro $20/seat pricing",
            })
        elif primary_cloud == "GCP":
            items.append({
                "name": "Google Cloud Run & Artifact Registry",
                "category": "Compute / Hosting",
                "purpose": "Autoscaling container runtime with zero idle cost and high concurrency.",
                "is_required": True,
                "billing_period": "monthly",
                "cost_inr": 4500.0 if not is_high_scale else 18000.0,
                "pricing_source": "GCP Cloud Run standard tier",
            })
        else:
            compute_name = "AWS ECS Fargate Container Cluster" if not is_high_scale else "AWS EKS Kubernetes Multi-AZ Cluster"
            compute_cost = 6500.0 if not is_high_scale else 28000.0
            items.append({
                "name": compute_name,
                "category": "Compute / Hosting",
                "purpose": "Managed container execution for backend services with automatic horizontal scaling.",
                "is_required": True,
                "billing_period": "monthly",
                "cost_inr": compute_cost,
                "pricing_source": "AWS Fargate / EC2 Pricing Calculator",
            })

        # 2. Database Hosting
        if "Redis" in db_primary or is_high_scale:
            items.append({
                "name": f"AWS RDS {db_primary.split('+')[0].strip()} (Multi-AZ)",
                "category": "Database",
                "purpose": "Managed relational database with automated daily snapshots and standby replica failover.",
                "is_required": True,
                "billing_period": "monthly",
                "cost_inr": 8500.0 if not is_high_scale else 24000.0,
                "pricing_source": "AWS RDS db.t4g.medium Multi-AZ",
            })
            items.append({
                "name": "AWS ElastiCache Redis Cluster",
                "category": "Database",
                "purpose": "In-memory caching layer for sub-millisecond query responses and live session tokens.",
                "is_required": True,
                "billing_period": "monthly",
                "cost_inr": 4200.0,
                "pricing_source": "AWS ElastiCache cache.t4g.micro",
            })
        elif "MongoDB" in db_primary:
            items.append({
                "name": "MongoDB Atlas Managed M10 Cluster",
                "category": "Database",
                "purpose": "Fully managed document database with end-to-end encryption and automated scaling.",
                "is_required": True,
                "billing_period": "monthly",
                "cost_inr": 5800.0,
                "pricing_source": "MongoDB Atlas M10 Tier",
            })
        else:
            items.append({
                "name": "AWS RDS PostgreSQL (Single-AZ)",
                "category": "Database",
                "purpose": "Managed PostgreSQL relational database with automated backups and connection pooling.",
                "is_required": True,
                "billing_period": "monthly",
                "cost_inr": 4500.0,
                "pricing_source": "AWS RDS db.t4g.small",
            })

        # 3. Storage & CDN
        items.append({
            "name": "AWS S3 Bucket & CloudFront CDN",
            "category": "Storage & CDN",
            "purpose": "Object storage for media uploads and fast global asset caching with SSL termination.",
            "is_required": True,
            "billing_period": "monthly",
            "cost_inr": 2000.0 if not is_high_scale else 8500.0,
            "pricing_source": "AWS S3 Standard + CloudFront data egress",
        })

        # 4. CI/CD & Development Tooling
        items.append({
            "name": "GitHub Actions Team & Code Repository",
            "category": "CI/CD & Tooling",
            "purpose": "Automated build pipelines, linting, test runners, and continuous deployment workflows.",
            "is_required": True,
            "billing_period": "monthly",
            "cost_inr": 1800.0,
            "pricing_source": "GitHub Team $4/user tier",
        })

        # 5. Monitoring, Logging & Error Tracking
        items.append({
            "name": "Sentry Application Performance & Error Tracking",
            "category": "Monitoring & Logging",
            "purpose": "Real-time crash analytics, stack traces, and API performance bottleneck alerts.",
            "is_required": True,
            "billing_period": "monthly",
            "cost_inr": 2200.0,
            "pricing_source": "Sentry Team Developer Tier",
        })

        if is_critical or is_high_scale:
            items.append({
                "name": "AWS CloudWatch Logs & Audit Tracing",
                "category": "Monitoring & Logging",
                "purpose": "Compliance log retention, metric alarms, and audit trail aggregation.",
                "is_required": True,
                "billing_period": "monthly",
                "cost_inr": 3500.0,
                "pricing_source": "AWS CloudWatch ingestion & dashboards",
            })

        # 6. Domain, DNS & Security
        items.append({
            "name": "Cloudflare Pro & SSL Certificate",
            "category": "Security & Network",
            "purpose": "Enterprise DDoS mitigation, Web Application Firewall (WAF), and HTTP/3 acceleration.",
            "is_required": True,
            "billing_period": "monthly",
            "cost_inr": 2100.0,
            "pricing_source": "Cloudflare Pro $25/mo plan",
        })

        # 7. One-Time Setup Costs
        items.append({
            "name": "Production VPC, DNS & IAM Security Setup",
            "category": "One-Time Setup",
            "purpose": "Architecture provisioning, zero-trust IAM roles, VPC peering, and secrets management.",
            "is_required": True,
            "billing_period": "one_time",
            "cost_inr": 25000.0 if not is_critical else 45000.0,
            "pricing_source": "Standard engineering setup hours (15-25h)",
        })

        items.append({
            "name": "CI/CD Pipeline & Staging Environment Bootstrap",
            "category": "One-Time Setup",
            "purpose": "Deployment automation scripts, environment secrets configuration, and test harnesses.",
            "is_required": True,
            "billing_period": "one_time",
            "cost_inr": 15000.0 if not is_critical else 25000.0,
            "pricing_source": "Standard DevOps pipeline configuration",
        })

        # Normalize billing_period and calculate totals
        total_one_time_inr = sum(i["cost_inr"] for i in items if i["billing_period"] in ("one_time", "One-Time"))
        total_monthly_inr = sum(i["cost_inr"] for i in items if i["billing_period"] in ("monthly", "Monthly"))
        annual_recurring_inr = total_monthly_inr * 12.0

        # Enhance with converted costs and standard casing
        for item in items:
            raw_period = str(item.get("billing_period", "")).lower()
            norm_period = "One-Time" if "one" in raw_period else "Monthly"
            item["billing_period"] = norm_period
            item["period"] = norm_period
            item["cost_converted"] = round(item["cost_inr"] / rate_conv, 2)
            item["currency_code"] = cur_code
            item["currency_symbol"] = cur_symbol

        return {
            "items": items,
            "total_one_time_infra_inr": round(total_one_time_inr, 2),
            "total_one_time_infra_converted": round(total_one_time_inr / rate_conv, 2),
            "total_monthly_recurring_inr": round(total_monthly_inr, 2),
            "total_monthly_recurring_converted": round(total_monthly_inr / rate_conv, 2),
            "annual_recurring_inr": round(annual_recurring_inr, 2),
            "annual_recurring_converted": round(annual_recurring_inr / rate_conv, 2),
            "currency": cur_code,
            "currency_symbol": cur_symbol,
            "exchange_rate": rate_conv,
            "recommended_setup_budget_inr": round(total_one_time_inr, 2),
            "rationale": f"Infrastructure configured for {user_scale} scale on {primary_cloud} with {db_primary} persistence.",
        }


infra_recommender = InfraRecommender()
