from typing import Any
from app.schemas.common import CamelModel
from app.schemas.menu import MenuItemOut


class MenuImportSummaryOut(CamelModel):
    id: str
    fileName: str
    status: str
    totalRows: int
    newCount: int
    updatedCount: int
    unchangedCount: int
    errorCount: int
    warningCount: int
    deactivatedCount: int
    createdAt: str
    approvedAt: str | None = None
    uploadedBy: str | None = None
    approvedBy: str | None = None


class MenuImportItemOut(CamelModel):
    id: str
    rowNumber: int
    itemCode: str | None = None
    itemName: str
    category: str
    action: str  # NEW | UPDATED | UNCHANGED | ERROR | POSSIBLE_DUPLICATE
    status: str  # VALID | WARNING | ERROR
    errorMessage: str | None = None
    warningMessage: str | None = None
    similarityMatch: str | None = None
    similarityScore: float | None = None
    oldValues: dict[str, Any] | None = None
    newValues: dict[str, Any] | None = None


class MenuImportDetailOut(CamelModel):
    summary: MenuImportSummaryOut
    items: list[MenuImportItemOut]
    missingItems: list[MenuItemOut] = []


class MenuApproveIn(CamelModel):
    deactivateMissing: bool = False
    notes: str | None = None

    @property
    def deactivate_missing(self) -> bool:
        return self.deactivateMissing


class MenuVersionOut(CamelModel):
    id: str
    versionNumber: int
    versionTag: str
    createdAt: str
    createdBy: str | None = None
    creatorName: str | None = None
    totalItems: int
    newItemsCount: int
    updatedItemsCount: int
    deactivatedItemsCount: int
    notes: str | None = None


class MenuChangeLogOut(CamelModel):
    id: str
    versionId: str
    itemCode: str | None = None
    itemName: str
    fieldName: str
    oldValue: str | None = None
    newValue: str | None = None
    changedAt: str
