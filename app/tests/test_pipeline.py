import pytest
import pandas as pd
from app.services.pipeline_service import PipelineService
from app.models.bordereaux import FileStatus


class TestPipeline:
    """Tests for pipeline service."""
    
    def test_process_file_with_template(
        self,
        db_session,
        sample_bordereaux_file,
        sample_template,
        sample_excel_file
    ):
        """Test processing a file with a matching template."""
        # Update file path to point to sample Excel file
        sample_bordereaux_file.file_path = sample_excel_file
        db_session.commit()
        
        service = PipelineService()
        
        # Mock the storage service to return our test file
        service.storage_service.get_file = lambda db, file_id: sample_bordereaux_file
        
        result = service.process_file(sample_bordereaux_file.id)
        
        assert result["success"] is True
        assert "template_id" in result or result.get("status") == "new_template_required"
        assert result["file_id"] == sample_bordereaux_file.id
    
    def test_process_file_no_template(
        self,
        db_session,
        sample_bordereaux_file,
        sample_excel_file
    ):
        """Test processing a file without a matching template."""
        # Update file path to point to sample Excel file
        sample_bordereaux_file.file_path = sample_excel_file
        db_session.commit()
        
        service = PipelineService()
        
        # Mock the storage service to return our test file
        service.storage_service.get_file = lambda db, file_id: sample_bordereaux_file
        
        result = service.process_file(sample_bordereaux_file.id)
        
        # Should either find a template or require a new one
        assert result["success"] is True
        assert result["file_id"] == sample_bordereaux_file.id
    
    def test_process_file_not_found(self, db_session):
        """Test processing a non-existent file."""
        service = PipelineService()
        
        result = service.process_file(99999)
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()
    
    def test_update_file_status(self, db_session, sample_bordereaux_file):
        """Test updating file status."""
        service = PipelineService()
        
        service._update_file_status(
            db_session,
            sample_bordereaux_file.id,
            FileStatus.PROCESSING
        )
        
        db_session.refresh(sample_bordereaux_file)
        assert sample_bordereaux_file.status == FileStatus.PROCESSING

