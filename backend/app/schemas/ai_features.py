from pydantic import Field
from app.schemas.common import CamelModel


class PredictionIn(CamelModel):
    item_name: str
    quantity: int = Field(default=1, ge=1)
    station: str | None = None
    current_workload: int = Field(default=0, ge=0)


class StationRouteIn(CamelModel):
    items: list[str]
    station_workload: dict[str, int] = Field(default_factory=dict)


class VoiceCommandIn(CamelModel):
    command: str
    execute: bool = True


class DemandForecastIn(CamelModel):
    horizon_days: int = Field(default=7, ge=1, le=90)


class ModificationImpactIn(CamelModel):
    add_items: dict[str, int] = Field(default_factory=dict)
    remove_items: dict[str, int] = Field(default_factory=dict)
    modification_text: str | None = None
    current_workload: int = Field(default=0, ge=0)
