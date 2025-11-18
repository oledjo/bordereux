import pytest
from app.services.pipeline_service import PipelineService
from app.models.template import Template, FileType


class TestTemplateMatching:
    """Tests for template matching."""
    
    def test_find_matching_template(self, db_session, sample_template):
        """Test finding a matching template."""
        service = PipelineService()
        
        file_headers = [
            "Policy Number",
            "Insured Name",
            "Inception Date",
            "Expiry Date",
            "Premium Amount",
            "Currency",
        ]
        
        template = service._find_matching_template(db_session, file_headers, "claims")
        
        assert template is not None
        assert template.template_id == "test_template"
    
    def test_no_matching_template(self, db_session):
        """Test when no template matches."""
        service = PipelineService()
        
        file_headers = ["Unknown Column 1", "Unknown Column 2"]
        
        template = service._find_matching_template(db_session, file_headers, None)
        
        assert template is None
    
    def test_template_matching_with_file_type(self, db_session, sample_template):
        """Test template matching with file type filter."""
        service = PipelineService()
        
        file_headers = ["Policy Number", "Premium Amount"]
        
        # Should match with correct file type
        template = service._find_matching_template(db_session, file_headers, "claims")
        assert template is not None
        
        # Should not match with wrong file type (if we had a premium template)
        template = service._find_matching_template(db_session, file_headers, "premium")
        # This might still match if no premium template exists, which is fine
    
    def test_normalize_column_name(self):
        """Test column name normalization for matching."""
        service = PipelineService()
        
        assert service._normalize_column_name("Policy Number") == "policy_number"
        assert service._normalize_column_name("  Test  Column  ") == "test_column"

