from sqlalchemy import Column, Integer, String, Date
from backend.database import Base
from datetime import date


class PantryItem(Base):
    """SQLAlchemy model for pantry items"""
    __tablename__ = "pantry_items"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    expiry_date = Column(Date, nullable=True)
    
    def __repr__(self):
        return f"<PantryItem(id={self.id}, name='{self.name}', expiry={self.expiry_date})>"
    
    @property
    def days_until_expiry(self) -> int:
        """Calculate days until expiry"""
        if not self.expiry_date:
            return 999  # No expiry date set
        delta = self.expiry_date - date.today()
        return delta.days
    
    @property
    def is_expiring_soon(self) -> bool:
        """Check if item is expiring within 3 days"""
        return self.days_until_expiry <= 3