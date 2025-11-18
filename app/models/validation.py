from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

from app.core.database import Base


class BordereauxValidationError(Base):
    """SQLAlchemy model for bordereaux validation errors."""
    __tablename__ = "bordereaux_validation_errors"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("bordereaux_files.id", ondelete="CASCADE"), nullable=False, index=True)
    row_index = Column(Integer, nullable=False)  # 0-based row index in the file
    error_code = Column(String(50), nullable=False, index=True)
    error_message = Column(Text, nullable=False)
    field_name = Column(String(100), nullable=True)  # Field that caused the error
    field_value = Column(Text, nullable=True)  # Value that caused the error
    rule_name = Column(String(100), nullable=True)  # Rule that failed
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    file = relationship("BordereauxFile", backref="validation_errors")

    def __repr__(self):
        return f"<BordereauxValidationError(id={self.id}, file_id={self.file_id}, row_index={self.row_index}, error_code='{self.error_code}')>"

