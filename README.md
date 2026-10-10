# CostPilot AI — Professional Multi-Page Software Cost Estimation Platform

**CostPilot AI** is an enterprise-grade, multi-page, AI-assisted software product cost, effort, and timeline estimation platform. Rather than relying on arbitrary formulas, gut-feel multipliers, or fabricated quotations, CostPilot AI pairs empirical feature-level priors with supervised machine learning benchmarks trained on the **CostPilot AI Training Dataset** (2,500 projects, 44,301 features, and 20 stress-test edge cases).

---

## 🏛️ System Architecture

```
c:\hakit/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI application & static frontend mounting
│   │   ├── core/
│   │   │   ├── config.py               # Domain constants, 34+ domains, 17 platforms, rate profiles
│   │   │   └── security.py             # PBKDF2-HMAC password hashing & session token authentication
│   │   ├── db/
│   │   │   ├── session.py              # SQLite connection, users/projects schema migrations & seeding
│   │   │   └── costpilot.db            # Local SQLite database
│   │   ├── schemas/
│   │   │   ├── auth.py                 # Pydantic schemas for registration, login, profile, password change
│   │   │   └── estimation.py           # Pydantic schemas for estimation & project persistence
│   │   ├── api/
│   │   │   ├── auth.py                 # Auth router (/register, /login, /me, /profile, /change-password)
│   │   │   └── routes.py               # Estimation, projects CRUD, and analytics endpoints
│   │   └── services/
│   │       ├── ml/
│   │       │   ├── data_loader.py      # Excel dataset loader & foreign-key validator
│   │       │   ├── train_model.py      # ML training pipeline with leakage audits
│   │       │   ├── predictor.py        # Safe inference predictor with domain archetype mapping
│   │       │   └── model_registry.py   # Artifact tracking and metadata loading
│   │       └── estimation/
│   │           ├── engine.py           # Authoritative 23-Step Estimation Engine
│   │           ├── feature_effort.py   # PERT O/M/P engine with Empirical Bayes shrinkage
│   │           ├── complexity.py       # 9-Factor complexity model (0-100 score)
│   │           ├── dependency_graph.py # DAG analyzer, cycle detection & critical path
│   │           ├── team_timeline.py    # Role allocations, FTE, & Brooks' Law coordination
│   │           ├── cost_budget.py      # Role costs, single-pass contingency, financial invariants
│   │           ├── risk_scoring.py     # Formula-driven risk scoring & confidence signals
│   │           └── explanations.py     # Natural language explanation narrative
│   ├── data/
│   │   └── CostPilot_AI_Training_Dataset.xlsx # 2,500 projects, 44,301 features
│   ├── artifacts/
│   │   ├── cost_model.joblib           # Trained RandomForestRegressor for Cost (INR)
│   │   ├── effort_model.joblib         # Trained RandomForestRegressor for Effort (Hours)
│   │   ├── duration_model.joblib       # Trained RandomForestRegressor for Duration (Days)
│   │   └── feature_catalog_stats.json  # Precomputed shrinkage statistics & priors
│   ├── reports/
│   │   ├── data_quality_report.json    # Schema & relationship validation report
│   │   ├── model_metrics.json          # Held-out test evaluation vs Naive Baseline
│   │   └── edge_case_eval.json         # Stress test evaluation across 20 synthetic edge cases
│   ├── tests/
│   │   ├── test_auth_and_multipage.py  # Auth, monotonicity, user isolation, 34 domains & 17 platforms
│   │   ├── test_data_loader.py         # Dataset integrity & FK project-feature linkage
│   │   ├── test_ml_pipeline.py         # Leakage audits, unseen categories, metrics
│   │   ├── test_estimation_engine.py   # Scenarios 1-16 & monotonic invariants
│   │   ├── test_dependencies.py        # Cycle rejection & critical path
│   │   ├── test_cost_invariants.py     # Financial invariants & single contingency
│   │   └── test_api_endpoints.py       # FastAPI integration & CRUD flow
│   └── requirements.txt
├── frontend/
│   ├── index.html                      # Multi-page application with Auth screen & App shell
│   ├── css/
│   │   └── style.css                   # Generous spacing scale (8/16/24/32/48px), dark/light theme
│   └── js/
│       └── app.js                      # Multi-page router, 6-step wizard controller, session management
└── README.md
```

---

## 🚀 Navigation & Application Flow

Unauthenticated visitors land on the **Login / Sign Up** screen first. Once authenticated, users enter the full application shell:

