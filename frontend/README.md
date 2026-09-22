# FOH Table Management — Frontend (UI/UX Phase)

Phase 1 UI built with **React + Vite**. Uses a **mock API** (localStorage) until the FastAPI backend is connected.

## Run locally

```bash
npm install
npm run dev
```

Open http://localhost:5173

## Demo accounts

| Role    | Email              | Password  |
|---------|--------------------|-----------|
| Owner   | owner@foh.demo     | demo1234  |
| Manager | manager@foh.demo   | demo1234  |
| Host    | host@foh.demo      | demo1234  |
| Waiter  | waiter@foh.demo    | demo1234  |

## Screens

- **Login** — auth + quick role switcher
- **Floor** — Konva floor plan, color-coded status, table detail panel
- **Users** (Owner only) — list, create, activate/deactivate staff

## Role behavior

| Role    | Floor edit | Seat guests | Users |
|---------|------------|---------------|-------|
| Owner   | Yes        | Yes           | Yes   |
| Manager | Yes        | Yes           | No    |
| Host    | View only  | Yes           | No    |
| Waiter  | View only  | Yes           | No    |

## Connect backend later

1. Copy `.env.example` to `.env`
2. Set `VITE_USE_MOCK=false` and `VITE_API_URL=http://localhost:8000`
3. API client in `src/api/client.ts` already maps to planned endpoints

## Stack (aligned with Implementation Guide)

- React 19, TypeScript, Vite
- react-router-dom
- **HTML/CSS floor canvas** (absolutely positioned tables — §4.2)
- `services/tableConfig.ts` — status colours, transitions, section icons
- `SocketContext` — ready for Flask-SocketIO (`VITE_SOCKET_URL`)

## Floor plan UI

- **White realistic canvas** with grid, section zones (Indoor / Outdoor / Bar), entrance & kitchen labels
- **Circle** tables (bar) and **rectangle** tables (8px radius per guide)
- Status colours from `STATUS_CONFIG` (background + border)
- Occupancy timer on occupied tables
- Stats bar (available, occupied, occupancy %)
- **Sessions** page with filter chips

## Run on Windows (PowerShell)

If `npm` is blocked by execution policy, use:

```powershell
npm.cmd install
npm.cmd run dev
```

Or: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## Reset mock data

Clear site localStorage for `foh-mock-store` or use DevTools → Application → Local Storage, then refresh.
