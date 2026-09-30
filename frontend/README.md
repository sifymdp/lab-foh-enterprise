# FOH Table Management — Frontend UI 🎨⚡

> Modern, real-time Front-of-House web application built with **React 19**, **TypeScript**, and **Vite**.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Application Screens & Features](#application-screens--features)
- [FOH Assistant & AI Key Configuration](#foh-assistant--ai-key-configuration)
- [State Management & Real-Time Sync](#state-management--real-time-sync)
- [Environment Configuration](#environment-configuration)
- [Available NPM Scripts](#available-npm-scripts)

---

## 🌟 Overview

The frontend interface provides a clean, responsive single-page application (SPA) tailored for restaurant host stands, manager terminals, cashier registers, waiter tablets, and kitchen display stations.

- **Framework**: React 19 + TypeScript 5.7+
- **Bundler & Dev Server**: Vite 6+
- **Styling**: Vanilla CSS design system with curated HSL palettes, smooth micro-animations, and responsive layouts.
- **Real-Time Communication**: WebSocket connection to `/ws/{floor_id}` with automatic reconnection and floor state invalidation.

---

## 🚀 Quick Start

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Start development server
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## 🖥️ Application Screens & Features

1. **Interactive Floor Plan (`/floor`)**
   - High-precision SVG/HTML5 canvas with section zones (Indoor, Outdoor/Patio, Bar).
   - Real-time color-coded table statuses (`AVAILABLE`, `SEATED`, `ORDERED`, `SERVED`, `BILLING`, `PAID`, `CLEANING`).
   - Drag-and-drop table repositioning with grid snapping.
   - Quick table action panel: seat guests, place order, request bill, mark paid, call busser.
   - Live CCTV video stream popup modal (`/stream/floor-1`).

2. **FOH AI Assistant (Floating Widget `✦`)**
   - Natural language command input with multi-turn conversation support.
   - Instant action execution (e.g., *"sent bill to t1"*, *"clean table 2"*).
   - In-widget **⚙ AI Key Setup Drawer**: select Groq, Gemini, or OpenAI and activate keys directly.

3. **POS Billing & Payments (`/bills`, `/payments`)**
   - Itemized bill generation with GST and service charges.
   - Split and multi-method payments (Cash, Card, UPI, QR).
   - Cashier shift drawer reconciliation (`/cashier-shifts`).
   - Manager approval modals for discounts and refunds.

4. **Kitchen Display System (`/kds`)**
   - Live order ticket queue with station routing (Grill, Fry, Salad, Bar).
   - Real-time bump and status progression (Received ➔ Preparing ➔ Ready ➔ Served).

5. **Menu Management & Excel Import (`/menu`)**
   - Category navigation and search.
   - Excel/CSV import modal with staging diff preview and version history rollback.

---

## 🤖 FOH Assistant & AI Key Configuration

The floating assistant at the bottom right corner includes a built-in provider badge:
- **`● GROQ AI`**: Active cloud LLM inference using Llama 3.3 70B.
- **`⚡ Local Intelligence`**: High-precision local rule-based intent parsing (no API key required).

Clicking the **⚙** button opens the inline key configuration drawer. Users can paste an API key directly from their browser, click **Activate**, and start chatting immediately without touching server files or restarting services.

---

## 🔄 State Management & Real-Time Sync

- **`AuthContext`**: Manages JWT tokens, user profiles, roles (`OWNER`, `MANAGER`, `HOST`, `CASHIER`, `WAITER`, `CHEF`), and permission gates.
- **`FloorContext`**: Holds active floor plan data, table coordinates, and provides `refresh()` to sync with the backend.
- **`SocketContext`**: Maintains persistent WebSocket connection to `/ws/{floor_id}?token=...`. Automatically triggers table re-renders upon receiving `table_updated`, `bill.created`, or `ai_alert` events.

---

## ⚙️ Environment Configuration

In `frontend/.env`:

```env
VITE_API_URL=http://localhost:8000
VITE_SOCKET_URL=http://localhost:8000
VITE_USE_MOCK=false
```

---

## 📜 Available NPM Scripts

- `npm run dev`: Start local Vite development server with Hot Module Replacement (HMR).
- `npm run build`: Compile and bundle production assets with TypeScript verification.
- `npm run preview`: Locally preview the production build bundle.
- `npx tsc --noEmit`: Typecheck the entire project without emitting code.

---
**FOH Frontend — Fast, Responsive, and User-Centric.**
