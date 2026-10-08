"""Safe, Read-Only Financial Reporting & Analytics Service.

Architectural Rule:
The AI is strictly READ-ONLY for financial intelligence.
This service provides approved aggregations (revenue, sales, daily/monthly summaries,
comparisons, and payment-method breakdowns) without exposing mutable transaction
handles, raw billing tables, or invoice modification capabilities.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.bill import Bill
from app.models.payment import Payment


class PaymentBreakdown(BaseModel):
    cash: float = 0.0
    card: float = 0.0
    upi: float = 0.0
    qr: float = 0.0
    online: float = 0.0
    total: float = 0.0


class DailyFinancialSummary(BaseModel):
    date: str
    gross_sales: float
    net_sales: float
    discount_total: float
    tax_total: float
    service_charge_total: float
    total_bills: int
    paid_bills: int
    pending_bills: int
    cancelled_bills: int
    refunded_bills: int
    transaction_count: int
    payment_methods: PaymentBreakdown


class MonthlyFinancialSummary(BaseModel):
    year: int
    month: int
    month_name: str
    gross_sales: float
    net_sales: float
    discount_total: float
    tax_total: float
    total_bills: int
    paid_bills: int
    transaction_count: int
    daily_average: float
    payment_methods: PaymentBreakdown


class PeriodComparison(BaseModel):
    period_a_label: str
    period_b_label: str
    period_a_revenue: float
    period_b_revenue: float
    absolute_change: float
    percentage_change: float
    trend: str  # "UP", "DOWN", "FLAT"


class SalesSummaryReport(BaseModel):
    date_range: str
    gross_sales: float
    net_sales: float
    transaction_count: int
    average_ticket: float
    payment_methods: PaymentBreakdown


class FinancialReport(BaseModel):
    start_date: str
    end_date: str
    gross_sales: float
    net_sales: float
    discount_total: float
    tax_total: float
    transaction_count: int
    paid_bills: int
    payment_methods: PaymentBreakdown


class FinancialReportingService:
    """Provides validated read-only aggregation reports for authorized Owners."""

    @staticmethod
    def _get_datetime_bounds(start_d: date, end_d: date) -> tuple[datetime, datetime]:
        start_dt = datetime(start_d.year, start_d.month, start_d.day, 0, 0, 0, tzinfo=timezone.utc)
        # End at end of end_d (exclusive bound of next day)
        end_dt = datetime(end_d.year, end_d.month, end_d.day, 0, 0, 0, tzinfo=timezone.utc) + timedelta(days=1)
        return start_dt, end_dt

    @classmethod
    def get_payment_method_summary(
        cls,
        db: Session,
        tenant_id: str,
        branch_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> PaymentBreakdown:
        if start_date is None:
            start_date = datetime.now(timezone.utc).date()
        if end_date is None:
            end_date = start_date

        start_dt, end_dt = cls._get_datetime_bounds(start_date, end_date)

        q = db.query(Payment).filter(
            Payment.tenant_id == tenant_id,
            Payment.payment_status == "SUCCESS",
            Payment.paid_at >= start_dt,
            Payment.paid_at < end_dt,
        )
        if branch_id:
            q = q.filter(Payment.branch_id == branch_id)

        payments = q.all()
        totals = {"CASH": 0.0, "CARD": 0.0, "UPI": 0.0, "QR": 0.0, "ONLINE": 0.0}
        for p in payments:
            method = (p.method or "").upper()
            if method in totals:
                totals[method] += float(p.amount or 0)
            elif method in ("STRIPE", "POS", "CREDIT_CARD", "DEBIT_CARD"):
                totals["CARD"] += float(p.amount or 0)

        total_sum = sum(totals.values())
        return PaymentBreakdown(
            cash=round(totals["CASH"], 2),
            card=round(totals["CARD"], 2),
            upi=round(totals["UPI"], 2),
            qr=round(totals["QR"], 2),
            online=round(totals["ONLINE"], 2),
            total=round(total_sum, 2),
        )

    @classmethod
    def get_daily_financial_summary(
        cls,
        db: Session,
        tenant_id: str,
        branch_id: str | None = None,
        target_date: date | None = None,
    ) -> DailyFinancialSummary:
        if target_date is None:
            target_date = datetime.now(timezone.utc).date()

        start_dt, end_dt = cls._get_datetime_bounds(target_date, target_date)

        bills_q = db.query(Bill).filter(
            Bill.tenant_id == tenant_id,
            Bill.generated_at >= start_dt,
            Bill.generated_at < end_dt,
        )
        if branch_id:
            bills_q = bills_q.filter(Bill.branch_id == branch_id)

        bills = bills_q.all()

        total_bills = len(bills)
        paid_bills = sum(1 for b in bills if (b.status or b.bill_status or "") == "PAID")
        pending_bills = sum(1 for b in bills if (b.status or b.bill_status or "") in ("OPEN", "READY_FOR_PAYMENT", "DRAFT"))
        cancelled_bills = sum(1 for b in bills if (b.status or b.bill_status or "") == "CANCELLED")
        refunded_bills = sum(1 for b in bills if (b.status or b.bill_status or "") == "REFUNDED")

        gross_sales = sum(float(b.subtotal or 0) for b in bills if (b.status or b.bill_status or "") == "PAID")
        discount_total = sum(float(b.discount_amount or 0) for b in bills)
        tax_total = sum(float(b.tax_amount or 0) for b in bills)
        service_charge_total = sum(float(b.service_charge_amount or 0) for b in bills)
        net_sales = sum(float(b.total or 0) for b in bills if (b.status or b.bill_status or "") == "PAID")

        methods = cls.get_payment_method_summary(db, tenant_id, branch_id, target_date, target_date)

        return DailyFinancialSummary(
            date=target_date.isoformat(),
            gross_sales=round(gross_sales, 2),
            net_sales=round(net_sales, 2),
            discount_total=round(discount_total, 2),
            tax_total=round(tax_total, 2),
            service_charge_total=round(service_charge_total, 2),
            total_bills=total_bills,
            paid_bills=paid_bills,
            pending_bills=pending_bills,
            cancelled_bills=cancelled_bills,
            refunded_bills=refunded_bills,
            transaction_count=paid_bills,
            payment_methods=methods,
        )

    @classmethod
    def get_monthly_financial_summary(
        cls,
        db: Session,
        tenant_id: str,
        branch_id: str | None = None,
        year: int | None = None,
        month: int | None = None,
    ) -> MonthlyFinancialSummary:
        now = datetime.now(timezone.utc)
        if year is None:
            year = now.year
        if month is None:
            month = now.month

        num_days = calendar.monthrange(year, month)[1]
        start_d = date(year, month, 1)
        end_d = date(year, month, num_days)
        start_dt, end_dt = cls._get_datetime_bounds(start_d, end_d)

        bills_q = db.query(Bill).filter(
            Bill.tenant_id == tenant_id,
            Bill.generated_at >= start_dt,
            Bill.generated_at < end_dt,
        )
        if branch_id:
            bills_q = bills_q.filter(Bill.branch_id == branch_id)

        bills = bills_q.all()

        total_bills = len(bills)
        paid_bills = sum(1 for b in bills if (b.status or b.bill_status or "") == "PAID")
        gross_sales = sum(float(b.subtotal or 0) for b in bills if (b.status or b.bill_status or "") == "PAID")
        discount_total = sum(float(b.discount_amount or 0) for b in bills)
        tax_total = sum(float(b.tax_amount or 0) for b in bills)
        net_sales = sum(float(b.total or 0) for b in bills if (b.status or b.bill_status or "") == "PAID")

        methods = cls.get_payment_method_summary(db, tenant_id, branch_id, start_d, end_d)
        daily_average = round(net_sales / max(num_days, 1), 2)

        return MonthlyFinancialSummary(
            year=year,
            month=month,
            month_name=calendar.month_name[month],
            gross_sales=round(gross_sales, 2),
            net_sales=round(net_sales, 2),
            discount_total=round(discount_total, 2),
            tax_total=round(tax_total, 2),
            total_bills=total_bills,
            paid_bills=paid_bills,
            transaction_count=paid_bills,
            daily_average=daily_average,
            payment_methods=methods,
        )

    @classmethod
    def compare_revenue(
        cls,
        db: Session,
        tenant_id: str,
        branch_id: str | None,
        period_a: tuple[date, date],
        period_b: tuple[date, date],
        label_a: str = "Period A",
        label_b: str = "Period B",
    ) -> PeriodComparison:
        start_a, end_a = period_a
        start_b, end_b = period_b

        dt_a_start, dt_a_end = cls._get_datetime_bounds(start_a, end_a)
        dt_b_start, dt_b_end = cls._get_datetime_bounds(start_b, end_b)

        q_a = db.query(func.coalesce(func.sum(Bill.total), 0)).filter(
            Bill.tenant_id == tenant_id,
            Bill.generated_at >= dt_a_start,
            Bill.generated_at < dt_a_end,
            Bill.status == "PAID",
        )
        if branch_id:
            q_a = q_a.filter(Bill.branch_id == branch_id)
        rev_a = float(q_a.scalar() or 0)

        q_b = db.query(func.coalesce(func.sum(Bill.total), 0)).filter(
            Bill.tenant_id == tenant_id,
            Bill.generated_at >= dt_b_start,
            Bill.generated_at < dt_b_end,
            Bill.status == "PAID",
        )
        if branch_id:
            q_b = q_b.filter(Bill.branch_id == branch_id)
        rev_b = float(q_b.scalar() or 0)

        diff = rev_a - rev_b
        pct = round((diff / rev_b * 100) if rev_b > 0 else 0.0, 2)
        trend = "UP" if diff > 0 else ("DOWN" if diff < 0 else "FLAT")

        return PeriodComparison(
            period_a_label=label_a,
            period_b_label=label_b,
            period_a_revenue=round(rev_a, 2),
            period_b_revenue=round(rev_b, 2),
            absolute_change=round(diff, 2),
            percentage_change=pct,
            trend=trend,
        )

    @classmethod
    def get_financial_report(
        cls,
        db: Session,
        tenant_id: str,
        branch_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> FinancialReport:
        if start_date is None:
            start_date = datetime.now(timezone.utc).date()
        if end_date is None:
            end_date = start_date

        start_dt, end_dt = cls._get_datetime_bounds(start_date, end_date)

        bills_q = db.query(Bill).filter(
            Bill.tenant_id == tenant_id,
            Bill.generated_at >= start_dt,
            Bill.generated_at < end_dt,
        )
        if branch_id:
            bills_q = bills_q.filter(Bill.branch_id == branch_id)

        bills = bills_q.all()

        paid_bills = sum(1 for b in bills if (b.status or b.bill_status or "") == "PAID")
        gross_sales = sum(float(b.subtotal or 0) for b in bills if (b.status or b.bill_status or "") == "PAID")
        discount_total = sum(float(b.discount_amount or 0) for b in bills)
        tax_total = sum(float(b.tax_amount or 0) for b in bills)
        net_sales = sum(float(b.total or 0) for b in bills if (b.status or b.bill_status or "") == "PAID")

        methods = cls.get_payment_method_summary(db, tenant_id, branch_id, start_date, end_date)

        return FinancialReport(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            gross_sales=round(gross_sales, 2),
            net_sales=round(net_sales, 2),
            discount_total=round(discount_total, 2),
            tax_total=round(tax_total, 2),
            transaction_count=paid_bills,
            paid_bills=paid_bills,
            payment_methods=methods,
        )

    @classmethod
    def get_sales_summary(
        cls,
        db: Session,
        tenant_id: str,
        branch_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> SalesSummaryReport:
        rep = cls.get_financial_report(db, tenant_id, branch_id, start_date, end_date)
        avg = round(rep.net_sales / max(rep.transaction_count, 1), 2)
        return SalesSummaryReport(
            date_range=f"{rep.start_date} to {rep.end_date}",
            gross_sales=rep.gross_sales,
            net_sales=rep.net_sales,
            transaction_count=rep.transaction_count,
            average_ticket=avg,
            payment_methods=rep.payment_methods,
        )


financial_reporting_service = FinancialReportingService()
