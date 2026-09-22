from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OrderItem(Base):
    """
    One row per menu item per order round.
    item_name and unit_price are snapshotted at order time so historical
    orders stay accurate even if the menu changes later.
    The FK to menu_items is nullable — if an item is deleted from the menu
    the order history is preserved via the snapshot columns.
    """
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    # soft FK — nullable so deleted menu items don't break historical orders
    menu_item_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("menu_items.id", ondelete="SET NULL"), nullable=True
    )
    # snapshot columns — never rely on menu_items for billing calculations
    item_name: Mapped[str] = mapped_column(String(120))
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    station: Mapped[str | None] = mapped_column(String(32), nullable=True, default=None)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None)
    allergy_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    item_status: Mapped[str] = mapped_column(String(20), default="RECEIVED")

    order: Mapped["Order"] = relationship("Order", back_populates="items")  # noqa: F821
    menu_item: Mapped["MenuItem | None"] = relationship(  # noqa: F821
        "MenuItem", back_populates="order_items"
    )
