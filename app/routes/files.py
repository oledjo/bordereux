from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.bordereaux import (
    BordereauxFile,
    BordereauxFileResponse,
    BordereauxRow,
    FileStatus
)
from app.models.validation import BordereauxValidationError
from app.models.template import TemplateCreate, FileType
from app.services.storage_service import StorageService
from app.services.pipeline_service import PipelineService
from app.services.template_repository import TemplateRepository
from app.core.logging import get_structured_logger
import json
from pathlib import Path

router = APIRouter(prefix="/files", tags=["files"])
logger = get_structured_logger(__name__)
storage_service = StorageService()
pipeline_service = PipelineService()
template_repository = TemplateRepository()


@router.get("/", response_class=HTMLResponse)
async def list_files(
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    db: Session = Depends(get_db)
):
    """List bordereaux files with status, sender, and created_at (HTML view).
    
    Args:
        status: Optional status filter
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        db: Database session
        
    Returns:
        HTML page with files table
    """
    try:
        query = db.query(BordereauxFile)
        
        # Filter by status if provided
        if status:
            try:
                status_enum = FileStatus(status.lower())
                query = query.filter(BordereauxFile.status == status_enum)
            except ValueError:
                pass
        
        # Order by created_at descending (newest first)
        query = query.order_by(BordereauxFile.created_at.desc())
        
        # Apply pagination
        files = query.offset(skip).limit(limit).all()
        
        # Build status filter options
        status_options = [s.value for s in FileStatus]
        status_filter_html = '<option value="">All Statuses</option>' + ''.join(
            f'<option value="{s}" {"selected" if status == s else ""}>{s.replace("_", " ").title()}</option>'
            for s in status_options
        )
        
        # Build table rows
        files_rows = ''
        if files:
            for file in files:
                status_class = file.status.value.replace("_", "-")
                status_display = file.status.value.replace("_", " ").title()
                # Add "Edit Mappings" and "Reprocess" buttons for NEW_TEMPLATE_REQUIRED status
                edit_mappings_cell = ""
                reprocess_cell = ""
                if file.status == FileStatus.NEW_TEMPLATE_REQUIRED:
                    edit_mappings_cell = f'<a href="/mappings/file/{file.id}" class="mappings-link" style="color: #007bff; text-decoration: none;">📋 Edit Mappings</a>'
                    reprocess_cell = f'<button onclick="reprocessFile(this, {file.id}, {json.dumps(file.filename)})" class="btn-reprocess">🔄 Reprocess</button>'
                else:
                    edit_mappings_cell = "-"
                    reprocess_cell = "-"
                
                files_rows += f'''
                <tr>
                    <td>{file.id}</td>
                    <td><a href="/files/{file.id}" class="file-link">{file.filename}</a></td>
                    <td><span class="badge badge-{status_class}">{status_display}</span></td>
                    <td>{file.sender or "N/A"}</td>
                    <td>{file.total_rows or 0}</td>
                    <td>{file.processed_rows or 0}</td>
                    <td>{file.created_at.strftime("%Y-%m-%d %H:%M") if file.created_at else "N/A"}</td>
                    <td style="text-align: center;">{edit_mappings_cell}</td>
                    <td style="text-align: center;">{reprocess_cell}</td>
                    <td style="text-align: center;">
                        <button onclick="deleteFile(this, {file.id}, {json.dumps(file.filename)})" class="btn-delete">Delete</button>
                    </td>
                </tr>
                '''
        else:
            files_rows = '<tr><td colspan="10"><div class="empty-state"><div class="empty-state-icon">📭</div><p>No files found</p></div></td></tr>'
        
        html_content = f'''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Bordereaux Files</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    background: #f5f5f5;
                    padding: 20px;
                }}
                .container {{
                    max-width: 1400px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    padding: 30px;
                }}
                h1 {{
                    color: #333;
                    margin-bottom: 20px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }}
                .header-actions {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 20px;
                }}
                .btn-back {{
                    padding: 10px 20px;
                    background: #6c757d;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    text-decoration: none;
                    font-weight: 600;
                    display: inline-block;
                    transition: all 0.2s;
                }}
                .btn-back:hover {{
                    background: #545b62;
                    transform: translateY(-2px);
                }}
                .btn {{
                    padding: 10px 20px;
                    border: none;
                    border-radius: 6px;
                    cursor: pointer;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 14px;
                    font-weight: 600;
                    transition: transform 0.2s;
                }}
                .btn-primary {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }}
                .btn-primary:hover {{
                    transform: translateY(-1px);
                    box-shadow: 0 4px 8px rgba(102, 126, 234, 0.3);
                }}
                .filters {{
                    display: flex;
                    gap: 15px;
                    margin-bottom: 20px;
                    align-items: center;
                }}
                .filter-group {{
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }}
                .filter-group label {{
                    font-weight: 600;
                    color: #555;
                }}
                select, input {{
                    padding: 8px 12px;
                    border: 1px solid #ddd;
                    border-radius: 6px;
                    font-size: 14px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                }}
                th {{
                    background: #f8f9fa;
                    padding: 12px;
                    text-align: left;
                    font-weight: 600;
                    color: #555;
                    border-bottom: 2px solid #dee2e6;
                }}
                td {{
                    padding: 12px;
                    border-bottom: 1px solid #dee2e6;
                }}
                tr:hover {{
                    background: #f8f9fa;
                }}
                .file-link {{
                    color: #667eea;
                    text-decoration: none;
                    font-weight: 600;
                }}
                .file-link:hover {{
                    text-decoration: underline;
                }}
                .badge {{
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 12px;
                    font-weight: 600;
                    text-transform: uppercase;
                }}
                .badge-pending {{ background: #fff3cd; color: #856404; }}
                .badge-received {{ background: #d1ecf1; color: #0c5460; }}
                .badge-processing {{ background: #d4edda; color: #155724; }}
                .badge-processed-ok {{ background: #d4edda; color: #155724; }}
                .badge-processed-with-errors {{ background: #f8d7da; color: #721c24; }}
                .badge-failed {{ background: #f8d7da; color: #721c24; }}
                .badge-new-template-required {{ background: #fff3cd; color: #856404; }}
                .btn-reprocess {{
                    padding: 6px 12px;
                    background: #28a745;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 12px;
                    font-weight: 600;
                }}
                .btn-reprocess:hover {{
                    background: #218838;
                }}
                .btn-reprocess:disabled {{
                    background: #6c757d;
                    cursor: not-allowed;
                    opacity: 0.6;
                }}
                .btn-delete {{
                    padding: 6px 12px;
                    background: #dc3545;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 12px;
                    font-weight: 600;
                }}
                .btn-delete:hover {{
                    background: #c82333;
                }}
                .btn-delete:disabled {{
                    background: #6c757d;
                    cursor: not-allowed;
                    opacity: 0.6;
                }}
                .empty-state {{
                    text-align: center;
                    padding: 60px 20px;
                    color: #999;
                }}
                .empty-state-icon {{
                    font-size: 48px;
                    margin-bottom: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header-actions">
                    <h1>📄 Bordereaux Files</h1>
                    <div>
                        <a href="/mappings" class="btn btn-secondary" style="margin-right: 10px;">📋 Templates</a>
                        <a href="/files/upload" class="btn btn-primary" style="margin-right: 10px;">+ Upload File</a>
                        <a href="/" class="btn-back">← Back to Home</a>
                    </div>
                </div>
                
                <div class="filters">
                    <div class="filter-group">
                        <label>Status:</label>
                        <select id="statusFilter" onchange="filterFiles()">
                            {status_filter_html}
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>Limit:</label>
                        <input type="number" id="limitFilter" value="{limit}" min="10" max="1000" step="10" onchange="filterFiles()">
                    </div>
                </div>
                
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Filename</th>
                            <th>Status</th>
                            <th>Sender</th>
                            <th>Total Rows</th>
                            <th>Processed</th>
                            <th>Created</th>
                            <th>Edit Mappings</th>
                            <th>Reprocess</th>
                            <th>Delete</th>
                        </tr>
                    </thead>
                    <tbody>
                        {files_rows}
                    </tbody>
                </table>
            </div>
            
            <script>
                function filterFiles() {{
                    const status = document.getElementById('statusFilter').value;
                    const limit = document.getElementById('limitFilter').value;
                    const params = new URLSearchParams();
                    if (status) params.append('status', status);
                    if (limit) params.append('limit', limit);
                    window.location.href = '/files?' + params.toString();
                }}
                
                async function reprocessFile(button, fileId, filename) {{
                    const confirmed = confirm(`Reprocess file "${{filename}}"?\\n\\nThis will attempt to match the file with an existing template and process it.`);
                    
                    if (!confirmed) {{
                        return;
                    }}
                    
                    // Disable button and show loading state
                    const originalText = button.innerHTML;
                    button.disabled = true;
                    button.innerHTML = '⏳ Processing...';
                    
                    try {{
                        const response = await fetch(`/files/${{fileId}}/reprocess`, {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                            }}
                        }});
                        
                        const result = await response.json();
                        
                        if (response.ok) {{
                            alert(`File reprocessed successfully!\\n\\nStatus: ${{result.status}}\\nTotal rows: ${{result.total_rows || 0}}\\nValid rows: ${{result.valid_rows || 0}}\\nError rows: ${{result.error_rows || 0}}`);
                            // Reload page to show updated status
                            window.location.reload();
                        }} else {{
                            alert(`Error reprocessing file: ${{result.detail || 'Unknown error'}}`);
                            button.disabled = false;
                            button.innerHTML = originalText;
                        }}
                    }} catch (error) {{
                        alert(`Error reprocessing file: ${{error.message}}`);
                        button.disabled = false;
                        button.innerHTML = originalText;
                    }}
                }}
                
                async function deleteFile(button, fileId, filename) {{
                    const confirmed = confirm(`Are you sure you want to delete the file "${{filename}}"?\\n\\nThis will permanently delete the file and all associated data. This action cannot be undone.`);
                    
                    if (!confirmed) {{
                        return;
                    }}
                    
                    // Disable button and show loading state
                    const originalText = button.innerHTML;
                    button.disabled = true;
                    button.innerHTML = '⏳';
                    
                    try {{
                        const response = await fetch(`/files/${{fileId}}/delete`, {{
                            method: 'DELETE',
                            headers: {{
                                'Content-Type': 'application/json',
                            }}
                        }});
                        
                        if (response.ok) {{
                            // Remove the row from table
                            const row = button.closest('tr');
                            row.style.opacity = '0.5';
                            row.style.transition = 'opacity 0.3s';
                            setTimeout(() => {{
                                row.remove();
                                // Check if table is now empty
                                const tbody = document.querySelector('table tbody');
                                if (tbody && tbody.children.length === 0) {{
                                    tbody.innerHTML = '<tr><td colspan="10"><div class="empty-state"><div class="empty-state-icon">📭</div><p>No files found</p></div></td></tr>';
                                }}
                            }}, 300);
                        }} else {{
                            const error = await response.json();
                            alert(`Error deleting file: ${{error.detail || 'Unknown error'}}`);
                            button.disabled = false;
                            button.innerHTML = originalText;
                        }}
                    }} catch (error) {{
                        alert(`Error deleting file: ${{error.message}}`);
                        button.disabled = false;
                        button.innerHTML = originalText;
                    }}
                }}
            </script>
        </body>
        </html>
        '''
        
        logger.info("Files listed", count=len(files), status=status, skip=skip, limit=limit)
        return HTMLResponse(content=html_content)
    
    except Exception as e:
        logger.error("Error listing files", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")


@router.get("/api", response_model=List[dict])
async def list_files_api(
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    db: Session = Depends(get_db)
):
    """List bordereaux files (API endpoint for JSON).
    
    Args:
        status: Optional status filter
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        db: Database session
        
    Returns:
        List of file summaries as JSON
    """
    try:
        query = db.query(BordereauxFile)
        
        if status:
            try:
                status_enum = FileStatus(status.lower())
                query = query.filter(BordereauxFile.status == status_enum)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status: {status}. Valid values: {[s.value for s in FileStatus]}"
                )
        
        query = query.order_by(BordereauxFile.created_at.desc())
        files = query.offset(skip).limit(limit).all()
        
        result = []
        for file in files:
            result.append({
                "id": file.id,
                "filename": file.filename,
                "status": file.status.value,
                "sender": file.sender,
                "subject": file.subject,
                "created_at": file.created_at.isoformat() if file.created_at else None,
                "total_rows": file.total_rows or 0,
                "processed_rows": file.processed_rows or 0,
            })
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing files", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")


