from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from datetime import datetime
import re

from app.core.database import get_db
from app.models.bordereaux import BordereauxFile, FileStatus
from app.services.storage_service import StorageService
from app.services.parsing_service import ParsingService
from app.services.template_repository import TemplateRepository
from app.services.mapping_service import map_to_canonical
from app.services.processing_service import ProcessingService
from app.services.mapping_suggestion_service import MappingSuggestionService
from app.core.logging import get_structured_logger


class PipelineService:
    """Service for processing bordereaux files through the complete pipeline."""
    
    def __init__(self):
        self.storage_service = StorageService()
        self.parsing_service = ParsingService()
        self.template_repository = TemplateRepository()
        self.processing_service = ProcessingService()
        self.suggestion_service = MappingSuggestionService()
        self.logger = get_structured_logger(__name__)
    
    def _normalize_column_name(self, column_name: str) -> str:
        """Normalize column name for comparison.
        
        Args:
            column_name: Column name to normalize
            
        Returns:
            Normalized column name
        """
        if not column_name:
            return ""
        
        normalized = str(column_name).strip().lower()
        normalized = re.sub(r'[^a-z0-9_]', '_', normalized)
        normalized = re.sub(r'_+', '_', normalized)
        normalized = normalized.strip('_')
        
        return normalized
    
    def _find_matching_template(
        self,
        db: Session,
        file_headers: List[str],
        file_type: Optional[str] = None
    ) -> Optional[Any]:
        """Find matching template for file headers.
        
        Args:
            db: Database session
            file_headers: List of column names from the file
            file_type: Optional file type filter (claims/premium/exposure)
            
        Returns:
            Matching Template or None if not found
        """
        # Get active templates, optionally filtered by file type
        from app.models.template import FileType
        
        file_type_enum = None
        if file_type:
            try:
                file_type_enum = FileType(file_type.lower())
            except ValueError:
                pass
        
        templates = self.template_repository.list_active_templates(
            db, file_type=file_type_enum
        )
        
        if not templates:
            return None
        
        # Simple matching: check if template column_mappings match file headers
        # Normalize headers for comparison
        normalized_headers = [
            self._normalize_column_name(h) for h in file_headers
        ]
        
        for template in templates:
            if not template.column_mappings:
                continue
            
            # Check if template column_mappings exactly match file headers
            template_columns = list(template.column_mappings.keys())
            normalized_template_cols = [
                self._normalize_column_name(c) for c in template_columns
            ]
            
            # Count matches (template columns found in file)
            matches = sum(
                1 for col in normalized_template_cols
                if col in normalized_headers
            )
            
            # Check for exact match: all template columns must be present
            # AND file must not have extra columns (strict matching)
            all_template_cols_match = matches == len(normalized_template_cols)
            file_has_extra_cols = len(normalized_headers) > len(normalized_template_cols)
            
            # For exact match: all template columns must be present and no extra columns
            if all_template_cols_match and not file_has_extra_cols:
                return template
            
            # Fallback: if exact match not found, use lenient matching (99% threshold)
            # This allows for minor variations but still requires high match rate
            if matches > 0 and matches >= len(normalized_template_cols) * 0.99:
                # Only use lenient matching if file doesn't have significantly more columns
                # (allow up to 10% more columns for flexibility)
                extra_cols_ratio = (len(normalized_headers) - len(normalized_template_cols)) / len(normalized_template_cols) if normalized_template_cols else 0
                if extra_cols_ratio <= 0.1:  # Allow up to 10% extra columns
                    return template
        
        return None
    
    def _update_file_status(
        self,
        db: Session,
        file_id: int,
        status: FileStatus,
        error_message: Optional[str] = None
    ) -> None:
        """Update file status.
        
        Args:
            db: Database session
            file_id: Bordereaux file ID
            status: New status
            error_message: Optional error message
        """
        bordereaux_file = db.query(BordereauxFile).filter(
            BordereauxFile.id == file_id
        ).first()
        
        if bordereaux_file:
            bordereaux_file.status = status
            if error_message:
                bordereaux_file.error_message = error_message
            db.commit()
    
    def process_file(self, file_id: int) -> Dict[str, Any]:
        """Process a bordereaux file through the complete pipeline.
        
        Steps:
        1. Load file metadata & path
        2. Parse into DataFrame
        3. Try template match
        4. If template found → map → normalize → validate → persist
        5. If no template → generate suggestion & mark status NEW_TEMPLATE_REQUIRED
        
        Args:
            file_id: Bordereaux file ID
            
        Returns:
            Dictionary with processing results
        """
        db = next(get_db())
        
        try:
            # Step 1: Load file metadata & path
            bordereaux_file = self.storage_service.get_file(db, file_id)
            
            if not bordereaux_file:
                return {
                    "success": False,
                    "error": f"File with ID {file_id} not found",
                    "file_id": file_id
                }
            
            file_path = bordereaux_file.file_path
            
            # Log pipeline start
            self.logger.info(
                "Pipeline started",
                file_id=file_id,
                filename=bordereaux_file.filename
            )
            
            # Update status to PROCESSING
            self._update_file_status(db, file_id, FileStatus.PROCESSING)
            
            # Step 2: Parse into DataFrame
            try:
                self.logger.debug("Parsing file", file_id=file_id, file_path=file_path)
                df = self.parsing_service.parse_file(file_path)
                file_headers = list(df.columns)
                self.logger.info(
                    "File parsed",
                    file_id=file_id,
                    row_count=len(df),
                    column_count=len(file_headers)
                )
            except Exception as e:
                error_msg = f"Error parsing file: {str(e)}"
                self.logger.error(
                    "File parsing failed",
                    file_id=file_id,
                    file_path=file_path,
                    error=str(e)
                )
                self._update_file_status(
                    db, file_id, FileStatus.FAILED, error_msg
                )
                return {
                    "success": False,
                    "error": error_msg,
                    "file_id": file_id,
                    "step": "parsing"
                }
            
            # Step 3: Try template match
            # Try to infer file type from filename or subject
            file_type = None
            if bordereaux_file.subject:
                subject_lower = bordereaux_file.subject.lower()
                if "claim" in subject_lower:
                    file_type = "claims"
                elif "premium" in subject_lower:
                    file_type = "premium"
                elif "exposure" in subject_lower:
                    file_type = "exposure"
            
            template = self._find_matching_template(db, file_headers, file_type)
            
            # Step 4: Process based on template availability
            if template:
                self.logger.info(
                    "Template matched",
                    file_id=file_id,
                    template_id=template.template_id,
                    template_name=template.name,
                    file_type=file_type
                )
                # Template found → map → normalize → validate → persist
                try:
                    # Map to canonical rows (normalization happens in mapping service)
                    canonical_rows = map_to_canonical(df, template, file_id)
                    
                    # Validate and persist
                    results = self.processing_service.process_and_persist(
                        db=db,
                        file_id=file_id,
                        canonical_rows=canonical_rows,
                        save_errors_to_db=True,
                        save_errors_to_json=True
                    )
                    
                    # Log pipeline completion
                    self.logger.info(
                        "Pipeline completed",
                        file_id=file_id,
                        template_id=template.template_id,
                        total_rows=results["total_rows"],
                        valid_rows=results["valid_rows"],
                        error_rows=results["error_rows"],
                        status=results["status"]
                    )
                    
                    return {
                        "success": True,
                        "file_id": file_id,
                        "template_id": template.template_id,
                        "template_name": template.name,
                        "total_rows": results["total_rows"],
                        "valid_rows": results["valid_rows"],
                        "error_rows": results["error_rows"],
                        "saved_rows": results["saved_rows"],
                        "status": results["status"],
                        "error_report_path": results.get("error_report_path"),
                    }
                
                except Exception as e:
                    error_msg = f"Error processing file with template: {str(e)}"
                    self.logger.error(
                        "Pipeline failed",
                        file_id=file_id,
                        template_id=template.template_id,
                        error=str(e)
                    )
                    self._update_file_status(
                        db, file_id, FileStatus.FAILED, error_msg
                    )
                    return {
                        "success": False,
                        "error": error_msg,
                        "file_id": file_id,
                        "step": "processing",
                        "template_id": template.template_id if template else None
                    }
            
            else:
                # No template found → generate suggestion & mark status NEW_TEMPLATE_REQUIRED
                self.logger.warning(
                    "No template found",
                    file_id=file_id,
                    file_type=file_type,
                    header_count=len(file_headers)
                )
                
                try:
                    suggestion_result = self.suggestion_service.process_file(
                        db=db,
                        file_id=file_id,
                        file_headers=file_headers,
                        metadata={
                            "filename": bordereaux_file.filename,
                            "sender": bordereaux_file.sender,
                            "subject": bordereaux_file.subject,
                        }
                    )
                    
                    self.logger.info(
                        "Mapping suggestion generated",
                        file_id=file_id,
                        proposal_path=suggestion_result["proposal_path"],
                        mapped_count=suggestion_result["mapped_count"],
                        total_headers=suggestion_result["total_headers"]
                    )
                    
                    return {
                        "success": True,
                        "file_id": file_id,
                        "status": "new_template_required",
                        "proposal_path": suggestion_result["proposal_path"],
                        "mapped_count": suggestion_result["mapped_count"],
                        "total_headers": suggestion_result["total_headers"],
                        "column_mappings": suggestion_result["column_mappings"],
                        "confidence_scores": suggestion_result["confidence_scores"],
                    }
                
                except Exception as e:
                    error_msg = f"Error generating mapping suggestion: {str(e)}"
                    self.logger.error(
                        "Suggestion generation failed",
                        file_id=file_id,
                        error=str(e)
                    )
                    self._update_file_status(
                        db, file_id, FileStatus.FAILED, error_msg
                    )
                    return {
                        "success": False,
                        "error": error_msg,
                        "file_id": file_id,
                        "step": "suggestion_generation"
                    }
        
        except Exception as e:
            # Catch-all for unexpected errors
            error_msg = f"Unexpected error in pipeline: {str(e)}"
            self.logger.exception(
                "Unexpected pipeline error",
                file_id=file_id,
                error=str(e)
            )
            try:
                self._update_file_status(
                    db, file_id, FileStatus.FAILED, error_msg
                )
            except Exception:
                pass  # If we can't update status, at least return error
            
            return {
                "success": False,
                "error": error_msg,
                "file_id": file_id,
                "step": "unknown"
            }
        
        finally:
            db.close()


def process_file(file_id: int) -> Dict[str, Any]:
    """Convenience function to process a file.
    
    Args:
        file_id: Bordereaux file ID
        
    Returns:
        Dictionary with processing results
    """
    service = PipelineService()
    return service.process_file(file_id)

