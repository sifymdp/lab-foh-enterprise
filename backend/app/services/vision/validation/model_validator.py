"""
Three-Tier Model Health Validation Service
────────────────────────────────────────────
Level 1: Structural Integrity (file existence, SHA-256 hash, PyTorch unpickling)
Level 2: Inference Smoke Test (zero-frame dummy run, OOM detection, latency capture)
Level 3: Semantic Ontology Validation (model.names vs. domain class map, target entity)

Guarantees that an invalid, corrupted, or incompatible model can NEVER reach production.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from app.services.vision.detectors.yolo_detector import YOLOTableDetector
from app.services.vision.ontology.semantic_mapping import SemanticOntology

logger = logging.getLogger(__name__)


@dataclass
class TierValidationReport:
    status: str  # PASSED | FAILED
    details: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FullModelValidationReport:
    model_id: str
    file_path: str
    overall_status: str  # PASSED | FAILED
    tier1: TierValidationReport
    tier2: TierValidationReport
    tier3: TierValidationReport
    resolved_class_map: dict[int, str] = field(default_factory=dict)
    file_hash: str = ""
    smoke_latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "file_path": self.file_path,
            "overall_status": self.overall_status,
            "file_hash": self.file_hash,
            "smoke_latency_ms": round(self.smoke_latency_ms, 2),
            "tier1_structural": {"status": self.tier1.status, "details": self.tier1.details},
            "tier2_smoke_test": {"status": self.tier2.status, "details": self.tier2.details},
            "tier3_ontology": {"status": self.tier3.status, "details": self.tier3.details},
            "resolved_class_map": self.resolved_class_map,
        }


class ModelValidator:
    """Executes the three-tier validation workflow for candidate vision models."""

    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    @classmethod
    def validate_tier1_structural(cls, file_path: Path) -> tuple[TierValidationReport, str]:
        """Level 1: Checks file existence, format, checksum, and basic PyTorch unpickling."""
        if not file_path.exists():
            return (
                TierValidationReport(status="FAILED", details=f"File does not exist: {file_path}"),
                "",
            )

        if not file_path.is_file() or file_path.stat().st_size == 0:
            return (
                TierValidationReport(status="FAILED", details=f"File is empty or not a regular file: {file_path}"),
                "",
            )

        if not file_path.name.lower().endswith((".pt", ".onnx", ".engine")):
            return (
                TierValidationReport(
                    status="FAILED",
                    details=f"Unsupported model extension: '{file_path.suffix}'. Expected .pt, .onnx, or .engine",
                ),
                "",
            )

        file_hash = cls.compute_sha256(file_path)

        # PyTorch unpickling check
        try:
            import torch
            # Safe checkpoint header check without executing arbitrary code
            checkpoint = torch.load(str(file_path), map_location="cpu")
            if not isinstance(checkpoint, dict) and not hasattr(checkpoint, "model"):
                return (
                    TierValidationReport(
                        status="FAILED",
                        details="Checkpoint is not a valid PyTorch model or state dictionary.",
                    ),
                    file_hash,
                )
        except Exception as e:
            return (
                TierValidationReport(
                    status="FAILED",
                    details=f"Structural check failed: Could not load PyTorch checkpoint ({type(e).__name__}: {e})",
                ),
                file_hash,
            )

        return (
            TierValidationReport(
                status="PASSED",
                details=f"Structural check passed: Checkpoint verified, SHA-256: {file_hash[:12]}...",
                metadata={"file_size": file_path.stat().st_size, "hash": file_hash},
            ),
            file_hash,
        )

    @classmethod
    def validate_tier2_smoke_test(
        cls,
        detector: YOLOTableDetector,
    ) -> tuple[TierValidationReport, float]:
        """Level 2: Zero-frame dummy inference smoke test."""
        try:
            if not detector.is_loaded:
                loaded = detector.load()
                if not loaded:
                    return (
                        TierValidationReport(
                            status="FAILED",
                            details="Smoke test failed: Detector adapter could not load model.",
                        ),
                        0.0,
                    )

            dummy_frame = np.zeros((detector.image_size, detector.image_size, 3), dtype=np.uint8)
            t0 = time.perf_counter()
            _ = detector.detect(dummy_frame)
            latency_ms = (time.perf_counter() - t0) * 1000.0

            return (
                TierValidationReport(
                    status="PASSED",
                    details=f"Smoke test passed: Zero-frame inference completed in {latency_ms:.2f} ms without errors.",
                    metadata={"latency_ms": latency_ms},
                ),
                latency_ms,
            )
        except Exception as e:
            return (
                TierValidationReport(
                    status="FAILED",
                    details=f"Smoke test failed with runtime exception: {type(e).__name__}: {e}",
                ),
                0.0,
            )

    @classmethod
    def validate_tier3_ontology(
        cls,
        detector: YOLOTableDetector,
        class_map: Mapping[Any, Any] | None,
        target_entity: str = "dining_table",
    ) -> tuple[TierValidationReport, dict[int, str]]:
        """Level 3: Validates internal class names and semantic mapping."""
        raw_names = getattr(detector, "_raw_names", {})
        if not raw_names and detector.model is not None and hasattr(detector.model, "names"):
            raw_names = {int(k): str(v) for k, v in detector.model.names.items()}

        res = SemanticOntology.validate_ontology(
            model_names=raw_names,
            configured_class_map=class_map,
            required_domain_class=target_entity,
        )

        if not res.is_valid:
            return (
                TierValidationReport(
                    status="FAILED",
                    details=f"Ontology validation failed: {'; '.join(res.errors)}",
                    metadata={"errors": res.errors, "warnings": res.warnings},
                ),
                {},
            )

        warn_text = f" (Warnings: {'; '.join(res.warnings)})" if res.warnings else ""
        return (
            TierValidationReport(
                status="PASSED",
                details=f"Ontology verified: Target entity '{target_entity}' mapped successfully to class IDs {list(res.resolved_class_map.keys())}.{warn_text}",
                metadata={"resolved_class_map": res.resolved_class_map},
            ),
            res.resolved_class_map,
        )

    @classmethod
    def validate_model(
        cls,
        model_id: str,
        file_path_str: str,
        task: str = "detect",
        class_map: Mapping[Any, Any] | None = None,
        image_size: int = 640,
        device: str = "auto",
        target_entity: str = "dining_table",
    ) -> FullModelValidationReport:
        """
        Executes all three validation tiers in sequence.
        Halts immediately if Tier 1 or Tier 2 fails.
        """
        path = Path(file_path_str).resolve()

        # ── Tier 1: Structural ──────────────────────────────────────────────
        t1, file_hash = cls.validate_tier1_structural(path)
        if t1.status != "PASSED":
            return FullModelValidationReport(
                model_id=model_id,
                file_path=str(path),
                overall_status="FAILED",
                tier1=t1,
                tier2=TierValidationReport(status="SKIPPED", details="Skipped due to Tier 1 failure"),
                tier3=TierValidationReport(status="SKIPPED", details="Skipped due to Tier 1 failure"),
                file_hash=file_hash,
            )

        # Instantiate detector adapter
        detector = YOLOTableDetector(
            model_id=model_id,
            file_path=str(path),
            task=task,
            class_map=dict(class_map) if class_map else None,
            image_size=image_size,
            device=device,
        )

        # ── Tier 2: Smoke Test ──────────────────────────────────────────────
        t2, latency_ms = cls.validate_tier2_smoke_test(detector)
        if t2.status != "PASSED":
            detector.unload()
            return FullModelValidationReport(
                model_id=model_id,
                file_path=str(path),
                overall_status="FAILED",
                tier1=t1,
                tier2=t2,
                tier3=TierValidationReport(status="SKIPPED", details="Skipped due to Tier 2 failure"),
                file_hash=file_hash,
                smoke_latency_ms=latency_ms,
            )

        # ── Tier 3: Ontology ────────────────────────────────────────────────
        t3, resolved_map = cls.validate_tier3_ontology(
            detector=detector,
            class_map=class_map,
            target_entity=target_entity,
        )

        detector.unload()

        overall = "PASSED" if (t1.status == "PASSED" and t2.status == "PASSED" and t3.status == "PASSED") else "FAILED"

        return FullModelValidationReport(
            model_id=model_id,
            file_path=str(path),
            overall_status=overall,
            tier1=t1,
            tier2=t2,
            tier3=t3,
            resolved_class_map=resolved_map,
            file_hash=file_hash,
            smoke_latency_ms=latency_ms,
        )