@router.delete("/{file_id}/delete")
async def delete_file(
    file_id: int,
    db: Session = Depends(get_db)
):
    """Delete a bordereaux file."""
    bordereaux_file = db.query(BordereauxFile).filter(BordereauxFile.id == file_id).first()
    
    if not bordereaux_file:
        raise HTTPException(status_code=404, detail=f"File with ID {file_id} not found")
    
    filename = bordereaux_file.filename
    
    logger.info("Deleting file", file_id=file_id, filename=filename)
    
    # Delete file using storage service
    deleted = storage_service.delete_file(db, file_id)
    
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete file")
    
    logger.info("File deleted successfully", file_id=file_id, filename=filename)
    
    # Return success response
    return JSONResponse(
        content={
            "success": True,
            "message": f"File '{filename}' deleted successfully"
        },
        status_code=200
    )


@router.get("/upload", response_class=HTMLResponse)
async def upload_page():
    """Serve the file upload page."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Upload Bordereaux File</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }
            .container {
                background: white;
                border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
                padding: 40px;
                max-width: 600px;
                width: 100%;
            }
            h1 {
                color: #333;
                margin-bottom: 10px;
                font-size: 28px;
            }
            .subtitle {
                color: #666;
                margin-bottom: 30px;
                font-size: 14px;
            }
            .upload-area {
                border: 2px dashed #ddd;
                border-radius: 8px;
                padding: 40px;
                text-align: center;
                transition: all 0.3s ease;
                cursor: pointer;
                background: #f9f9f9;
            }
            .upload-area:hover {
                border-color: #667eea;
                background: #f0f0ff;
            }
            .upload-area.dragover {
                border-color: #667eea;
                background: #e8e8ff;
            }
            .upload-icon {
                font-size: 48px;
                color: #667eea;
                margin-bottom: 15px;
            }
            .upload-text {
                color: #666;
                margin-bottom: 10px;
                font-size: 16px;
            }
            .upload-hint {
                color: #999;
                font-size: 12px;
            }
            input[type="file"] {
                display: none;
            }
            .file-info {
                margin-top: 20px;
                padding: 15px;
                background: #f0f0f0;
                border-radius: 6px;
                display: none;
            }
            .file-info.show {
                display: block;
            }
            .file-name {
                font-weight: 600;
                color: #333;
                margin-bottom: 5px;
            }
            .file-size {
                color: #666;
                font-size: 14px;
            }
            button {
                width: 100%;
                padding: 15px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                margin-top: 20px;
                transition: transform 0.2s ease;
            }
            button:hover:not(:disabled) {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            }
            button:disabled {
                opacity: 0.6;
                cursor: not-allowed;
            }
            .progress {
                margin-top: 20px;
                display: none;
            }
            .progress.show {
                display: block;
            }
            .progress-bar {
                width: 100%;
                height: 8px;
                background: #f0f0f0;
                border-radius: 4px;
                overflow: hidden;
            }
            .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                width: 0%;
                transition: width 0.3s ease;
            }
            .result {
                margin-top: 20px;
                padding: 20px;
                border-radius: 8px;
                display: none;
            }
            .result.show {
                display: block;
            }
            .result.success {
                background: #d4edda;
                border: 1px solid #c3e6cb;
                color: #155724;
            }
            .result.error {
                background: #f8d7da;
                border: 1px solid #f5c6cb;
                color: #721c24;
            }
            .result-info {
                margin-top: 15px;
                font-size: 14px;
            }
            .result-info p {
                margin: 5px 0;
            }
            .link {
                color: #667eea;
                text-decoration: none;
                font-weight: 600;
            }
            .link:hover {
                text-decoration: underline;
            }
            .btn-back {
                padding: 10px 20px;
                background: #6c757d;
                color: white;
                border: none;
                border-radius: 6px;
                text-decoration: none;
                font-weight: 600;
                display: inline-block;
                transition: all 0.2s;
            }
            .btn-back:hover {
                background: #545b62;
                transform: translateY(-2px);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h1>📄 Upload Bordereaux File</h1>
                <a href="/" class="btn-back">← Back to Home</a>
            </div>
            <p class="subtitle">Upload an Excel or CSV file to process</p>
            
            <form id="uploadForm" enctype="multipart/form-data">
                <div class="upload-area" id="uploadArea">
                    <div class="upload-icon">📁</div>
                    <div class="upload-text">Click to select or drag and drop</div>
                    <div class="upload-hint">Supports .xlsx, .xls, and .csv files</div>
                    <input type="file" id="fileInput" name="file" accept=".xlsx,.xls,.csv" required>
                </div>
                
                <div class="file-info" id="fileInfo">
                    <div class="file-name" id="fileName"></div>
                    <div class="file-size" id="fileSize"></div>
                </div>
                
                <div class="progress" id="progress">
                    <div class="progress-bar">
                        <div class="progress-fill" id="progressFill"></div>
                    </div>
                </div>
                
                <button type="submit" id="submitBtn">Upload and Process</button>
            </form>
            
            <div class="result" id="result"></div>
        </div>
        
        <script>
            const uploadArea = document.getElementById('uploadArea');
            const fileInput = document.getElementById('fileInput');
            const fileInfo = document.getElementById('fileInfo');
            const fileName = document.getElementById('fileName');
            const fileSize = document.getElementById('fileSize');
            const uploadForm = document.getElementById('uploadForm');
            const submitBtn = document.getElementById('submitBtn');
            const progress = document.getElementById('progress');
            const progressFill = document.getElementById('progressFill');
            const result = document.getElementById('result');
            
            // Click to select file
            uploadArea.addEventListener('click', () => fileInput.click());
            
            // Drag and drop
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });
            
            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });
            
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    fileInput.files = files;
                    handleFileSelect(files[0]);
                }
            });
            
            // File input change
            fileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    handleFileSelect(e.target.files[0]);
                }
            });
            
            function handleFileSelect(file) {
                fileName.textContent = file.name;
                fileSize.textContent = formatFileSize(file.size);
                fileInfo.classList.add('show');
                result.classList.remove('show');
            }
            
            function formatFileSize(bytes) {
                if (bytes === 0) return '0 Bytes';
                const k = 1024;
                const sizes = ['Bytes', 'KB', 'MB', 'GB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
            }
            
            // Form submission
            uploadForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                
                submitBtn.disabled = true;
                submitBtn.textContent = 'Processing...';
                progress.classList.add('show');
                result.classList.remove('show');
                
                // Simulate progress
                let progressValue = 0;
                const progressInterval = setInterval(() => {
                    progressValue += 10;
                    if (progressValue < 90) {
                        progressFill.style.width = progressValue + '%';
                    }
                }, 200);
                
                try {
                    const response = await fetch('/files/upload', {
                        method: 'POST',
                        body: formData
                    });
                    
                    clearInterval(progressInterval);
                    progressFill.style.width = '100%';
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        showResult('success', 'File uploaded and processed successfully!', data);
                    } else {
                        showResult('error', 'Error processing file: ' + (data.detail || 'Unknown error'), null);
                    }
                } catch (error) {
                    clearInterval(progressInterval);
                    showResult('error', 'Error uploading file: ' + error.message, null);
                } finally {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Upload and Process';
                    setTimeout(() => {
                        progress.classList.remove('show');
                        progressFill.style.width = '0%';
                    }, 1000);
                }
            });
            
            function showResult(type, message, data) {
                result.className = 'result ' + type + ' show';
                let html = '<strong>' + message + '</strong>';
                
                if (data) {
                    html += '<div class="result-info">';
                    if (data.file_id) {
                        html += '<p>File ID: <strong>' + data.file_id + '</strong></p>';
                        html += '<p><a href="/files/' + data.file_id + '" class="link">View file details</a></p>';
                    }
                    if (data.total_rows !== undefined) {
                        html += '<p>Total rows: ' + data.total_rows + '</p>';
                        html += '<p>Valid rows: ' + (data.valid_rows || 0) + '</p>';
                        html += '<p>Error rows: ' + (data.error_rows || 0) + '</p>';
                    }
                    if (data.status) {
                        html += '<p>Status: <strong>' + data.status + '</strong></p>';
                    }
                    if (data.template_id) {
                        html += '<p>Template: ' + data.template_name + ' (' + data.template_id + ')</p>';
                    }
                    if (data.proposal_path) {
                        html += '<p>Mapping proposal generated. Status: <strong>new_template_required</strong></p>';
                    }
                    html += '</div>';
                }
                
                result.innerHTML = html;
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and process a bordereaux file.
    
    Args:
        file: Uploaded file (Excel or CSV)
        db: Database session
        
    Returns:
        Processing results
    """
    try:
        # Validate file type
        allowed_extensions = ['.xlsx', '.xls', '.csv']
        file_extension = '.' + file.filename.split('.')[-1].lower() if '.' in file.filename else ''
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Read file content
        file_bytes = await file.read()
        
        if len(file_bytes) == 0:
            raise HTTPException(status_code=400, detail="File is empty")
        
        logger.info("File upload started", filename=file.filename, size=len(file_bytes))
        
        # Save file using storage service
        save_result = storage_service.save_raw_file(
            db=db,
            file_bytes=file_bytes,
            filename=file.filename,
            source_email="web_upload",
            subject="Web Upload",
        )
        
        file_id = save_result['file_id']
        
        # Update status to RECEIVED
        from app.models.bordereaux import FileStatus
        bordereaux_file = db.query(BordereauxFile).filter(BordereauxFile.id == file_id).first()
        if bordereaux_file:
            bordereaux_file.status = FileStatus.RECEIVED
            db.commit()
        
        # Process file through pipeline
        logger.info("Processing uploaded file", file_id=file_id)
        result = pipeline_service.process_file(file_id)
        
        if result.get("success"):
            logger.info("File processed successfully", file_id=file_id, status=result.get("status"))
            return JSONResponse(content=result, status_code=200)
        else:
            logger.error("File processing failed", file_id=file_id, error=result.get("error"))
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Error processing file")
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error uploading file", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


