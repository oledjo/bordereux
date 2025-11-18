from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.bordereaux import (
    BordereauxFile,
    BordereauxRow,
    BordereauxRowCreate,
    FileStatus
)
from app.models.validation import BordereauxValidationError
from app.services.validation_service import ValidationService
from app.core.logging import get_structured_logger


class ProcessingService:
    """Service for processing and persisting bordereaux data."""
    
    def __init__(self, rules_file: str = "rules.json"):
        self.validation_service = ValidationService(rules_file=rules_file)
        self.logger = get_structured_logger(__name__)
    
    def _create_bordereaux_row(
        self,
        db: Session,
        row_data: BordereauxRowCreate
    ) -> BordereauxRow:
        """Create a BordereauxRow from BordereauxRowCreate.
        
        Args:
            db: Database session
            row_data: Row data to create
            
        Returns:
            Created BordereauxRow instance
        """
        bordereaux_row = BordereauxRow(
            file_id=row_data.file_id,
            policy_number=row_data.policy_number,
            insured_name=row_data.insured_name,
            inception_date=row_data.inception_date,
            expiry_date=row_data.expiry_date,
            premium_amount=row_data.premium_amount,
            currency=row_data.currency,
            claim_amount=row_data.claim_amount,
            commission_amount=row_data.commission_amount,
            net_premium=row_data.net_premium,
            broker_name=row_data.broker_name,
            product_type=row_data.product_type,
            coverage_type=row_data.coverage_type,
            risk_location=row_data.risk_location,
            row_number=row_data.row_number,
            raw_data=row_data.raw_data,
        )
        
        db.add(bordereaux_row)
        return bordereaux_row
    
    def _update_file_stats(
        self,
        db: Session,
        file_id: int,
        total_rows: int,
        valid_rows: int,
        error_rows: int,
        status: FileStatus
    ) -> None:
        """Update bordereaux file with processing statistics and status.
        
        Args:
            db: Database session
            file_id: Bordereaux file ID
            total_rows: Total number of rows processed
            valid_rows: Number of valid rows
            error_rows: Number of error rows
            status: Final processing status
        """
        bordereaux_file = db.query(BordereauxFile).filter(
            BordereauxFile.id == file_id
        ).first()
        
        if bordereaux_file:
            bordereaux_file.total_rows = total_rows
            bordereaux_file.processed_rows = valid_rows
            bordereaux_file.status = status
            bordereaux_file.processed_at = datetime.utcnow()
            
            # Set error message if there are errors
            if error_rows > 0:
                bordereaux_file.error_message = f"Processed with {error_rows} validation errors"
            else:
                bordereaux_file.error_message = None
            
            db.commit()
    
    def process_and_persist(
        self,
        db: Session,
        file_id: int,
        canonical_rows: List[BordereauxRowCreate],
        save_errors_to_db: bool = True,
        save_errors_to_json: bool = True
    ) -> Dict[str, Any]:
        """Process canonical rows: validate, persist valid rows, and save errors.
        
        Args:
            db: Database session
            file_id: Bordereaux file ID
            canonical_rows: List of canonical rows to process
            save_errors_to_db: Whether to save errors to database
            save_errors_to_json: Whether to save errors to JSON file
            
        Returns:
            Dictionary with processing results:
                - total_rows: Total number of rows
                - valid_rows: Number of valid rows
                - error_rows: Number of error rows
                - saved_rows: Number of rows saved to database
                - saved_errors: Number of errors saved
                - status: Final file status
                - error_report_path: Path to error JSON file (if saved)
        """
        total_rows = len(canonical_rows)
        
        self.logger.info(
            "Validation started",
            file_id=file_id,
            total_rows=total_rows
        )
        
        # Validate rows
        valid_rows, error_rows = self.validation_service.validate_rows(canonical_rows)
        
        valid_count = len(valid_rows)
        error_count = len(error_rows)
        
        self.logger.info(
            "Validation completed",
            file_id=file_id,
            total_rows=total_rows,
            valid_rows=valid_count,
            error_rows=error_count
        )
        
        # Persist valid rows
        saved_count = 0
        for row in valid_rows:
            try:
                # Ensure file_id is set
                row.file_id = file_id
                self._create_bordereaux_row(db, row)
                saved_count += 1
            except Exception as e:
                self.logger.error(
                    "Error saving row",
                    file_id=file_id,
                    row_number=row.row_number,
                    error=str(e)
                )
                # Add to error rows
                error_rows.append({
                    "row_index": row.row_number - 1 if row.row_number else saved_count,
                    "error_code": "PERSISTENCE_ERROR",
                    "error_message": f"Error saving row to database: {str(e)}",
                    "field_name": None,
                    "field_value": None,
                    "rule_name": "persistence"
                })
                error_count += 1
                valid_count -= 1
        
        # Commit valid rows
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise Exception(f"Error committing rows to database: {str(e)}")
        
        # Save validation errors
        saved_errors = 0
        error_report_path = None
        
        if error_rows:
            if save_errors_to_db:
                saved_errors = self.validation_service.save_validation_errors(
                    db, file_id, error_rows
                )
            
            if save_errors_to_json:
                error_report_path = self.validation_service.save_validation_errors_json(
                    file_id, error_rows
                )
        
        # Determine final status
        if error_count == 0:
            status = FileStatus.PROCESSED_OK
        else:
            status = FileStatus.PROCESSED_WITH_ERRORS
        
        # Update file statistics and status
        self._update_file_stats(
            db, file_id, total_rows, valid_count, error_count, status
        )
        
        self.logger.info(
            "Processing completed",
            file_id=file_id,
            total_rows=total_rows,
            valid_rows=valid_count,
            error_rows=error_count,
            saved_rows=saved_count,
            status=status.value
        )
        
        return {
            "total_rows": total_rows,
            "valid_rows": valid_count,
            "error_rows": error_count,
            "saved_rows": saved_count,
            "saved_errors": saved_errors,
            "status": status.value,
            "error_report_path": str(error_report_path) if error_report_path else None,
        }
    
    def process_file_with_template(
        self,
        db: Session,
        file_id: int,
        file_path: str,
        template,
        save_errors_to_db: bool = True,
        save_errors_to_json: bool = True
    ) -> Dict[str, Any]:
        """Process file: parse, map, validate, and persist.
        
        Convenience method that combines parsing, mapping, validation, and persistence.
        
        Args:
            db: Database session
            file_id: Bordereaux file ID
            file_path: Path to the file to process
            template: Template to use for mapping
            save_errors_to_db: Whether to save errors to database
            save_errors_to_json: Whether to save errors to JSON file
            
        Returns:
            Dictionary with processing results
        """
        from app.services.parsing_service import ParsingService
        from app.services.mapping_service import map_to_canonical
        
        # Parse file
        parsing_service = ParsingService()
        df = parsing_service.parse_file(file_path)
        
        # Map to canonical rows
        canonical_rows = map_to_canonical(df, template, file_id)
        
        # Process and persist
        return self.process_and_persist(
            db, file_id, canonical_rows, save_errors_to_db, save_errors_to_json
        )


def process_and_persist(
    db: Session,
    file_id: int,
    canonical_rows: List[BordereauxRowCreate],
    rules_file: Optional[str] = None,
    save_errors_to_db: bool = True,
    save_errors_to_json: bool = True
) -> Dict[str, Any]:
    """Convenience function to process and persist rows.
    
    Args:
        db: Database session
        file_id: Bordereaux file ID
        canonical_rows: List of canonical rows to process
        rules_file: Optional path to rules JSON file
        save_errors_to_db: Whether to save errors to database
        save_errors_to_json: Whether to save errors to JSON file
        
    Returns:
        Dictionary with processing results
    """
    service = ProcessingService(rules_file=rules_file) if rules_file else ProcessingService()
    return service.process_and_persist(
        db, file_id, canonical_rows, save_errors_to_db, save_errors_to_json
    )

