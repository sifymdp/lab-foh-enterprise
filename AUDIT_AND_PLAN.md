# FOH Restaurant Project - Comprehensive Audit & Implementation Plan
**Date**: 2026-08-18  
**Status**: Ready for Phase 1 Implementation

---

## 📊 EXECUTIVE SUMMARY

### ✅ GOOD NEWS
Your FOH project is **exceptionally well-architected** for the upgrades we need to add!

**What's Already Built:**
- ✅ **RBAC Framework** - 22 permissions defined, role mapping created, discount limits set
- ✅ **Billing System** - Bill, Payment, PaymentTransaction models with Stripe integration started
- ✅ **Audit Logging** - Append-only audit logs ready
- ✅ **JWT Authentication** - Token-based auth with bcrypt hashing
- ✅ **WebSocket Real-time** - Room-based broadcasting for live updates
- ✅ **Order Management** - Full order-to-payment lifecycle
- ✅ **Database Design** - SQLAlchemy with SQLite/PostgreSQL support

**What's Missing:**
- ❌ Multi-tenant architecture (CRITICAL)
- ❌ Tax & service charge calculation system
- ❌ Discount approval workflow
- ❌ AI billing intelligence (anomaly detection, risk scoring, recommendations)
- ❌ Permission enforcement in service layer
- ❌ Staff-to-table assignment system
- ❌ Frontend pages for billing dashboard & AI alerts
- ❌ Tests (zero coverage currently)

### 📈 Impact Assessment
| Component | Status | Impact on Upgrade |
|-----------|--------|-------------------|
| RBAC Framework | ✅ 80% Done | Just needs enforcement |
| Multi-tenant | ❌ 0% Done | CRITICAL - must do first |
| Billing | ⚠️ 40% Done | Bill/Payment exist, needs service layer |
| Payments | ⚠️ 30% Done | Stripe setup started, needs webhooks |
| AI Billing | ❌ 0% Done | Complete new feature |
| Tests | ❌ 0% Done | Major gap |

---

## 🏗️ CURRENT ARCHITECTURE

### Backend Stack
```
FastAPI (Python 3.10+)
  ├── SQLAlchemy 2.0 (ORM)
  ├── JWT + bcrypt (Auth)
  ├── Native WebSockets (Real-time)
  ├── YOLOv8 + OpenCV (Camera pipeline)
  └── Stripe (Payments)
```

### Existing Routers (13 total)
- ✅ auth, users, floors, tables, sessions, orders, menu
- ✅ reservations, guest, ai, ws, stream, audit

### Existing Models (16 total)
- ✅ User, Bill, Payment, PaymentTransaction, Order, OrderItem
- ✅ DiningSession, Table, Floor, Section, Menu, Reservation
- ✅ AuditLog, AIEvent, StatusHistory, Cleaning

### Database
- 📦 SQLite (demo), PostgreSQL-ready
- 📋 No migration tool (manual ALTER TABLE)
- 🔒 Proper relationships with FKs and cascades

---

## 🔍 DETAILED FINDINGS

### What Works Great

#### 1. **Authentication & JWT**
```python
# Location: backend/app/core/security.py
✅ Password hashing with bcrypt
✅ JWT with HS256 algorithm
✅ 8-hour token expiration
✅ Token validation on WS connect
```

#### 2. **Permission System (Already Designed!)**
```
PERMISSIONS DEFINED (22 total):
  billing.* (view, create, update, cancel)
  discount.* (apply, approve)
  payment.* (view, create, refund)
  ai.billing.* (view, review, override)
  user.*, table.*, floor.*, etc.

ROLE MAPPING:
  OWNER       → All permissions
  MANAGER     → 14 permissions
  SUPERVISOR  → 10 permissions
  CASHIER     → 5 permissions
  HOST        → 2 permissions
  WAITER      → 3 permissions

DISCOUNT LIMITS (Server-side):
  OWNER:       100%
  MANAGER:     30%
  SUPERVISOR:  15%
  CASHIER:     5%
  WAITER:      5%
  HOST:        0%
```

**Status**: Defined in `app/core/permissions.py` but NOT ENFORCED in routers/services yet.