@router.get("/{file_id}", response_class=HTMLResponse)
async def get_file_details(
    file_id: int,
    db: Session = Depends(get_db)
):
    """Get detailed information about a bordereaux file (HTML view).
    
    Args:
        file_id: File ID
        db: Database session
        
    Returns:
        HTML page with file details and data table
    """
    try:
        bordereaux_file = db.query(BordereauxFile).filter(
            BordereauxFile.id == file_id
        ).first()
        
        if not bordereaux_file:
            raise HTTPException(status_code=404, detail=f"File with ID {file_id} not found")
        
        # Get rows
        rows = db.query(BordereauxRow).filter(
            BordereauxRow.file_id == file_id
        ).order_by(BordereauxRow.row_number).all()
        
        # Get error count
        error_count = db.query(BordereauxValidationError).filter(
            BordereauxValidationError.file_id == file_id
        ).count()
        
        # Build rows table
        rows_table = ''
        if rows:
            # Get column names from first row
            row_dict = rows[0].__dict__
            columns = [k for k in row_dict.keys() if not k.startswith('_') and k not in ['id', 'file_id', 'created_at', 'updated_at', 'raw_data']]
            
            # Header
            rows_table = '<thead><tr>' + ''.join(f'<th>{col.replace("_", " ").title()}</th>' for col in columns) + '</tr></thead><tbody>'
            
            # Rows
            for row in rows:
                rows_table += '<tr>'
                for col in columns:
                    value = getattr(row, col, None)
                    if value is None:
                        rows_table += '<td>-</td>'
                    elif isinstance(value, (int, float)):
                        rows_table += f'<td>{value}</td>'
                    else:
                        rows_table += f'<td>{str(value)}</td>'
                rows_table += '</tr>'
            rows_table += '</tbody>'
        else:
            rows_table = '<tbody><tr><td colspan="10" class="empty-state"><div class="empty-state-icon">📭</div><p>No rows processed yet</p></td></tr></tbody>'
        
        # Status badge
        status_class = bordereaux_file.status.value.replace("_", "-")
        status_display = bordereaux_file.status.value.replace("_", " ").title()
        
        # Success rate
        success_rate = (
            (bordereaux_file.processed_rows / bordereaux_file.total_rows * 100)
            if bordereaux_file.total_rows and bordereaux_file.total_rows > 0
            else 0
        )
        
        html_content = f'''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>File Details - {bordereaux_file.filename}</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    background: #f5f5f5;
                    padding: 20px;
                }}
                .container {{
                    max-width: 1600px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    padding: 30px;
                }}
                .header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 2px solid #dee2e6;
                }}
                .header h1 {{
                    color: #333;
                    font-size: 24px;
                }}
                .btn {{
                    padding: 10px 20px;
                    border: none;
                    border-radius: 6px;
                    cursor: pointer;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 14px;
                    font-weight: 600;
                    transition: transform 0.2s;
                }}
                .btn-secondary {{
                    background: #6c757d;
                    color: white;
                }}
                .btn-secondary:hover {{
                    transform: translateY(-1px);
                    box-shadow: 0 4px 8px rgba(108, 117, 125, 0.3);
                }}
                .info-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                .info-card {{
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 6px;
                }}
                .info-card label {{
                    display: block;
                    font-size: 12px;
                    color: #666;
                    margin-bottom: 5px;
                    text-transform: uppercase;
                    font-weight: 600;
                }}
                .info-card value {{
                    display: block;
                    font-size: 16px;
                    color: #333;
                    font-weight: 600;
                }}
                .badge {{
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 12px;
                    font-weight: 600;
                    text-transform: uppercase;
                }}
                .badge-pending {{ background: #fff3cd; color: #856404; }}
                .badge-received {{ background: #d1ecf1; color: #0c5460; }}
                .badge-processing {{ background: #d4edda; color: #155724; }}
                .badge-processed-ok {{ background: #d4edda; color: #155724; }}
                .badge-processed-with-errors {{ background: #f8d7da; color: #721c24; }}
                .badge-failed {{ background: #f8d7da; color: #721c24; }}
                .badge-new-template-required {{ background: #fff3cd; color: #856404; }}
                .stats {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                    gap: 15px;
                    margin-bottom: 30px;
                }}
                .stat-card {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 8px;
                    text-align: center;
                }}
                .stat-card .value {{
                    font-size: 32px;
                    font-weight: 700;
                    margin-bottom: 5px;
                }}
                .stat-card .label {{
                    font-size: 14px;
                    opacity: 0.9;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                }}
                th {{
                    background: #f8f9fa;
                    padding: 12px;
                    text-align: left;
                    font-weight: 600;
                    color: #555;
                    border-bottom: 2px solid #dee2e6;
                    position: sticky;
                    top: 0;
                }}
                td {{
                    padding: 12px;
                    border-bottom: 1px solid #dee2e6;
                }}
                tbody tr:hover {{
                    background: #f8f9fa;
                }}
                .empty-state {{
                    text-align: center;
                    padding: 60px 20px;
                    color: #999;
                }}
                .empty-state-icon {{
                    font-size: 48px;
                    margin-bottom: 10px;
                }}
                .section-title {{
                    font-size: 20px;
                    color: #333;
                    margin: 30px 0 15px 0;
                    padding-bottom: 10px;
                    border-bottom: 2px solid #dee2e6;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📄 {bordereaux_file.filename}</h1>
                    <a href="/files" class="btn btn-secondary">← Back to Files</a>
                </div>
                
                <div class="stats">
                    <div class="stat-card">
                        <div class="value">{bordereaux_file.total_rows or 0}</div>
                        <div class="label">Total Rows</div>
                    </div>
                    <div class="stat-card">
                        <div class="value">{bordereaux_file.processed_rows or 0}</div>
                        <div class="label">Processed Rows</div>
                    </div>
                    <div class="stat-card">
                        <div class="value">{error_count}</div>
                        <div class="label">Errors</div>
                    </div>
                    <div class="stat-card">
                        <div class="value">{success_rate:.1f}%</div>
                        <div class="label">Success Rate</div>
                    </div>
                </div>
                
                <div class="info-grid">
                    <div class="info-card">
                        <label>Status</label>
                        <value><span class="badge badge-{status_class}">{status_display}</span></value>
                    </div>
                    <div class="info-card">
                        <label>File ID</label>
                        <value>{bordereaux_file.id}</value>
                    </div>
                    <div class="info-card">
                        <label>File Size</label>
                        <value>{(bordereaux_file.file_size / 1024):.2f} KB</value>
                    </div>
                    <div class="info-card">
                        <label>Sender</label>
                        <value>{bordereaux_file.sender or "N/A"}</value>
                    </div>
                    <div class="info-card">
                        <label>Subject</label>
                        <value>{bordereaux_file.subject or "N/A"}</value>
                    </div>
                    <div class="info-card">
                        <label>Created</label>
                        <value>{bordereaux_file.created_at.strftime("%Y-%m-%d %H:%M:%S") if bordereaux_file.created_at else "N/A"}</value>
                    </div>
                    <div class="info-card">
                        <label>Processed</label>
                        <value>{bordereaux_file.processed_at.strftime("%Y-%m-%d %H:%M:%S") if bordereaux_file.processed_at else "Not processed"}</value>
                    </div>
                    {f'<div class="info-card"><label>Error Message</label><value style="color: #721c24;">{bordereaux_file.error_message}</value></div>' if bordereaux_file.error_message else ''}
                </div>
                
                <h2 class="section-title">Processed Rows</h2>
                <div style="overflow-x: auto; max-height: 600px; overflow-y: auto;">
                    <table>
                        {rows_table}
                    </table>
                </div>
                
                {f'<h2 class="section-title">Validation Errors</h2><p><a href="/files/{file_id}/errors" class="btn btn-secondary">View {error_count} Error(s)</a></p>' if error_count > 0 else ''}
            </div>
        </body>
        </html>
        '''
        
        logger.info("File details retrieved", file_id=file_id)
        return HTMLResponse(content=html_content)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting file details", file_id=file_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error getting file details: {str(e)}")


