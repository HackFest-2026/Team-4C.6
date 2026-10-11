import json
import logging
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)


class ExtractedFeature(BaseModel):
    id: Optional[str] = None
    name: str
    category: str
    complexity: str = "Medium"
    description: str = ""
    relevance_reason: str = ""
    priority: str = "Must-Have"  # Must-Have | Should-Have | Could-Have
    dependencies: List[str] = Field(default_factory=list)
    integration_requirements: List[str] = Field(default_factory=list)
    status: str = "recommended"  # recommended | accepted | rejected
    is_provisional: bool = False

    def __getitem__(self, item):
        return getattr(self, item)

    def __contains__(self, item):
        return hasattr(self, item)

    def get(self, item, default=None):
        return getattr(self, item, default)


class RequirementExtractionResult(BaseModel):
    project_name: str = ""
    project_type: str = "SaaS Web Application"
    overall_complexity: str = "Medium"
    features: List[ExtractedFeature]
    recommended_tech_stack: Dict[str, str] = Field(default_factory=dict)
    missing_requirements: List[str] = Field(default_factory=list)
    clarification_questions: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    profile_complete: bool = True
    is_provisional: bool = False
    completeness_score: float = 100.0
    is_ai_generated: bool = False
    provider_used: str = "rule_based_offline"
    model_provenance: str = "Profile Rules Engine (CostPilot Institutional Dataset)"

    def __getitem__(self, item):
        return getattr(self, item)

    def __contains__(self, item):
        return hasattr(self, item)

    def get(self, item, default=None):
        return getattr(self, item, default)


