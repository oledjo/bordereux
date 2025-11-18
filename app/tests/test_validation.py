import pytest
from datetime import date
from app.services.validation_service import ValidationService
from app.models.bordereaux import BordereauxRowCreate, Currency


class TestValidation:
    """Tests for validation service."""
    
    def test_validate_required_fields(self):
        """Test validation of required fields."""
        service = ValidationService()
        
        # Row with missing required field
        row = BordereauxRowCreate(
            file_id=1,
            policy_number=None,  # Required field missing
            premium_amount=1000.0,
        )
        
        valid_rows, error_rows = service.validate_rows([row])
        
        assert len(valid_rows) == 0
        assert len(error_rows) > 0
        assert any(error.get("error_code") == "REQUIRED_FIELD_MISSING" for error in error_rows)
    
    def test_validate_date_order(self):
        """Test validation of date order (inception <= expiry)."""
        service = ValidationService()
        
        # Row with invalid date order
        row = BordereauxRowCreate(
            file_id=1,
            policy_number="POL001",
            inception_date=date(2025, 1, 1),
            expiry_date=date(2024, 1, 1),  # Expiry before inception
        )
        
        valid_rows, error_rows = service.validate_rows([row])
        
        assert len(valid_rows) == 0
        assert len(error_rows) > 0
        assert any(error.get("error_code") == "DATE_VALIDATION_FAILED" for error in error_rows)
    
    def test_validate_numeric_rules(self):
        """Test validation of numeric rules (non-negative amounts)."""
        service = ValidationService()
        
        # Row with negative premium
        row = BordereauxRowCreate(
            file_id=1,
            policy_number="POL001",
            premium_amount=-100.0,  # Negative amount
        )
        
        valid_rows, error_rows = service.validate_rows([row])
        
        assert len(valid_rows) == 0
        assert len(error_rows) > 0
        assert any(error.get("error_code") == "NUMERIC_VALIDATION_FAILED" for error in error_rows)
    
    def test_validate_valid_row(self):
        """Test that a valid row passes all validations."""
        service = ValidationService()
        
        row = BordereauxRowCreate(
            file_id=1,
            policy_number="POL001",
            inception_date=date(2024, 1, 1),
            expiry_date=date(2025, 1, 1),
            premium_amount=1000.0,
        )
        
        valid_rows, error_rows = service.validate_rows([row])
        
        assert len(valid_rows) == 1
        assert len(error_rows) == 0
    
    def test_validate_multiple_rows(self):
        """Test validation of multiple rows."""
        service = ValidationService()
        
        rows = [
            BordereauxRowCreate(file_id=1, policy_number="POL001", premium_amount=1000.0),
            BordereauxRowCreate(file_id=1, policy_number=None, premium_amount=2000.0),  # Invalid
            BordereauxRowCreate(file_id=1, policy_number="POL003", premium_amount=-100.0),  # Invalid
        ]
        
        valid_rows, error_rows = service.validate_rows(rows)
        
        assert len(valid_rows) == 1
        assert len(error_rows) == 2