#### 3. **Billing System (Partial)**
```
✅ Bill model with subtotal/total
✅ Payment model (CASH or STRIPE)
✅ PaymentTransaction for webhook idempotency
✅ Bill lifecycle (OPEN → PAID)
✅ Stripe PaymentIntent started

❌ Missing: Bill service layer
❌ Missing: Tax calculation
❌ Missing: Service charge calculation
❌ Missing: Discount model
❌ Missing: Discount approval workflow
```

#### 4. **Audit Logging**
```python
# Location: backend/app/models/audit_log.py
✅ Append-only audit trail
✅ Tracks user, action, resource, old/new values
✅ JSON serialization for complex data
✅ Service function: log_action()
✅ No update/delete endpoints (immutable)
```

#### 5. **WebSocket Real-time**
```python
# Location: backend/app/socket_manager.py
✅ Room-based broadcasting (by floor_id)
✅ Async-safe emit from threadpool code
✅ JWT authentication
✅ Events: table_updated, ai_alert, order_placed, payment_confirmed

Ready to extend with:
  - PAYMENT_SUCCESS, PAYMENT_FAILED
  - AI_ANOMALY_DETECTED, DISCOUNT_APPROVED
  - And more custom events
```

#### 6. **Order & Session Lifecycle**
```python
✅ DiningSession.status tracks full flow
✅ Order items with unit_price, quantity
✅ Bill generation from served items
✅ Bill mark-paid endpoint
```

---

### Critical Gaps

#### 1. **MULTI-TENANT ARCHITECTURE** ⚠️ CRITICAL
```
PROBLEM: No tenant/organization isolation
- Restaurant A can access Restaurant B's data
- No tenant_id in queries
- Security vulnerability

REQUIRED CHANGES:
  1. Create Organization model
  2. Create Branch model
  3. Add tenant_id to ALL tables
  4. Scope all queries to tenant_id
  5. Add organization/branch management APIs
  6. Update JWT to include tenant_id
  
ESTIMATED: 2-3 days
RISK: High (touches all tables)
```

#### 2. **TAX & SERVICE CHARGE SYSTEM**
```
PROBLEM: Bill has only subtotal and total
- No tax_amount field
- No service_charge_amount field
- No tax rule configuration
- Hard-coded rates not possible

REQUIRED CHANGES:
  1. Create TaxRule model
  2. Create ServiceCharge model
  3. Add tax_amount, service_charge_amount to Bill
  4. Enhance Bill model with rule_ids (for reproducibility)
  5. Create billing calculation engine
  6. API for managing tax/service charge rules
  
ESTIMATED: 1-2 days
```

#### 3. **DISCOUNT APPROVAL WORKFLOW**
```
PROBLEM: Discount permissions exist but not implemented
- No Discount model
- No DiscountApproval model
- No workflow for approvals
- Discount limits not enforced

REQUIRED CHANGES:
  1. Create Discount model
  2. Create DiscountApproval model
  3. Implement discount request → approval workflow
  4. Enforce RBAC limits in billing service
  5. Add approval endpoints
  
ESTIMATED: 1-2 days
```

#### 4. **AI BILLING INTELLIGENCE** (Completely Missing)
```
REQUIRED NEW FEATURES:
  1. BillingAnomaly model
  2. Isolation Forest anomaly detector
  3. Risk scoring system
  4. Discount recommendation engine
  5. API endpoints for AI billing
  6. Manager dashboard
  
ESTIMATED: 2-3 days
```

#### 5. **PERMISSION ENFORCEMENT**
```
PROBLEM: Permissions defined but not checked
- Permission system exists in core/permissions.py
- Not enforced in any router or service
- RBAC is purely declarative

REQUIRED CHANGES:
  1. Create permission checking decorator
  2. Add permission checks to all routers
  3. Add permission validation in services
  4. Implement scope checks (tenant, branch, table)
  
ESTIMATED: 1-2 days
```

