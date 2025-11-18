import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from datetime import date
from sqlalchemy.orm import Session

from app.models.bordereaux import BordereauxRowCreate
from app.models.validation import BordereauxValidationError


class ValidationService:
    """Service for validating bordereaux rows against rules."""
    
    def __init__(self, rules_file: str = "rules.json"):
        self.rules_file = Path(rules_file)
        self.rules = self._load_rules()
    
    def _load_rules(self) -> Dict[str, Any]:
        """Load validation rules from JSON file.
        
        Returns:
            Dictionary with validation rules
        """
        if not self.rules_file.exists():
            # Return default rules if file doesn't exist
            return self._get_default_rules()
        
        try:
            with open(self.rules_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading rules file: {str(e)}")
            return self._get_default_rules()
    
    def _get_default_rules(self) -> Dict[str, Any]:
        """Get default validation rules.
        
        Returns:
            Dictionary with default rules
        """
        return {
            "required_fields": [
                "policy_number"
            ],
            "date_rules": [
                {
                    "name": "inception_before_expiry",
                    "inception_field": "inception_date",
                    "expiry_field": "expiry_date",
                    "message": "Inception date must be before or equal to expiry date"
                }
            ],
            "numeric_rules": [
                {
                    "name": "premium_non_negative",
                    "field": "premium_amount",
                    "min_value": 0,
                    "message": "Premium amount must be greater than or equal to 0"
                },
                {
                    "name": "claim_non_negative",
                    "field": "claim_amount",
                    "min_value": 0,
                    "message": "Claim amount must be greater than or equal to 0"
                },
                {
                    "name": "commission_non_negative",
                    "field": "commission_amount",
                    "min_value": 0,
                    "message": "Commission amount must be greater than or equal to 0"
                },
                {
                    "name": "net_premium_non_negative",
                    "field": "net_premium",
                    "min_value": 0,
                    "message": "Net premium must be greater than or equal to 0"
                }
            ]
        }
    
    def _validate_required_fields(
        self,
        row: BordereauxRowCreate,
        row_index: int,
        required_fields: List[str]
    ) -> List[Dict[str, Any]]:
        """Validate required fields are not null.
        
        Args:
            row: Bordereaux row to validate
            row_index: Index of the row
            required_fields: List of required field names
            
        Returns:
            List of error dictionaries
        """
        errors = []
        
        for field_name in required_fields:
            value = getattr(row, field_name, None)
            if value is None:
                errors.append({
                    "row_index": row_index,
                    "error_code": "REQUIRED_FIELD_MISSING",
                    "error_message": f"Required field '{field_name}' is missing or null",
                    "field_name": field_name,
                    "field_value": None,
                    "rule_name": "required_field"
                })
        
        return errors
    
    def _validate_date_rules(
        self,
        row: BordereauxRowCreate,
        row_index: int,
        date_rules: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Validate date-related rules.
        
        Args:
            row: Bordereaux row to validate
            row_index: Index of the row
            date_rules: List of date validation rules
            
        Returns:
            List of error dictionaries
        """
        errors = []
        
        for rule in date_rules:
            rule_name = rule.get("name", "unknown")
            inception_field = rule.get("inception_field")
            expiry_field = rule.get("expiry_field")
            message = rule.get("message", "Date validation failed")
            
            if inception_field and expiry_field:
                inception_date = getattr(row, inception_field, None)
                expiry_date = getattr(row, expiry_field, None)
                
                # Only validate if both dates are present
                if inception_date is not None and expiry_date is not None:
                    if inception_date > expiry_date:
                        errors.append({
                            "row_index": row_index,
                            "error_code": "DATE_VALIDATION_FAILED",
                            "error_message": message,
                            "field_name": f"{inception_field},{expiry_field}",
                            "field_value": f"{inception_date},{expiry_date}",
                            "rule_name": rule_name
                        })
        
        return errors
    
    def _validate_numeric_rules(
        self,
        row: BordereauxRowCreate,
        row_index: int,
        numeric_rules: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Validate numeric field rules.
        
        Args:
            row: Bordereaux row to validate
            row_index: Index of the row
            numeric_rules: List of numeric validation rules
            
        Returns:
            List of error dictionaries
        """
        errors = []
        
        for rule in numeric_rules:
            rule_name = rule.get("name", "unknown")
            field_name = rule.get("field")
            min_value = rule.get("min_value")
            max_value = rule.get("max_value")
            message = rule.get("message", "Numeric validation failed")
            
            if field_name:
                value = getattr(row, field_name, None)
                
                # Only validate if value is present
                if value is not None:
                    try:
                        num_value = float(value)
                        
                        if min_value is not None and num_value < min_value:
                            errors.append({
                                "row_index": row_index,
                                "error_code": "NUMERIC_VALIDATION_FAILED",
                                "error_message": message,
                                "field_name": field_name,
                                "field_value": str(value),
                                "rule_name": rule_name
                            })
                        
                        if max_value is not None and num_value > max_value:
                            errors.append({
                                "row_index": row_index,
                                "error_code": "NUMERIC_VALIDATION_FAILED",
                                "error_message": message,
                                "field_name": field_name,
                                "field_value": str(value),
                                "rule_name": rule_name
                            })
                    except (ValueError, TypeError):
                        errors.append({
                            "row_index": row_index,
                            "error_code": "INVALID_NUMERIC_VALUE",
                            "error_message": f"Field '{field_name}' contains invalid numeric value",
                            "field_name": field_name,
                            "field_value": str(value),
                            "rule_name": rule_name
                        })
        
        return errors
    
    def validate_rows(
        self,
        rows: List[BordereauxRowCreate]
    ) -> Tuple[List[BordereauxRowCreate], List[Dict[str, Any]]]:
        """Validate list of canonical rows against rules.
        
        Args:
            rows: List of BordereauxRowCreate objects to validate
            
        Returns:
            Tuple of (valid_rows, error_rows) where error_rows contain error dictionaries
        """
        valid_rows = []
        error_rows = []
        
        for idx, row in enumerate(rows):
            row_errors = []
            
            # Validate required fields
            required_fields = self.rules.get("required_fields", [])
            row_errors.extend(self._validate_required_fields(row, idx, required_fields))
            
            # Validate date rules
            date_rules = self.rules.get("date_rules", [])
            row_errors.extend(self._validate_date_rules(row, idx, date_rules))
            
            # Validate numeric rules
            numeric_rules = self.rules.get("numeric_rules", [])
            row_errors.extend(self._validate_numeric_rules(row, idx, numeric_rules))
            
            if row_errors:
                error_rows.extend(row_errors)
            else:
                valid_rows.append(row)
        
        return valid_rows, error_rows
    
    def save_validation_errors(
        self,
        db: Session,
        file_id: int,
        error_rows: List[Dict[str, Any]]
    ) -> int:
        """Save validation errors to database.
        
        Args:
            db: Database session
            file_id: Bordereaux file ID
            error_rows: List of error dictionaries
            
        Returns:
            Number of errors saved
        """
        count = 0
        
        for error in error_rows:
            validation_error = BordereauxValidationError(
                file_id=file_id,
                row_index=error["row_index"],
                error_code=error["error_code"],
                error_message=error["error_message"],
                field_name=error.get("field_name"),
                field_value=error.get("field_value"),
                rule_name=error.get("rule_name")
            )
            db.add(validation_error)
            count += 1
        
        db.commit()
        return count
    
    def save_validation_errors_json(
        self,
        file_id: int,
        error_rows: List[Dict[str, Any]],
        output_dir: str = "validation_reports"
    ) -> Path:
        """Save validation errors to JSON file.
        
        Args:
            file_id: Bordereaux file ID
            error_rows: List of error dictionaries
            output_dir: Directory to save JSON file
            
        Returns:
            Path to saved JSON file
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        from datetime import datetime
        filename = f"validation_errors_{file_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        file_path = output_path / filename
        
        report = {
            "file_id": file_id,
            "generated_at": datetime.utcnow().isoformat(),
            "total_errors": len(error_rows),
            "errors": error_rows
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        return file_path


def validate_rows(
    rows: List[BordereauxRowCreate],
    rules_file: Optional[str] = None
) -> Tuple[List[BordereauxRowCreate], List[Dict[str, Any]]]:
    """Convenience function to validate rows.
    
    Args:
        rows: List of BordereauxRowCreate objects to validate
        rules_file: Optional path to rules JSON file
        
    Returns:
        Tuple of (valid_rows, error_rows)
    """
    service = ValidationService(rules_file=rules_file) if rules_file else ValidationService()
    return service.validate_rows(rows)

