import pytest
import pandas as pd
from datetime import date
from app.services.mapping_service import map_to_canonical
from app.models.bordereaux import BordereauxRowCreate


class TestMapping:
    """Tests for mapping service."""
    
    def test_map_to_canonical(self, sample_template):
        """Test mapping DataFrame to canonical rows."""
        data = {
            "Policy Number": ["POL001", "POL002"],
            "Insured Name": ["John Doe", "Jane Smith"],
            "Inception Date": ["2024-01-01", "2024-02-01"],
            "Expiry Date": ["2025-01-01", "2025-02-01"],
            "Premium Amount": [1000.50, 2000.75],
            "Currency": ["USD", "USD"],
        }
        
        df = pd.DataFrame(data)
        canonical_rows = map_to_canonical(df, sample_template, file_id=1)
        
        assert len(canonical_rows) == 2
        assert isinstance(canonical_rows[0], BordereauxRowCreate)
        assert canonical_rows[0].policy_number == "POL001"
        assert canonical_rows[0].insured_name == "John Doe"
        assert canonical_rows[0].premium_amount == 1000.50
    
    def test_map_with_missing_columns(self, sample_template):
        """Test mapping with missing columns (should handle gracefully)."""
        data = {
            "Policy Number": ["POL001"],
            "Insured Name": ["John Doe"],
            # Missing other columns
        }
        
        df = pd.DataFrame(data)
        canonical_rows = map_to_canonical(df, sample_template, file_id=1)
        
        assert len(canonical_rows) == 1
        assert canonical_rows[0].policy_number == "POL001"
        # Missing fields should be None
        assert canonical_rows[0].premium_amount is None
    
    def test_map_with_date_normalization(self, sample_template):
        """Test that dates are normalized correctly."""
        data = {
            "Policy Number": ["POL001"],
            "Inception Date": ["2024-01-01"],
            "Expiry Date": ["2025-01-01"],
        }
        
        df = pd.DataFrame(data)
        canonical_rows = map_to_canonical(df, sample_template, file_id=1)
        
        assert canonical_rows[0].inception_date == date(2024, 1, 1)
        assert canonical_rows[0].expiry_date == date(2025, 1, 1)
    
    def test_map_with_currency_normalization(self, sample_template):
        """Test that currency is normalized correctly."""
        data = {
            "Policy Number": ["POL001"],
            "Currency": ["usd"],
        }
        
        df = pd.DataFrame(data)
        canonical_rows = map_to_canonical(df, sample_template, file_id=1)
        
        # Currency should be normalized to uppercase
        assert canonical_rows[0].currency == "USD"

