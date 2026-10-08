# Front-of-House (FOH) Management Platform — Architecture Documentation

## 1. System Overview

The **FOH Table Management & CCTV Intelligence System** is an enterprise-grade restaurant operational platform designed for fine dining and high-turnover restaurants. It pairs real-time floor plan orchestration, order management, dynamic role-based access control (RBAC), and cashier shift reconciliation with automated computer vision telemetry from ceiling-mounted CCTV cameras.

```
┌────────────────────────────────────────────────────────────────────────┐
│                          React 19 Frontend                             │
│  (Vite + TypeScript + HTML5 Canvas Floor Editor + WebSocket Live Sync) │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ HTTP REST & WebSocket (/ws/{floor_id})
┌──────────────────────────────────▼─────────────────────────────────────┐
│                          FastAPI Backend Core                          │
│                                                                        │
│  ┌────────────────────┐ ┌────────────────────┐ ┌────────────────────┐  │
│  │   RBAC & Security  │ │ Table Status Machine│ │  Billing & Shifts  │  │
│  │ (6 Roles, Overrides│ │ (State Graph Engine│ │ (Reconciliation,   │  │
│  │  Lockout, Sessions)│ │ BILLING Protection)│ │  Tax, Discounts)   │  │
│  └────────────────────┘ └────────────────────┘ └────────────────────┘  │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    CCTV Vision Subsystem                         │  │
│  │ (YOLO11n Person Detect + table_cleanliness_best.pt + Mismatches) │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ SQLAlchemy 2.0 ORM
┌──────────────────────────────────▼─────────────────────────────────────┐
│                       PostgreSQL Database                              │
│         (35+ Normalized Tables, Alembic Versioned Migrations)          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Modules & Responsibilities

### 2.1 Role-Based Access Control (RBAC)
- **Roles**:
  - `OWNER`: Full administrative rights, permission matrices, and financial audits.
  - `MANAGER`: Branch management, refunds approval, camera calibration, staff operations.
  - `HOST`: Table seating, reservation stand, guest intake.
  - `CASHIER`: Cash drawer, shift lifecycle, payment processing, bill settlements.
  - `WAITER`: Table order taking, service workflow, table status inspection.
  - `CHEF`: Kitchen Display System (KDS), ticket bumping, item priority.
- **Dynamic Permission Resolution**:
  Permissions are evaluated through `has_user_permission(db, user, perm)` checking:
  1. Permanent Owner override.
  2. Active time-limited temporary overrides (`TemporaryPermission`).
  3. Direct user permission overrides (`UserPermission`).
  4. Database-driven customized role permissions (`RolePermission`).
  5. Static default catalogue fallback (`ROLE_PERMISSIONS`).

### 2.2 Table Status State Machine
Tables follow a deterministic lifecycle managed in `app/core/status_machine.py`:
- `AVAILABLE` &rarr; `RESERVED` | `SEATED` | `MAINTENANCE`
- `RESERVED` &rarr; `SEATED` | `AVAILABLE`
- `SEATED` &rarr; `ACTIVE` | `AVAILABLE` | `CLEANING`
- `ACTIVE` &rarr; `BILLING` | `SEATED` | `CLEANING` | `AVAILABLE`
- `BILLING` &rarr; `CLEANING` | `ACTIVE` | `AVAILABLE`
- `CLEANING` &rarr; `AVAILABLE` | `SEATED`
- **Protection Rules**: Automated CCTV is strictly forbidden from transitioning a table out of `BILLING` state; human cashier/staff confirmation is required to avoid premature unrecorded walkouts.

### 2.3 Cashier Shift & Billing Lifecycle
- **Shift Opening**: Cashiers start shifts declaring opening till cash (float).
- **Billing Workflow**: Order Items &rarr; Bill generated &rarr; Role-limited discount applied &rarr; Payment recorded &rarr; Bill marked `PAID`.
- **Shift Reconciliation**: Cashiers declare actual cash counted. The system computes expected till balance (`Opening Float + Cash Sales - Cash Refunds`), calculates overage/shortage differences, and logs the reconciliation in `status_history` and `audit_logs`.

### 2.4 Multi-Tenancy & Data Isolation
Every core table contains `tenant_id` (foreign key to `organizations`) and optional `branch_id` (foreign key to `branches`). API dependencies automatically scope queries to ensure strict multi-tenant isolation.
