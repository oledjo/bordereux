from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum as PyEnum
import enum

from app.core.database import Base
from pydantic import BaseModel, Field, ConfigDict


# Enums
class FileType(str, enum.Enum):
    """Bordereaux file type."""
    CLAIMS = "claims"
    PREMIUM = "premium"
    EXPOSURE = "exposure"


# SQLAlchemy ORM Model
class Template(Base):
    """SQLAlchemy model for bordereaux templates."""
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    carrier = Column(String(255), nullable=True)
    file_type = Column(String(50), nullable=False, index=True)
    pattern = Column(Text, nullable=True)  # JSON string of required columns/pattern
    column_mappings = Column(JSON, nullable=False)  # Dict: source_column -> canonical_field
    version = Column(String(50), nullable=False, default="1.0.0")
    active_flag = Column(Boolean, default=True, nullable=False, index=True)
    json_file_path = Column(String(500), nullable=True)  # Path to JSON file
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<Template(id={self.id}, template_id='{self.template_id}', name='{self.name}')>"


# Pydantic Models
class TemplateBase(BaseModel):
    """Base Pydantic model for template."""
    model_config = ConfigDict(from_attributes=True)
    
    template_id: str = Field(..., description="Unique template identifier")
    name: str = Field(..., description="Template name")
    carrier: Optional[str] = Field(None, description="Carrier name")
    file_type: FileType = Field(..., description="File type (claims/premium/exposure)")
    pattern: Optional[Dict[str, Any]] = Field(None, description="Required columns/pattern as dict")
    column_mappings: Dict[str, str] = Field(..., description="Mapping from source column to canonical field")
    version: str = Field("1.0.0", description="Template version")
    active_flag: bool = Field(True, description="Whether template is active")


class TemplateCreate(TemplateBase):
    """Pydantic model for creating a template."""
    json_file_path: Optional[str] = Field(None, description="Path to JSON file")


class TemplateUpdate(BaseModel):
    """Pydantic model for updating a template."""
    model_config = ConfigDict(from_attributes=True)
    
    name: Optional[str] = None
    carrier: Optional[str] = None
    file_type: Optional[FileType] = None
    pattern: Optional[Dict[str, Any]] = None
    column_mappings: Optional[Dict[str, str]] = None
    version: Optional[str] = None
    active_flag: Optional[bool] = None
    json_file_path: Optional[str] = None


class TemplateResponse(TemplateBase):
    """Pydantic model for template response."""
    id: int
    json_file_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