```
Website URL
  ↓
Login / Sign Up (Auth Screen)
  ↓
Authenticated Dashboard (Welcome banner, real database KPIs, recent projects)
  ↓
User selects "New Estimate"
  ↓
Dedicated New Estimate Wizard (6 distinct navigable steps)
  ├─ Step 1: Project Information (34+ Domains, 17 Platforms, Complexity, Scale, Region)
  ├─ Step 2: Technical Specifications (Frontend, Backend, DB, Cloud, Security, Real-Time)
  ├─ Step 3: Feature Builder (AI Scope Extraction, manual features, PERT priors)
  ├─ Step 4: Team and Rates (Headcount, hourly rates, financial invariants)
  ├─ Step 5: Timeline Constraints (Days/Weeks/Months conversion, contingency %)
  └─ Step 6: Review & Generate (Authoritative 23-step calculation, breakdown, What-If)
  ↓
User clicks "Save Project"
  ↓
Project persisted to SQLite database and appears in "My Projects"
```

---

## 🔒 Authentication & User Isolation

- **Password Security**: Passwords hashed using standard library `hashlib.pbkdf2_hmac` with SHA-256 and a 16-byte cryptographically secure salt (`secrets.token_bytes`). Plaintext passwords are never stored or logged.
- **Session Tokens**: Tamper-proof HMAC-SHA256 signed session tokens verified on every protected request.
- **Project Isolation**: Projects and estimates are tied to `user_id`. Users can view and delete only their own records. Cross-user delete attempts return `403 Forbidden`.
- **Pre-seeded Demo User**:
  - Email: `demo@costpilot.ai`
  - Password: `Password@123`

---

## 📈 Monotonic Complexity Strategy

Complexity strictly affects project effort and budget for equivalent projects:
$$\text{Budget}(\text{Low}) < \text{Budget}(\text{Medium}) < \text{Budget}(\text{High}) < \text{Budget}(\text{Very High})$$

1. **Feature-Level Priors**: Features with `"Auto"` or unspecified complexity inherit the project's overall complexity level, drawing from empirical base hours (Low: 8h, Medium: 16h, High: 32h, Very High: 64h).
2. **Project Foundation Work**: Project-level baseline architecture, setup, and coordination work scale proportionally with overall complexity ($0.85\times < 1.00\times < 1.25\times < 1.55\times$).
3. **Risk Scoring**: Risk quartile cutoffs and schedule pressure scale with project difficulty.
4. **Target Leakage Audited**: Model inputs are strictly pre-project characteristics; complexity is not artificially multiplied or arbitrarily inflated.

---

## 💰 Authoritative Financial Invariants

The backend estimation engine strictly enforces financial consistency across all views:

1. **Role Cost**:
   $$\text{Role Cost} = \text{Allocated Role Hours} \times \text{Role Hourly Rate}$$
2. **Total Labour Cost**:
   $$\text{Total Labour Cost} = \sum \text{Role Costs}$$
3. **Pre-Contingency Cost**:
   $$\text{Pre-Contingency Cost} = \text{Total Labour Cost} + \text{Infrastructure} + \text{Tooling} + \text{Direct Costs}$$
4. **Contingency Applied Strictly Once**:
   $$\text{Contingency Amount} = \text{Pre-Contingency Cost} \times \text{Contingency Rate}$$
5. **Final Budget**:
   $$\text{Final Budget} = \text{Pre-Contingency Cost} + \text{Contingency Amount}$$

---

## 🧪 Comprehensive Automated Test Results

The backend includes a comprehensive pytest suite covering all 8 modules (46 test scenarios):

| Test Suite | Tests | Status | Description |
| :--- | :---: | :---: | :--- |
| `test_auth_and_multipage.py` | 6 | **PASSED** | Registration, login, profile, strict complexity monotonicity, project isolation & deletion, 34 domains & 17 platforms |
| `test_api_endpoints.py` | 8 | **PASSED** | Health, model status/metrics, scope analyze, batch features, CRUD flow, what-if |
| `test_cost_invariants.py` | 6 | **PASSED** | Mandatory financial invariants, single contingency, rate monotonicity |
| `test_data_loader.py` | 4 | **PASSED** | Dataset file verification, sheet inspection, FK linkage |
| `test_dependencies.py` | 2 | **PASSED** | Directed Acyclic Graph (DAG) cycle detection & critical path calculation |
| `test_estimation_engine.py` | 16 | **PASSED** | Scenarios 1-16 covering various domain archetypes and edge cases |
| `test_ml_pipeline.py` | 4 | **PASSED** | Target leakage audits, unseen categorical values, held-out evaluation metrics |
| **Total** | **46** | **100% PASS** | Zero failures across entire suite |

---

## 🛠️ Running the Application

### 1. Start the FastAPI Backend & Web Server
```bash
cd c:\hakit\backend
C:\anaconda\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Open your browser at `http://127.0.0.1:8000`.

### 2. Run the Automated Test Suite
```bash
cd c:\hakit\backend
C:\anaconda\python.exe -m pytest tests/test_auth_and_multipage.py tests/test_api_endpoints.py tests/test_cost_invariants.py tests/test_estimation_engine.py -v
```
