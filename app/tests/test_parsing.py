import pytest
from app.services.parsing_service import ParsingService


class TestParsingService:
    """Tests for file parsing service."""
    
    def test_parse_excel_file(self, sample_excel_file):
        """Test parsing an Excel file."""
        service = ParsingService()
        df = service.parse_file(sample_excel_file)
        
        assert df is not None
        assert len(df) == 3
        assert "Policy Number" in df.columns
        assert "Premium Amount" in df.columns
    
    def test_parse_csv_file(self, sample_csv_file):
        """Test parsing a CSV file."""
        service = ParsingService()
        df = service.parse_file(sample_csv_file)
        
        assert df is not None
        assert len(df) == 3
        assert "Policy Number" in df.columns
        assert "Premium Amount" in df.columns
    
    def test_parse_invalid_file(self):
        """Test parsing an invalid file raises an error."""
        service = ParsingService()
        
        with pytest.raises(Exception):
            service.parse_file("/nonexistent/file.xlsx")
    
    def test_normalize_column_name(self):
        """Test column name normalization."""
        service = ParsingService()
        
        assert service._normalize_column_name("Policy Number") == "policy_number"
        assert service._normalize_column_name("Premium Amount") == "premium_amount"
        assert service._normalize_column_name("Inception Date") == "inception_date"
        assert service._normalize_column_name("  Test Column  ") == "test_column"

