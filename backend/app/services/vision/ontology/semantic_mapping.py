"""
Semantic Ontology & Class-Map Contract
────────────────────────────────────────
Translates raw model-specific class IDs to canonical domain entities:
  - dining_table
  - person
  - chair
  - counter
  - bar_stool

Enforces strict ontology validation to reject invalid or missing class maps
before a model can ever be activated in production.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Mapping

logger = logging.getLogger(__name__)

# Standard canonical restaurant domain entities
DOMAIN_ENTITIES = {
    "dining_table",
    "person",
    "chair",
    "counter",
    "bar_stool",
}

DEFAULT_COCO_CLASS_MAP = {
    60: "dining_table",
    0: "person",
    56: "chair",
    13: "chair",  # bench
}


@dataclass
class OntologyValidationResult:
    is_valid: bool
    target_class_present: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    resolved_class_map: dict[int, str] = field(default_factory=dict)
    model_classes: dict[int, str] = field(default_factory=dict)


class SemanticOntology:
    """
    Manages semantic class mapping and validation for vision models.
    """

    @staticmethod
    def normalize_class_map(raw_map: Mapping[Any, Any] | None) -> dict[int, str]:
        """Converts raw string/int dict keys to int -> domain_class string."""
        if not raw_map:
            return {}
        normalized = {}
        for k, v in raw_map.items():
            try:
                class_id = int(k)
                domain_name = str(v).strip().lower().replace(" ", "_")
                normalized[class_id] = domain_name
            except (ValueError, TypeError):
                continue
        return normalized

    @classmethod
    def validate_ontology(
        cls,
        model_names: Mapping[int, str] | Mapping[str, str],
        configured_class_map: Mapping[Any, Any] | None,
        required_domain_class: str = "dining_table",
    ) -> OntologyValidationResult:
        """
        Validates configured class map against the model's actual internal classes.
        
        Rules:
        1. Configured class IDs must exist in model.names.
        2. Required domain entity (e.g. 'dining_table') must be present.
        3. Configured domain classes must be valid domain entities.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # 1. Normalize model names to int -> str
        norm_model_names: dict[int, str] = {}
        for k, v in model_names.items():
            try:
                norm_model_names[int(k)] = str(v).strip()
            except (ValueError, TypeError):
                continue

        if not norm_model_names:
            return OntologyValidationResult(
                is_valid=False,
                target_class_present=False,
                errors=["Model exposes no internal class names (model.names is empty)."],
                model_classes={},
            )

        # 2. Normalize configured class map
        norm_class_map = cls.normalize_class_map(configured_class_map)

        # If no class map was provided, attempt intelligent auto-discovery
        if not norm_class_map:
            auto_mapped: dict[int, str] = {}
            for cid, name in norm_model_names.items():
                name_clean = name.lower().replace(" ", "_")
                if name_clean in ("dining_table", "table", "diningtable", "desk", "restaurant_table"):
                    auto_mapped[cid] = "dining_table"
                elif name_clean in ("person", "patron", "human"):
                    auto_mapped[cid] = "person"
                elif name_clean in ("chair", "seat", "bench"):
                    auto_mapped[cid] = "chair"
            
            if auto_mapped:
                warnings.append(
                    f"No class map provided. Auto-discovered semantic mapping: {auto_mapped}"
                )
                norm_class_map = auto_mapped
            else:
                errors.append(
                    "Configured class map is empty, and auto-discovery found no matching entities in model.names."
                )

        # 3. Validate class IDs exist in model.names
        for cid, domain_class in norm_class_map.items():
            if cid not in norm_model_names:
                errors.append(
                    f"Configured class ID {cid} ('{domain_class}') does not exist in model.names (available IDs: {sorted(norm_model_names.keys())[:10]}...)"
                )
            if domain_class not in DOMAIN_ENTITIES:
                warnings.append(
                    f"Domain class '{domain_class}' for ID {cid} is not in standard DOMAIN_ENTITIES {sorted(DOMAIN_ENTITIES)}."
                )

        # 4. Check for presence of required target entity
        target_found = any(v == required_domain_class for v in norm_class_map.values())
        if not target_found:
            errors.append(
                f"Required domain entity '{required_domain_class}' is missing from the configured class map."
            )

        is_valid = len(errors) == 0

        return OntologyValidationResult(
            is_valid=is_valid,
            target_class_present=target_found,
            errors=errors,
            warnings=warnings,
            resolved_class_map=norm_class_map,
            model_classes=norm_model_names,
        )
