import logging
from typing import Dict, Any, List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class TechStackRecommender:
    """
    Analyzes Step 1 Project Information (Domain, Platforms, Complexity, Scale, Region, Scope)
    and generates defensible, project-specific technical stack recommendations for Step 2.
    """

    def recommend(
        self,
        project_name: str = "",
        project_type: str = "SaaS Platform",
        description: str = "",
        overall_complexity: str = "Medium",
        target_platforms: Optional[List[str]] = None,
        user_scale: str = "1k-10k",
        client_region: str = "India",
    ) -> Dict[str, Any]:
        platforms = target_platforms or ["Web Application"]
        p_text = f"{project_name} {project_type} {description}".lower()
        platforms_lower = " ".join(platforms).lower()

        # 1. Frontend Recommendation
        if "mobile" in platforms_lower or "cross-platform" in platforms_lower or "android" in platforms_lower or "ios" in platforms_lower:
            if "web" in platforms_lower:
                frontend = ["React", "Flutter"]
                fe_reason = "Flutter for cross-platform iOS/Android mobile clients paired with React for the web client."
            else:
                frontend = ["Flutter"]
                fe_reason = "Flutter for native 60fps performance across iOS and Android from a single codebase."
        elif "e-commerce" in p_text or "marketplace" in p_text or "portfolio" in p_text or "website" in p_text:
            frontend = ["Next.js"]
            fe_reason = "Next.js for server-side rendering (SSR), high Lighthouse scores, and search-engine indexation (SEO)."
        else:
            frontend = ["React"]
            fe_reason = "React component ecosystem with modern state management, well suited for reactive SaaS dashboards."

        # 2. Backend Recommendation
        if any(w in p_text for w in ["ai", "ml", "machine learning", "data", "analytics", "nlp", "llm"]):
            backend = ["FastAPI_Python"]
            be_reason = "FastAPI / Python for native asynchronous ASGI execution and seamless integration with ML libraries."
        elif "high" in overall_complexity.lower() or "1m+" in user_scale or "100k-1m" in user_scale:
            if "fintech" in p_text or "banking" in p_text:
                backend = ["Spring_Boot"]
                be_reason = "Java Spring Boot for enterprise-grade type safety, strict ACID transactions, and bank-grade thread isolation."
            else:
                backend = ["Go"]
                be_reason = "Go (Golang) for sub-millisecond coroutine concurrency and high-throughput microservices."
        elif "food delivery" in p_text or "ride booking" in p_text or "real-time" in p_text or "live" in p_text:
            backend = ["Node.js_Express"]
            be_reason = "Node.js / Express with event-driven non-blocking I/O, ideal for WebSockets and rapid dispatch."
        else:
            backend = ["Node.js_Express"]
            be_reason = "Node.js / Express for rapid development and extensive npm package ecosystem."

        # 3. Database Architecture
        if "food delivery" in p_text or "ride booking" in p_text or "100k-1m" in user_scale or "1m+" in user_scale:
            database = ["PostgreSQL + Redis"]
            db_reason = "PostgreSQL for ACID transactional persistence combined with Redis for low-latency session and geospatial caching."
        elif "analytics" in p_text or "catalog" in p_text or "iot" in p_text:
            database = ["MongoDB"]
            db_reason = "MongoDB document store for dynamic schema flexibility and high ingestion throughput."
        else:
            database = ["PostgreSQL"]
            db_reason = "PostgreSQL relational database for strong relational integrity, JSONB support, and indexing."

        # 4. Cloud / Hosting
        if "1m+" in user_scale or overall_complexity in ("High", "Very High") or "fintech" in p_text:
            cloud = ["AWS"]
            cloud_reason = "AWS for enterprise compliance certifications (SOC2, PCI-DSS, ISO27001) and multi-AZ failover."
        elif "next.js" in [f.lower() for f in frontend] and user_scale == "1k-10k":
            cloud = ["Vercel_Supabase"]
            cloud_reason = "Vercel edge hosting + Supabase managed database for ultra-low latency serverless deployment."
        elif any(w in p_text for w in ["ai", "data", "analytics", "bigquery"]):
            cloud = ["GCP"]
            cloud_reason = "Google Cloud Platform (GCP) for native Vertex AI and BigQuery data processing."
        else:
            cloud = ["AWS"]
            cloud_reason = "AWS for reliable general-purpose cloud services (ECS Fargate, RDS, CloudFront)."

        # 5. Payment Integration
        if any(w in p_text for w in ["food", "ecommerce", "e-commerce", "marketplace", "travel", "ticket"]):
            payment = "Stripe"
            pay_reason = "Stripe / Razorpay for secure multi-currency card, UPI, and webhook processing."
        elif "fintech" in p_text or "banking" in p_text or "global" in p_text:
            payment = "Multiple"
            pay_reason = "Multi-gateway fallback (Stripe + Razorpay + Wire) for payment redundancy and international settlement."
        elif "saas" in p_text or "subscription" in p_text:
            payment = "Stripe"
            pay_reason = "Stripe Billing for automated recurring recurring subscription tiers and pro-rated invoicing."
        else:
            payment = "None"
            pay_reason = "No payment gateway required for internal tools, portals, or standard information apps."

        # 6. Authentication Requirements
        if "fintech" in p_text or "banking" in p_text or overall_complexity == "Very High":
            auth = ["Enterprise_SSO"]
            auth_reason = "Enterprise SAML / Okta SSO with mandatory multi-factor authentication (MFA) and hardware key support."
        elif "saas" in p_text or "b2b" in p_text:
            auth = ["OAuth_SSO"]
            auth_reason = "Google and GitHub OAuth 2.0 social sign-in combined with JWT session tokens."
        else:
            auth = ["JWT_Sessions"]
            auth_reason = "Tamper-proof HMAC signed JWT tokens with PBKDF2 password hashing and secure HTTP-only cookies."

        # 7. Security & Compliance
        if "fintech" in p_text or "banking" in p_text or "healthcare" in p_text or "telemedicine" in p_text:
            security = "Critical"
            sec_reason = "Regulated industry standard (HIPAA, PCI-DSS Level 1, audit logging, TLS 1.3 in-transit and at-rest encryption)."
        elif overall_complexity in ("High", "Very High") or "saas" in p_text:
            security = "High"
            sec_reason = "High security: Role-Based Access Control (RBAC), rate-limiting, CORS, and automated OWASP vulnerability scans."
        else:
            security = "Standard"
            sec_reason = "Standard baseline: HTTPS encryption, OWASP top 10 sanitization, and parameterized queries."

        # 8. Real-Time Functionality
        if any(w in p_text for w in ["live", "gps", "tracking", "chat", "messaging", "driver", "ride", "food"]):
            realtime = "WebSockets"
            rt_reason = "Bi-directional WebSockets for live driver location updates, real-time dispatch, and chat notifications."
        elif any(w in p_text for w in ["notification", "feed", "alert", "dashboard"]):
            realtime = "SSE"
            rt_reason = "Server-Sent Events (SSE) for unidirectional real-time metrics and operational push alerts."
        else:
            realtime = "None"
            rt_reason = "Standard stateless HTTP REST / GraphQL requests are sufficient."

        # 9. Quality & Testing Level
        if security == "Critical" or overall_complexity == "Very High":
            testing = "MissionCritical"
            test_reason = "Mission Critical: 90%+ automated unit test coverage, load testing, and independent third-party penetration testing."
        elif overall_complexity == "High":
            testing = "High"
            test_reason = "Comprehensive QA: Cypress/Playwright End-to-End browser tests and CI/CD automated test gates."
        else:
            testing = "Standard"
            test_reason = "Standard QA: Pytest / Jest unit testing combined with manual user-acceptance testing (UAT)."

        # 10. External Integrations
        integrations = []
        if payment != "None":
            integrations.append("Stripe / Razorpay Gateway")
        if any(w in p_text for w in ["food", "ride", "delivery", "map", "location", "gps"]):
            integrations.append("Google Maps & Geocoding API")
        if any(w in p_text for w in ["sms", "otp", "phone"]):
            integrations.append("Twilio (SMS & Phone OTP)")
        if any(w in p_text for w in ["email", "notify", "newsletter", "invite"]):
            integrations.append("SendGrid / Resend (Transactional Email)")
        if any(w in p_text for w in ["ai", "llm", "chat", "gpt", "extract"]):
            integrations.append("OpenAI API / Anthropic (LLM Inference)")
        integrations.append("AWS S3 / Cloudflare R2 (Object Storage)")

        return {
            "project_name": project_name,
            "project_type": project_type,
            "overall_complexity": overall_complexity,
            "recommended_specifications": {
                "frontend_stack": frontend,
                "backend_stack": backend,
                "database": database,
                "hosting_platform": cloud,
                "payment_integration": payment,
                "auth_requirements": auth,
                "security_compliance": security,
                "realtime_features": realtime,
                "quality_testing": testing,
                "external_integrations": integrations,
            },
            "rationales": {
                "frontend": fe_reason,
                "backend": be_reason,
                "database": db_reason,
                "cloud": cloud_reason,
                "payment": pay_reason,
                "auth": auth_reason,
                "security": sec_reason,
                "realtime": rt_reason,
                "testing": test_reason,
            },
            "is_ai_generated": False,
            "provider_used": "Domain Architecture Engine (Rule-based offline)",
        }


tech_stack_recommender = TechStackRecommender()
