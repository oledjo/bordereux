from typing import Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.models.bordereaux import BordereauxFile, FileStatus
from app.services.pipeline_service import PipelineService
from app.core.logging import get_structured_logger


class ProcessNewFilesJob:
    """Job to process all unprocessed bordereaux files."""
    
    def __init__(self):
        self.pipeline_service = PipelineService()
        self.logger = get_structured_logger(__name__)
    
    def run(self) -> Dict[str, Any]:
        """Run the job to process all unprocessed files.
        
        Queries files with status RECEIVED and processes each one.
        
        Returns:
            Dictionary with job execution results:
                - processed_count: Number of files processed
                - success_count: Number of files processed successfully
                - failed_count: Number of files that failed
                - new_template_count: Number of files requiring new templates
                - results: List of individual file processing results
        """
        db = next(get_db())
        
        results = {
            "processed_count": 0,
            "success_count": 0,
            "failed_count": 0,
            "new_template_count": 0,
            "results": [],
        }
        
        try:
            # Query files with status RECEIVED
            unprocessed_files = db.query(BordereauxFile).filter(
                BordereauxFile.status == FileStatus.RECEIVED
            ).all()
            
            if not unprocessed_files:
                self.logger.info("No unprocessed files found")
                return results
            
            self.logger.info(
                "Processing new files job started",
                file_count=len(unprocessed_files)
            )
            
            # Process each file
            for bordereaux_file in unprocessed_files:
                file_id = bordereaux_file.id
                filename = bordereaux_file.filename
                
                self.logger.info(
                    "Processing file",
                    file_id=file_id,
                    filename=filename
                )
                
                try:
                    # Process file through pipeline
                    result = self.pipeline_service.process_file(file_id)
                    
                    # Track results
                    file_result = {
                        "file_id": file_id,
                        "filename": filename,
                        "success": result.get("success", False),
                        "status": result.get("status"),
                        "error": result.get("error"),
                        "step": result.get("step"),
                    }
                    
                    if result.get("success"):
                        results["success_count"] += 1
                        
                        # Add processing details if available
                        if "total_rows" in result:
                            file_result["total_rows"] = result.get("total_rows")
                            file_result["valid_rows"] = result.get("valid_rows")
                            file_result["error_rows"] = result.get("error_rows")
                            file_result["saved_rows"] = result.get("saved_rows")
                            file_result["template_id"] = result.get("template_id")
                            file_result["template_name"] = result.get("template_name")
                            file_result["error_report_path"] = result.get("error_report_path")
                        
                        if result.get("status") == "new_template_required":
                            results["new_template_count"] += 1
                            file_result["proposal_path"] = result.get("proposal_path")
                            file_result["mapped_count"] = result.get("mapped_count")
                            file_result["total_headers"] = result.get("total_headers")
                    else:
                        results["failed_count"] += 1
                    
                    results["results"].append(file_result)
                    results["processed_count"] += 1
                    
                    # Log result
                    if result.get("success"):
                        if result.get("status") == "new_template_required":
                            self.logger.info(
                                "File requires new template",
                                file_id=file_id,
                                proposal_path=result.get('proposal_path'),
                                mapped_count=result.get('mapped_count')
                            )
                        else:
                            self.logger.info(
                                "File processed successfully",
                                file_id=file_id,
                                template_id=result.get('template_id'),
                                total_rows=result.get('total_rows', 0),
                                valid_rows=result.get('valid_rows', 0),
                                error_rows=result.get('error_rows', 0)
                            )
                    else:
                        self.logger.error(
                            "File processing failed",
                            file_id=file_id,
                            error=result.get('error'),
                            step=result.get('step')
                        )
                
                except Exception as e:
                    # Catch any unexpected errors
                    error_msg = f"Unexpected error processing file {file_id}: {str(e)}"
                    self.logger.exception(
                        "Unexpected error processing file",
                        file_id=file_id,
                        error=str(e)
                    )
                    
                    results["failed_count"] += 1
                    results["processed_count"] += 1
                    results["results"].append({
                        "file_id": file_id,
                        "filename": filename,
                        "success": False,
                        "error": error_msg,
                        "step": "unknown"
                    })
        
        except Exception as e:
            self.logger.exception("Error in process_new_files job", error=str(e))
            raise
        
        finally:
            db.close()
        
        # Log summary
        self.logger.info(
            "Processing new files job completed",
            processed_count=results['processed_count'],
            success_count=results['success_count'],
            failed_count=results['failed_count'],
            new_template_count=results['new_template_count']
        )
        
        return results


def run_process_new_files_job() -> Dict[str, Any]:
    """Convenience function to run the process new files job.
    
    Returns:
        Dictionary with job execution results
    """
    job = ProcessNewFilesJob()
    return job.run()

