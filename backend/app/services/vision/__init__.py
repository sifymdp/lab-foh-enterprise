"""
Vision Module Public Facade
─────────────────────────────
Exports core vision services, detectors, registry, scheduler, and benchmarking tools.
"""

from app.services.vision.detectors import BaseTableDetector, YOLOTableDetector
from app.services.vision.geometry import (
    NormalizedDetection,
    PolygonGeometry,
    polygon_iou,
    transform_polygon_homography,
)
from app.services.vision.ontology import SemanticOntology
from app.services.vision.registry import model_registry
from app.services.vision.scheduling import FrameScheduler, SchedulerTelemetry
from app.services.vision.benchmarking import (
    run_comparative_benchmark,
    shadow_runner,
    evaluate_spatial_stability,
)
from app.services.vision.lifecycle import lifecycle_service

__all__ = [
    "BaseTableDetector",
    "YOLOTableDetector",
    "PolygonGeometry",
    "NormalizedDetection",
    "polygon_iou",
    "transform_polygon_homography",
    "SemanticOntology",
    "model_registry",
    "FrameScheduler",
    "SchedulerTelemetry",
    "run_comparative_benchmark",
    "shadow_runner",
    "evaluate_spatial_stability",
    "lifecycle_service",
]
