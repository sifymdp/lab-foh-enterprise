"""
Temporal Occupancy State Machine & Confidence Engine
────────────────────────────────────────────────────
Prevents rapid flapping and false positives by confirming occupancy and departure
over multiple consecutive frames and time windows.

States:
  - UNKNOWN
  - POSSIBLE_OCCUPIED
  - OCCUPIED_CONFIRMED
  - POSSIBLE_EMPTY
  - EMPTY_CONFIRMED
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TableTemporalState:
    table_id: str
    state: str = "UNKNOWN"
    people_count: int = 0
    tracked_ids: list[int] = field(default_factory=list)
    confidence: float = 0.0
    consecutive_present_count: int = 0
    consecutive_absent_count: int = 0
    first_seen_present: float | None = None
    first_seen_absent: float | None = None
    last_updated: float = field(default_factory=time.time)


class TemporalOccupancyTracker:
    _instance: TemporalOccupancyTracker | None = None

    def __init__(self) -> None:
        # table_id -> TableTemporalState
        self._states: dict[str, TableTemporalState] = {}

    @classmethod
    def get_instance(cls) -> TemporalOccupancyTracker:
        if cls._instance is None:
            cls._instance = TemporalOccupancyTracker()
        return cls._instance

    def get_state(self, table_id: str) -> TableTemporalState:
        if table_id not in self._states:
            self._states[table_id] = TableTemporalState(table_id=table_id)
        return self._states[table_id]

    def update(
        self,
        table_id: str,
        detected_people: int,
        raw_confidence: float,
        tracked_ids: list[int] | None = None,
    ) -> TableTemporalState:
        now = time.time()
        st = self.get_state(table_id)
        st.last_updated = now
        ids = tracked_ids or []

        confirm_frames = max(settings.cv_occupancy_confirm_frames, 2)
        departure_seconds = max(settings.cv_departure_confirm_seconds, 5)

        if detected_people > 0:
            # Person present
            st.consecutive_present_count += 1
            st.consecutive_absent_count = 0
            st.first_seen_absent = None
            if st.first_seen_present is None:
                st.first_seen_present = now

            st.people_count = detected_people
            st.tracked_ids = ids

            # Calculate confidence score based on detection strength + temporal stability
            temporal_boost = min(st.consecutive_present_count / float(confirm_frames), 1.0) * 0.3
            st.confidence = min(round(raw_confidence * 0.7 + temporal_boost, 2), 0.99)

            if st.consecutive_present_count >= confirm_frames:
                st.state = "OCCUPIED_CONFIRMED"
            else:
                st.state = "POSSIBLE_OCCUPIED"

        else:
            # No person detected
            st.consecutive_absent_count += 1
            st.consecutive_present_count = 0
            st.first_seen_present = None
            if st.first_seen_absent is None:
                st.first_seen_absent = now

            absent_duration = now - st.first_seen_absent

            if absent_duration >= departure_seconds or st.consecutive_absent_count >= (confirm_frames * 2):
                st.state = "EMPTY_CONFIRMED"
                st.people_count = 0
                st.tracked_ids = []
                st.confidence = 0.95
            elif st.state in ("OCCUPIED_CONFIRMED", "POSSIBLE_OCCUPIED"):
                st.state = "POSSIBLE_EMPTY"
                st.confidence = max(round(st.confidence * 0.8, 2), 0.3)
            else:
                st.state = "EMPTY_CONFIRMED"
                st.people_count = 0
                st.tracked_ids = []
                st.confidence = 0.90

        return st

    def reset(self, table_id: str | None = None) -> None:
        if table_id:
            self._states.pop(table_id, None)
        else:
            self._states.clear()


temporal_tracker = TemporalOccupancyTracker.get_instance()
