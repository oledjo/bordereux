from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from enum import Enum as PyEnum
import enum

from app.core.database import Base
from pydantic import BaseModel, Field, ConfigDict


# Enums
class Currency(str, enum.Enum):
    """Currency enum."""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CAD = "CAD"
    AUD = "AUD"
    JPY = "JPY"
    CHF = "CHF"
    ZAR = "ZAR"
    NGN = "NGN"
    GHS = "GHS"
    KES = "KES"


class FileStatus(str, enum.Enum):
    """Bordereaux file processing status."""
    PENDING = "pending"
    RECEIVED = "received"
    NEW_TEMPLATE_REQUIRED = "new_template_required"
    PROCESSING = "processing"
    PROCESSED_OK = "processed_ok"
    PROCESSED_WITH_ERRORS = "processed_with_errors"
    COMPLETED = "completed"
    FAILED = "failed"


# SQLAlchemy ORM Models
class BordereauxFile(Base):
    """SQLAlchemy model for bordereaux files."""
    __tablename__ = "bordereaux_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=True)  # Size in bytes
    mime_type = Column(String(100), nullable=True)
    status = Column(Enum(FileStatus), default=FileStatus.PENDING, nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    total_rows = Column(Integer, default=0)
    processed_rows = Column(Integer, default=0)
    # Email metadata
    sender = Column(String(255), nullable=True, index=True)  # Source email address
    subject = Column(String(500), nullable=True)  # Email subject
    file_hash = Column(String(64), nullable=True, index=True)  # SHA-256 hash of file content
    received_at = Column(DateTime(timezone=True), nullable=True)  # When email was received
    proposal_path = Column(String(500), nullable=True)  # Path to mapping proposal JSON file
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    rows = relationship("BordereauxRow", back_populates="file", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BordereauxFile(id={self.id}, filename='{self.filename}', status='{self.status}')>"


class BordereauxRow(Base):
    """SQLAlchemy model for bordereaux rows."""
    __tablename__ = "bordereaux_rows"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("bordereaux_files.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Policy information
    policy_number = Column(String(100), nullable=True, index=True)
    insured_name = Column(String(255), nullable=True)
    inception_date = Column(Date, nullable=True, index=True)
    expiry_date = Column(Date, nullable=True, index=True)
    
    # Financial information
    premium_amount = Column(Float, nullable=True)
    currency = Column(Enum(Currency), nullable=True)
    claim_amount = Column(Float, nullable=True)
    commission_amount = Column(Float, nullable=True)
    net_premium = Column(Float, nullable=True)
    
    # Additional information
    broker_name = Column(String(255), nullable=True)
    product_type = Column(String(100), nullable=True)
    coverage_type = Column(String(100), nullable=True)
    risk_location = Column(String(255), nullable=True)
    
    # Metadata
    row_number = Column(Integer, nullable=True)  # Original row number in the file
    raw_data = Column(Text, nullable=True)  # JSON string of original row data for reference
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    file = relationship("BordereauxFile", back_populates="rows")

    def __repr__(self):
        return f"<BordereauxRow(id={self.id}, policy_number='{self.policy_number}', file_id={self.file_id})>"


# Pydantic Models
class BordereauxRowBase(BaseModel):
    """Base Pydantic model for bordereaux row."""
    model_config = ConfigDict(from_attributes=True)
    
    policy_number: Optional[str] = Field(None, description="Policy number")
    insured_name: Optional[str] = Field(None, description="Name of the insured")
    inception_date: Optional[date] = Field(None, description="Policy inception date")
    expiry_date: Optional[date] = Field(None, description="Policy expiry date")
    premium_amount: Optional[float] = Field(None, description="Premium amount")
    currency: Optional[Currency] = Field(None, description="Currency code")
    claim_amount: Optional[float] = Field(None, description="Claim amount")
    commission_amount: Optional[float] = Field(None, description="Commission amount")
    net_premium: Optional[float] = Field(None, description="Net premium amount")
    broker_name: Optional[str] = Field(None, description="Broker name")
    product_type: Optional[str] = Field(None, description="Product type")
    coverage_type: Optional[str] = Field(None, description="Coverage type")
    risk_location: Optional[str] = Field(None, description="Risk location")


class BordereauxRowCreate(BordereauxRowBase):
    """Pydantic model for creating a bordereaux row."""
    file_id: int = Field(..., description="ID of the bordereaux file")
    row_number: Optional[int] = Field(None, description="Original row number in the file")
    raw_data: Optional[str] = Field(None, description="JSON string of original row data")


class BordereauxRowResponse(BordereauxRowBase):
    """Pydantic model for bordereaux row response."""
    id: int
    file_id: int
    row_number: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BordereauxFileBase(BaseModel):
    """Base Pydantic model for bordereaux file."""
    model_config = ConfigDict(from_attributes=True)
    
    filename: str = Field(..., description="Name of the file")
    file_path: str = Field(..., description="Path to the file")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="MIME type of the file")
    sender: Optional[str] = Field(None, description="Source email address")
    subject: Optional[str] = Field(None, description="Email subject")
    file_hash: Optional[str] = Field(None, description="SHA-256 hash of file content")
    received_at: Optional[datetime] = Field(None, description="When email was received")
    proposal_path: Optional[str] = Field(None, description="Path to mapping proposal JSON file")


class BordereauxFileCreate(BordereauxFileBase):
    """Pydantic model for creating a bordereaux file."""
    pass


class BordereauxFileResponse(BordereauxFileBase):
    """Pydantic model for bordereaux file response."""
    id: int
    status: FileStatus
    error_message: Optional[str] = None
    total_rows: int = 0
    processed_rows: int = 0
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BordereauxFileWithRows(BordereauxFileResponse):
    """Pydantic model for bordereaux file with rows."""
    rows: list[BordereauxRowResponse] = []

    model_config = ConfigDict(from_attributes=True)

