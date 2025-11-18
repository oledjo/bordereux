import os
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.bordereaux import BordereauxFile, FileStatus
from app.core.logging import get_structured_logger


class StorageService:
    """Service for managing file storage and metadata."""
    
    def __init__(self):
        self.settings = get_settings()
        self.storage_path = Path(self.settings.storage_base_path)
        self.logger = get_structured_logger(__name__)
        self._ensure_storage_directory()
    
    def _ensure_storage_directory(self) -> None:
        """Ensure the storage directory exists."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    def _generate_file_hash(self, file_bytes: bytes) -> str:
        """Generate SHA-256 hash of file content."""
        return hashlib.sha256(file_bytes).hexdigest()
    
    def _generate_unique_filename(self, original_filename: str, file_hash: str) -> str:
        """Generate a unique filename to avoid collisions.
        
        Format: {hash}_{timestamp}_{original_filename}
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        # Sanitize original filename
        safe_filename = "".join(c for c in original_filename if c.isalnum() or c in "._-")
        # Use first 8 chars of hash for readability
        hash_prefix = file_hash[:8]
        return f"{hash_prefix}_{timestamp}_{safe_filename}"
    
    def _get_mime_type(self, filename: str) -> Optional[str]:
        """Get MIME type based on file extension."""
        extension = Path(filename).suffix.lower()
        mime_types = {
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
            ".csv": "text/csv",
        }
        return mime_types.get(extension)
    
    def save_raw_file(
        self,
        db: Session,
        file_bytes: bytes,
        filename: str,
        source_email: Optional[str] = None,
        received_at: Optional[datetime] = None,
        subject: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Save raw file to filesystem and persist metadata in database.
        
        Implements de-duplication: if a file with the same SHA256 hash already exists,
        returns the existing file_id and status without saving or reprocessing.
        
        Args:
            db: Database session
            file_bytes: File content as bytes
            filename: Original filename
            source_email: Email address of sender
            received_at: When the email was received
            subject: Email subject line
            
        Returns:
            Dictionary with:
                - file_id: ID of the bordereaux file record
                - status: Current processing status
                - is_duplicate: True if file was already present, False if newly saved
        """
        # Generate SHA256 hash of file content
        file_hash = self._generate_file_hash(file_bytes)
        
        # Check if file with same hash already exists (de-duplication)
        existing_file = db.query(BordereauxFile).filter(
            BordereauxFile.file_hash == file_hash
        ).first()
        
        if existing_file:
            # File already exists - return existing ID and status without reprocessing
            self.logger.debug(
                "Duplicate file detected",
                file_id=existing_file.id,
                filename=filename,
                file_hash=file_hash[:8]
            )
            return {
                "file_id": existing_file.id,
                "status": existing_file.status.value,
                "is_duplicate": True,
            }
        
        # Generate unique filename for storage
        unique_filename = self._generate_unique_filename(filename, file_hash)
        file_path = self.storage_path / unique_filename
        
        # Ensure storage directory exists
        self._ensure_storage_directory()
        
        # Save file to filesystem
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        
        # Get file metadata
        file_size = len(file_bytes)
        mime_type = self._get_mime_type(filename)
        
        # Create database record
        bordereaux_file = BordereauxFile(
            filename=filename,
            file_path=str(file_path),
            file_size=file_size,
            mime_type=mime_type,
            status=FileStatus.PENDING,
            sender=source_email,
            subject=subject,
            file_hash=file_hash,
            received_at=received_at or datetime.utcnow(),
        )
        
        db.add(bordereaux_file)
        db.commit()
        db.refresh(bordereaux_file)
        
        self.logger.info(
            "File saved",
            file_id=bordereaux_file.id,
            filename=filename,
            file_size=file_size,
            file_hash=file_hash[:8],
            sender=source_email
        )
        
        return {
            "file_id": bordereaux_file.id,
            "status": bordereaux_file.status.value,
            "is_duplicate": False,
        }
    
    def get_file_path(self, db: Session, file_id: int) -> Optional[str]:
        """Get file path for a given file ID.
        
        Args:
            db: Database session
            file_id: ID of the bordereaux file
            
        Returns:
            File path if found, None otherwise
        """
        bordereaux_file = db.query(BordereauxFile).filter(
            BordereauxFile.id == file_id
        ).first()
        
        if not bordereaux_file:
            return None
        
        return bordereaux_file.file_path
    
    def get_file(self, db: Session, file_id: int) -> Optional[BordereauxFile]:
        """Get bordereaux file record by ID.
        
        Args:
            db: Database session
            file_id: ID of the bordereaux file
            
        Returns:
            BordereauxFile instance if found, None otherwise
        """
        return db.query(BordereauxFile).filter(
            BordereauxFile.id == file_id
        ).first()
    
    def check_duplicate(self, db: Session, file_bytes: bytes) -> Optional[BordereauxFile]:
        """Check if a file with the same hash already exists.
        
        Args:
            db: Database session
            file_bytes: File content as bytes
            
        Returns:
            Existing BordereauxFile if duplicate found, None otherwise
        """
        file_hash = self._generate_file_hash(file_bytes)
        return db.query(BordereauxFile).filter(
            BordereauxFile.file_hash == file_hash
        ).first()
    
    def file_exists(self, file_path: str) -> bool:
        """Check if a file exists at the given path.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file exists, False otherwise
        """
        return Path(file_path).exists()
    
    def delete_file(self, db: Session, file_id: int) -> bool:
        """Delete file from filesystem and database.
        
        Args:
            db: Database session
            file_id: ID of the bordereaux file to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        bordereaux_file = db.query(BordereauxFile).filter(
            BordereauxFile.id == file_id
        ).first()
        
        if not bordereaux_file:
            return False
        
        # Delete from filesystem
        file_path = Path(bordereaux_file.file_path)
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                # File might already be deleted, continue
                pass
        
        # Delete from database (cascade will handle rows)
        db.delete(bordereaux_file)
        db.commit()
        
        return True

