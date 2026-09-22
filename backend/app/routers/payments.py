import hashlib
import hmac
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from app.config import settings
from app.core.deps import require_permission
from app.core.permissions import PERM_PAYMENT_VIEW
from app.core.ids import new_id
from app.database import get_db
from app.models import Bill, Payment, PaymentTransaction, User

router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db), x_webhook_signature: str | None = Header(default=None)):
    raw = await request.body()
    expected = hmac.new(settings.payment_webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
    if not x_webhook_signature or not hmac.compare_digest(expected, x_webhook_signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    body = json.loads(raw)
    event_id, event_type = body.get("id"), body.get("type")
    if not event_id or not event_type:
        raise HTTPException(status_code=422, detail="Webhook id and type are required")
    if db.query(PaymentTransaction).filter(PaymentTransaction.stripe_event_id == event_id).first():
        return {"ok": True, "duplicate": True}
    data = body.get("data", {})
    bill = db.query(Bill).filter(Bill.id == data.get("bill_id")).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    payment = db.query(Payment).filter(Payment.bill_id == bill.id).first()
    if not payment:
        payment = Payment(id=new_id(), bill_id=bill.id, tenant_id=bill.tenant_id, branch_id=bill.branch_id, method="STRIPE", amount=float(bill.total), reference=data.get("transaction_id"), paid_at=datetime.now(timezone.utc))
        db.add(payment); db.flush()
    db.add(PaymentTransaction(id=new_id(), payment_id=payment.id, stripe_event_id=event_id, event_type=event_type, received_at=datetime.now(timezone.utc)))
    if event_type in {"payment.succeeded", "payment_intent.succeeded"}:
        bill.status = "PAID"; bill.paid_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "status": bill.status}

@router.get("/{payment_id}")
def get_payment(payment_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission(PERM_PAYMENT_VIEW))):
    q = db.query(Payment).filter(Payment.id == payment_id, Payment.tenant_id == user.tenant_id)
    if user.branch_id:
        q = q.filter(Payment.branch_id == user.branch_id)
    row = q.first()
    if not row: raise HTTPException(status_code=404, detail="Payment not found")
    return {"id": row.id, "billId": row.bill_id, "method": row.method, "amount": float(row.amount), "reference": row.reference, "paidAt": row.paid_at}