@router.get("/{file_id}/api", response_model=dict)
async def get_file_details_api(
    file_id: int,
    db: Session = Depends(get_db)
):
    """Get detailed information about a bordereaux file (API endpoint for JSON).
    
    Args:
        file_id: File ID
        db: Database session
        
    Returns:
        File details with summary statistics as JSON
    """
    try:
        bordereaux_file = db.query(BordereauxFile).filter(
            BordereauxFile.id == file_id
        ).first()
        
        if not bordereaux_file:
            raise HTTPException(status_code=404, detail=f"File with ID {file_id} not found")
        
        row_count = db.query(BordereauxRow).filter(
            BordereauxRow.file_id == file_id
        ).count()
        
        error_count = db.query(BordereauxValidationError).filter(
            BordereauxValidationError.file_id == file_id
        ).count()
        
        result = {
            "id": bordereaux_file.id,
            "filename": bordereaux_file.filename,
            "file_path": bordereaux_file.file_path,
            "file_size": bordereaux_file.file_size,
            "mime_type": bordereaux_file.mime_type,
            "status": bordereaux_file.status.value,
            "sender": bordereaux_file.sender,
            "subject": bordereaux_file.subject,
            "file_hash": bordereaux_file.file_hash,
            "received_at": bordereaux_file.received_at.isoformat() if bordereaux_file.received_at else None,
            "proposal_path": bordereaux_file.proposal_path,
            "error_message": bordereaux_file.error_message,
            "total_rows": bordereaux_file.total_rows or 0,
            "processed_rows": bordereaux_file.processed_rows or 0,
            "created_at": bordereaux_file.created_at.isoformat() if bordereaux_file.created_at else None,
            "updated_at": bordereaux_file.updated_at.isoformat() if bordereaux_file.updated_at else None,
            "processed_at": bordereaux_file.processed_at.isoformat() if bordereaux_file.processed_at else None,
            "summary": {
                "row_count": row_count,
                "error_count": error_count,
                "success_rate": (
                    (bordereaux_file.processed_rows / bordereaux_file.total_rows * 100)
                    if bordereaux_file.total_rows and bordereaux_file.total_rows > 0
                    else 0
                ),
            }
        }
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting file details", file_id=file_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error getting file details: {str(e)}")