# =====================================================================
# DOMAIN PROFILE ARCHETYPES FOR TAILORED SPECIFICATIONS
# =====================================================================
DOMAIN_CATALOG = {
    "education": {
        "archetype": "Learning Management System",
        "features": [
            {
                "name": "Student & Faculty Authentication & RBAC",
                "category": "Authentication",
                "complexity": "Medium",
                "priority": "Must-Have",
                "description": "Role-based access control separating Student, Teacher, Parent, and Campus Administrator permissions.",
                "relevance_reason": "Academic institutions require strict separation of student records, grading privileges, and administrative governance.",
                "dependencies": [],
                "integrations": [],
            },
            {
                "name": "Course & Curriculum Management",
                "category": "CRUD/data module",
                "complexity": "Medium",
                "priority": "Must-Have",
                "description": "Create, publish, and manage courses, syllabus modules, lecture schedules, and prerequisite tracks.",
                "relevance_reason": "Core operational backbone for department curriculum and semester planning.",
                "dependencies": ["Student & Faculty Authentication & RBAC"],
                "integrations": [],
            },
            {
                "name": "Class Attendance & Daily Roll Call",
                "category": "CRUD/data module",
                "complexity": "Low",
                "priority": "Must-Have",
                "description": "Teacher digital attendance register with automated absentee percentage alerts and reports.",
                "relevance_reason": "Essential for tracking student semester minimum attendance thresholds.",
                "dependencies": ["Course & Curriculum Management"],
                "integrations": [],
            },
            {
                "name": "Assignments, Submissions & Plagiarism Check",
                "category": "File/media storage",
                "complexity": "High",
                "priority": "Should-Have",
                "description": "Assignment upload repository, deadline enforcement, rubric evaluations, and text matching.",
                "relevance_reason": "Enables digital coursework submission and academic integrity verification.",
                "dependencies": ["Course & Curriculum Management"],
                "integrations": ["Plagiarism Detection API"],
            },
            {
                "name": "Gradebook & Examination Results",
                "category": "Analytics/reporting",
                "complexity": "High",
                "priority": "Must-Have",
                "description": "GPA/CGPA computation, exam marks entry, report card generation, and transcript PDF export.",
                "relevance_reason": "Authoritative record keeping for term marks, grading curves, and official degree credentials.",
                "dependencies": ["Course & Curriculum Management"],
                "integrations": [],
            },
            {
                "name": "Tuition Fee Billing & Online Payments",
                "category": "Payment integration",
                "complexity": "High",
                "priority": "Must-Have",
                "description": "Semester tuition fee schedules, installment tracking, Razorpay/Stripe checkout, and fee receipts.",
                "relevance_reason": "Streamlines bursar collections and eliminates manual bank reconciliation.",
                "dependencies": ["Student & Faculty Authentication & RBAC"],
                "integrations": ["Payment Gateway API"],
            },
            {
                "name": "Campus Announcements & Parent SMS Alerts",
                "category": "Email/SMS notifications",
                "complexity": "Medium",
                "priority": "Should-Have",
                "description": "Urgent campus broadcast notices, exam date alerts, and fee due reminders.",
                "relevance_reason": "Critical communication channel between faculty, students, and guardians.",
                "dependencies": [],
                "integrations": ["SMS/Email Gateway API"],
            },
            {
                "name": "Institutional Analytics & Accreditation Dashboard",
                "category": "Admin dashboard",
                "complexity": "High",
                "priority": "Could-Have",
                "description": "Department pass percentages, faculty workload KPIs, and compliance audit reports for regulators.",
                "relevance_reason": "Required for dean oversight and regulatory accreditation submissions.",
                "dependencies": ["Gradebook & Examination Results"],
                "integrations": [],
            },
        ],
    },
    "healthcare": {
        "archetype": "Healthcare Portal",
        "features": [
            {
                "name": "Patient Registration & Secure Health Profile",
                "category": "Authentication",
                "complexity": "High",
                "priority": "Must-Have",
                "description": "HIPAA/ABDM compliant registration, demographic records, emergency contacts, and encrypted credentials.",
                "relevance_reason": "Fundamental medical identity requirement protecting sensitive patient records.",
                "dependencies": [],
                "integrations": [],
            },
            {
                "name": "Doctor Scheduling & Appointment Booking",
                "category": "Booking/scheduling",
                "complexity": "Medium",
                "priority": "Must-Have",
                "description": "Provider clinic availability calendars, slot reservation, rescheduling, and automated cancellation queues.",
                "relevance_reason": "Core patient journey workflow eliminating clinic overcrowding and booking conflicts.",
                "dependencies": ["Patient Registration & Secure Health Profile"],
                "integrations": [],
            },
            {
                "name": "Teleconsultation & Encrypted Video Calling",
                "category": "Real-time features",
                "complexity": "Very High",
                "priority": "Must-Have",
                "description": "Peer-to-peer WebRTC video consultations with in-call chat, screen sharing, and call session logs.",
                "relevance_reason": "Enables remote patient diagnosis and virtual clinical consultations.",
                "dependencies": ["Doctor Scheduling & Appointment Booking"],
                "integrations": ["WebRTC Gateway", "Twilio Video API"],
            },
            {
                "name": "Electronic Health Records (EHR) & Vitals History",
                "category": "CRUD/data module",
                "complexity": "Very High",
                "priority": "Must-Have",
                "description": "Structured clinical notes, ICD-10 diagnostic coding, vitals time-series graphs, and allergies tracking.",
                "relevance_reason": "Crucial clinical history for medical decision support and continuity of care.",
                "dependencies": ["Patient Registration & Secure Health Profile"],
                "integrations": [],
            },
            {
                "name": "Digital E-Prescription & Pharmacy Dispatch",
                "category": "CRUD/data module",
                "complexity": "High",
                "priority": "Must-Have",
                "description": "Doctor digitally signed medication orders, drug-drug interaction warnings, and pharmacy fulfillment API.",
                "relevance_reason": "Ensures prescription legibility, reduces dosage errors, and speeds medication delivery.",
                "dependencies": ["Electronic Health Records (EHR) & Vitals History"],
                "integrations": ["Pharmacy Partner API"],
            },
            {
                "name": "Lab Test Ordering & Diagnostic Reports Upload",
                "category": "File/media storage",
                "complexity": "Medium",
                "priority": "Should-Have",
                "description": "Diagnostic pathology order placement, encrypted PDF report storage, and patient alert webhooks.",
                "relevance_reason": "Connects diagnostic laboratories directly to patient timeline and attending physician.",
                "dependencies": ["Patient Registration & Secure Health Profile"],
                "integrations": ["Diagnostic Lab API"],
            },
            {
                "name": "Medical Consultation Billing & Insurance Claims",
                "category": "Payment integration",
                "complexity": "Very High",
                "priority": "Should-Have",
                "description": "Co-pay collection, payment gateway, insurance claim pre-authorization submission, and invoice receipts.",
                "relevance_reason": "Reconciles provider consultation fees and patient insurance reimbursement claims.",
                "dependencies": ["Doctor Scheduling & Appointment Booking"],
                "integrations": ["Payment Gateway", "Health Insurance Clearinghouse API"],
            },
            {
                "name": "HIPAA/Audit Compliance & Access Logging",
                "category": "Security/compliance",
                "complexity": "High",
                "priority": "Must-Have",
                "description": "Immutable tamper-evident record access logs detailing who viewed which patient chart and when.",
                "relevance_reason": "Strict legal mandate to protect PHI data integrity and pass healthcare privacy audits.",
                "dependencies": [],
                "integrations": [],
            },
        ],
    },
    "real estate": {
        "archetype": "Booking Platform",
        "features": [
            {
                "name": "User, Agent & Broker Authentication",
                "category": "Authentication",
                "complexity": "Medium",
                "priority": "Must-Have",
                "description": "Multi-tier accounts for Buyers, Sellers, Verified Agents, and Agency Broker Admins.",
                "relevance_reason": "Enables property listing management while granting distinct buyer inquiry privileges.",
                "dependencies": [],
                "integrations": [],
            },
            {
                "name": "Property Listings & High-Res Media Gallery",
                "category": "CRUD/data module",
                "complexity": "Medium",
                "priority": "Must-Have",
                "description": "Detailed listings with floor plans, photo galleries, architectural specs, pricing, and amenities.",
                "relevance_reason": "The core inventory catalog representing properties available for sale or lease.",
                "dependencies": ["User, Agent & Broker Authentication"],
                "integrations": ["Cloudinary / S3 Media CDN"],
            },
            {
                "name": "Geospatial Map Search & Neighborhood Filters",
                "category": "Search/filter",
                "complexity": "High",
                "priority": "Must-Have",
                "description": "Interactive map boundaries, radius search, nearby schools/transit score, and price-bracket filters.",
                "relevance_reason": "Location is the primary decision factor for real estate buyers and tenants.",
                "dependencies": ["Property Listings & High-Res Media Gallery"],
                "integrations": ["Google Maps / Mapbox API"],
            },
            {
                "name": "In-Person & Virtual Tour Scheduling",
                "category": "Booking/scheduling",
                "complexity": "Medium",
                "priority": "Must-Have",
                "description": "Property walkthrough calendar booking with instant agent SMS confirmation and calendar sync.",
                "relevance_reason": "Drives real-world lead conversion from online listing to physical viewing.",
                "dependencies": ["Property Listings & High-Res Media Gallery"],
                "integrations": ["Google Calendar Sync"],
            },
            {
                "name": "Buyer Inquiries & Real-Time Agent Chat",
                "category": "Real-time features",
                "complexity": "High",
                "priority": "Should-Have",
                "description": "Instant messaging between prospective buyers and assigned listing agents with push notifications.",
                "relevance_reason": "Maintains immediate engagement and prompt response times on high-intent buyer leads.",
                "dependencies": ["User, Agent & Broker Authentication"],
                "integrations": ["WebSocket Messaging"],
            },
            {
                "name": "Rental Lease Application & Credit Check",
                "category": "Security/compliance",
                "complexity": "High",
                "priority": "Should-Have",
                "description": "Online tenant application, employment verification, background check upload, and digital lease signing.",
                "relevance_reason": "Automates tenant screening for landlords and property management firms.",
                "dependencies": ["Property Listings & High-Res Media Gallery"],
                "integrations": ["Background Check API", "DocuSign API"],
            },
            {
                "name": "Booking Deposit & Token Payment Gateway",
                "category": "Payment integration",
                "complexity": "High",
                "priority": "Could-Have",
                "description": "Secure escrow token deposit, earnest money transfer, and digital payment receipts.",
                "relevance_reason": "Secures property reservation legally prior to final purchase agreement.",
                "dependencies": ["User, Agent & Broker Authentication"],
                "integrations": ["Payment Gateway API"],
            },
            {
                "name": "Agency Performance & Lead Analytics",
                "category": "Admin dashboard",
                "complexity": "High",
                "priority": "Could-Have",
                "description": "Lead response times, listing view heatmaps, conversion rates by neighborhood, and agent commission tracking.",
                "relevance_reason": "Empowers brokerage management to optimize ad spend and agent performance.",
                "dependencies": [],
                "integrations": [],
            },
        ],
    },
    "logistics": {
        "archetype": "Internal Admin Tool",
        "features": [
            {
                "name": "Carrier, Dispatcher & Driver Authentication",
                "category": "Authentication",
                "complexity": "Medium",
                "priority": "Must-Have",
                "description": "Role-based mobile and web access for Fleet Managers, Dispatchers, Warehouse Staff, and Field Drivers.",
                "relevance_reason": "Secures internal operations and segregates warehouse vs driver responsibilities.",
                "dependencies": [],
                "integrations": [],
            },
            {
                "name": "Shipment Order Booking & Consignment Manifest",
                "category": "CRUD/data module",
                "complexity": "Medium",
                "priority": "Must-Have",
                "description": "Create consignments with weight, dimensions, pickup/drop addresses, hazardous classification, and bill of lading.",
                "relevance_reason": "Core transaction unit detailing cargo specifications and handling instructions.",
                "dependencies": ["Carrier, Dispatcher & Driver Authentication"],
                "integrations": [],
            },
            {
                "name": "Barcode & QR Code Scanning for Inward/Outward",
                "category": "CRUD/data module",
                "complexity": "Medium",
                "priority": "Must-Have",
                "description": "Mobile camera or laser barcode scan at checkpoint handovers, docks, and sorting hubs.",
                "relevance_reason": "Eliminates lost consignments and validates physical cargo transfer at each logistics leg.",
                "dependencies": ["Shipment Order Booking & Consignment Manifest"],
                "integrations": [],
            },
            {
                "name": "Live GPS Fleet Tracking & Geofencing",
                "category": "Real-time features",
                "complexity": "Very High",
                "priority": "Must-Have",
                "description": "Continuous vehicle telemetry, driver mobile GPS updates, map visualization, and geofence entry/exit events.",
                "relevance_reason": "Real-time visibility for dispatchers and automated estimated time of arrival (ETA) calculation.",
                "dependencies": ["Carrier, Dispatcher & Driver Authentication"],
                "integrations": ["Google Maps / HERE Fleet API", "MQTT/IoT Telemetry"],
            },
            {
                "name": "Route Optimization & Multi-Stop Dispatch Engine",
                "category": "Booking/scheduling",
                "complexity": "Very High",
                "priority": "Should-Have",
                "description": "Vehicle routing algorithm optimizing fuel, transit times, and vehicle capacity across multi-drop orders.",
                "relevance_reason": "Reduces fuel expenditure and maximizes fleet asset utilization per delivery cycle.",
                "dependencies": ["Shipment Order Booking & Consignment Manifest"],
                "integrations": ["Routing Optimization API"],
            },
            {
                "name": "Digital Proof of Delivery (e-POD) & Signatures",
                "category": "File/media storage",
                "complexity": "Medium",
                "priority": "Must-Have",
                "description": "Recipient touch-screen signature capture, timestamped delivery photos, and OTP handover verification.",
                "relevance_reason": "Legal proof of handover preventing dispute claims and confirming completed service.",
                "dependencies": ["Live GPS Fleet Tracking & Geofencing"],
                "integrations": [],
            },
            {
                "name": "Automated Customer Tracking & SMS Alerts",
                "category": "Email/SMS notifications",
                "complexity": "Medium",
                "priority": "Should-Have",
                "description": "Public parcel tracking link, out-for-delivery SMS triggers, and delayed transit notices.",
                "relevance_reason": "Reduces inbound support volume by providing shippers and recipients self-serve tracking.",
                "dependencies": ["Live GPS Fleet Tracking & Geofencing"],
                "integrations": ["Twilio / SendGrid API"],
            },
            {
                "name": "Fleet Utilization & Transit SLA Analytics",
                "category": "Analytics/reporting",
                "complexity": "High",
                "priority": "Could-Have",
                "description": "On-time in-full (OTIF) rate, fuel burn KPIs, driver idle times, and vehicle maintenance reminders.",
                "relevance_reason": "Operational intelligence for logistics executives to benchmark carrier partner SLAs.",
                "dependencies": [],
                "integrations": [],
            },
        ],
    },
    "crm": {
        "archetype": "CRM",
        "features": [
            {
                "name": "Sales Rep Authentication & Team Hierarchy",
                "category": "Authentication",
                "complexity": "Medium",
                "priority": "Must-Have",
                "description": "Single sign-on, sales team territories, manager visibility hierarchies, and audit security.",
                "relevance_reason": "Ensures sales representatives only access designated accounts and assigned leads.",
                "dependencies": [],
                "integrations": [],
            },
            {
                "name": "Lead Ingestion & Contact Management",
                "category": "CRUD/data module",
                "complexity": "Medium",
                "priority": "Must-Have",
                "description": "Lead capture forms, company accounts, contact interaction timelines, and duplicate deduplication.",
                "relevance_reason": "Centralized golden record repository for all prospect and customer relationships.",
                "dependencies": ["Sales Rep Authentication & Team Hierarchy"],
                "integrations": [],
            },
            {
                "name": "Visual Sales Pipeline & Deal Stages",
                "category": "CRUD/data module",
                "complexity": "Medium",
                "priority": "Must-Have",
                "description": "Drag-and-drop Kanban pipeline tracking deals from Prospect to Proposal, Negotiation, and Closed-Won.",
                "relevance_reason": "Provides visual pipeline clarity for sales forecasting and deal velocity management.",
                "dependencies": ["Lead Ingestion & Contact Management"],
                "integrations": [],
            },
            {
                "name": "Email Integration & Two-Way Thread Sync",
                "category": "Third-party API integration",
                "complexity": "High",
                "priority": "Should-Have",
                "description": "Bi-directional Google Workspace and Outlook integration logging incoming and outgoing sales emails.",
                "relevance_reason": "Maintains complete correspondence history on the deal record without leaving the CRM.",
                "dependencies": ["Lead Ingestion & Contact Management"],
                "integrations": ["Gmail / Microsoft Graph API"],
            },
            {
                "name": "Automated Follow-Up Tasks & Reminders",
                "category": "Booking/scheduling",
                "complexity": "Low",
                "priority": "Must-Have",
                "description": "Activity task queues, call logging, automated follow-up reminders, and calendar sync.",
                "relevance_reason": "Prevents high-value deals from going cold due to missed sales follow-ups.",
                "dependencies": ["Visual Sales Pipeline & Deal Stages"],
                "integrations": [],
            },
            {
                "name": "Revenue Forecasting & Win-Rate Analytics",
                "category": "Analytics/reporting",
                "complexity": "High",
                "priority": "Should-Have",
                "description": "Weighted revenue forecast, sales cycle duration, conversion funnel by rep, and quota tracking.",
                "relevance_reason": "Critical executive reporting tool for sales leadership to predict monthly and quarterly bookings.",
                "dependencies": ["Visual Sales Pipeline & Deal Stages"],
                "integrations": [],
            },
            {
                "name": "REST API & Webhook Lead Extensibility",
                "category": "Third-party API integration",
                "complexity": "Medium",
                "priority": "Could-Have",
                "description": "Inbound webhooks for website landing pages, marketing automation tools (HubSpot/Marketo), and Zapier.",
                "relevance_reason": "Connects top-of-funnel inbound marketing campaigns directly into the sales CRM pipeline.",
                "dependencies": ["Lead Ingestion & Contact Management"],
                "integrations": ["Zapier / Custom Webhooks"],
            },
        ],
    },
    "fintech": {
        "archetype": "Fintech Application",
        "features": [
            {
                "name": "Identity & KYC Verification Pipeline",
                "category": "Security/compliance",
                "complexity": "Very High",
                "priority": "Must-Have",
                "description": "Government ID upload, facial biometric liveness check, and anti-money laundering (AML) sanctions screening.",
                "relevance_reason": "Statutory regulatory requirement for financial institutions before opening accounts.",
                "dependencies": [],
                "integrations": ["KYC Provider API", "AML Watchlist API"],
            },
            {
                "name": "Multi-Factor Authentication & Biometrics",
                "category": "Authentication",
                "complexity": "High",
                "priority": "Must-Have",
                "description": "Hardware token support, device binding, SMS/TOTP authenticator app verification, and biometric login.",
                "relevance_reason": "Critical security defense against account takeover and credential stuffing attacks.",
                "dependencies": [],
                "integrations": [],
            },
            {
                "name": "Double-Entry Account & Balance Ledger",
                "category": "CRUD/data module",
                "complexity": "Very High",
                "priority": "Must-Have",
                "description": "ACID transactional double-entry accounting ledger tracking debits, credits, holds, and balance statements.",
                "relevance_reason": "The core financial ground truth guaranteeing mathematically balanced financial books.",
                "dependencies": ["Identity & KYC Verification Pipeline"],
                "integrations": [],
            },
            {
                "name": "Fund Transfers & Payment Rails Integration",
                "category": "Payment integration",
                "complexity": "Very High",
                "priority": "Must-Have",
                "description": "ACH, IMPS/NEFT, UPI, and wire transfer processing with automated fraud checks and transaction signing.",
                "relevance_reason": "Enables customers to execute outbound and inbound monetary transfers.",
                "dependencies": ["Double-Entry Account & Balance Ledger"],
                "integrations": ["Core Banking API", "Payment Gateway"],
            },
            {
                "name": "Transaction History & Searchable PDF Statements",
                "category": "Analytics/reporting",
                "complexity": "Medium",
                "priority": "Must-Have",
                "description": "Indexed transaction filters, category spend summaries, and certified monthly statement PDF generation.",
                "relevance_reason": "Empowers customers with audit visibility into their historical expenditures and deposits.",
                "dependencies": ["Double-Entry Account & Balance Ledger"],
                "integrations": [],
            },
            {
                "name": "Maker-Checker Approval Workflows & RBAC",
                "category": "Role-based permissions",
                "complexity": "High",
                "priority": "Should-Have",
                "description": "Dual-control authorization where high-value transfers initiated by a Maker must be approved by a Checker.",
                "relevance_reason": "Standard banking control preventing unauthorized or rogue internal transactions.",
                "dependencies": ["Multi-Factor Authentication & Biometrics"],
                "integrations": [],
            },
            {
                "name": "Tamper-Evident Immutable Audit Event Log",
                "category": "Security/compliance",
                "complexity": "High",
                "priority": "Must-Have",
                "description": "Cryptographically hashed audit log recording every balance modification, auth event, and admin override.",
                "relevance_reason": "Required for statutory regulatory compliance (SOC2, PCI-DSS, ISO27001).",
                "dependencies": [],
                "integrations": [],
            },
        ],
    },
    "ecommerce": {
        "archetype": "E-commerce",
        "features": [
            {
                "name": "Customer Accounts & Address Book",
                "category": "Authentication",
                "complexity": "Low",
                "priority": "Must-Have",
                "description": "Customer email/social signup, saved delivery addresses, order history, and preferences.",
                "relevance_reason": "Allows shoppers to save delivery information and track past orders easily.",
                "dependencies": [],
                "integrations": [],
            },
            {
                "name": "Product Catalog & SKU Variant Inventory",
                "category": "CRUD/data module",
                "complexity": "Medium",
                "priority": "Must-Have",
                "description": "Hierarchical category trees, product variants (size/color), real-time stock counts, and high-res images.",
                "relevance_reason": "The primary retail merchandise display enabling customer product discovery.",
                "dependencies": [],
                "integrations": [],
            },
            {
                "name": "Faceted Search & Dynamic Product Filters",
                "category": "Search/filter",
                "complexity": "Medium",
                "priority": "Must-Have",
                "description": "Full-text search, price ranges, brand filters, customer review filters, and sorting algorithms.",
                "relevance_reason": "Assists customers in quickly locating desired products among large catalogs.",
                "dependencies": ["Product Catalog & SKU Variant Inventory"],
                "integrations": [],
            },
            {
                "name": "Persistent Shopping Cart & Coupon Engine",
                "category": "CRUD/data module",
                "complexity": "Medium",
                "priority": "Must-Have",
                "description": "Cross-device persistent cart, promo code discounts, tax calculation, and free shipping thresholds.",
                "relevance_reason": "Core conversion funnel converting browsing interest into order checkout.",
                "dependencies": ["Product Catalog & SKU Variant Inventory"],
                "integrations": [],
            },
            {
                "name": "Secure Checkout & Payment Gateway Integration",
                "category": "Payment integration",
                "complexity": "High",
                "priority": "Must-Have",
                "description": "Multi-method checkout (Cards, UPI, Apple Pay, Buy Now Pay Later) with webhook charge verification.",
                "relevance_reason": "Facilitates seamless, secure monetary settlement of customer purchases.",
                "dependencies": ["Persistent Shopping Cart & Coupon Engine"],
                "integrations": ["Stripe / Razorpay API"],
            },
            {
                "name": "Order Management & Carrier Shipping Labels",
                "category": "Booking/scheduling",
                "complexity": "High",
                "priority": "Must-Have",
                "description": "Fulfillment workflows, automated carrier label generation, split shipments, and refund approvals.",
                "relevance_reason": "Enables warehouse staff to pack, dispatch, and track orders to completion.",
                "dependencies": ["Secure Checkout & Payment Gateway Integration"],
                "integrations": ["ShipStation / EasyPost API"],
            },
            {
                "name": "Verified Purchaser Reviews & Ratings",
                "category": "CRUD/data module",
                "complexity": "Low",
                "priority": "Should-Have",
                "description": "Star ratings, photo reviews, verified purchase badge, and helpfulness upvotes.",
                "relevance_reason": "Builds social proof and trust, significantly boosting product conversion rates.",
                "dependencies": ["Customer Accounts & Address Book"],
                "integrations": [],
            },
            {
                "name": "Merchant Analytics & Inventory Stock Alerts",
                "category": "Admin dashboard",
                "complexity": "High",
                "priority": "Could-Have",
                "description": "Sales GMV reports, average order value (AOV), cart abandonment metrics, and low stock warnings.",
                "relevance_reason": "Gives retail managers the data needed to restock popular products and optimize marketing.",
                "dependencies": [],
                "integrations": [],
            },
        ],
    },
    "saas": {
        "archetype": "SaaS Web Application",
        "features": [
            {
                "name": "Multi-Tenant Workspace & Organization Isolation",
                "category": "Multi-tenancy",
                "complexity": "Very High",
                "priority": "Must-Have",
                "description": "Logical multi-tenancy with isolated tenant data, custom subdomains, and workspace invitations.",
                "relevance_reason": "Core foundational architecture for B2B SaaS enabling independent corporate customer workspaces.",
                "dependencies": [],
                "integrations": [],
            },
            {
                "name": "Enterprise SSO & Role-Based Access Control",
                "category": "Role-based permissions",
                "complexity": "High",
                "priority": "Must-Have",
                "description": "Google Workspace / SAML Okta SSO, Admin/Editor/Viewer role tiers, and user group management.",
                "relevance_reason": "Required for enterprise IT departments to manage employee access across the organization.",
                "dependencies": ["Multi-Tenant Workspace & Organization Isolation"],
                "integrations": ["Google / Okta SAML SSO"],
            },
            {
                "name": "Tiered Subscription Billing & Self-Serve Portal",
                "category": "Subscription/billing",
                "complexity": "High",
                "priority": "Must-Have",
                "description": "Monthly/annual subscription tiers, seat-based billing, plan upgrades, and Stripe billing portal.",
                "relevance_reason": "Automates SaaS recurring revenue collection and customer billing management.",
                "dependencies": ["Multi-Tenant Workspace & Organization Isolation"],
                "integrations": ["Stripe Billing / Paddle API"],
            },
            {
                "name": "Core Business Workflow & Entity Management",
                "category": "CRUD/data module",
                "complexity": "High",
                "priority": "Must-Have",
                "description": "Application-specific primary operational entities, state machines, and collaborative workflows.",
                "relevance_reason": "The primary value proposition and workflow engine of the SaaS application.",
                "dependencies": ["Multi-Tenant Workspace & Organization Isolation"],
                "integrations": [],
            },
            {
                "name": "Developer Public REST API & Webhook Ingestion",
                "category": "Third-party API integration",
                "complexity": "High",
                "priority": "Should-Have",
                "description": "API keys management, granular scope permissions, rate limiting, and outbound event webhooks.",
                "relevance_reason": "Allows technical customers to automate workflows and integrate the SaaS platform into their stack.",
                "dependencies": ["Core Business Workflow & Entity Management"],
                "integrations": [],
            },
            {
                "name": "Usage Metrics & Tenant Audit Trail",
                "category": "Audit logs",
                "complexity": "High",
                "priority": "Should-Have",
                "description": "Workspace activity log, quota consumption counters, exportable security audit logs.",
                "relevance_reason": "Provides enterprise customers with transparency into platform usage and security events.",
                "dependencies": ["Enterprise SSO & Role-Based Access Control"],
                "integrations": [],
            },
        ],
    },
}


