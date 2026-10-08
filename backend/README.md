# FOH Table Management — Backend Engine 🚀

> High-performance FastAPI backend powered by SQLAlchemy 2.0, Ultralytics YOLO11 Computer Vision, native WebSockets, and Conversational AI with multi-provider cloud & local fallback.

---

## 📋 Table of Contents

- [Architecture Overview](#architecture-overview)
- [Quick Start Guide](#quick-start-guide)
- [Directory Structure](#directory-structure)
- [Database & Seed Data](#database--seed-data)
- [Computer Vision Pipeline](#computer-vision-pipeline)
- [AI & Natural Language Processing](#ai--natural-language-processing)
- [API Routers Catalog](#api-routers-catalog)
- [Staff Roles & Permissions](#staff-roles--permissions)
- [Running Automated Tests](#running-automated-tests)
- [Common Troubleshooting](#common-troubleshooting)

---

## 🏛️ Architecture Overview

The backend is built with **FastAPI** and runs on Python 3.11–3.13. It manages all restaurant state machine logic, real-time WebSocket communication, POS transactions, computer vision table analysis, and AI chat.

- **Framework**: FastAPI with Pydantic v2 schemas.
- **ORM / Database**: SQLAlchemy 2.0 with SQLite by default (`foh.db`), with turnkey PostgreSQL connection pooling.
- **Computer Vision**: Ultralytics YOLO11 (`yolo11n.pt`) + custom cleanliness weights (`table_cleanliness_best.pt`).
- **AI Providers**: Groq Cloud LLM (Llama 3.3 70B), Google Gemini (Gemini 2.0 Flash), OpenAI, and local Rule-Based Maitre D'.
- **Real-Time Layer**: Native WebSocket hub broadcasting table updates, alerts, and billing events to `/ws/{floor_id}` rooms.

---

## ⚡ Quick Start Guide

### 1. Requirements
- **Python**: `3.11`, `3.12`, or `3.13` (avoid 3.14 until all C-extensions are updated).

### 2. Setup Virtual Environment

**Windows (PowerShell):**
```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS / Linux:**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Launch Development Server

```bash
python -m uvicorn app.main:socket_app --host 127.0.0.1 --port 8000 --reload
```

- **API Base URL**: `http://127.0.0.1:8000`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`
- **ReDoc Schema Browser**: `http://127.0.0.1:8000/redoc`

---

## 📂 Directory Structure

```
backend/
├── alembic/                 # Database migrations (optional PostgreSQL setup)
├── app/
│   ├── config.py            # Pydantic BaseSettings & .env reader
│   ├── database.py          # SQLAlchemy Engine, SessionLocal, health checks
│   ├── main.py              # FastAPI application, CORS, routers & lifespan
│   ├── seed.py              # Idempotent demo database seeder
│   ├── seed_data.py         # Static menu items, initial floor & staff definitions
│   ├── core/
│   │   ├── permissions.py   # RBAC permission matrix (50+ actions)
│   │   ├── security.py      # Password hashing (bcrypt) & JWT issuance
│   │   ├── status_machine.py# Validated table transitions
│   │   ├── vision_engine.py # YOLO model initialization & inference
│   │   └── yolo_models.py   # Table cleanliness detector model manager
│   ├── models/              # SQLAlchemy ORM models (Audit, Bill, Order, Table, etc.)
│   ├── routers/             # 25+ API routers (ai, auth, billing, floors, tables, etc.)
│   ├── schemas/             # Pydantic camelCase request/response schemas
│   ├── services/            # Business logic:
│   │   ├── ai_service.py    # Seating suggestions, shift reports, alerts
│   │   ├── billing_service.py# Taxes, discounts, totals & bill generation
│   │   ├── chat_service.py  # Conversational floor assistant & NLU parser
│   │   ├── groq_llm.py      # Dynamic key detection & multi-provider client
│   │   └── video_sources.py # RTSP, YouTube Live & MP4 capture wrappers
│   └── workers/
│       └── camera_worker.py # Background CCTV analysis tick loop
├── camera_uploads/          # Sample restaurant CCTV video recordings
├── models/
│   ├── yolo11n.pt           # Ultralytics base detection weights
│   └── table_cleanliness_best.pt # Custom table state classifier
├── test_all_flows.py        # End-to-end user scenario testing
└── test_full_suite.py       # Comprehensive regression test suite
```

---

## 🗄️ Database & Seed Data

On application startup (`lifespan`), the system automatically runs `seed_database(db)`. The seeder is **100% idempotent**: it checks `db.get(...)` before inserting so you can restart or hot-reload without `UNIQUE constraint` errors.

### Resetting the Database
To reset the database back to clean demo data at any time:
```bash
# 1. Stop the server
# 2. Delete the SQLite database file:
rm foh.db         # Linux/macOS
Remove-Item foh.db # Windows PowerShell

# 3. Start the server (foh.db will be recreated and freshly seeded)
python -m uvicorn app.main:socket_app --host 127.0.0.1 --port 8000 --reload
```

---

## 👁️ Computer Vision Pipeline

1. **Background Worker** (`camera_worker.py`): Wakes up every `CAMERA_SCAN_INTERVAL_SECONDS` (default: 10s).
2. **Multi-Frame Sampling**: Captures 5 sample frames per table under camera authority to avoid transient glitches.
3. **ROI Bounding Box Evaluation**: Compares detected bounding boxes with the table's configured Region of Interest (ROI).
4. **Consecutive Tick Agreement**: Requires **3 consecutive ticks** to agree before changing a table's status, preventing false triggers.
5. **Enforced Safety Guard**: Tables in `BILLING` are protected from camera resets to avoid interfering with pending payments.

---

## 🤖 AI & Natural Language Processing

### Multi-Provider Architecture (`groq_llm.py`)
The system supports multiple cloud providers with automatic local fallback:
1. **Groq Cloud (Recommended)**: Ultra-fast inference on `llama-3.3-70b-versatile` with automatic fallback to `llama-3.1-8b-instant`.
2. **Google Gemini**: Uses `gemini-2.0-flash`.
3. **OpenAI / OpenRouter**: Uses `gpt-4o-mini` or custom models.
4. **Local Engine**: Instant rule-based parsing that operates without any internet connection.

### Dynamic Key Configuration (`POST /ai/configure-key`)
You can configure or update API keys at runtime without restarting the server:
- Via the frontend **FOH Assistant ⚙ drawer**.
- Or via HTTP:
```bash
curl -X POST http://127.0.0.1:8000/ai/configure-key \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"provider": "groq", "api_key": "gsk_your_key_here"}'
```

### Table Intent Parsing
Commands are parsed with high precision, ignoring prepositions:
- `"sent bill to t1"` or `"bill table 1"` ➔ Transition to `BILLING`.
- `"clean table 2"` ➔ Transition to `CLEANING`.
- `"free table 3"` or `"mark t3 available"` ➔ Transition to `AVAILABLE`.
- `"seat 4 at t2"` ➔ Seats party of 4 at Table T2.
- `"which tables are free?"` ➔ Summarizes available vs occupied tables.

---

## 📡 API Routers Catalog

All endpoints require a Bearer JWT token in the `Authorization` header, except `/auth/login`, `/health`, and `/guest/menu`.

| Router | Prefix | Key Endpoints | Description |
|:---|:---|:---|:---|
| `auth` | `/auth` | `POST /login`, `GET /me` | Authentication & token verification |
| `floors` | `/floors` | `GET /current`, `PUT /current` | Floor plan canvas layout & section zones |
| `tables` | `/tables` | `GET /`, `PATCH /{id}/status` | Table CRUD and state machine transitions |
| `sessions`| `/sessions`| `POST /seat`, `POST /{id}/close` | Dining session management & guest tracking |
| `billing` | `/billing` | `POST /bills`, `POST /bills/{id}/pay` | Itemized bills, GST, service charge, payments |
| `cashier_shifts` | `/cashier-shifts` | `POST /start`, `PATCH /{id}/end` | Drawer floats, reconciliation, discrepancies |
| `refunds` | `/refunds` | `POST /`, `PATCH /{id}/approve` | Refund requests and Manager approvals |
| `revenue` | `/revenue` | `GET /daily`, `GET /payment-methods` | Shift totals, sales analytics, breakdown |
| `ai` | `/ai` | `POST /chat`, `GET /provider`, `POST /configure-key` | FOH Assistant & dynamic AI key setup |
| `vision` | `/vision` | `GET /detections`, `POST /calibrate-roi` | Live YOLO frame analysis & ROI tuning |
| `stream` | `/stream` | `GET /{floor_id}` | Real-time annotated MJPEG camera stream |
| `guest` | `/guest` | `GET /menu?token=` | Public guest ordering menu & waiter bell |
| `ws` | `/ws` | `WS /{floor_id}?token=` | WebSocket room for real-time staff sync |

---

## 👥 Staff Roles & Permissions

| Role | Default Email | Default Password | Primary Scope |
|:---|:---|:---|:---|
| **Owner** | `owner@gmail.com` | `Owner@1234` | Full access, user management, financial reports |
| **Manager** | `manager@gmail.com` | `Manager@1234` | Shift approvals, discounts, floor layout editing |
| **Host** | `host@gmail.com` | `Host@1234` | Guest seating, reservations, waitlist |
| **Cashier** | `cashier@gmail.com` | `Cashier@1234` | Shift drawer, bill creation, payment processing |
| **Waiter** | `waiter@gmail.com` | `Waiter@1234` | Order placement, serving, bill requests |
| **Chef** | `chef@gmail.com` | `Chef@1234` | Kitchen Display System (KDS), ticket bumping |

---

## 🧪 Running Automated Tests

Run the built-in test suites from the `backend/` directory:

```bash
# 1. Run complete enterprise test suite (auth, billing, shifts, refunds, revenue, audit logs)
python test_full_suite.py

# 2. Run table NLU extraction & dynamic key persistence test
python -c "from app.services.chat_service import _extract_table_number; assert _extract_table_number('sent bill to t1') == '1'; print('NLU test: PASSED!')"
```

---

## 🔧 Common Troubleshooting

1. **`AttributeError: module 'bcrypt' has no attribute '__about__'`**
   - This is a harmless warning trapped internally by `passlib` on newer bcrypt releases; authentication continues to function correctly.
2. **`ModuleNotFoundError: No module named 'app'`**
   - Ensure you are running commands with `python -m uvicorn ...` from the `backend/` folder, or add `.` to your `PYTHONPATH`.
3. **Port 8000 is already in use**
   - In PowerShell, run:
     ```powershell
     Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process -Force
     ```

---
**FOH Backend Engine — Reliable, Fast, and Extensible.**