@router.get("/{file_id}/errors", response_class=HTMLResponse)
async def get_file_errors(
    file_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    db: Session = Depends(get_db)
):
    """Get validation errors for a bordereaux file (HTML view).
    
    Args:
        file_id: File ID
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        db: Database session
        
    Returns:
        HTML page with validation errors table
    """
    try:
        # Verify file exists
        bordereaux_file = db.query(BordereauxFile).filter(
            BordereauxFile.id == file_id
        ).first()
        
        if not bordereaux_file:
            raise HTTPException(status_code=404, detail=f"File with ID {file_id} not found")
        
        # Get validation errors
        errors = db.query(BordereauxValidationError).filter(
            BordereauxValidationError.file_id == file_id
        ).order_by(BordereauxValidationError.row_index).offset(skip).limit(limit).all()
        
        # Build errors table
        errors_rows = ''
        if errors:
            for error in errors:
                errors_rows += f'''
                <tr>
                    <td>{error.row_index}</td>
                    <td><span class="error-code">{error.error_code}</span></td>
                    <td>{error.error_message}</td>
                    <td>{error.field_name or "-"}</td>
                    <td>{error.field_value or "-"}</td>
                    <td>{error.rule_name or "-"}</td>
                </tr>
                '''
        else:
            errors_rows = '<tr><td colspan="6"><div class="empty-state"><div class="empty-state-icon">✅</div><p>No validation errors</p></div></td></tr>'
        
        html_content = f'''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Validation Errors - {bordereaux_file.filename}</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    background: #f5f5f5;
                    padding: 20px;
                }}
                .container {{
                    max-width: 1400px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    padding: 30px;
                }}
                .header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 2px solid #dee2e6;
                }}
                .header h1 {{
                    color: #333;
                    font-size: 24px;
                }}
                .btn {{
                    padding: 10px 20px;
                    border: none;
                    border-radius: 6px;
                    cursor: pointer;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 14px;
                    font-weight: 600;
                    transition: transform 0.2s;
                }}
                .btn-secondary {{
                    background: #6c757d;
                    color: white;
                }}
                .btn-secondary:hover {{
                    transform: translateY(-1px);
                    box-shadow: 0 4px 8px rgba(108, 117, 125, 0.3);
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                }}
                th {{
                    background: #f8f9fa;
                    padding: 12px;
                    text-align: left;
                    font-weight: 600;
                    color: #555;
                    border-bottom: 2px solid #dee2e6;
                }}
                td {{
                    padding: 12px;
                    border-bottom: 1px solid #dee2e6;
                }}
                tr:hover {{
                    background: #f8f9fa;
                }}
                .error-code {{
                    background: #f8d7da;
                    color: #721c24;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 600;
                    font-family: monospace;
                }}
                .empty-state {{
                    text-align: center;
                    padding: 60px 20px;
                    color: #999;
                }}
                .empty-state-icon {{
                    font-size: 48px;
                    margin-bottom: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⚠️ Validation Errors - {bordereaux_file.filename}</h1>
                    <a href="/files/{file_id}" class="btn btn-secondary">← Back to File</a>
                </div>
                
                <table>
                    <thead>
                        <tr>
                            <th>Row Index</th>
                            <th>Error Code</th>
                            <th>Error Message</th>
                            <th>Field Name</th>
                            <th>Field Value</th>
                            <th>Rule Name</th>
                        </tr>
                    </thead>
                    <tbody>
                        {errors_rows}
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        '''
        
        logger.info(
            "File errors retrieved",
            file_id=file_id,
            error_count=len(errors),
            skip=skip,
            limit=limit
        )
        
        return HTMLResponse(content=html_content)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting file errors", file_id=file_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error getting file errors: {str(e)}")