#### 6. **STAFF-TABLE ASSIGNMENT**
```
MISSING: No way to assign waiters to tables
- Waiters can't be restricted to specific tables
- No section-based access control
- Affects RBAC scope

REQUIRED CHANGES:
  1. Create StaffTableAssignment model
  2. Add APIs for assignment management
  3. Implement query scoping based on assignments
  
ESTIMATED: 1 day
```

#### 7. **TESTS**
```
CURRENT: Zero tests
  - No unit tests
  - No integration tests
  - No test fixtures
  - No pytest configuration

REQUIRED:
  - Test coverage > 80%
  - RBAC tests
  - Billing tests
  - Payment tests
  - AI tests
  - Tenant isolation tests
  
ESTIMATED: 2-3 days
```

---

## 📋 API ENDPOINTS INVENTORY

### Implemented (Working)
```
POST   /auth/login
GET    /auth/me
GET    /users
GET    /floors
GET    /tables
PUT    /tables/{id}
POST   /sessions/seat
GET    /sessions
POST   /sessions/{id}/close
POST   /sessions/{id}/request-bill     ← Creates Bill
POST   /sessions/{id}/mark-paid        ← Marks Bill PAID
GET    /sessions/{id}/bill
POST   /orders
GET    /orders
GET    /menu
GET    /reservations
GET    /ai
GET    /ws (info)
WS     /ws/{floor_id}
GET    /audit (implied)
```

### Missing (Required)
```
POST   /organizations                    (create org)
GET    /organizations                    (list orgs)
POST   /branches/{org_id}                (create branch)
GET    /branches                         (list branches)

GET    /bills                            (list with filters)
GET    /bills/{bill_id}                  (details with calculations)
POST   /bills/{id}/discount              (apply or request)
POST   /bills/{id}/cancel
POST   /bills/{id}/refund

GET    /discounts/pending                (approval queue)
POST   /discounts/{id}/approve
POST   /discounts/{id}/reject

POST   /billing/tax-rules                (create)
GET    /billing/tax-rules                (list)
PUT    /billing/tax-rules/{id}           (update)

POST   /billing/service-charges          (create)
GET    /billing/service-charges          (list)

POST   /payments/webhook                 (Stripe)
GET    /payments/{id}/refund

GET    /ai/billing/anomalies             (list detected)
GET    /ai/billing/{bill_id}/risk-score  (details)
POST   /ai/billing/{bill_id}/review      (mark reviewed)
GET    /ai/billing/{bill_id}/discount-recommendation
GET    /ai/billing/stats                 (analytics)
```

---

## 🗄️ DATABASE SCHEMA - NEW TABLES REQUIRED

### Organization & Tenant
```sql
CREATE TABLE organizations (
  id VARCHAR(64) PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  email VARCHAR(255),
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE branches (
  id VARCHAR(64) PRIMARY KEY,
  organization_id VARCHAR(64) NOT NULL,
  name VARCHAR(120) NOT NULL,
  address TEXT,
  city VARCHAR(120),
  currency VARCHAR(3) DEFAULT 'USD',
  created_at TIMESTAMP,
  FOREIGN KEY (organization_id) REFERENCES organizations(id)
);
```

