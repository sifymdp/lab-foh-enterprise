from app.schemas.common import CamelModel
from app.schemas.floor import RectBounds


class CameraRoiSuggestionOut(CamelModel):
    frame_width: int
    frame_height: int
    sampled_frames: int
    method: str
    confidence: float
    roi_coords: RectBounds
    candidates: list[RectBounds]


class CameraSnapshotAnalysisIn(CamelModel):
    roi_coords: RectBounds | None = None


class CameraSceneDetectionOut(CamelModel):
    label: str
    confidence: float
    bounds: RectBounds


class CameraSnapshotAnalysisOut(CamelModel):
    frame_width: int
    frame_height: int
    roi_used: RectBounds | None = None
    roi_label: str | None = None
    roi_confidence: float | None = None
    scene_summary: dict[str, int]
    scene_detections: list[CameraSceneDetectionOut]