@router.post("/{file_id}/reprocess")
async def reprocess_file(
    file_id: int,
    db: Session = Depends(get_db)
):
    """Reprocess a file through the pipeline.
    
    This is useful for files with NEW_TEMPLATE_REQUIRED status after a template has been created.
    """
    bordereaux_file = db.query(BordereauxFile).filter(BordereauxFile.id == file_id).first()
    
    if not bordereaux_file:
        raise HTTPException(status_code=404, detail=f"File with ID {file_id} not found")
    
    logger.info("Reprocessing file", file_id=file_id, filename=bordereaux_file.filename)
    
    # Process file through pipeline
    result = pipeline_service.process_file(file_id)
    
    if result.get("success"):
        logger.info("File reprocessed successfully", file_id=file_id, status=result.get("status"))
        return JSONResponse(content=result, status_code=200)
    else:
        logger.error("File reprocessing failed", file_id=file_id, error=result.get("error"))
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Error reprocessing file")
        )


@router.get("/{file_id}/errors/api", response_model=List[dict])
async def get_file_errors_api(
    file_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    db: Session = Depends(get_db)
):
    """Get validation errors for a bordereaux file (API endpoint for JSON).
    
    Args:
        file_id: File ID
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        db: Database session
        
    Returns:
        List of validation errors as JSON
    """
    try:
        bordereaux_file = db.query(BordereauxFile).filter(
            BordereauxFile.id == file_id
        ).first()
        
        if not bordereaux_file:
            raise HTTPException(status_code=404, detail=f"File with ID {file_id} not found")
        
        errors = db.query(BordereauxValidationError).filter(
            BordereauxValidationError.file_id == file_id
        ).order_by(BordereauxValidationError.row_index).offset(skip).limit(limit).all()
        
        result = []
        for error in errors:
            result.append({
                "id": error.id,
                "row_index": error.row_index,
                "error_code": error.error_code,
                "error_message": error.error_message,
                "field_name": error.field_name,
                "field_value": error.field_value,
                "rule_name": error.rule_name,
                "created_at": error.created_at.isoformat() if error.created_at else None,
            })
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting file errors", file_id=file_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error getting file errors: {str(e)}")
