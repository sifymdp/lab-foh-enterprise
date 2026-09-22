# CCTV Table Intelligence & Computer Vision Subsystem

## 1. CCTV Architecture

The CCTV intelligence pipeline bridges overhead video streams with digital restaurant tables. It runs an asynchronous worker loop evaluating table occupancy and cleanliness every scan interval (default: 10s).

```
  Camera Stream (RTSP/MJPEG/MP4)
                 │
                 ▼
  OpenCV Frame Extraction (1920×1080)
                 │
                 ▼
  YOLO11n Full-Frame Person Detection ───┐
                 │                       │
                 ▼                       ▼
  Table ROI Cropping & IoU Matching ◄────┘
                 │
                 ▼
  Temporal State Filter (Rolling 5-scan Window)
                 │
                 ▼
  Custom Table Cleanliness Model (table_cleanliness_best.pt)
                 │
                 ▼
  Mismatch Evaluator & Verification Alert Engine
```

---

## 2. Model Pipeline

1. **Person Detection (`yolo11n.pt`)**:
   - Runs across full frame to detect patrons and staff.
   - Calculates Intersection over Union (IoU) overlap against calibrated table Region of Interest (ROI) polygons.
   - Requires consecutive confirmation before state advancement to prevent false flickers.

2. **Table State & Cleanliness (`table_cleanliness_best.pt`)**:
   - Custom YOLO model classifying table ROI surface into clean, dirty, or occupied states.
   - Enforces a 60-second grace period after guests depart before marking table as dirty to allow for quick busing.

---

## 3. Discrepancy & Walkout Detection

The `mismatch_service.py` continuously compares digital FOH records against physical computer vision state:

| Mismatch Type | Digital State | CCTV Observation | System Action |
|---------------|---------------|------------------|---------------|
| `UNRECORDED_OCCUPANCY` | `AVAILABLE` or `RESERVED` | Patrons seated (&ge; 55% conf) | Broadcasts Host seating alert |
| `STALE_OCCUPANCY` | `ACTIVE` or `SEATED` | Table confirmed empty | Prompts staff to verify table |
| `UNPAID_WALKOUT_SUSPECT` | `BILLING` | Table confirmed empty | Urgent alert to Cashier & Manager |
| `SEATED_AT_DIRTY_TABLE` | `CLEANING` | Guests seated at unbused table | High-priority buser notification |

---

## 4. CCTV Safety & Protection Invariants

- **BILLING Protection**: CCTV cannot transition a table from `BILLING` to `AVAILABLE` or `CLEANING`. Only human cashier settlement or manual supervisor override can clear a billing table.
- **ACTIVE Protection**: CCTV cannot auto-close an `ACTIVE` dining session. It will generate a verification alert instead.
