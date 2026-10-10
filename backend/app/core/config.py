import os
from pathlib import Path
from typing import Dict, Any
from pydantic_settings import BaseSettings

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
REPORTS_DIR = BASE_DIR / "reports"

DATA_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    PROJECT_NAME: str = "CostPilot AI"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment & Secrets
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "costpilot-super-secret-dev-key-2026")
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "offline")  # offline | gemini | openai
    AI_API_KEY: str = os.getenv("AI_API_KEY", "")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/app/db/costpilot.db")
    
    # Data & Artifacts
    DATASET_PATH: str = str(DATA_DIR / "CostPilot_AI_Training_Dataset.xlsx")
    ARTIFACTS_DIR: str = str(ARTIFACTS_DIR)
    REPORTS_DIR: str = str(REPORTS_DIR)
    
    # Financial & Currency Defaults
    DEFAULT_CURRENCY: str = "INR"
    DEFAULT_CONTINGENCY_PCT: float = 0.15  # 15%
    
    # Work & Capacity Defaults
    WORKING_HOURS_PER_DAY: float = 8.0
    PRODUCTIVE_HOURS_PER_DAY: float = 6.0
    WORKING_DAYS_PER_WEEK: int = 5
    DEFAULT_AVAILABILITY_FACTOR: float = 0.85
    MAX_TEAM_SIZE: int = 30
    MIN_TEAM_SIZE: int = 1
    
    # Complexity 9-Factor Weights (sum = 1.00)
    COMPLEXITY_FACTOR_WEIGHTS: Dict[str, float] = {
        "technical_difficulty": 0.20,
        "database_complexity": 0.10,
        "integration_complexity": 0.15,
        "security": 0.15,
        "ui_ux_complexity": 0.10,
        "realtime_requirements": 0.10,
        "aiml_requirements": 0.10,
        "platform_complexity": 0.05,
        "dependencies": 0.05,
    }
    
    # Complexity Thresholds
    COMPLEXITY_THRESHOLDS: Dict[str, tuple] = {
        "Low": (0.0, 24.99),
        "Medium": (25.0, 49.99),
        "High": (50.0, 74.99),
        "Very High": (75.0, 100.0),
    }
    
    # Risk Factor Weights (sum = 1.00)
    RISK_FACTOR_WEIGHTS: Dict[str, float] = {
        "project_complexity": 0.20,
        "deadline_pressure": 0.20,
        "dependency_complexity": 0.15,
        "external_integrations": 0.15,
        "security_requirements": 0.10,
        "platform_count": 0.05,
        "team_pressure": 0.10,
        "unknown_requirements": 0.05,
    }
    
    # Hourly Rate Profiles in INR
    RATE_PROFILES: Dict[str, Dict[str, float]] = {
        "Startup": {
            "Frontend Developer": 800.0,
            "Backend Developer": 900.0,
            "Full-Stack Developer": 850.0,
            "UI/UX Designer": 700.0,
            "QA/Test Engineer": 600.0,
            "DevOps/Cloud Engineer": 1000.0,
            "Data/ML Engineer": 1200.0,
            "Project Manager": 950.0,
            "Security Specialist": 1300.0,
        },
        "Professional": {
            "Frontend Developer": 1200.0,
            "Backend Developer": 1400.0,
            "Full-Stack Developer": 1300.0,
            "UI/UX Designer": 1100.0,
            "QA/Test Engineer": 900.0,
            "DevOps/Cloud Engineer": 1500.0,
            "Data/ML Engineer": 1800.0,
            "Project Manager": 1500.0,
            "Security Specialist": 2000.0,
        },
        "Enterprise": {
            "Frontend Developer": 1800.0,
            "Backend Developer": 2100.0,
            "Full-Stack Developer": 2000.0,
            "UI/UX Designer": 1600.0,
            "QA/Test Engineer": 1400.0,
            "DevOps/Cloud Engineer": 2200.0,
            "Data/ML Engineer": 2600.0,
            "Project Manager": 2300.0,
            "Security Specialist": 2800.0,
        },
    }
    
    # Role Allocation Profiles by Project Type (Percentages sum to 100%)
    ROLE_PROFILES_BY_PROJECT_TYPE: Dict[str, Dict[str, float]] = {
        "AI-enabled Platform": {
            "Frontend Developer": 0.18,
            "Backend Developer": 0.24,
            "UI/UX Designer": 0.10,
            "QA/Test Engineer": 0.15,
            "DevOps/Cloud Engineer": 0.11,
            "Project Manager": 0.07,
            "Data/ML Engineer": 0.15,
        },
        "Fintech Application": {
            "Frontend Developer": 0.20,
            "Backend Developer": 0.30,
            "UI/UX Designer": 0.10,
            "QA/Test Engineer": 0.20,
            "DevOps/Cloud Engineer": 0.10,
            "Project Manager": 0.10,
            "Data/ML Engineer": 0.00,
        },
        "Mobile App + Backend": {
            "Frontend Developer": 0.35,  # Mobile client
            "Backend Developer": 0.25,
            "UI/UX Designer": 0.15,
            "QA/Test Engineer": 0.13,
            "DevOps/Cloud Engineer": 0.05,
            "Project Manager": 0.07,
            "Data/ML Engineer": 0.00,
        },
        "Portfolio Website": {
            "Frontend Developer": 0.50,
            "Backend Developer": 0.10,
            "UI/UX Designer": 0.25,
            "QA/Test Engineer": 0.10,
            "DevOps/Cloud Engineer": 0.00,
            "Project Manager": 0.05,
            "Data/ML Engineer": 0.00,
        },
        "E-commerce": {
            "Frontend Developer": 0.25,
            "Backend Developer": 0.30,
            "UI/UX Designer": 0.15,
            "QA/Test Engineer": 0.15,
            "DevOps/Cloud Engineer": 0.08,
            "Project Manager": 0.07,
            "Data/ML Engineer": 0.00,
        },
        "Default": {
            "Frontend Developer": 0.25,
            "Backend Developer": 0.30,
            "UI/UX Designer": 0.12,
            "QA/Test Engineer": 0.15,
            "DevOps/Cloud Engineer": 0.08,
            "Project Manager": 0.10,
            "Data/ML Engineer": 0.00,
        },
    }

    # Platform Multiplier (applies ONLY to client/frontend effort)
    PLATFORM_MULTIPLIERS: Dict[str, float] = {
        "Web Application": 1.0,
        "Responsive Website": 0.95,
        "Progressive Web App (PWA)": 1.10,
        "Android Application": 1.05,
        "iOS Application": 1.05,
        "Cross-Platform Mobile Application": 1.25,
        "Desktop Application": 1.30,
        "Web + Mobile": 1.35,
        "Web + Mobile + Desktop": 1.65,
        "API / Backend Service": 0.80,
        "SaaS / Cloud Platform": 1.05,
        "AI/ML Platform": 1.25,
        "Data Engineering Platform": 1.15,
        "IoT / Embedded Software": 1.40,
        "Browser Extension": 0.85,
        "Chatbot / Conversational Application": 0.90,
        "Custom Platform": 1.00,
        # Backward compatibility aliases
        "Web": 1.0,
        "Mobile (iOS or Android)": 1.0,
        "Web + Mobile (Cross-platform)": 1.35,
        "Web + Native iOS + Native Android": 1.85,
        "Desktop + Web": 1.40,
    }

    DOMAIN_ARCHETYPE_MAPPING: Dict[str, str] = {
        "Business Website": "Portfolio Website",
        "Portfolio Website": "Portfolio Website",
        "E-commerce": "E-commerce",
        "Online Marketplace": "E-commerce",
        "SaaS Platform": "SaaS Web Application",
        "SaaS Web Application": "SaaS Web Application",
        "Food Delivery": "Booking Platform",
        "Grocery Delivery": "Booking Platform",
        "Ride Booking": "Booking Platform",
        "Travel Booking": "Booking Platform",
        "Booking Platform": "Booking Platform",
        "Education / E-learning": "SaaS Web Application",
        "Learning Management System": "SaaS Web Application",
        "Healthcare": "Healthcare Portal",
        "Telemedicine": "Healthcare Portal",
        "Healthcare Portal": "Healthcare Portal",
        "FinTech": "Fintech Application",
        "Banking": "Fintech Application",
        "Insurance": "Fintech Application",
        "Fintech Application": "Fintech Application",
        "Real Estate": "Booking Platform",
        "Logistics": "Internal Admin Tool",
        "Inventory Management": "Internal Admin Tool",
        "CRM": "CRM",
        "ERP": "Internal Admin Tool",
        "HR Management": "Internal Admin Tool",
        "Internal Admin Tool": "Internal Admin Tool",
        "Project Management Software": "SaaS Web Application",
        "Social Networking": "AI-enabled Platform",
        "Messaging Platform": "AI-enabled Platform",
        "Media Streaming": "AI-enabled Platform",
        "IoT Platform": "AI-enabled Platform",
        "AI/ML Application": "AI-enabled Platform",
        "Generative AI Application": "AI-enabled Platform",
        "AI-enabled Platform": "AI-enabled Platform",
        "Data Analytics Platform": "SaaS Web Application",
        "Cybersecurity Software": "Internal Admin Tool",
        "Government/Public Service": "Internal Admin Tool",
        "Enterprise Application": "Internal Admin Tool",
        "Mobile App + Backend": "Mobile App + Backend",
        "Custom / Other": "SaaS Web Application",
    }

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
