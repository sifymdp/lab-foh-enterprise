# Import order matters — parent tables must be imported before child tables
# so SQLAlchemy resolves ForeignKey references correctly.

from app.models.user import User
from app.models.organization import Organization
from app.models.branch import Branch
from app.models.floor import Floor
from app.models.section import Section
from app.models.table import Table
from app.models.reservation import Reservation
from app.models.status_history import StatusHistory
from app.models.menu_item import MenuItem
from app.models.session import DiningSession
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.bill import Bill
from app.models.cashier_shift import CashierShift          # NEW
from app.models.payment import Payment, PaymentTransaction
from app.models.refund_request import RefundRequest        # NEW
from app.models.qr_code import TableQRCode
from app.models.cleaning import CleaningEvent, DepartureEvent
from app.models.ai_event import AIEvent
from app.models.audit_log import AuditLog
from app.models.tax_rule import TaxRule
from app.models.service_charge import ServiceCharge
from app.models.discount import Discount
from app.models.billing_anomaly import BillingAnomaly

# New Dynamic RBAC and Settings models
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user_permission import UserPermission
from app.models.user_branch import UserBranch
from app.models.temporary_permission import TemporaryPermission
from app.models.permission_history import PermissionHistory
from app.models.user_session import UserSession
from app.models.staff_table_assignment import StaffTableAssignment
from app.models.system_configuration import SystemConfiguration
# Vision & CCTV Models
from app.models.vision import Camera, CameraCalibration, TableROI, VisionObservation, VisionMismatch

# Team Member Integrated Models
from app.models.order_analytics import OrderAnalytics
from app.models.customer import CustomerOTP, CustomerWaitlistEntry

__all__ = [
    "User",
    "Organization",
    "Branch",
    "Floor",
    "Section",
    "Table",
    "Reservation",
    "StatusHistory",
    "MenuItem",
    "DiningSession",
    "Order",
    "OrderItem",
    "Bill",
    "CashierShift",
    "Payment",
    "PaymentTransaction",
    "RefundRequest",
    "TableQRCode",
    "CleaningEvent",
    "DepartureEvent",
    "AIEvent",
    "AuditLog",
    "TaxRule",
    "ServiceCharge",
    "Discount",
    "BillingAnomaly",
    "Role",
    "RolePermission",
    "UserPermission",
    "UserBranch",
    "TemporaryPermission",
    "PermissionHistory",
    "UserSession",
    "StaffTableAssignment",
    "SystemConfiguration",
    "Camera",
    "CameraCalibration",
    "TableROI",
    "VisionObservation",
    "VisionMismatch",
    "OrderAnalytics",
    "CustomerOTP",
    "CustomerWaitlistEntry",
]

