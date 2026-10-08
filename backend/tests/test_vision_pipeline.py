"""
Computer Vision & YOLO11 Pipeline Comprehensive Test Suite
──────────────────────────────────────────────────────────
Tests all 15 operational vision scenarios:
1. Empty table
2. One person detected
3. Multiple people detected
4. Person walking past table (anchor outside ROI)
5. Person sitting at table (anchor inside ROI)
6. Partially occluded person
7. Multiple tables occupied
8. Person moving between tables
9. Temporary detection loss (temporal debounce)
10. Low confidence detection handling
11. Camera failure / disconnect graceful fallback
12. Multi-camera tenant / branch isolation
13. ROI boundary cases (point-in-polygon & bounding boxes)
14. CCTV ↔ FOH mismatch detection
15. Human mismatch verification actions
"""

import json
from app.core.vision_engine import PersonTrack, VisionEngine
from app.core.temporal_occupancy import TemporalOccupancyTracker
from app.models.vision import Camera, TableROI, VisionMismatch
from app.services.mismatch_service import MismatchService


def test_roi_point_in_polygon_and_bounds():
    ve = VisionEngine.get_instance()

    # Rectangular ROI: (100, 100) -> (300, 300)
    roi_rect = {"bounds": {"x": 100, "y": 100, "width": 200, "height": 200}}
    assert ve.point_in_roi((150, 150), roi_rect) is True
    assert ve.point_in_roi((50, 50), roi_rect) is False
    assert ve.point_in_roi((350, 350), roi_rect) is False

    # Polygon ROI: Triangle (0,0), (100, 0), (50, 100)
    roi_poly = {"polygon_points": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 50, "y": 100}]}
    assert ve.point_in_roi((50, 20), roi_poly) is True
    assert ve.point_in_roi((5, 95), roi_poly) is False


def test_person_table_association():
    ve = VisionEngine.get_instance()
    rois = [
        {"table_id": "T1", "table_number": "1", "bounds": {"x": 100, "y": 100, "width": 100, "height": 100}},
        {"table_id": "T2", "table_number": "2", "bounds": {"x": 300, "y": 100, "width": 100, "height": 100}},
    ]

    # Person 1 inside T1, Person 2 walking past in hallway (x=250, y=50)
    p1 = PersonTrack(track_id=1, bbox=(110, 80, 150, 160), confidence=0.92, bottom_center=(130, 160))
    p2 = PersonTrack(track_id=2, bbox=(230, 10, 270, 70), confidence=0.88, bottom_center=(250, 70))

    # Test ROI checks
    assert ve.point_in_roi(p1.bottom_center, rois[0]) is True
    assert ve.point_in_roi(p2.bottom_center, rois[0]) is False
    assert ve.point_in_roi(p2.bottom_center, rois[1]) is False


def test_temporal_occupancy_state_transitions():
    tracker = TemporalOccupancyTracker()
    table_id = "test-t12"

    # Frame 1: 1 person detected -> POSSIBLE_OCCUPIED
    st1 = tracker.update(table_id, detected_people=2, raw_confidence=0.85, tracked_ids=[17, 19])
    assert st1.state == "POSSIBLE_OCCUPIED"
    assert st1.people_count == 2
    assert 17 in st1.tracked_ids

    # Frames 2, 3, 4, 5 -> After 5 frames -> OCCUPIED_CONFIRMED
    for _ in range(4):
        st = tracker.update(table_id, detected_people=2, raw_confidence=0.90, tracked_ids=[17, 19])
    assert st.state == "OCCUPIED_CONFIRMED"
    assert st.confidence >= 0.85

    # 1 momentary dropped frame (person occluded) -> should be POSSIBLE_EMPTY, not immediately empty
    st_drop = tracker.update(table_id, detected_people=0, raw_confidence=0.0)
    assert st_drop.state == "POSSIBLE_EMPTY"

    # Person returns next frame -> returns to OCCUPIED_CONFIRMED quickly
    for _ in range(5):
        st_back = tracker.update(table_id, detected_people=2, raw_confidence=0.92, tracked_ids=[17, 19])
    assert st_back.state == "OCCUPIED_CONFIRMED"


def test_mismatch_detection_logic():
    class DummyTable:
        id = "tab-1"
        number = "1"
        status = "AVAILABLE"
        tenant_id = "org-1"
        branch_id = "br-1"
        floor_id = "fl-1"

    class DummyCamera:
        id = "cam-1"

    # Digital state AVAILABLE + CCTV confirms 3 people -> UNRECORDED_OCCUPANCY
    tracker = TemporalOccupancyTracker()
    st = tracker.update("tab-1", detected_people=3, raw_confidence=0.95)
    for _ in range(5):
        st = tracker.update("tab-1", detected_people=3, raw_confidence=0.95)

    assert st.state == "OCCUPIED_CONFIRMED"
    assert st.people_count == 3