class RequirementExtractor:
    """
    Profile-Based AI Scope & Requirements Assistant Engine.
    Analyzes the user's actual project profile (Domain, Name, Description, Platforms,
    Complexity, Traffic Scale, Tech Stack, and Security requirements) to generate
    relevant, defensible requirements with explanations and user-actionable controls.
    """

    def extract(
        self,
        description: str = "",
        project_type: Optional[str] = None,
        project_name: Optional[str] = None,
        overall_complexity: Optional[str] = "Medium",
        target_platforms: Optional[List[str]] = None,
        user_scale: Optional[str] = "1k-10k",
        tech_stack: Optional[Dict[str, Any]] = None,
        existing_features: Optional[List[str]] = None,
        client_region: Optional[str] = "India",
        quality_requirement: Optional[str] = "Standard",
        realtime_requirement: Optional[str] = "None",
        security_compliance: Optional[str] = "Standard",
        deadline_days: Optional[int] = None,
        budget_constraint: Optional[float] = None,
        additional_notes: Optional[str] = "",
        domain: Optional[str] = None,
        expected_scale: Optional[str] = None,
    ) -> RequirementExtractionResult:
        """
        Extracts structured software specifications tailored to the project profile.
        """
        p_name = (project_name or "").strip()
        p_type = (domain or project_type or "SaaS Platform").strip()
        p_desc = (description or "").strip()
        notes = (additional_notes or "").strip()
        scale = (expected_scale or user_scale or "1k-10k").strip()
        full_text = f"{p_name} {p_type} {p_desc} {notes}".strip()
        full_lower = full_text.lower()
        platforms = target_platforms or ["Web Application"]
        complexity = overall_complexity or "Medium"
        existing = [f.lower().strip() for f in (existing_features or [])]

        # Step A: Inspect Profile Completeness
        missing_requirements = []
        clarification_questions = []
        is_profile_complete = True

        if len(p_desc) < 25 and not notes:
            is_profile_complete = False
            missing_requirements.append("Detailed scope overview is brief. Additional operational details will refine feature hours.")
            clarification_questions.append("What are the primary target user personas and their distinct operational workflows?")
        
        if not target_platforms or len(target_platforms) == 0:
            missing_requirements.append("Target delivery platforms unspecified; defaulted to Web Application.")
            clarification_questions.append("Will the software require native mobile apps (iOS/Android), desktop clients, or responsive web only?")

        if complexity in ("High", "Very High") and security_compliance == "Standard":
            clarification_questions.append("Are there specific regulatory compliance mandates (e.g., GDPR, HIPAA, SOC2, PCI-DSS) for this project?")

        if user_scale in ("100k-1M", "1M+"):
            clarification_questions.append("What are the expected peak concurrent user loads and burst traffic tolerances?")

        # Step B & C: Synthesize Contextual Requirements from Project Profile
        matched_domain_key = None
        for key in DOMAIN_CATALOG.keys():
            if key in full_lower or key in p_type.lower():
                matched_domain_key = key
                break

        # Check secondary domain keywords
        if not matched_domain_key:
            if any(w in full_lower for w in ["college", "university", "school", "student", "teacher", "campus", "course", "grade", "faculty", "lms", "academy"]):
                matched_domain_key = "education"
            elif any(w in full_lower for w in ["doctor", "patient", "clinic", "hospital", "telemedicine", "medical", "prescription", "health", "ehr", "clinical"]):
                matched_domain_key = "healthcare"
            elif any(w in full_lower for w in ["property", "realty", "broker", "apartment", "rental", "estate", "tenant", "landlord", "listing"]):
                matched_domain_key = "real estate"
            elif any(w in full_lower for w in ["fleet", "truck", "warehouse", "freight", "cargo", "shipment", "transit", "barcode", "pod", "delivery tracking"]):
                matched_domain_key = "logistics"
            elif any(w in full_lower for w in ["sales", "pipeline", "deal", "lead", "contact", "opportunity", "rep", "outreach"]):
                matched_domain_key = "crm"
            elif any(w in full_lower for w in ["bank", "wallet", "ledger", "kyc", "transfer", "wire", "fintech", "payment rail"]):
                matched_domain_key = "fintech"
            elif any(w in full_lower for w in ["cart", "catalog", "checkout", "sku", "store", "ecommerce", "e-commerce", "retail"]):
                matched_domain_key = "ecommerce"
            elif any(w in full_lower for w in ["tenant", "workspace", "subscription", "saas", "b2b"]):
                matched_domain_key = "saas"

        features: List[ExtractedFeature] = []

        if matched_domain_key and matched_domain_key in DOMAIN_CATALOG:
            domain_info = DOMAIN_CATALOG[matched_domain_key]
            derived_type = domain_info.get("archetype", p_type)
            raw_features = domain_info.get("features", [])

            for i, rf in enumerate(raw_features):
                # Filter out already existing features
                if rf["name"].lower().strip() in existing:
                    continue

                # Adjust complexity according to overall project complexity
                comp = rf.get("complexity", "Medium")
                if complexity == "Low" and comp in ("High", "Very High"):
                    comp = "Medium"
                elif complexity == "Very High" and comp == "Medium":
                    comp = "High"

                features.append(
                    ExtractedFeature(
                        id=f"rec_{i+1}",
                        name=rf["name"],
                        category=rf.get("category", "CRUD/data module"),
                        complexity=comp,
                        description=rf.get("description", ""),
                        relevance_reason=rf.get("relevance_reason", f"Relevant for {p_name or p_type}"),
                        priority=rf.get("priority", "Must-Have"),
                        dependencies=rf.get("dependencies", []),
                        integration_requirements=rf.get("integrations", []),
                        status="recommended",
                        is_provisional=not is_profile_complete,
                    )
                )
        else:
            # Custom / Arbitrary Domain Profile Synthesis
            derived_type = p_type or "Custom Platform"
            
            # Extract key nouns and phrases from project description and name
            target_nouns = []
            clean_text = re.sub(r"[^a-zA-Z0-9\s]", " ", full_text)
            words = [w.capitalize() for w in clean_text.split() if len(w) > 3 and w.lower() not in {"with", "from", "that", "this", "have", "will", "build", "create", "need", "system", "platform", "application"}]
            if words:
                target_nouns = words[:4]

            primary_entity = target_nouns[0] if target_nouns else "Primary Business Entity"
            secondary_entity = target_nouns[1] if len(target_nouns) > 1 else "Operations"

            candidate_features = [
                {
                    "name": f"{p_name or 'System'} User Authentication & Permissions",
                    "category": "Authentication",
                    "complexity": "Medium",
                    "priority": "Must-Have",
                    "description": "Secure identity authentication with role-based access control and password recovery.",
                    "relevance_reason": f"Protects administrative capabilities and data privacy for {p_name or p_type} users.",
                    "dependencies": [],
                    "integrations": [],
                },
                {
                    "name": f"{primary_entity} Management & Data Registry",
                    "category": "CRUD/data module",
                    "complexity": "Medium" if complexity != "Very High" else "High",
                    "priority": "Must-Have",
                    "description": f"Core operations for creating, updating, searching, and managing {primary_entity.lower()} records.",
                    "relevance_reason": f"Primary functional requirement central to {p_name or p_type}.",
                    "dependencies": [f"{p_name or 'System'} User Authentication & Permissions"],
                    "integrations": [],
                },
                {
                    "name": f"{secondary_entity} Workflow & Processing State Machine",
                    "category": "CRUD/data module",
                    "complexity": "High" if complexity in ("High", "Very High") else "Medium",
                    "priority": "Must-Have",
                    "description": f"Lifecycle status transitions, review approvals, and business validation rules for {secondary_entity.lower()}.",
                    "relevance_reason": f"Automates operational handoffs and enforces process integrity.",
                    "dependencies": [f"{primary_entity} Management & Data Registry"],
                    "integrations": [],
                },
                {
                    "name": "Advanced Search, Filtering & Export",
                    "category": "Search/filter",
                    "complexity": "Low",
                    "priority": "Should-Have",
                    "description": "Indexed search filters, multi-column sorting, and Excel/CSV data export.",
                    "relevance_reason": "Enables rapid record discovery and spreadsheet data extraction.",
                    "dependencies": [f"{primary_entity} Management & Data Registry"],
                    "integrations": [],
                },
                {
                    "name": f"{p_name or 'Executive'} Operational Analytics Dashboard",
                    "category": "Admin dashboard",
                    "complexity": "High",
                    "priority": "Should-Have",
                    "description": "Consolidated KPIs, activity charts, system health metrics, and executive summary reports.",
                    "relevance_reason": "Provides stakeholders immediate visibility into operational performance.",
                    "dependencies": [],
                    "integrations": [],
                },
                {
                    "name": "Automated Email & System Event Notifications",
                    "category": "Email/SMS notifications",
                    "complexity": "Low",
                    "priority": "Could-Have",
                    "description": "Transactional status alerts, deadline reminders, and system event triggers.",
                    "relevance_reason": "Keeps users informed of critical updates without active dashboard monitoring.",
                    "dependencies": [],
                    "integrations": ["SendGrid / Transactional Email API"],
                },
            ]

            # Platform-specific additions
            if any("mobile" in p.lower() or "android" in p.lower() or "ios" in p.lower() for p in platforms):
                candidate_features.append({
                    "name": "Mobile Push Notifications & Offline Sync",
                    "category": "Real-time features",
                    "complexity": "High",
                    "priority": "Should-Have",
                    "description": "Firebase Cloud Messaging push alerts and local SQLite storage for offline connectivity.",
                    "relevance_reason": f"Essential for native mobile experiences specified in target platforms ({', '.join(platforms)}).",
                    "dependencies": [f"{p_name or 'System'} User Authentication & Permissions"],
                    "integrations": ["Firebase Cloud Messaging API"],
                })

            for i, cf in enumerate(candidate_features):
                if cf["name"].lower().strip() in existing:
                    continue
                features.append(
                    ExtractedFeature(
                        id=f"rec_{i+1}",
                        name=cf["name"],
                        category=cf["category"],
                        complexity=cf["complexity"],
                        description=cf["description"],
                        relevance_reason=cf["relevance_reason"],
                        priority=cf["priority"],
                        dependencies=cf["dependencies"],
                        integration_requirements=cf["integrations"],
                        status="recommended",
                        is_provisional=not is_profile_complete,
                    )
                )

        # Default recommended tech stack based on project profile
        rec_stack = {
            "frontend_stack": "Flutter" if any("mobile" in p.lower() for p in platforms) and not any("web" in p.lower() for p in platforms) else "React",
            "backend_stack": "FastAPI_Python" if any(w in full_lower for w in ["ai", "ml", "python", "data"]) else "Node.js_Express",
            "database": "PostgreSQL",
            "hosting_platform": "AWS",
        }

        assumptions = [
            f"Assumes standard relational PostgreSQL architecture deployed on {rec_stack['hosting_platform']}.",
            f"Target client platforms: {', '.join(platforms)}.",
            f"Expected initial concurrency scaled for {user_scale} active users.",
        ]

        completeness = 100.0
        if not is_profile_complete:
            completeness -= 45.0
        if len(missing_requirements) > 1:
            completeness -= 20.0
        completeness = max(15.0, min(100.0, completeness))

        return RequirementExtractionResult(
            project_name=p_name or "Active Estimation Project",
            project_type=derived_type,
            overall_complexity=complexity,
            features=features,
            recommended_tech_stack=rec_stack,
            missing_requirements=missing_requirements,
            clarification_questions=clarification_questions,
            assumptions=assumptions,
            profile_complete=is_profile_complete,
            is_provisional=not is_profile_complete,
            completeness_score=completeness,
            is_ai_generated=False,
            provider_used="rule_based_offline",
            model_provenance="Profile Rules Engine (CostPilot Institutional Dataset)",
        )


requirement_extractor = RequirementExtractor()