### Billing Enhancements
```sql
ALTER TABLE bills ADD COLUMN tenant_id VARCHAR(64);
ALTER TABLE bills ADD COLUMN branch_id VARCHAR(64);
ALTER TABLE bills ADD COLUMN discount_amount DECIMAL(10,2) DEFAULT 0;
ALTER TABLE bills ADD COLUMN discount_reason VARCHAR(255);
ALTER TABLE bills ADD COLUMN discount_user_id VARCHAR(64);
ALTER TABLE bills ADD COLUMN tax_amount DECIMAL(10,2) DEFAULT 0;
ALTER TABLE bills ADD COLUMN service_charge_amount DECIMAL(10,2) DEFAULT 0;
ALTER TABLE bills ADD COLUMN tax_rule_id VARCHAR(64);
ALTER TABLE bills ADD COLUMN service_charge_rule_id VARCHAR(64);

CREATE TABLE tax_rules (
  id VARCHAR(64) PRIMARY KEY,
  tenant_id VARCHAR(64) NOT NULL,
  branch_id VARCHAR(64),
  tax_name VARCHAR(120),
  tax_rate DECIMAL(5,4),
  is_active BOOLEAN DEFAULT TRUE,
  effective_from TIMESTAMP,
  effective_to TIMESTAMP,
  created_at TIMESTAMP,
  FOREIGN KEY (tenant_id) REFERENCES organizations(id),
  FOREIGN KEY (branch_id) REFERENCES branches(id)
);

CREATE TABLE service_charges (
  id VARCHAR(64) PRIMARY KEY,
  tenant_id VARCHAR(64) NOT NULL,
  branch_id VARCHAR(64),
  charge_name VARCHAR(120),
  charge_percent DECIMAL(5,4),
  is_active BOOLEAN DEFAULT TRUE,
  effective_from TIMESTAMP,
  effective_to TIMESTAMP,
  created_at TIMESTAMP
);

CREATE TABLE discounts (
  id VARCHAR(64) PRIMARY KEY,
  bill_id VARCHAR(64) NOT NULL,
  tenant_id VARCHAR(64) NOT NULL,
  branch_id VARCHAR(64),
  user_id VARCHAR(64),
  discount_type VARCHAR(20),
  discount_value DECIMAL(10,2),
  reason TEXT,
  approval_status VARCHAR(20),
  approval_user_id VARCHAR(64),
  approval_reason TEXT,
  approval_at TIMESTAMP,
  created_at TIMESTAMP,
  FOREIGN KEY (bill_id) REFERENCES bills(id),
  FOREIGN KEY (tenant_id) REFERENCES organizations(id)
);

CREATE TABLE billing_anomalies (
  id VARCHAR(64) PRIMARY KEY,
  bill_id VARCHAR(64) NOT NULL,
  tenant_id VARCHAR(64) NOT NULL,
  branch_id VARCHAR(64),
  risk_score INTEGER,
  risk_level VARCHAR(20),
  anomaly_type VARCHAR(80),
  reasons TEXT,
  features TEXT,
  model_version VARCHAR(20),
  review_status VARCHAR(20),
  reviewed_by VARCHAR(64),
  review_reason TEXT,
  reviewed_at TIMESTAMP,
  created_at TIMESTAMP,
  FOREIGN KEY (bill_id) REFERENCES bills(id),
  FOREIGN KEY (tenant_id) REFERENCES organizations(id)
);
```

---

## 🚀 IMPLEMENTATION ROADMAP

### Phase 1: Multi-Tenant Foundation (Days 1-3)
```
Priority: CRITICAL (must do first)
Impact: All subsequent work depends on this
Risk: High (schema changes)

Tasks:
  ✓ Create Organization & Branch models
  ✓ Add tenant_id, branch_id to all tables
  ✓ Create tenant context dependency injection
  ✓ Update JWT to include tenant_id
  ✓ Scope all queries to tenant
  ✓ Create org/branch management APIs

Files: 15+
Changes: Deep (touches all models)

Result: Multi-tenant isolation working, all existing features still work
```

### Phase 2: RBAC Enforcement (Days 4-5)
```
Priority: HIGH (core security)
Impact: Protects sensitive operations
Risk: Medium (adds validation)

Tasks:
  ✓ Create permission checking utilities
  ✓ Add @require_permission decorators to routers
  ✓ Add validation in service layer
  ✓ Implement scope checking (staff-table access)
  ✓ Create audit logging hooks

Files: 20+
Changes: Moderate (add checks everywhere)

Result: Permissions enforced at router + service level
```

### Phase 3: Billing System (Days 6-8)
```
Priority: HIGH (core revenue system)
Impact: Enables discounts, tax, service charge
Risk: High (financial logic)

Tasks:
  ✓ Create TaxRule model
  ✓ Create ServiceCharge model
  ✓ Create Discount & DiscountApproval models
  ✓ Implement billing calculation engine
  ✓ Create billing service layer
  ✓ Implement discount workflow
  ✓ API endpoints for discount/tax/service charge

Files: 10+
Changes: Moderate (new models + service)

Result: Complete billing system with tax, service charge, discounts
```

