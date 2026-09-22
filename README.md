# FOH Table Management

Restaurant front-of-house floor management with camera-driven table status.

A ceiling camera watches the dining room. A custom-trained YOLOv8 model reads each table as
**clean**, **dirty**, or **occupied**, and the backend turns those readings into real table
statuses — seating a table when guests arrive, flagging it for cleaning when they leave a mess,
and freeing it once it's clear. Every staff screen updates live over WebSockets.

---

## Contents

- [Features](#features)
- [Stack](#stack)
- [Quick start](#quick-start)
- [Demo logins](#demo-logins)
- [How the camera pipeline works](#how-the-camera-pipeline-works)
- [Configuration](#configuration)
- [Project structure](#project-structure)
- [API overview](#api-overview)
- [Troubleshooting](#troubleshooting)

---

## Features

- **Live floor plan** — drag-and-drop layout editor, colour-coded table statuses, real-time sync
- **Camera-driven status** — custom YOLOv8 model classifies each table's region of interest
- **ROI setup** — draw a region per table over a camera snapshot, with auto-detect assistance
- **Table lifecycle** — seven states with server-enforced legal transitions
- **Guest QR ordering** — scan-to-order menu, no app install, rotatable tokens
- **AI alerts** — dirty-table escalation and walkout ("left during billing") detection
- **Floor assistant** — chat about live floor state; works offline via a deterministic fallback
- **Role-based access** — Owner / Manager / Host / Waiter, enforced server-side
- **Reservations, sessions, billing, menu management, shift reports**

---

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.13 |
| Database | SQLite via SQLAlchemy 2.0 (PostgreSQL-ready) |
| Computer vision | Ultralytics YOLOv8 + OpenCV |
| Frontend | React 19 + TypeScript + Vite |
| Real-time | Native WebSockets |
| Auth | JWT (HS256) + bcrypt |
| LLM (optional) | Ollama, local |

---

## Quick start

### Option A — Docker (recommended)

```bash
git clone https://github.com/Laahir/FOH-table-management.git
cd FOH-table-management
docker compose up --build
```

Open **http://localhost:5173**.

First build takes several minutes (PyTorch). Later starts take seconds.

```bash
docker compose up -d        # background
docker compose logs -f      # watch camera decisions
docker compose down         # stop
```

### Option B — Run locally

**Requires Python 3.11–3.13** (see [Troubleshooting](#troubleshooting) — 3.14 will not build)
and **Node 20.19+**.

Backend:

```bash
cd backend
python3.13 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Point at the repo-root database, which holds the saved floorplan + ROIs
echo 'DATABASE_URL=sqlite:///../foh.db' > .env
echo 'CAMERA_SCAN_INTERVAL_SECONDS=10' >> .env

uvicorn app.main:app --reload
```

Frontend, in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

| Service | URL |
|---|---|
| App | http://localhost:5173 |
| API | http://localhost:8000 |
| Interactive API docs | http://localhost:8000/docs |

---

## Demo logins

Password for all accounts: **`demo1234`**

| Role | Email |
|---|---|
| Owner | `owner@foh.demo` |
| Manager | `manager@foh.demo` |
| Host | `host@foh.demo` |
| Waiter | `waiter@foh.demo` |

---

## How the camera pipeline works

The trained model ships in the repo at `backend/models/table_cleanliness_best.pt`
(classes: `clean`, `dirty`, `occupied`).

1. A background worker wakes every `CAMERA_SCAN_INTERVAL_SECONDS`.
2. For each table under camera authority it samples 5 frames from that table's source.
3. YOLO runs once per frame on the **full** frame; each detection is matched to a table by how
   much of that table's ROI rectangle it covers (default threshold: 30%).
4. The frame readings collapse into one smoothed label per table per tick.
5. A status changes only after **3 consecutive ticks agree**.

### Transitions the camera is allowed to make

| From | Camera sees | To |
|---|---|---|
| `AVAILABLE` | `occupied` ×3 | `SEATED` |
| `SEATED` | `dirty` ×3 (guests gone) | `CLEANING` |
| `SEATED` | `clean` ×3 (guests gone) | `AVAILABLE` |
| `CLEANING` | `clean` ×3 (after grace period) | `AVAILABLE` |
| `BILLING` | empty ×3 | *(alert only — status never changes)* |

### Deliberate limits

- **Payment states are untouchable.** A table in `BILLING` never changes status from the camera.
- **An unclear view is never "clean."** No ROI match means *no reading*; the previous state holds.
- **Cleaning has a grace period** (`CAMERA_CLEANING_GRACE_SECONDS`) before the camera judges.
- **Alerts are edge-triggered** — they fire once and re-arm only on a status change.

### Recorded footage

For demos, `camera_url` may point at a video file. Captures are held open between ticks and
positioned by elapsed wall-clock time, so a recording plays forward at real-time speed and loops
at the end — behaving like a live camera. Sample videos live in `backend/camera_uploads/`.

---

## Configuration

Backend settings are read from environment variables or `backend/.env`
(see `backend/.env.example`).

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./foh.db` | **Relative to the working directory** — see Troubleshooting |
| `JWT_SECRET` | `dev-secret-change-in-production` | Change for any real deployment |
| `JWT_EXPIRE_HOURS` | `8` | Token lifetime |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated |
| `CAMERA_ENABLED` | `true` | Set `false` to disable the pipeline entirely |
| `YOLO_TABLE_STATE_MODEL_PATH` | `backend/models/table_cleanliness_best.pt` | Searched relative to the backend dir too |
| `CAMERA_SCAN_INTERVAL_SECONDS` | `30` | Use `10` for demos |
| `CONSECUTIVE_SCANS_REQUIRED` | `3` | Ticks that must agree before a status changes |
| `TABLE_STATE_CONFIDENCE_THRESHOLD` | `0.25` | Minimum detection confidence |
| `CAMERA_CLEANING_GRACE_SECONDS` | `60` | Quiet period after entering `CLEANING` |
| `STREAM_ROI_MATCH_MIN_OVERLAP` | `0.3` | ROI coverage needed to match a detection |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Optional; assistant falls back without it |

Frontend (`frontend/.env`):

| Variable | Value |
|---|---|
| `VITE_API_URL` | `http://localhost:8000` |
| `VITE_SOCKET_URL` | `http://localhost:8000` |
| `VITE_USE_MOCK` | `false` |

---

## Project structure

```
backend/
  app/
    routers/      HTTP endpoints (12 routers, ~46 routes)
    services/     business logic — camera_pipeline, table, session, ai, ...
    models/       SQLAlchemy ORM models (17)
    schemas/      Pydantic request/response shapes
    core/         security, permissions, status machine, YOLO, ROI matching
    workers/      background camera scan loop
  models/         trained YOLO weights (best.pt)
  camera_uploads/ demo video sources
frontend/
  src/
    pages/        Floor, Camera Setup, Sessions, Reservations, Menu, Reports...
    components/   floor plan canvas, ROI modal, chat dock, layout
    context/      auth, floor state, socket
    api/          typed API client
compose.yaml      full stack
foh.db            demo database (floorplan + ROIs)
```

---

## API overview

Interactive docs at `/docs` when running. Highlights:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/auth/login` | Obtain JWT |
| `GET` | `/floors/current` | Floor plan with tables |
| `PATCH` | `/tables/{id}/status` | Change status (validated against the state machine) |
| `POST` | `/tables/{id}/camera/upload` | Upload a camera source for a table |
| `POST` | `/tables/{id}/camera/auto-roi` | Suggest an ROI rectangle |
| `POST` | `/tables/{id}/camera/analyze-snapshot` | Run the model on one snapshot |
| `GET` | `/stream/{floor_id}` | Annotated MJPEG live stream |
| `POST` | `/sessions/seat` | Seat a party |
| `POST` | `/ai/chat` | Ask the floor assistant |
| `GET` | `/ai/events` | Open alerts |
| `GET` | `/guest/menu?token=` | Guest QR menu (no auth) |
| `WS` | `/ws/{floor_id}?token=` | `table_updated`, `ai_alert`, `order_placed`, `payment_confirmed` |

---

## Troubleshooting

**`pip install` fails building `pydantic-core` / "PyO3's maximum supported version is 3.13"**
Your Python is 3.14. Rebuild the venv with 3.11–3.13:
```bash
rm -rf venv && python3.13 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

**Floor plan shows 10 tables with patio and bar sections**
That's the seeded demo layout — the backend couldn't find `foh.db` and created an empty one.
`DATABASE_URL` is *relative to where you launch uvicorn*, so running from `backend/` looks for
`backend/foh.db`. Point it at the repo-root database:
```bash
echo 'DATABASE_URL=sqlite:///../foh.db' > backend/.env
```
The real floorplan has **5 tables in one section**.

**`Failed to load table-state YOLO model` / `FileNotFoundError`**
`backend/models/table_cleanliness_best.pt` is missing. Note the repo's `.gitignore` excludes
`*.pt` with an explicit exception for this file — if you copied files manually, copy the
`.gitignore` too, or the weights get skipped.

**Login fails with "Invalid email or password" but the credentials are right**
The login page reports *any* failure that way, including "backend unreachable." Check
`http://localhost:8000/health` returns `{"ok":true}`. Both servers must run at once.

**Docker build downloads gigabytes of NVIDIA CUDA packages, or times out**
Torch's default wheels pull CUDA runtimes that Docker Desktop can't use. The backend Dockerfile
installs the CPU build first — make sure you're using the committed Dockerfile.

**`Bind for 0.0.0.0:8000 failed: port is already allocated`**
A local uvicorn is already running. Stop it, or stop the containers:
```bash
lsof -ti :8000 -sTCP:LISTEN | xargs kill
```

**Table statuses never change**
Restart the backend after code changes, and confirm the pipeline is alive:
```bash
docker compose logs backend | grep "Camera changed"
```
Remember an `AVAILABLE` table reading `dirty` correctly does nothing — only three consecutive
`occupied` reads promote it. See [the transition table](#transitions-the-camera-is-allowed-to-make).

**`opencv` ImportError: `libGL.so.1: cannot open shared object file`**
Ultralytics pulls non-headless opencv. In a slim image install `libgl1` and `libglib2.0-0`
(the backend Dockerfile already does).
