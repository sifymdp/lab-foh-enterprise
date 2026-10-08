"""
Vision Model Lifecycle Service
────────────────────────────────
Coordinates model registration, three-tier validation, promotion to production,
one-click rollback, and runtime health watchdog checks.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.vision_model import VisionModelRecord
from app.services.vision.registry.model_registry import model_registry
from app.services.vision.validation.model_validator import ModelValidator

logger = logging.getLogger(__name__)


class ModelLifecycleService:

    @staticmethod
    def register_candidate_model(
        db: Session,
        model_name: str,
        file_path: str,
        version: str = "1.0",
        architecture: str = "YOLO11",
        task: str = "detect",
        class_map: dict[int, str] | None = None,
        confidence_threshold: float = 0.35,
        image_size: int = 640,
        user_id: str | None = None,
    ) -> VisionModelRecord:
        return model_registry.register_model(
            db=db,
            model_name=model_name,
            file_path_str=file_path,
            version=version,
            architecture=architecture,
            task=task,
            class_map=class_map,
            confidence_threshold=confidence_threshold,
            image_size=image_size,
            created_by=user_id,
        )

    @staticmethod
    def validate_candidate_model(
        db: Session,
        model_id: str,
    ) -> dict[str, Any]:
        record = db.query(VisionModelRecord).filter(VisionModelRecord.id == model_id).first()
        if not record:
            raise ValueError(f"Model ID '{model_id}' not found.")

        import json
        class_map = {}
        if record.class_map_json:
            try:
                class_map = {int(k): str(v) for k, v in json.loads(record.class_map_json).items()}
            except Exception:
                pass

        report = ModelValidator.validate_model(
            model_id=record.id,
            file_path_str=record.file_path,
            task=record.task,
            class_map=class_map,
            image_size=record.image_size,
        )

        record.validation_status = report.overall_status
        db.commit()
        return report.to_dict()

    @staticmethod
    def activate_model(
        db: Session,
        model_id: str,
        user_id: str | None = None,
        reason: str | None = None,
    ) -> VisionModelRecord:
        return model_registry.promote_to_production(
            db=db,
            model_id=model_id,
            user_id=user_id,
            reason=reason,
        )

    @staticmethod
    def rollback_model(
        db: Session,
        user_id: str | None = None,
        reason: str | None = None,
    ) -> VisionModelRecord:
        return model_registry.rollback(
            db=db,
            user_id=user_id,
            reason=reason,
        )


lifecycle_service = ModelLifecycleService()