### Phase 4: Payment Integration (Day 9)
```
Priority: MEDIUM (already partially done)
Impact: Enables real payments
Risk: Medium (external dependency)

Tasks:
  ✓ Implement Stripe webhook signature validation
  ✓ Create payment webhook handler
  ✓ Ensure idempotent webhook processing
  ✓ Real-time WebSocket updates on payment events

Files: 3-4
Changes: Small (complete existing work)

Result: Production-ready Stripe integration
```

### Phase 5: AI Billing Intelligence (Days 10-12)
```
Priority: HIGH (differentiator feature)
Impact: Fraud detection, risk alerts
Risk: Medium (ML integration)

Tasks:
  ✓ Create BillingAnomaly model
  ✓ Implement Isolation Forest detector
  ✓ Implement risk scoring
  ✓ Implement discount recommendation
  ✓ API endpoints
  ✓ Manager dashboard data

Files: 5-7
Changes: Moderate (new services + ML)

Result: AI-powered fraud detection working
```

### Phase 6: Testing (Days 13-14)
```
Priority: HIGH (quality assurance)
Impact: Confidence in production
Risk: Low (additive)

Tasks:
  ✓ Write unit tests for all services
  ✓ Write integration tests for workflows
  ✓ Write E2E tests for critical paths
  ✓ Security tests (tenant isolation)
  ✓ Target > 80% coverage

Files: 20+
Changes: Additive only

Result: Comprehensive test suite
```

### Phase 7: Frontend Pages (Days 13-14, parallel)
```
Priority: MEDIUM (UI layer)
Impact: User experience
Risk: Low (isolated)

Tasks:
  ✓ BillingPage (list, details, actions)
  ✓ AIBillingDashboard (anomalies, alerts)
  ✓ DiscountApprovalPage (approval queue)
  ✓ AuditLogPage (compliance)
  ✓ OrganizationManagement
  ✓ Context/hooks for state management

Files: 15+
Changes: Additive only

Result: Complete UI for new features
```

### Phase 8: Docker & Deployment (Day 15)
```
Priority: MEDIUM (operational)
Impact: Production readiness
Risk: Low (configuration)

Tasks:
  ✓ Add PostgreSQL to docker-compose
  ✓ Add Redis to docker-compose
  ✓ Update .env.example with all variables
  ✓ Create migration scripts
  ✓ Add health checks
  ✓ Document setup

Files: 3-4
Changes: Configuration

Result: Production-ready deployment setup
```

---

## 📊 EFFORT ESTIMATE

```
Total: 12-15 days (full-time)
       3-4 weeks (part-time)

Per Phase:
  Phase 1 (Foundation):   2-3 days (CRITICAL)
  Phase 2 (RBAC):         1-2 days
  Phase 3 (Billing):      2-3 days
  Phase 4 (Payments):     1 day
  Phase 5 (AI):           2-3 days
  Phase 6 (Tests):        2-3 days
  Phase 7 (Frontend):     2 days (can be parallel)
  Phase 8 (Docker):       1 day

Risk Areas:
  - Phase 1: Multi-tenant schema migration (HIGH RISK)
  - Phase 5: ML model training on real data (MEDIUM RISK)
  - Phase 6: Test coverage for security (MEDIUM RISK)

Quick Wins:
  - Payment webhook completion (already started)
  - Permission enforcement (already defined)
  - Audit logging (already implemented)
```

---

## ✅ SUCCESS CRITERIA

Each phase is complete when:
1. All code is written and committed
2. All tests pass (if applicable)
3. No existing FOH functionality is broken
4. Code review completed
5. Documentation updated

### Final Acceptance Criteria
```
✅ User login with JWT and multi-tenant context
✅ Tenant isolation enforced on all queries
✅ RBAC permissions checked on all operations
✅ Tax/service charge calculated correctly on bills
✅ Discount workflow enforced with approvals
✅ Payment webhook processing idempotently
✅ AI anomaly detection working in real-time
✅ Manager dashboard displaying all new data
✅ Audit logs recording all actions
✅ All tests passing (> 80% coverage)
✅ Docker-compose running all services
✅ Existing FOH features all working
✅ No data leaks between tenants
✅ No SQL injection vulnerabilities
✅ No unauthorized API access
```

