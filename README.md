# MOH – Ministry of Health Claims Intelligence Platform

[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live-brightgreen?logo=github)](https://fadil369.github.io/MOH/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/github/license/Fadil369/MOH)](LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-85%25%2B-success)](#testing)
[![Google Chat](https://img.shields.io/badge/Google%20Chat-Join%20Space-blue?logo=googlechat)](https://chat.google.com/room/AAQAUkMiTP8?cls=7)

> An AI-powered, NPHIES-compliant healthcare claims management platform for Saudi Arabia — automating rejection triage, fraud detection, FHIR bundle construction, and human-in-the-loop escalation.

---

## 📑 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Key Features](#key-features)
- [Module Reference](#module-reference)
  - [Core](#core)
  - [Agents (LINC)](#agents-linc)
  - [Microservices](#microservices)
  - [Integrations](#integrations)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Running Services](#running-services)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Security](#security)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

The **MOH Claims Intelligence Platform** streamlines the full lifecycle of healthcare insurance claims in Saudi Arabia — from submission through NPHIES (National Platform for Health Information Exchange Services) to automated rejection handling, appeal routing, and audit reporting.

It combines a **microservices architecture** (FastAPI) with **AI/ML agents** (LINC — Learning Intelligent Network Components) to reduce manual review time, prevent fraud, and maintain full regulatory compliance with MOH standards.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     SBS Landing Service  (:8005)            │
│              (Entry point – claim intake & routing)         │
└───────────────────────┬─────────────────────────────────────┘
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
  ┌──────────────┐ ┌──────────┐ ┌──────────────────┐
  │  Normalizer  │ │  Signer  │ │ Financial Rules  │
  │   (:8001)    │ │ (:8002)  │ │    (:8003)       │
  └──────────────┘ └──────────┘ └──────────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │  NPHIES Bridge  │
              │    (:8004)      │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  NPHIES Saudi   │
              │  (nphies.sa)    │
              └─────────────────┘

           AI Agents (LINC Layer)
  ┌──────────┬──────────┬──────────┬──────────┐
  │AuthLINC  │ Clinical │Compliance│  Fraud   │
  │          │  LINC    │  LINC    │Detection │
  └──────────┴──────────┴──────────┴──────────┘

           Integrations
  ┌────────────┬────────────┬────────────┐
  │Google Chat │ Vertex AI  │  n8n       │
  │    Bot     │ (Gemini)   │ Workflows  │
  └────────────┴────────────┴────────────┘
```

---

## Key Features

| Feature | Description |
|---|---|
| 🤖 **AI Rejection Triage** | Automatically classifies and routes rejected claims (administrative, clinical, pre-authorization, medication/device, policy) |
| 🔐 **Security & PHI Masking** | AES-GCM encryption, HMAC signing, RBAC policy, and PHI field masking for HIPAA/PDPL compliance |
| 📋 **FHIR R4 Builder** | Constructs compliant FHIR bundles for NPHIES submission and appeals |
| 🧠 **Fraud Detection** | Isolation Forest anomaly detection + duplicate billing checks + heuristic fraud scoring |
| 🔄 **NPHIES Integration** | Direct async HTTP bridge to Saudi Arabia's national health claims exchange |
| 👩‍⚕️ **Human-in-the-Loop (HITL)** | Escalates high-value claims (> 10,000 SAR) to human reviewers via Google Chat |
| 📊 **Google Workspace** | Chat bot, space management, and real-time claim issue tracking |
| ⚡ **n8n Automation** | Low-code workflow orchestration for claim pipelines |
| 🌐 **Vertex AI** | Gemini-powered AI analysis for clinical assessment |

---

## Module Reference

### Core

Located in `core/` — shared models and business logic used across all services.

| File | Purpose |
|---|---|
| `models.py` | Pydantic data models: `ClaimLine`, `FHIRBundle`, `HITLRequest`, `ClaimIssue`, enums |
| `decision_engine.py` | Routes claims to APPEAL / RESUBMIT_NEW / CANCEL / VOID based on rejection type and fraud score |
| `fhir_builder.py` | Constructs FHIR R4 compliant bundles for NPHIES submissions |
| `security.py` | `PHIMasker`, `AESCipher`, `RBACPolicy`, HMAC generation |
| `logging_config.py` | Structured logging via `structlog` |

#### Rejection Routing Logic

```
ADMINISTRATIVE       → RESUBMIT_NEW
CLINICAL_DOCUMENTATION → APPEAL
PREAUTHORIZATION
  └─ code BE-1-4*   → RESUBMIT_NEW
  └─ other          → APPEAL
MEDICATION_DEVICE    → APPEAL
POLICY_LIMITATION
  └─ fraud_score > 0.7 → VOID
  └─ other           → APPEAL
```

#### HITL Threshold

Claims exceeding **10,000 SAR** are automatically escalated for human review.

---

### Agents (LINC)

Located in `agents/` — AI-powered specialist agents.

| Agent | Class | Capabilities |
|---|---|---|
| `auth_linc.py` | `AuthLINC` | Eligibility verification, pre-authorization checks, coverage lookup |
| `clinical_linc.py` | `ClinicalLINC` | Clinical documentation review and assessment |
| `compliance_linc.py` | `ComplianceLINC` | Regulatory compliance checks (MOH/NPHIES rules) |
| `fraud_detection_linc.py` | `FraudDetectionLINC` | Anomaly detection (Isolation Forest), duplicate billing, fraud scoring |
| `predictive_linc.py` | `PredictiveLINC` | Predictive analytics for claim outcome forecasting |

**Fraud Score Heuristics**

| Condition | Score Contribution |
|---|---|
| `amount_sar > 50,000` | +0.30 |
| No `preauth_id` and `amount_sar > 10,000` | +0.20 |
| Rejection code starts with `CV` | +0.10 |
| Maximum cap | 1.00 |

---

### Microservices

Each service is a standalone FastAPI application, containerised with Docker.

#### Normalizer — Port 8001
Standardises incoming claim data to the internal `ClaimLine` format.

#### Signer — Port 8002
Cryptographically signs FHIR bundles using AES-GCM / HMAC before NPHIES submission.

#### Financial Rules Engine — Port 8003
Classifies rejection codes into `RejectionType` categories based on MOH financial rules.

#### NPHIES Bridge — Port 8004

| Endpoint | Method | Description |
|---|---|---|
| `/submit` | POST | Submit a FHIR bundle to NPHIES |
| `/status/{claim_id}` | GET | Query claim status from NPHIES |
| `/portal-extractions` | POST | Ingest normalized Oracle/NPHIES portal extraction artifacts |
| `/portal-extractions` | GET | List stored portal extraction artifacts |
| `/portal-extractions/{extraction_id}` | GET | Retrieve one stored portal extraction artifact |
| `/health` | GET | Service health check |

#### SBS Landing — Port 8005 (Main Entry Point)

| Endpoint | Method | Description |
|---|---|---|
| `/process` | POST | Intake claims, classify, route, identify HITL |
| `/dashboard` | GET | Operational status of all services |
| `/health` | GET | Service health check |

---

### Integrations

Located in `integrations/` — external system connectors.

| File | Purpose |
|---|---|
| `google_chat_bot.py` | Google Chat bot for claim notifications and HITL escalation |
| `workspace_events.py` | Google Workspace event subscriptions (Chat space lifecycle) |
| `issue_store.py` | Persistent claim issue tracker backed by Google Chat spaces |
| `n8n_workflow.py` | n8n REST API client for triggering automation workflows |
| `vertex_ai.py` | Vertex AI / Gemini client for AI-powered clinical analysis |

---

## Getting Started

### Prerequisites

- Python **3.11+**
- Docker & Docker Compose
- (Optional) Google Cloud credentials for Workspace/Vertex AI integration
- (Optional) n8n instance for workflow automation

### Installation

```bash
# Clone the repository
git clone https://github.com/Fadil369/MOH.git
cd MOH

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running Services

#### All services via Docker Compose

```bash
docker-compose up --build
```

This starts all five microservices:

| Service | URL |
|---|---|
| Normalizer | http://localhost:8001 |
| Signer | http://localhost:8002 |
| Financial Rules | http://localhost:8003 |
| NPHIES Bridge | http://localhost:8004 |
| SBS Landing | http://localhost:8005 |

#### Individual service (development)

```bash
uvicorn services.sbs_landing.main:app --reload --port 8005
```

#### Interactive API docs

Each FastAPI service exposes Swagger UI at `/docs` and ReDoc at `/redoc`.

---

## Configuration

### Oracle Portal MCP Starter Pack

MOH includes a branch-safe Oracle portal adapter and shared environment contract:

- Shared contract: `config/oracle-portal.env.contract`
- Example env: `.env.oracle-portal.example`
- Adapter: `integrations/oracle_portal_adapter.py`

Adapter guardrails:

- Allowed branches enforced from `ORACLE_PORTAL_ALLOWED_BRANCHES`
- Default branch fallback via `ORACLE_PORTAL_DEFAULT_BRANCH`
- Live submission blocked unless `ORACLE_PORTAL_ALLOW_LIVE_SUBMIT=true`

The adapter supports calling MCP tools through `ORACLE_PORTAL_MCP_ENDPOINT`.

Set the following environment variables (or use a `.env` file):

| Variable | Description | Default |
|---|---|---|
| `NPHIES_API_URL` | NPHIES endpoint base URL | `https://nphies.sa/api` |
| `AES_KEY` | 32-byte AES key (base64) | Random per-run |
| `HMAC_KEY` | HMAC signing key | — |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID for Vertex AI | — |
| `GOOGLE_CHAT_SPACE_ID` | Default Chat space for HITL | `spaces/AAQAUkMiTP8` |
| `N8N_BASE_URL` | n8n instance URL | — |
| `N8N_API_KEY` | n8n API key | — |
| `N8N_PORTAL_EXTRACTION_WEBHOOK_URL` | n8n webhook URL to trigger on ingested portal extraction | — |
| `HITL_THRESHOLD_SAR` | Override HITL amount threshold | `10000` |

---

## API Reference

### Submit Claims (SBS Landing)

```http
POST http://localhost:8005/process
Content-Type: application/json

{
  "claims": [
    {
      "patient_id": "P-001",
      "provider_id": "PROV-100",
      "amount_sar": 15000.00,
      "rejection_code": "BE-1-4-1",
      "date_of_service": "2025-01-15",
      "preauth_id": "PA-2025-001"
    }
  ]
}
```

**Response:**

```json
{
  "processed": 1,
  "routes": {
    "<service_line_id>": "RESUBMIT_NEW"
  },
  "hitl_required": ["<service_line_id>"]
}
```

### Submit FHIR Bundle to NPHIES

```http
POST http://localhost:8004/submit
Content-Type: application/fhir+json

{
  "resourceType": "Bundle",
  "type": "transaction",
  "entry": [...]
}
```

---

### Ingest Portal Extraction Artifact

```http
POST http://localhost:8004/portal-extractions
Content-Type: application/json

{
  "source": "oracle",
  "portalUrl": "https://128.1.1.185/prod/faces/Home",
  "currentUrl": "https://128.1.1.185/prod/faces/Dashboard",
  "capturedAt": "2026-04-15T10:00:00Z",
  "auth": {
    "attempted": true,
    "mode": "password",
    "likelySuccessful": true
  },
  "endpoints": {
    "urls": ["https://128.1.1.185/api/claims"],
    "processUrls": ["https://128.1.1.185/api/claims"],
    "ids": {"claim": ["CLM-1001"]}
  }
}
```

This endpoint accepts the normalized extraction artifact emitted by the SBS Oracle and NPHIES portal scanners and stores it for downstream review or workflow orchestration.

---

## Testing

Tests are located in the `tests/` directory and use **pytest** with async support and coverage gating.

```bash
# Run all tests with coverage report
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_decision_engine.py
```

Coverage is enforced at a minimum of **85%** (`--cov-fail-under=85`).

---

## Security

The platform implements multiple security layers:

- **PHI Masking** — Patient IDs and names are masked in logs and responses (`PHIMasker`)
- **AES-256-GCM Encryption** — Sensitive claim data is encrypted at rest and in transit (`AESCipher`)
- **HMAC-SHA256 Signing** — FHIR bundles are signed to ensure integrity before NPHIES submission
- **RBAC** — Role-based access control with four built-in roles:

| Role | Permissions |
|---|---|
| `billing_admin` | read_claims, submit_claims, view_dashboard |
| `clinical_reviewer` | read_claims, review_clinical, approve_appeal |
| `compliance_officer` | read_claims, view_audit_log, check_compliance |
| `auditor` | read_claims, view_audit_log |

---

## Deployment

### Docker Compose (Recommended)

```bash
docker-compose up -d --build
```

### GitHub Pages (Documentation Site)

The public documentation site is deployed automatically to GitHub Pages on every push to `main`.

🌐 **Live site:** https://fadil369.github.io/MOH/

The workflow is defined in `.github/workflows/static.yml`.

### Production Considerations

- Use a secrets manager (e.g., Google Secret Manager, AWS Secrets Manager) for all credentials
- Enable HTTPS/TLS termination at your ingress/load balancer
- Set `AES_KEY` and `HMAC_KEY` as persistent secrets (not random per-run)
- Configure NPHIES sandbox URL for staging: `https://nphies-sandbox.sa/api`

---

## Community & Support

Join the MOH Claims Platform team on **Google Chat** for real-time collaboration, HITL escalations, and support:

➡️ **[Open MOH Claims Chat Space](https://chat.google.com/room/AAQAUkMiTP8?cls=7)**

The space is used for:
- Human-in-the-Loop (HITL) claim review notifications (claims > 10,000 SAR)
- Team collaboration on complex rejection cases
- System alerts and integration status updates

The space ID used by the integration is `spaces/AAQAUkMiTP8` (constant `HITL_SPACE_ID` in `integrations/google_chat_bot.py`).

---

## Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'feat: add your feature'`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

Please ensure all tests pass and coverage remains above 85% before submitting.

---

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.