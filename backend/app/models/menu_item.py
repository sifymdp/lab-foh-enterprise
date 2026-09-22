from sqlalchemy import Boolean, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    # free-text category — e.g. "Starters", "Mains", "Drinks", "Desserts"
    # kept as String (not enum) so managers can add categories without a code deploy
    category: Mapped[str] = mapped_column(String(60))
    # False = item hidden from guest QR menu immediately, no restart needed
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    # KDS station routing — ALL | GRILL | FRY | PIZZA | BAR | DESSERT (nullable = ALL)
    station: Mapped[str | None] = mapped_column(String(32), nullable=True, default=None)

    @property
    def is_available(self) -> bool:
        return bool(self.available)

    @is_available.setter
    def is_available(self, value: bool) -> None:
        self.available = bool(value)

    order_items: Mapped[list["OrderItem"]] = relationship(  # noqa: F821
        "OrderItem", back_populates="menu_item"
    )
