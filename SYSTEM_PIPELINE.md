# FOH Enterprise System Pipeline Architecture 🏗️⚡

This document provides a comprehensive end-to-end technical blueprint of the pipelines running across the **FOH Table Management Enterprise** platform. It details data flow, processing stages, decision logic, security guardrails, and real-time synchronization mechanisms.

---

## 📑 Table of Contents

1. [High-Level System Pipeline Architecture](#1-high-level-system-pipeline-architecture)
2. [Computer Vision & CCTV Intelligence Pipeline](#2-computer-vision--cctv-intelligence-pipeline)
3. [Natural Language AI Operating Layer Pipeline](#3-natural-language-ai-operating-layer-pipeline)
4. [Zero-Trust Financial Firewall (6-Layer Isolation Architecture)](#4-zero-trust-financial-firewall-6-layer-isolation-architecture)
5. [Real-Time WebSocket Synchronization Pipeline](#5-real-time-websocket-synchronization-pipeline)
6. [KDS, Order Lifecycle & Dining Session Pipeline](#6-kds-order-lifecycle--dining-session-pipeline)
7. [High-Concurrency Database Engine & Concurrency Pipeline](#7-high-concurrency-database-engine--concurrency-pipeline)

---

## 1. High-Level System Pipeline Architecture

The platform operates across four primary real-time pipelines:

```mermaid
flowchart TB
    subgraph Ingestion["1. Multi-Modal Ingestion"]
        UI["Web / Mobile Staff Client"]
        Guest["Guest Mobile (QR Scan)"]
        CCTV["CCTV RTSP / Video Stream"]
        LLM_User["Natural Language Voice / Chat"]
    end

    subgraph Security["2. Security & Policy Layer"]
        AUTH["JWT Auth & RBAC (6 Roles)"]
        FIREWALL["6-Layer Financial Isolation Firewall"]
        IMPORT_GUARD["Import Boundary Hard Enforcement"]
    end

    subgraph Processing["3. Core Processing Pipelines"]
        CV_PIPE["YOLO11 Vision & ROI Pipeline<br/>(Occupancy / Cleanliness / Mismatch)"]
        AI_PIPE["OpenRouter Multi-Model Router<br/>(Primary, Vision, Decision, Fallback)"]
        POS_PIPE["POS State Machine & Dining Sessions<br/>(Available -> Seated -> Billing -> Cleaning)"]
        KDS_PIPE["KDS Station Routing & Order Flow"]
    end

    subgraph DataSync["4. Persistence & Real-Time Sync"]
        DB[("SQLite WAL Engine<br/>(PRAGMA journal_mode=WAL)")]
        WS_HUB["WebSocket Hub (/ws/{floor_id})"]
        AUDIT["Immutable AI Audit Log (AIAuditEvent)"]
    end

    UI --> AUTH
    Guest --> AUTH
    LLM_User --> AUTH
    CCTV --> CV_PIPE

    AUTH --> FIREWALL
    FIREWALL --> AI_PIPE
    AUTH --> POS_PIPE
    AUTH --> KDS_PIPE

    CV_PIPE --> POS_PIPE
    CV_PIPE --> WS_HUB
    AI_PIPE --> WS_HUB
    AI_PIPE --> AUDIT
    POS_PIPE --> DB
    POS_PIPE --> WS_HUB
    KDS_PIPE --> DB
    KDS_PIPE --> WS_HUB
```

---

## 2. Computer Vision & CCTV Intelligence Pipeline

The vision pipeline ingests live video streams, identifies physical table zones, evaluates table states using deep learning, detects mismatches against the POS system, and triggers loss prevention alerts.

```mermaid
sequenceDiagram
    autonumber
    participant Camera as RTSP / Camera Capture
    participant Worker as Camera Worker (Interval 10s)
    participant Engine as YOLO11 Vision Engine
    participant Classifier as Cleanliness Classifier
    participant Mismatch as Mismatch & Walkout Service
    participant Hub as WebSocket Hub
    participant DB as SQLite (WAL)

    Camera->>Worker: Provide frame buffer
    Worker->>Engine: Run object detection (person, dishes, bottles)
    Engine-->>Worker: Bounding boxes & confidence scores
    
    loop For each Table ROI
        Worker->>Classifier: Crop table ROI & classify cleanliness
        Classifier-->>Worker: State (CLEAN / DIRTY / OCCUPIED) + confidence
        Worker->>DB: Persist VisionObservation record
    end

    Worker->>Mismatch: Compare Vision State with DB Table Status
    alt Discrepancy Detected (e.g. Vision=OCCUPIED, POS=AVAILABLE)
        Mismatch->>DB: Log AIMismatchEvent
        Mismatch->>Hub: Broadcast 'table_mismatch' alert to staff
    else Walkout Risk (Vision=VACANT, POS=BILLING without payment)
        Mismatch->>DB: Log Walkout Incident with evidence snapshot
        Mismatch->>Hub: Broadcast 'walkout_alert' to manager / host
    end

    Worker->>Hub: Broadcast updated floor frame / telemetry
```

### Vision Pipeline Stages:
1. **Frame Capture & Non-blocking Ingestion (`camera_utils.py`)**:
   - Ingests RTSP feeds, webcams, or pre-recorded MP4 video streams.
   - Employs wall-clock seeking for recorded test files to ensure simulated CCTV mirrors real elapsed time.
   - Protected with bounded acquisition locks (`timeout=1.0s`) to prevent worker deadlock during camera disconnects.
2. **Object Detection (`yolo11n.pt`)**:
   - Detects diners, waitstaff, glasses, plates, and cutleries in the frame with normalized coordinates.
3. **Region of Interest (ROI) Mapping**:
   - Projects normalized table bounding polygons calibrated in the Floor Plan Editor over detection coordinates using Intersection-over-Union (IoU).
4. **Table State Classification (`table_cleanliness_best.pt`)**:
   - High-precision secondary CNN specifically trained on restaurant table states:
     - `CLEAN`: Sanitized table, zero tableware, chairs tucked.
     - `OCCUPIED`: Diners present, active dining.
     - `DIRTY`: Diners departed, unbussed plates and glasses remaining.
5. **Operational Mismatch Engine (`mismatch_service.py`)**:
   - Cross-checks vision truth with system status:
     - *Vision says Occupied, but System says Available* $\rightarrow$ **Ghost Seating Alert**.
     - *Vision says Clean, but System says Cleaning* $\rightarrow$ **Auto-Turnover Prompt**.
     - *Vision says Empty, but System says Billing (unpaid)* $\rightarrow$ **Walkout Anomaly Trigger**.

---

## 3. Natural Language AI Operating Layer Pipeline

The Natural Language AI Operating Layer empowers Owners and Managers to control front-of-house operations, query operational metrics, and inspect camera anomalies through natural conversation.

```mermaid
flowchart TD
    User["Owner / Manager Chat Query"] --> Auth["Auth Check (ai.assistant.use)"]
    Auth --> L1["L1 Financial Firewall Check"]
    
    L1 -- Financial Term Detected --> Refuse["Return Safe Refusal Text<br/>(ZERO Billing Data Access)"]
    
    L1 -- Operational Query --> DateRes["Deterministic Date Resolver<br/>(Prevents Hallucinated Dates)"]
    DateRes --> Policy["Policy Engine Classification<br/>(Floor, Staff, Vision, KDS, Shift)"]
    
    Policy --> Router["Model Router (OpenRouter Multi-Model)"]
    Router --> Primary{"Primary Model<br/>Available?"}
    
    Primary -- Yes --> ModelRun["Execute Model Inference"]
    Primary -- No / Rate Limit --> Fallback["Fallback Chain<br/>(Llama 3.3 70B / Claude / GPT)"]
    Fallback --> ModelRun

    ModelRun -- Tool Call Required --> ToolExec["Tool Registry & Sanitized Adapters"]
    ToolExec --> Adapter["Sanitized Database Adapters<br/>(extra='forbid', Zero Financial Fields)"]
    Adapter --> L4Scan["L4 Egress & Response Scanner"]
    L4Scan --> ModelRun

    ModelRun -- Final Response --> OutVal["Output & Route Validator"]
    OutVal --> ActionGen["Attach Validated UI Actions<br/>(e.g., NAVIGATE /floor, /camera-setup)"]
    ActionGen --> Redactor["L6 Persistence Redactor"]
    Redactor --> AuditDB[("Persist AIAuditEvent")]
    ActionGen --> Response["Send Response to UI Widget"]
```

### AI Pipeline Stages:
1. **RBAC & Permission Check**:
   - Enforces `PERM_AI_ASSISTANT_USE` (`ai.assistant.use`). Requires `OWNER` or `MANAGER` role.
2. **L1 Request Firewall**:
   - Intercepts prompts before LLM dispatch. If queries touch revenue, bills, cashier drawers, payments, taxes, or tips, the request is immediately rejected with standard refusal text.
3. **Deterministic Date Resolution (`resolve_date_expression`)**:
   - Converts natural language temporal terms (*"today"*, *"yesterday"*, *"last night"*, *"this shift"*) into exact UTC timestamps, eliminating LLM time hallucinations.
4. **Multi-Model Routing via OpenRouter (`model_router.py`)**:
   - **Primary Model**: Versatile conversational reasoning (`deepseek/deepseek-chat`, `anthropic/claude-3.5-sonnet`).
   - **Vision Model**: Multimodal image & camera analysis (`google/gemini-flash-1.5`, `openai/gpt-4o`).
   - **Decision Model**: Fast classification and routing (`openai/gpt-4o-mini`).
   - **Fallback Chain**: Automatic, seamless failover if OpenRouter returns 429, 500, or timeout.
5. **Sanitized Adapters & Tool Execution**:
   - The AI interacts strictly with `sanitized_adapters.py`. Pydantic models forbid all billing/monetary attributes.
6. **L4 Egress Scanner & Route Allowlist Validation**:
   - Scans tool results and model outputs for accidental leaks.
   - Validates generated UI actions against a strict allowlist (`/floor`, `/camera-setup`, `/orders`, `/reservations`).
7. **L6 Audit Redaction & Persistence**:
   - Sanitizes parameters and persists immutable records in `AIAuditEvent`.

---

## 4. Zero-Trust Financial Firewall (6-Layer Isolation Architecture)

To guarantee that proprietary financial, billing, payment, and revenue information is never exposed to the AI model or chat logs, the platform implements a defense-in-depth, 6-layer architectural firewall:

```mermaid
graph LR
    subgraph L1_to_L3["Ingress & Code Boundaries"]
        L1["Layer 1: Request Firewall<br/>(Regex & Keyword Block)"]
        L2["Layer 2: RBAC & Policy Guard<br/>(Permission Enforcement)"]
        L3["Layer 3: Import Boundary Guard<br/>(Hard Runtime Model Isolation)"]
    end

    subgraph L4_to_L6["Execution & Storage Boundaries"]
        L4["Layer 4: Sanitized Adapters<br/>(Pydantic extra='forbid')"]
        L5["Layer 5: Egress Scanner<br/>(Financial Token Scrubbing)"]
        L6["Layer 6: Persistence Redactor<br/>(Safe Audit Logging)"]
    end

    L1 --> L2 --> L3 --> L4 --> L5 --> L6
```

| Layer | Component | Mechanism | Guarantee |
|:---|:---|:---|:---|
| **L1** | `financial_firewall.py` | Regex pattern matching on incoming prompts for 8 financial categories | Refuses financial prompts immediately without calling LLMs |
| **L2** | `policy_engine.py` | RBAC permission validation & request categorization | Blocks unauthorized roles from triggering privileged actions |
| **L3** | `import_guard.py` | AST/module inspection asserting zero billing imports in AI packages | Prevents any developer from accidentally importing `Bill`, `Payment`, etc. |
| **L4** | `sanitized_adapters.py` | Custom DB adapters with Pydantic `extra="forbid"` models | Only outputs counts, occupancy rates, and operational timestamps |
| **L5** | `egress_scanner.py` | Token & regex scanning on tool outputs and raw model responses | Catches and redacts accidental monetary values before returning to client |
| **L6** | `redactor.py` | Recursive dictionary masking on payloads stored in `AIAuditEvent` | Ensures database logs never store sensitive credentials or monetary numbers |

---

## 5. Real-Time WebSocket Synchronization Pipeline

The real-time synchronization pipeline maintains sub-50ms floor state consistency across all connected host stands, server tablets, manager dashboards, and cashier terminals.

```mermaid
sequenceDiagram
    autonumber
    participant Client as Frontend Client (React)
    participant Socket as WebSocket Route (/ws/{floor_id})
    participant Room as Room Hub Manager
    participant StateMachine as Table Status Machine
    participant DB as SQLite DB (WAL)

    Client->>Socket: Connect with JWT (?token=...)
    Socket->>Room: Register connection in floor_id room
    Room-->>Client: Connection ACK & current floor state

    Note over Client,StateMachine: Staff action (e.g. Waiter marks Table 4 as 'CLEANING')
    Client->>StateMachine: PATCH /tables/4/status {status: 'CLEANING'}
    StateMachine->>StateMachine: Validate transition (PAID -> CLEANING: Legal)
    StateMachine->>DB: Commit table update (WAL mode)
    StateMachine->>Room: Broadcast 'table_status_changed' event
    
    par Multi-client Broadcast
        Room->>Client: Emit event to Waiter Tablet
        Room->>Client: Emit event to Host Stand
        Room->>Client: Emit event to Manager Dashboard
    end
```

---

## 6. KDS, Order Lifecycle & Dining Session Pipeline

The dining session pipeline tracks guests from greeting to departure, synchronizing kitchen preparation tickets with table turnover.

```mermaid
stateDiagram-v2
    [*] --> AVAILABLE: Table Clean & Ready

    AVAILABLE --> SEATED: Host seats party (POST /sessions/seat)
    SEATED --> ORDERED: Waiter / QR Order placed
    
    state ORDERED {
        [*] --> TicketCreated
        TicketCreated --> GrillStation: Station Routing
        TicketCreated --> FryStation: Station Routing
        TicketCreated --> BarStation: Station Routing
        GrillStation --> Cooked: Chef Bump
        FryStation --> Cooked: Chef Bump
        BarStation --> Cooked: Bartender Bump
        Cooked --> [*]
    }

    ORDERED --> SERVED: Waiter delivers all dishes
    SERVED --> BILLING: Guest requests bill (Waiter / QR Bell)
    BILLING --> PAID: Cashier processes payment
    PAID --> CLEANING: Busser alerted for turnover
    CLEANING --> AVAILABLE: Table sanitized & inspected

    BILLING --> WalkoutAlert: Camera detects empty table before payment
```

---

## 7. High-Concurrency Database Engine & Concurrency Pipeline

To eliminate SQLite concurrency bottlenecks and deadlocks on Windows systems, the backend utilizes an optimized Write-Ahead Logging (WAL) architecture:

```mermaid
flowchart TD
    subgraph Readers["Concurrent Readers (Non-Blocking)"]
        R1["Health Checks (/health)"]
        R2["Floor State API (/floors/current)"]
        R3["AI Sanitized Adapters"]
        R4["KDS Ticket Viewers"]
    end

    subgraph Writers["Serialized Writers"]
        W1["Order Placement"]
        W2["POS Payment Checkout"]
        W3["Camera Worker Observations"]
    end

    subgraph Engine["SQLite Engine (WAL Mode)"]
        PRAGMA1["PRAGMA journal_mode=WAL"]
        PRAGMA2["PRAGMA synchronous=NORMAL"]
        PRAGMA3["PRAGMA busy_timeout=15000"]
        
        WAL_FILE[("foh.db-wal<br/>(Write-Ahead Log)")]
        MAIN_DB[("foh.db<br/>(Main Database)")]
    end

    Readers -->|Read unblocked| MAIN_DB
    Readers -->|Read unblocked| WAL_FILE
    Writers -->|Append writes| WAL_FILE
    WAL_FILE -. Checkpoint .-> MAIN_DB
```

### Key Concurrency Configurations:
- **`PRAGMA journal_mode=WAL`**: Allows infinite simultaneous readers while a write is occurring. Readers never block writers, and writers never block readers.
- **`PRAGMA synchronous=NORMAL`**: Provides durability while reducing disk flushes, ensuring sub-millisecond writes.
- **`PRAGMA busy_timeout=15000`**: Automatically waits up to 15 seconds if a write lock is temporarily contested, eliminating `database is locked` exceptions.
- **Sub-Second Graceful Shutdown**: Background workers utilize cooperative `threading.Event()` checks and bounded `asyncio.wait_for` timeouts (1-2s), allowing clean server restarts in under **0.1 seconds**.

---

*Authored for the FOH Table Management Enterprise Platform.*
