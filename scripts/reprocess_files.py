#!/usr/bin/env python3
"""Script to reprocess files that need template matching."""

from app.core.database import get_db
from app.models.bordereaux import BordereauxFile, FileStatus
from app.services.pipeline_service import PipelineService

def reprocess_files_with_status(status: FileStatus):
    """Reprocess files with a specific status."""
    db = next(get_db())
    pipeline_service = PipelineService()
    
    files = db.query(BordereauxFile).filter(
        BordereauxFile.status == status
    ).all()
    
    if not files:
        print(f"No files found with status: {status.value}")
        return
    
    print(f"Found {len(files)} files with status: {status.value}")
    print("=" * 60)
    
    for file in files:
        print(f"\nProcessing file {file.id}: {file.filename}")
        try:
            result = pipeline_service.process_file(file.id)
            if result.get("success"):
                print(f"  ✅ Success - Status: {result.get('status')}")
                if result.get("template_id"):
                    print(f"     Template: {result.get('template_name')}")
            else:
                print(f"  ❌ Failed: {result.get('error')}")
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
    
    db.close()

if __name__ == "__main__":
    reprocess_files_with_status(FileStatus.NEW_TEMPLATE_REQUIRED)

