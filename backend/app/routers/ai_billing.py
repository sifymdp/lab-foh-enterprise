import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.deps import require_permission
from app.core.permissions import PERM_AI_BILLING_REVIEW, PERM_AI_BILLING_VIEW
from app.database import get_db
from app.models import Bill, BillingAnomaly, User
from app.services.ai_billing_service import analyze_bill

router = APIRouter(prefix="/ai/billing", tags=["ai-billing"])

@router.get("/anomalies")
def anomalies(db: Session = Depends(get_db), user: User = Depends(require_permission(PERM_AI_BILLING_VIEW))):
    q = db.query(BillingAnomaly).filter(BillingAnomaly.tenant_id == user.tenant_id)
    if user.branch_id:
        q = q.filter(BillingAnomaly.branch_id == user.branch_id)
    rows = q.order_by(BillingAnomaly.created_at.desc()).all()
    return [{"id": r.id, "billId": r.bill_id, "riskScore": r.risk_score, "riskLevel": r.risk_level, "reasons": json.loads(r.reasons), "status": r.review_status} for r in rows]

@router.post("/{bill_id}/analyze")
def analyze(bill_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission(PERM_AI_BILLING_VIEW))):
    q = db.query(Bill).filter(Bill.id == bill_id, Bill.tenant_id == user.tenant_id)
    if user.branch_id:
        q = q.filter(Bill.branch_id == user.branch_id)
    bill = q.first()
    if not bill: raise HTTPException(status_code=404, detail="Bill not found")
    row = analyze_bill(db, bill, user)
    return {"id": row.id, "billId": row.bill_id, "riskScore": row.risk_score, "riskLevel": row.risk_level, "reasons": json.loads(row.reasons), "modelVersion": row.model_version}

@router.post("/{bill_id}/review")
def review(bill_id: str, status: str, db: Session = Depends(get_db), user: User = Depends(require_permission(PERM_AI_BILLING_REVIEW))):
    q = db.query(BillingAnomaly).join(Bill, Bill.id == BillingAnomaly.bill_id).filter(BillingAnomaly.bill_id == bill_id, BillingAnomaly.tenant_id == user.tenant_id)
    if user.branch_id:
        q = q.filter(BillingAnomaly.branch_id == user.branch_id)
    row = q.order_by(BillingAnomaly.created_at.desc()).first()
    if not row: raise HTTPException(status_code=404, detail="Anomaly not found")
    if status not in {"UNDER_REVIEW", "CONFIRMED", "DISMISSED"}: raise HTTPException(status_code=422, detail="Invalid review status")
    row.review_status = status; row.reviewed_by = user.id; db.commit()
    return {"status": row.review_status, "reviewedBy": user.id}
