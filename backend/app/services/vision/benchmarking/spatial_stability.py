"""
500-Frame Static Spatial Consistency Evaluator
────────────────────────────────────────────────
Because tables are static physical furniture, this evaluator tests spatial
consistency and physical stability over an image/video sequence.

Computes:
  - Centroid variance
  - Area variance / jitter
  - IoU stability
  - Temporary disappearance rate
  - Spatial Stability Score (0.0 - 1.0)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

from app.services.vision.detectors.base_detector import BaseTableDetector
from app.services.vision.geometry.geometry_models import NormalizedDetection, PolygonGeometry
from app.services.vision.geometry.geometry_service import distance_between_centroids, polygon_iou

logger = logging.getLogger(__name__)


@dataclass
class TableTrackRecord:
    track_id: int
    centroids: list[tuple[float, float]] = field(default_factory=list)
    areas: list[float] = field(default_factory=list)
    ious: list[float] = field(default_factory=list)
    confidences: list[float] = field(default_factory=list)
    disappearance_count: int = 0
    consecutive_missing: int = 0
    last_polygon: PolygonGeometry | None = None
    frames_seen: int = 0


@dataclass
class SpatialStabilityResult:
    total_frames: int
    tables_tracked: int
    spatial_stability_score: float  # 0.0 - 1.0
    avg_iou_stability: float
    avg_centroid_variance_px: float
    avg_area_jitter_ratio: float
    total_disappearances: int
    avg_confidence: float
    details_per_table: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_frames": self.total_frames,
            "tables_tracked": self.tables_tracked,
            "spatial_stability_score": round(self.spatial_stability_score, 4),
            "avg_iou_stability": round(self.avg_iou_stability, 4),
            "avg_centroid_variance_px": round(self.avg_centroid_variance_px, 2),
            "avg_area_jitter_ratio": round(self.avg_area_jitter_ratio, 4),
            "total_disappearances": self.total_disappearances,
            "avg_confidence": round(self.avg_confidence, 4),
            "details_per_table": self.details_per_table,
        }


def evaluate_spatial_stability(
    detector: BaseTableDetector,
    frames: Sequence[np.ndarray],
    iou_match_threshold: float = 0.35,
) -> SpatialStabilityResult:
    """
    Runs candidate detector over up to 500 frames and tracks polygon stability across frames.
    """
    total_frames = len(frames)
    if total_frames == 0:
        return SpatialStabilityResult(0, 0, 0.0, 0.0, 0.0, 0.0, 0, 0.0)

    table_tracks: list[TableTrackRecord] = []
    next_track_id = 1

    for frame_idx, frame in enumerate(frames):
        detections = detector.detect(frame)
        matched_track_indices = set()

        # Match current detections with active tracks via polygon IoU
        for det in detections:
            best_iou = 0.0
            best_track_idx = -1

            for idx, trk in enumerate(table_tracks):
                if idx in matched_track_indices or trk.last_polygon is None:
                    continue
                iou = polygon_iou(det.geometry, trk.last_polygon)
                if iou > best_iou:
                    best_iou = iou
                    best_track_idx = idx

            if best_track_idx >= 0 and best_iou >= iou_match_threshold:
                # Update existing track
                matched_track_indices.add(best_track_idx)
                trk = table_tracks[best_track_idx]
                trk.frames_seen += 1
                trk.consecutive_missing = 0
                trk.centroids.append(det.geometry.centroid())
                trk.areas.append(det.geometry.area())
                trk.ious.append(best_iou)
                trk.confidences.append(det.confidence)
                trk.last_polygon = det.geometry
            else:
                # New table track discovered
                new_trk = TableTrackRecord(
                    track_id=next_track_id,
                    centroids=[det.geometry.centroid()],
                    areas=[det.geometry.area()],
                    ious=[1.0],
                    confidences=[det.confidence],
                    last_polygon=det.geometry,
                    frames_seen=1,
                )
                next_track_id += 1
                table_tracks.append(new_trk)

        # Increment disappearance for tracks not seen in this frame
        for idx, trk in enumerate(table_tracks):
            if idx not in matched_track_indices and trk.frames_seen >= 2:
                trk.consecutive_missing += 1
                if trk.consecutive_missing == 1:
                    trk.disappearance_count += 1

    # Filter out transient false-positive flickers (seen in only 1 frame)
    valid_tracks = [t for t in table_tracks if t.frames_seen >= max(2, int(total_frames * 0.05))]
    if not valid_tracks:
        valid_tracks = table_tracks

    if not valid_tracks:
        return SpatialStabilityResult(total_frames, 0, 0.0, 0.0, 0.0, 0.0, 0, 0.0)

    all_ious: list[float] = []
    all_centroid_vars: list[float] = []
    all_area_jitters: list[float] = []
    all_confs: list[float] = []
    total_disappearances = sum(t.disappearance_count for t in valid_tracks)
    details: list[dict[str, Any]] = []

    for trk in valid_tracks:
        # 1. IoU stability
        mean_iou = float(np.mean(trk.ious)) if trk.ious else 0.0
        all_ious.append(mean_iou)

        # 2. Centroid variance (pixels)
        if len(trk.centroids) > 1:
            cxs = [c[0] for c in trk.centroids]
            cys = [c[1] for c in trk.centroids]
            c_var = float(np.var(cxs) + np.var(cys))
        else:
            c_var = 0.0
        all_centroid_vars.append(c_var)

        # 3. Area jitter (relative ratio)
        if len(trk.areas) > 1:
            mean_area = float(np.mean(trk.areas))
            area_std = float(np.std(trk.areas))
            jitter = (area_std / max(mean_area, 1.0)) if mean_area > 0 else 0.0
        else:
            jitter = 0.0
        all_area_jitters.append(jitter)

        mean_conf = float(np.mean(trk.confidences)) if trk.confidences else 0.0
        all_confs.append(mean_conf)

        details.append({
            "table_track_id": trk.track_id,
            "frames_seen": trk.frames_seen,
            "mean_iou": round(mean_iou, 3),
            "centroid_variance": round(c_var, 2),
            "area_jitter": round(jitter, 3),
            "disappearances": trk.disappearance_count,
            "mean_confidence": round(mean_conf, 3),
        })

    avg_iou = float(np.mean(all_ious)) if all_ious else 0.0
    avg_c_var = float(np.mean(all_centroid_vars)) if all_centroid_vars else 0.0
    avg_area_jitter = float(np.mean(all_area_jitters)) if all_area_jitters else 0.0
    avg_conf = float(np.mean(all_confs)) if all_confs else 0.0

    # ── Formula for Spatial Stability Score (0.0 to 1.0) ───────────────────
    # Normalized weights:
    #   w1 (0.40): IoU stability
    #   w2 (0.30): Centroid stability (penalizes variance > 25px)
    #   w3 (0.20): Area stability (penalizes jitter > 0.3)
    #   w4 (0.10): Disappearance penalty
    c_term = max(0.0, 1.0 - (avg_c_var / 25.0))
    a_term = max(0.0, 1.0 - (avg_area_jitter / 0.35))
    d_penalty = min(1.0, total_disappearances / max(total_frames * 0.1, 1.0))

    stability_score = round(
        max(0.0, min(1.0, 0.40 * avg_iou + 0.30 * c_term + 0.20 * a_term - 0.10 * d_penalty)),
        4,
    )

    return SpatialStabilityResult(
        total_frames=total_frames,
        tables_tracked=len(valid_tracks),
        spatial_stability_score=stability_score,
        avg_iou_stability=avg_iou,
        avg_centroid_variance_px=avg_c_var,
        avg_area_jitter_ratio=avg_area_jitter,
        total_disappearances=total_disappearances,
        avg_confidence=avg_conf,
        details_per_table=details,
    )
