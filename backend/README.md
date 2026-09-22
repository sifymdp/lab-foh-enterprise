# FOH Table Management — Backend (Phase 1)

FastAPI + SQLAlchemy REST API matching `frontend/src/api/client.ts`.

## Quick start (SQLite — no Docker)

Requires **Python 3.11–3.13** (3.14 not yet supported by all deps).

```bash
cd backend
py -3.13 -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env          # optional; SQLite is default
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## Quick start (PostgreSQL + Docker)

```bash
# From repo root
docker compose up -d

cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# Set in .env: DATABASE_URL=postgresql://foh:foh@localhost:5432/foh
uvicorn app.main:app --reload --port 8000
```

## Connect frontend

In `frontend/.env`:

```env
VITE_USE_MOCK=false
VITE_API_URL=http://localhost:8000
```

## Demo logins

| Email | Password |
|-------|----------|
| owner@foh.demo | demo1234 |
| manager@foh.demo | demo1234 |
| host@foh.demo | demo1234 |
| waiter@foh.demo | demo1234 |

## API endpoints

| Method | Path |
|--------|------|
| POST | `/auth/login` |
| GET | `/auth/me` |
| GET/PUT | `/floors/current` |
| POST | `/floors/current/reset` |
| POST | `/tables` |
| PUT | `/tables/{id}` |
| PATCH | `/tables/{id}/status` |
| DELETE | `/tables/{id}` |
| GET | `/sessions` |
| POST | `/sessions/seat` |
| POST | `/sessions/{id}/close` |
| GET | `/users` (Owner) |
| POST | `/users` (Owner) |
| PATCH | `/users/{id}/active` (Owner) |