---

## 📁 FILES TO CREATE/MODIFY

### Phase 1 (Multi-Tenant)
**Create (8 files):**
- `models/organization.py`
- `models/branch.py`
- `services/tenant_service.py`
- `core/tenant_context.py`
- `routers/organizations.py`
- `routers/branches.py`
- `schemas/organization.py`
- `schemas/branch.py`

**Modify (11 files):**
- All `models/*.py` (add tenant_id, branch_id)
- `core/security.py` (JWT with tenant)
- `core/deps.py` (tenant context)
- `database.py` (migrations)
- `config.py` (.env vars)

### Phase 2 (RBAC)
**Create (1 file):**
- `core/rbac.py` (decorators)

**Modify (15+ files):**
- All `routers/*.py` (add permission checks)
- All `services/*.py` (add validation)

### Phase 3 (Billing)
**Create (5 files):**
- `models/discount.py`
- `models/tax_rule.py`
- `models/service_charge.py`
- `services/billing_service.py`
- `routers/billing.py`

**Modify (3 files):**
- `models/bill.py` (enhance)
- `schemas/billing.py` (new)
- `routers/sessions.py` (use billing service)

### Phase 4 (Payments)
**Create (2 files):**
- `services/payment_service.py`
- `core/stripe_utils.py`

**Modify (2 files):**
- `routers/payments.py` (new endpoints)
- `config.py` (Stripe env vars)

### Phase 5 (AI)
**Create (4 files):**
- `models/billing_anomaly.py`
- `ml/billing_anomaly_detector.py`
- `ml/risk_scorer.py`
- `services/ai_billing_service.py`

**Modify (1 file):**
- `routers/ai_billing.py` (new)

### Phase 6 (Tests)
**Create (15+ files):**
- `tests/conftest.py`
- `tests/test_*.py` (unit tests)
- `tests/fixtures/*.py`

### Phase 7 (Frontend)
**Create (15+ files):**
- `components/billing/*.tsx`
- `components/ai-billing/*.tsx`
- `pages/BillingPage.tsx`
- `pages/AIBillingPage.tsx`
- `context/BillingContext.tsx`
- etc.

### Phase 8 (Docker)
**Modify (2-3 files):**
- `docker-compose.yml`
- `.env.example`
- `.env.production` (docs only)

---

## 🎯 NEXT STEPS

### Immediate (Today)
1. ✅ Review this audit report
2. ✅ Confirm you want to proceed with all 8 phases
3. ✅ Identify any priorities or constraints
4. ⏭️ Start Phase 1: Multi-Tenant Foundation

### Phase 1 Kickoff
1. Create Organization & Branch models
2. Add migrations for tenant_id, branch_id
3. Create tenant context dependency
4. Update JWT to include tenant info
5. Scope all queries
6. Test with existing users

### Rules for Success
```
1. DO NOT break existing FOH functionality
2. DO commit after each small feature
3. DO write tests as you go
4. DO document your changes
5. DO NOT hardcode secrets
6. DO NOT trust frontend for calculations
7. DO use WebSocket for real-time updates
8. DO scope all queries to tenant
```

---

## 📞 Questions?

### Current Architecture Questions
- Do you want to keep SQLite for dev or upgrade to PostgreSQL immediately?
- Should we migrate existing demo data or start fresh?
- Do you need backward compatibility with existing API clients?

### Feature Questions
- Should AI billing be real-time or batch processing?
- Do you need multiple organizations right away or just the foundation?
- Should discount approvals go to specific users or a queue?

### Timeline Questions
- Can you dedicate full-time for 2 weeks?
- Or should we spread this over 4 weeks part-time?
- Any hard deadlines?

---

## 📚 AUDIT DOCUMENTS

Complete audit details saved to:
- `/memories/session/foh_audit_report.md` - Detailed findings
- `/memories/session/implementation_plan.md` - Step-by-step guide

**This summary**:
- `/lab-foh-main sample/AUDIT_AND_PLAN.md` (this file)

Ready to start Phase 1? Let me know!
