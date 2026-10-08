"""
Vision Model Management Database Models
─────────────────────────────────────────
Stores registered CV models, versions, three-tier validation results,
offline and shadow benchmark evaluations, and atomic activation/rollback audit trails.
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VisionModelRecord(Base):
    """
    Metadata catalog for all registered vision models (Production, Candidate, Archived).
    """
    __tablename__ = "vision_models"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g., "model-yolo11n", "model-restaurant-v1"
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="1.0")
    framework: Mapped[str] = mapped_column(String(32), default="ultralytics")  # ultralytics | pytorch | onnx
    architecture: Mapped[str] = mapped_column(String(64), default="YOLO11")    # YOLO11 | YOLO26 | RF-DETR | Custom
    task: Mapped[str] = mapped_column(String(32), default="detect")             # detect | obb | segment
    role: Mapped[str] = mapped_column(String(32), default="table_layout")       # table_layout | person_tracking | cleanliness
    
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)   # SHA-256 checksum
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    
    # JSON dictionary of internal model classes: {"0": "person", "60": "dining table"}
    classes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON semantic class map: {"60": "dining_table"} or {"0": "dining_table"}
    class_map_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Hyperparameters & Inference Config
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.35)
    iou_threshold: Mapped[float] = mapped_column(Float, default=0.45)
    image_size: Mapped[int] = mapped_column(Integer, default=640)
    expected_device: Mapped[str] = mapped_column(String(16), default="auto")    # auto | cuda | cpu
    
    # Source & Provenance
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    creator: Mapped[str | None] = mapped_column(String(120), nullable=True)
    license: Mapped[str | None] = mapped_column(String(64), default="Proprietary / Internal")
    dataset_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dataset_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    
    # Lifecycle Status: PRODUCTION | CANDIDATE | ARCHIVED | REJECTED
    status: Mapped[str] = mapped_column(String(32), default="CANDIDATE", index=True)
    validation_status: Mapped[str] = mapped_column(String(32), default="PENDING")  # PENDING | PASSED | FAILED
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    # Relationships
    validations: Mapped[list["VisionModelValidation"]] = relationship(
        "VisionModelValidation", back_populates="model", cascade="all, delete-orphan"
    )
    benchmarks: Mapped[list["VisionModelBenchmark"]] = relationship(
        "VisionModelBenchmark", back_populates="model", cascade="all, delete-orphan"
    )
    activations: Mapped[list["VisionModelActivation"]] = relationship(
        "VisionModelActivation", back_populates="model", cascade="all, delete-orphan"
    )
    shadow_metrics: Mapped[list["VisionShadowMetric"]] = relationship(
        "VisionShadowMetric", back_populates="model", cascade="all, delete-orphan"
    )


class VisionModelValidation(Base):
    """
    Three-Tier Model Health Validation Logs.
    Tier 1: Structural (File, Checksum, PyTorch unpickling)
    Tier 2: Inference Smoke Test (Zero-frame dummy run, latency, OOM check)
    Tier 3: Ontology Verification (model.names vs. semantic class map)
    """
    __tablename__ = "vision_model_validations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("vision_models.id", ondelete="CASCADE"), index=True, nullable=False
    )
    overall_status: Mapped[str] = mapped_column(String(32), nullable=False)  # PASSED | FAILED
    
    # Tier 1: Structural
    tier1_status: Mapped[str] = mapped_column(String(32), default="PENDING")
    tier1_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Tier 2: Smoke Test
    tier2_status: Mapped[str] = mapped_column(String(32), default="PENDING")
    tier2_smoke_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    tier2_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Tier 3: Ontology
    tier3_status: Mapped[str] = mapped_column(String(32), default="PENDING")
    tier3_target_class_found: Mapped[bool] = mapped_column(Boolean, default=False)
    tier3_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    validated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    model: Mapped["VisionModelRecord"] = relationship("VisionModelRecord", back_populates="validations")


class VisionModelBenchmark(Base):
    """
    Benchmark evaluation report (Offline sequence or 500-Frame Spatial Consistency).
    """
    __tablename__ = "vision_model_benchmarks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("vision_models.id", ondelete="CASCADE"), index=True, nullable=False
    )
    benchmark_type: Mapped[str] = mapped_column(String(32), default="OFFLINE")  # OFFLINE | 500_FRAME_SPATIAL | SHADOW
    video_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    frames_evaluated: Mapped[int] = mapped_column(Integer, default=0)
    
    # Performance telemetry
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    p95_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    avg_fps: Mapped[float] = mapped_column(Float, default=0.0)
    gpu_memory_mb: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # Detection metrics
    detection_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Spatial stability metrics (for 500-frame test)
    spatial_stability_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0 - 1.0
    centroid_variance: Mapped[float | None] = mapped_column(Float, nullable=True)
    area_variance: Mapped[float | None] = mapped_column(Float, nullable=True)
    iou_stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    disappearance_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Summary & JSON Report
    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    model: Mapped["VisionModelRecord"] = relationship("VisionModelRecord", back_populates="benchmarks")


class VisionModelActivation(Base):
    """
    Audit log of model activation, promotion to production, or rollback.
    """
    __tablename__ = "vision_model_activations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("vision_models.id", ondelete="CASCADE"), index=True, nullable=False
    )
    previous_model_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # ACTIVATE | ROLLBACK | AUTOMATIC_FALLBACK
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    activated_by_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    model: Mapped["VisionModelRecord"] = relationship("VisionModelRecord", back_populates="activations")


class VisionShadowMetric(Base):
    """
    Rolling live telemetry captured when a model runs in candidate shadow mode.
    """
    __tablename__ = "vision_shadow_metrics"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("vision_models.id", ondelete="CASCADE"), index=True, nullable=False
    )
    camera_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, index=True)
    
    inference_ms: Mapped[float] = mapped_column(Float, default=0.0)
    fps: Mapped[float] = mapped_column(Float, default=0.0)
    detections: Mapped[int] = mapped_column(Integer, default=0)
    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="HEALTHY")  # HEALTHY | DEGRADED | TIMEOUT | ERROR

    model: Mapped["VisionModelRecord"] = relationship("VisionModelRecord", back_populates="shadow_metrics")
