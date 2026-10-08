import json
from datetime import datetime, timezone
from app.core.ids import new_id
from app.models import Bill, BillingAnomaly, User

def analyze_bill(db, bill: Bill, user: User) -> BillingAnomaly:
    subtotal = float(bill.subtotal or 0)
    discount = float(bill.discount_amount or 0)
    percent = discount / subtotal * 100 if subtotal else 0
    reasons: list[str] = []
    score = 0
    if percent > 30:
        score += 55; reasons.append(f"Discount {percent:.1f}% exceeds the normal manager threshold")
    elif percent > 15:
        score += 25; reasons.append(f"Discount {percent:.1f}% is above the branch review threshold")
    if subtotal < 10:
        score += 20; reasons.append("Unusually small bill value")
    if bill.status == "CANCELLED":
        score += 25; reasons.append("Cancelled bill requires review")
    score = min(score, 100)
    level = "HIGH" if score >= 70 else "MEDIUM" if score >= 35 else "LOW"
    row = BillingAnomaly(id=new_id(), bill_id=bill.id, tenant_id=user.tenant_id, branch_id=bill.branch_id, risk_score=score, risk_level=level, reasons=json.dumps(reasons or ["No unusual billing signals detected"]), model_version="rules-v1", created_at=datetime.now(timezone.utc))
    db.add(row); db.commit(); db.refresh(row)
    return row
