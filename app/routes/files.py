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
from app.core.layout import wrap_with_layout
import json
from pathlib import Path

router = APIRouter(prefix="/files", tags=["files"])
logger = get_structured_logger(__name__)
storage_service = StorageService()
pipeline_service = PipelineService()
template_repository = TemplateRepository()


@router.get("/", response_class=HTMLResponse)
async def list_files(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(1000, ge=1, le=10000, description="Number of records to return"),
    db: Session = Depends(get_db)
):
    """List bordereaux files with sorting and filtering (HTML view).
    
    Args:
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        db: Database session
        
    Returns:
        HTML page with files table
    """
    try:
        query = db.query(BordereauxFile)
        
        # Order by created_at descending (newest first) by default
        query = query.order_by(BordereauxFile.created_at.desc())
        
        # Get all files (client-side filtering/sorting will handle it)
        files = query.offset(skip).limit(limit).all()
        
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
                    edit_mappings_cell = f'<a href="/mappings/file/{file.id}" class="btn-link">Edit Mappings</a>'
                    reprocess_cell = f'<button class="btn-link reprocess-btn" data-file-id="{file.id}" data-filename="{file.filename.replace(chr(34), "&quot;").replace(chr(39), "&#39;")}">Reprocess</button>'
                else:
                    edit_mappings_cell = "-"
                    reprocess_cell = "-"
                
                files_rows += f'''
                <tr data-file-id="{file.id}" data-filename="{file.filename.replace('"', '&quot;')}">
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
                        <button class="btn-delete" data-file-id="{file.id}" data-filename="{file.filename.replace('"', '&quot;')}">Delete</button>
                    </td>
                </tr>
                '''
        else:
            files_rows = '<tr><td colspan="10"><div class="empty-state"><p>No files found</p></div></td></tr>'
        
        page_css = """
                h1 {
                    color: #003781;
                    margin-bottom: 30px;
                    font-size: 28px;
                    font-weight: 600;
                    letter-spacing: -0.5px;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                }
                th {
                    background: #f8f9fa;
                    padding: 14px 12px;
                    text-align: left;
                    font-weight: 600;
                    color: #003781;
                    border-bottom: 2px solid #dee2e6;
                    font-size: 13px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    cursor: pointer;
                    user-select: none;
                    position: relative;
                }
                th.sortable:hover {
                    background: #e9ecef;
                }
                th.sortable::after {
                    content: ' ↕';
                    opacity: 0.5;
                    font-size: 10px;
                    margin-left: 5px;
                }
                th.sort-asc::after {
                    content: ' ↑';
                    opacity: 1;
                }
                th.sort-desc::after {
                    content: ' ↓';
                    opacity: 1;
                }
                td {
                    padding: 14px 12px;
                    border-bottom: 1px solid #e9ecef;
                    font-size: 14px;
                    color: #495057;
                }
                tr:hover {
                    background: #f8f9fa;
                }
                .file-link {
                    color: #003781;
                    text-decoration: none;
                    font-weight: 500;
                }
                .file-link:hover {
                    text-decoration: underline;
                    color: #002d66;
                }
                .btn-link {
                    color: #003781;
                    text-decoration: none;
                    font-weight: 500;
                    padding: 6px 12px;
                    border-radius: 4px;
                    transition: all 0.2s;
                    display: inline-block;
                    background: none;
                    border: none;
                    cursor: pointer;
                    font-size: 12px;
                }
                .btn-link:hover {
                    background: #f8f9fa;
                    color: #002d66;
                }
                button.btn-link {
                    font-family: inherit;
                }
                .badge {
                    padding: 4px 10px;
                    border-radius: 3px;
                    font-size: 11px;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 0.3px;
                }
                .badge-pending { background: #fff3cd; color: #856404; }
                .badge-received { background: #d1ecf1; color: #0c5460; }
                .badge-processing { background: #cfe2ff; color: #003781; }
                .badge-processed-ok { background: #d1e7dd; color: #0f5132; }
                .badge-processed-with-errors { background: #f8d7da; color: #842029; }
                .badge-failed { background: #f8d7da; color: #842029; }
                .badge-new-template-required { background: #fff3cd; color: #856404; }
                .btn-reprocess {
                    padding: 6px 14px;
                    background: #198754;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 12px;
                    font-weight: 500;
                    transition: all 0.2s;
                }
                .btn-reprocess:hover {
                    background: #157347;
                }
                .btn-reprocess:disabled {
                    background: #6c757d;
                    cursor: not-allowed;
                    opacity: 0.6;
                }
                .btn-edit-mappings {
                    padding: 6px 14px;
                    background: #003781;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 12px;
                    font-weight: 500;
                    transition: all 0.2s;
                }
                .btn-edit-mappings:hover {
                    background: #002d66;
                }
                .btn-delete {
                    padding: 6px 14px;
                    background: #dc3545;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 12px;
                    font-weight: 500;
                    transition: all 0.2s;
                }
                .btn-delete:hover {
                    background: #bb2d3b;
                }
                .btn-delete:disabled {
                    background: #6c757d;
                    cursor: not-allowed;
                    opacity: 0.6;
                }
                .empty-state {
                    text-align: center;
                    padding: 60px 20px;
                    color: #999;
                }
                .empty-state-icon {
                    font-size: 48px;
                    margin-bottom: 10px;
                }
                """
        
        content = f'''
                <h1>Bordereaux Files</h1>
                
                <table id="filesTable">
                    <thead>
                        <tr>
                            <th class="sortable" data-column="id">ID</th>
                            <th class="sortable" data-column="filename">Filename</th>
                            <th class="sortable" data-column="status">Status</th>
                            <th class="sortable" data-column="sender">Sender</th>
                            <th class="sortable" data-column="total_rows">Total Rows</th>
                            <th class="sortable" data-column="processed_rows">Processed</th>
                            <th class="sortable" data-column="created_at">Created</th>
                            <th>Edit Mappings</th>
                            <th>Reprocess</th>
                            <th>Delete</th>
                        </tr>
                    </thead>
                    <tbody id="filesTableBody">
                        {files_rows}
                    </tbody>
                </table>
                
                <script>
                let allFilesData = [];
                let currentSort = {{ column: 'created_at', direction: 'desc' }};
                
                // Store original data
                document.querySelectorAll('#filesTableBody tr').forEach(row => {{
                    if (row.cells.length > 0) {{
                        const data = {{
                            id: row.cells[0].textContent.trim(),
                            filename: row.cells[1].querySelector('a') ? row.cells[1].querySelector('a').textContent.trim() : row.cells[1].textContent.trim(),
                            status: row.cells[2].querySelector('.badge') ? row.cells[2].querySelector('.badge').textContent.trim() : row.cells[2].textContent.trim(),
                            sender: row.cells[3].textContent.trim(),
                            total_rows: parseInt(row.cells[4].textContent.trim()) || 0,
                            processed_rows: parseInt(row.cells[5].textContent.trim()) || 0,
                            created_at: row.cells[6].textContent.trim(),
                            html: row.outerHTML
                        }};
                        allFilesData.push(data);
                    }}
                }});
                
                // Sorting functionality
                document.querySelectorAll('th.sortable').forEach(header => {{
                    header.addEventListener('click', function() {{
                        const column = this.dataset.column;
                        
                        // Toggle sort direction
                        if (currentSort.column === column) {{
                            currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
                        }} else {{
                            currentSort.column = column;
                            currentSort.direction = 'asc';
                        }}
                        
                        // Update header classes
                        document.querySelectorAll('th.sortable').forEach(h => {{
                            h.classList.remove('sort-asc', 'sort-desc');
                        }});
                        this.classList.add(`sort-${{currentSort.direction}}`);
                        
                        applySort();
                    }});
                }});
                
                function applySort() {{
                    // Sort data
                    const sortedData = [...allFilesData].sort((a, b) => {{
                        let aVal = a[currentSort.column];
                        let bVal = b[currentSort.column];
                        
                        // Handle numeric columns
                        if (currentSort.column === 'id' || currentSort.column === 'total_rows' || currentSort.column === 'processed_rows') {{
                            aVal = parseInt(aVal) || 0;
                            bVal = parseInt(bVal) || 0;
                        }} else {{
                            aVal = String(aVal || '').toLowerCase();
                            bVal = String(bVal || '').toLowerCase();
                        }}
                        
                        if (currentSort.direction === 'asc') {{
                            return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
                        }} else {{
                            return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
                        }}
                    }});
                    
                    // Update table
                    const tbody = document.getElementById('filesTableBody');
                    tbody.innerHTML = sortedData.map(file => file.html).join('');
                    // Re-attach event listeners for buttons
                    attachButtonListeners();
                }}
                
                function attachButtonListeners() {{
                    // Re-attach delete button listeners
                    document.querySelectorAll('.btn-delete').forEach(button => {{
                        if (!button.hasAttribute('data-listener-attached')) {{
                            button.setAttribute('data-listener-attached', 'true');
                            const fileId = button.getAttribute('data-file-id');
                            const filename = button.getAttribute('data-filename');
                            if (fileId && filename) {{
                                button.onclick = function() {{ deleteFile(this, parseInt(fileId), filename); }};
                            }}
                        }}
                    }});
                    
                    // Re-attach reprocess button listeners
                    document.querySelectorAll('button.reprocess-btn').forEach(button => {{
                        if (!button.hasAttribute('data-listener-attached')) {{
                            button.setAttribute('data-listener-attached', 'true');
                            const fileId = button.getAttribute('data-file-id');
                            const filename = button.getAttribute('data-filename');
                            if (fileId && filename) {{
                                button.onclick = function() {{ reprocessFile(this, parseInt(fileId), filename); }};
                            }}
                        }}
                    }});
                }}
                
                // Attach initial listeners
                attachButtonListeners();
                
                // Initialize sort indicator
                document.querySelector('th[data-column="created_at"]').classList.add('sort-desc');
                
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
                                    tbody.innerHTML = '<tr><td colspan="10"><div class="empty-state"><p>No files found</p></div></td></tr>';
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
        '''
        
        html_content = wrap_with_layout(
            content=content,
            page_title="Bordereaux Files",
            current_page="files",
            additional_css=page_css
        )
        
        logger.info("Files listed", count=len(files), skip=skip, limit=limit)
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


@router.get("/upload/modal", response_class=HTMLResponse)
async def upload_file_modal():
    """Serve the file upload modal content."""
    modal_css = """
            .subtitle {
                color: #495057;
                margin-bottom: 20px;
                font-size: 14px;
                font-weight: 400;
            }
            .upload-area {
                border: 2px dashed #ced4da;
                border-radius: 4px;
                padding: 40px;
                text-align: center;
                transition: all 0.2s ease;
                cursor: pointer;
                background: #f8f9fa;
            }
            .upload-area:hover {
                border-color: #003781;
                background: #f0f4ff;
            }
            .upload-area.dragover {
                border-color: #003781;
                background: #e6edff;
            }
            .upload-icon {
                font-size: 48px;
                color: #003781;
                margin-bottom: 15px;
            }
            .upload-text {
                color: #495057;
                margin-bottom: 10px;
                font-size: 16px;
            }
            .upload-hint {
                color: #6c757d;
                font-size: 12px;
            }
            input[type="file"] {
                display: none;
            }
            .file-info {
                margin-top: 20px;
                padding: 15px;
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 4px;
                display: none;
            }
            .file-info.show {
                display: block;
            }
            .file-name {
                font-weight: 600;
                color: #003781;
                margin-bottom: 5px;
            }
            .file-size {
                color: #6c757d;
                font-size: 14px;
            }
            button#uploadButton {
                width: 100%;
                padding: 14px;
                background: #003781;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 16px;
                font-weight: 500;
                cursor: pointer;
                margin-top: 20px;
                transition: all 0.2s ease;
            }
            button#uploadButton:hover:not(:disabled) {
                background: #002d66;
            }
            button#uploadButton:disabled {
                background: #6c757d;
                cursor: not-allowed;
                opacity: 0.6;
            }
            .error {
                margin-top: 15px;
                padding: 12px;
                background: #f8d7da;
                border: 1px solid #f1aeb5;
                border-radius: 4px;
                color: #842029;
                display: none;
            }
            .error.show {
                display: block;
            }
            .success {
                margin-top: 15px;
                padding: 12px;
                background: #d1e7dd;
                border: 1px solid #badbcc;
                border-radius: 4px;
                color: #0f5132;
                display: none;
            }
            .success.show {
                display: block;
            }
            .files-list {
                margin-top: 20px;
                max-height: 200px;
                overflow-y: auto;
            }
            .files-list-header {
                font-weight: 600;
                color: #003781;
                margin-bottom: 10px;
                font-size: 14px;
            }
            .file-item {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 10px 12px;
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 4px;
                margin-bottom: 8px;
            }
            .file-item .file-name {
                flex: 1;
                font-weight: 500;
                color: #003781;
                font-size: 14px;
                margin-right: 10px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            .file-item .file-size {
                color: #6c757d;
                font-size: 12px;
                margin-right: 10px;
            }
            .file-item .file-remove {
                background: none;
                border: none;
                color: #dc3545;
                font-size: 20px;
                cursor: pointer;
                padding: 0 5px;
                line-height: 1;
                transition: color 0.2s;
            }
            .file-item .file-remove:hover {
                color: #bb2d3b;
            }
            """
    
    modal_content = f"""
        <div class="modal-header">
            <h2>Upload Bordereaux File</h2>
            <button class="modal-close" onclick="closeModal()">×</button>
        </div>
        <div class="modal-body">
            <p class="subtitle">Upload an Excel or CSV file to process</p>
            
            <div class="upload-area" id="uploadArea" onclick="document.getElementById('fileInput').click()">
                <div class="upload-icon">📄</div>
                <div class="upload-text">Click to select or drag and drop</div>
                <div class="upload-hint">Supports .xlsx, .xls, and .csv files (multiple files allowed)</div>
            </div>
            
            <input type="file" id="fileInput" accept=".xlsx,.xls,.csv" multiple />
            
            <div class="files-list" id="filesList"></div>
            
            <div class="error" id="errorMessage"></div>
            <div class="success" id="successMessage"></div>
            
            <button id="uploadButton" onclick="uploadFiles()" disabled>Upload and Process</button>
        </div>
        <style>
            {modal_css}
        </style>
        <script>
            (function() {{
                setTimeout(function() {{
                    const fileInput = document.getElementById('fileInput');
                    const uploadArea = document.getElementById('uploadArea');
                    const filesList = document.getElementById('filesList');
                    const uploadButton = document.getElementById('uploadButton');
                    const errorMessage = document.getElementById('errorMessage');
                    const successMessage = document.getElementById('successMessage');
                    
                    if (!fileInput || !uploadArea || !filesList || !uploadButton) {{
                        console.error('Required elements not found');
                        return;
                    }}
                    
                    let selectedFiles = [];
                    
                    fileInput.addEventListener('change', function(e) {{
                        if (e.target.files && e.target.files.length > 0) {{
                            handleFilesSelect(Array.from(e.target.files));
                        }}
                    }});
                    
                    uploadArea.addEventListener('dragover', function(e) {{
                        e.preventDefault();
                        uploadArea.classList.add('dragover');
                    }});
                    
                    uploadArea.addEventListener('dragleave', function(e) {{
                        e.preventDefault();
                        uploadArea.classList.remove('dragover');
                    }});
                    
                    uploadArea.addEventListener('drop', function(e) {{
                        e.preventDefault();
                        uploadArea.classList.remove('dragover');
                        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {{
                            handleFilesSelect(Array.from(e.dataTransfer.files));
                        }}
                    }});
                    
                    function handleFilesSelect(files) {{
                        if (!files || files.length === 0) return;
                        
                        const allowedExtensions = ['.xlsx', '.xls', '.csv'];
                        const validFiles = [];
                        const invalidFiles = [];
                        
                        files.forEach(file => {{
                            const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
                            if (allowedExtensions.includes(fileExtension)) {{
                                validFiles.push(file);
                            }} else {{
                                invalidFiles.push(file.name);
                            }}
                        }});
                        
                        if (invalidFiles.length > 0) {{
                            showError('Invalid file(s): ' + invalidFiles.join(', ') + '. Please select .xlsx, .xls, or .csv files.');
                        }}
                        
                        if (validFiles.length > 0) {{
                            selectedFiles = validFiles;
                            updateFilesList();
                            uploadButton.disabled = false;
                            hideError();
                            hideSuccess();
                        }}
                    }}
                    
                    function updateFilesList() {{
                        if (selectedFiles.length === 0) {{
                            filesList.innerHTML = '';
                            return;
                        }}
                        
                        let html = '<div class="files-list-header">Selected Files (' + selectedFiles.length + '):</div>';
                        selectedFiles.forEach((file, index) => {{
                            html += '<div class="file-item">';
                            html += '<span class="file-name">' + file.name + '</span>';
                            html += '<span class="file-size">' + formatFileSize(file.size) + '</span>';
                            html += '<button class="file-remove" data-index="' + index + '">×</button>';
                            html += '</div>';
                        }});
                        filesList.innerHTML = html;
                        
                        // Attach remove handlers
                        const removeButtons = filesList.querySelectorAll('.file-remove');
                        removeButtons.forEach(btn => {{
                            btn.addEventListener('click', function() {{
                                const index = parseInt(this.getAttribute('data-index'));
                                removeFile(index);
                            }});
                        }});
                    }}
                    
                    function removeFile(index) {{
                        selectedFiles.splice(index, 1);
                        updateFilesList();
                        if (selectedFiles.length === 0) {{
                            uploadButton.disabled = true;
                            fileInput.value = '';
                        }}
                    }}
                    
                    function formatFileSize(bytes) {{
                        if (bytes === 0) return '0 Bytes';
                        const k = 1024;
                        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
                        const i = Math.floor(Math.log(bytes) / Math.log(k));
                        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
                    }}
                    
                    window.uploadFiles = async function() {{
                        if (selectedFiles.length === 0) {{
                            showError('Please select at least one file first');
                            return;
                        }}
                        
                        const formData = new FormData();
                        selectedFiles.forEach(file => {{
                            formData.append('files', file);
                        }});
                        
                        uploadButton.disabled = true;
                        uploadButton.textContent = 'Uploading ' + selectedFiles.length + ' file(s)...';
                        hideError();
                        hideSuccess();
                        
                        try {{
                            const response = await fetch('/files/upload', {{
                                method: 'POST',
                                body: formData
                            }});
                            
                            const result = await response.json();
                            
                            if (response.ok) {{
                                const successCount = result.success_count || selectedFiles.length;
                                const errorCount = result.error_count || 0;
                                let message = successCount + ' file(s) uploaded and processed successfully!';
                                if (errorCount > 0) {{
                                    message += ' ' + errorCount + ' file(s) failed.';
                                }}
                                showSuccess(message);
                                setTimeout(() => {{
                                    window.location.reload();
                                }}, 2000);
                            }} else {{
                                showError(result.detail || 'Error uploading files');
                                uploadButton.disabled = false;
                                uploadButton.textContent = 'Upload and Process';
                            }}
                        }} catch (error) {{
                            showError('Error uploading files: ' + error.message);
                            uploadButton.disabled = false;
                            uploadButton.textContent = 'Upload and Process';
                        }}
                    }};
                    
                    function showError(message) {{
                        if (errorMessage) {{
                            errorMessage.textContent = message;
                            errorMessage.classList.add('show');
                        }}
                    }}
                    
                    function hideError() {{
                        if (errorMessage) {{
                            errorMessage.classList.remove('show');
                        }}
                    }}
                    
                    function showSuccess(message) {{
                        if (successMessage) {{
                            successMessage.textContent = message;
                            successMessage.classList.add('show');
                        }}
                    }}
                    
                    function hideSuccess() {{
                        if (successMessage) {{
                            successMessage.classList.remove('show');
                        }}
                    }}
                }}, 100);
            }})();
        </script>
    """
    return HTMLResponse(content=modal_content)


@router.get("/upload", response_class=HTMLResponse)
async def upload_page():
    """Serve the file upload page."""
    page_css = """
            h1 {
                color: #003781;
                margin-bottom: 12px;
                font-size: 28px;
                font-weight: 600;
                letter-spacing: -0.5px;
            }
            .subtitle {
                color: #495057;
                margin-bottom: 30px;
                font-size: 14px;
                font-weight: 400;
            }
            .upload-area {
                border: 2px dashed #ced4da;
                border-radius: 4px;
                padding: 40px;
                text-align: center;
                transition: all 0.2s ease;
                cursor: pointer;
                background: #f8f9fa;
            }
            .upload-area:hover {
                border-color: #003781;
                background: #f0f4ff;
            }
            .upload-area.dragover {
                border-color: #003781;
                background: #e6edff;
            }
            .upload-icon {
                font-size: 48px;
                color: #003781;
                margin-bottom: 15px;
            }
            .upload-text {
                color: #495057;
                margin-bottom: 10px;
                font-size: 16px;
                font-weight: 500;
            }
            .upload-hint {
                color: #6c757d;
                font-size: 12px;
            }
            input[type="file"] {
                display: none;
            }
            .file-info {
                margin-top: 20px;
                padding: 15px;
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 4px;
                display: none;
            }
            .file-info.show {
                display: block;
            }
            .file-name {
                font-weight: 600;
                color: #003781;
                margin-bottom: 5px;
            }
            .file-size {
                color: #6c757d;
                font-size: 14px;
            }
            button {
                width: 100%;
                padding: 14px;
                background: #003781;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 16px;
                font-weight: 500;
                cursor: pointer;
                margin-top: 20px;
                transition: all 0.2s ease;
            }
            button:hover:not(:disabled) {
                background: #002d66;
            }
            button:disabled {
                background: #6c757d;
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
                background: #e9ecef;
                border-radius: 4px;
                overflow: hidden;
            }
            .progress-fill {
                height: 100%;
                background: #003781;
                width: 0%;
                transition: width 0.3s ease;
            }
            .result {
                margin-top: 20px;
                padding: 16px;
                border-radius: 4px;
                display: none;
            }
            .result.show {
                display: block;
            }
            .result.success {
                background: #d1e7dd;
                border: 1px solid #badbcc;
                color: #0f5132;
            }
            .result.error {
                background: #f8d7da;
                border: 1px solid #f1aeb5;
                color: #842029;
            }
            .result-info {
                margin-top: 15px;
                font-size: 14px;
            }
            .result-info p {
                margin: 5px 0;
            }
            .link {
                color: #003781;
                text-decoration: none;
                font-weight: 500;
            }
            .link:hover {
                text-decoration: underline;
                color: #002d66;
            }
            .btn-back {
                padding: 10px 20px;
                background: #6c757d;
                color: white;
                border: none;
                border-radius: 4px;
                text-decoration: none;
                font-weight: 500;
                display: inline-block;
                transition: all 0.2s;
                font-size: 14px;
            }
            """
    
    content = """
            <h1>Upload Bordereaux File</h1>
            <p class="subtitle">Upload an Excel or CSV file to process</p>
            
            <form id="uploadForm" enctype="multipart/form-data">
                <div class="upload-area" id="uploadArea">
                    <div class="upload-icon">📄</div>
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
    """
    
    html_content = wrap_with_layout(
        content=content,
        page_title="Upload Bordereaux File",
        current_page="upload",
        additional_css=page_css
    )
    return HTMLResponse(content=html_content)


@router.post("/upload")
async def upload_file(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """Upload and process bordereaux files.
    
    Args:
        files: Uploaded files (Excel or CSV) - can be multiple
        db: Database session
        
    Returns:
        Processing results for all files
    """
    from app.models.bordereaux import FileStatus
    
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="No files provided")
    
    allowed_extensions = ['.xlsx', '.xls', '.csv']
    results = []
    success_count = 0
    error_count = 0
    
    for file in files:
        try:
            # Validate file type
            file_extension = '.' + file.filename.split('.')[-1].lower() if '.' in file.filename else ''
            
            if file_extension not in allowed_extensions:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
                })
                error_count += 1
                continue
            
            # Read file content
            file_bytes = await file.read()
            
            if len(file_bytes) == 0:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": "File is empty"
                })
                error_count += 1
                continue
            
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
            bordereaux_file = db.query(BordereauxFile).filter(BordereauxFile.id == file_id).first()
            if bordereaux_file:
                bordereaux_file.status = FileStatus.RECEIVED
                db.commit()
            
            # Process file through pipeline
            logger.info("Processing uploaded file", file_id=file_id)
            result = pipeline_service.process_file(file_id)
            
            if result.get("success"):
                logger.info("File processed successfully", file_id=file_id, status=result.get("status"))
                results.append({
                    "filename": file.filename,
                    "success": True,
                    "file_id": file_id,
                    **result
                })
                success_count += 1
            else:
                logger.error("File processing failed", file_id=file_id, error=result.get("error"))
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": result.get("error", "Error processing file")
                })
                error_count += 1
        
        except Exception as e:
            logger.exception("Error uploading file", filename=file.filename, error=str(e))
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })
            error_count += 1
    
    return JSONResponse(content={
        "success": error_count == 0,
        "success_count": success_count,
        "error_count": error_count,
        "results": results
    }, status_code=200 if success_count > 0 else 500)


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
            rows_table = '<tbody><tr><td colspan="10" class="empty-state"><p>No rows processed yet</p></td></tr></tbody>'
        
        # Status badge
        status_class = bordereaux_file.status.value.replace("_", "-")
        status_display = bordereaux_file.status.value.replace("_", " ").title()
        
        # Success rate
        success_rate = (
            (bordereaux_file.processed_rows / bordereaux_file.total_rows * 100)
            if bordereaux_file.total_rows and bordereaux_file.total_rows > 0
            else 0
        )
        
        page_css = """
                h1 {
                    color: #003781;
                    margin-bottom: 20px;
                    font-size: 28px;
                    font-weight: 600;
                    letter-spacing: -0.5px;
                }
                .header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 1px solid #e9ecef;
                }
                .btn-link {
                    color: #003781;
                    text-decoration: none;
                    font-weight: 500;
                    padding: 6px 12px;
                    border-radius: 4px;
                    transition: all 0.2s;
                }
                .btn-link:hover {
                    background: #f8f9fa;
                    color: #002d66;
                }
                .stats {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }
                .stat-card {
                    background: white;
                    border: 1px solid #e9ecef;
                    border-radius: 4px;
                    padding: 20px;
                    text-align: center;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
                }
                .stat-card .value {
                    font-size: 32px;
                    font-weight: 600;
                    color: #003781;
                    margin-bottom: 8px;
                }
                .stat-card .label {
                    font-size: 13px;
                    color: #6c757d;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    font-weight: 500;
                }
                .info-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }
                .info-card {
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 4px;
                    border: 1px solid #e9ecef;
                }
                .info-card label {
                    display: block;
                    font-size: 12px;
                    color: #6c757d;
                    margin-bottom: 8px;
                    text-transform: uppercase;
                    font-weight: 500;
                    letter-spacing: 0.5px;
                }
                .info-card value {
                    display: block;
                    font-size: 14px;
                    color: #495057;
                    font-weight: 500;
                }
                .badge {
                    padding: 4px 10px;
                    border-radius: 3px;
                    font-size: 11px;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 0.3px;
                }
                .badge-pending { background: #fff3cd; color: #856404; }
                .badge-received { background: #d1ecf1; color: #0c5460; }
                .badge-processing { background: #cfe2ff; color: #003781; }
                .badge-processed-ok { background: #d1e7dd; color: #0f5132; }
                .badge-processed-with-errors { background: #f8d7da; color: #842029; }
                .badge-failed { background: #f8d7da; color: #842029; }
                .badge-new-template-required { background: #fff3cd; color: #856404; }
                .section-title {
                    font-size: 20px;
                    color: #003781;
                    margin: 30px 0 15px 0;
                    padding-bottom: 10px;
                    border-bottom: 1px solid #e9ecef;
                    font-weight: 600;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                }
                th {
                    background: #f8f9fa;
                    padding: 14px 12px;
                    text-align: left;
                    font-weight: 600;
                    color: #003781;
                    border-bottom: 2px solid #dee2e6;
                    font-size: 13px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    position: sticky;
                    top: 0;
                }
                td {
                    padding: 14px 12px;
                    border-bottom: 1px solid #e9ecef;
                    font-size: 14px;
                    color: #495057;
                }
                tbody tr:hover {
                    background: #f8f9fa;
                }
                .empty-state {
                    text-align: center;
                    padding: 60px 20px;
                    color: #6c757d;
                }
                .empty-state-icon {
                    font-size: 48px;
                    margin-bottom: 10px;
                }
                .table-container {
                    overflow-x: auto;
                    max-height: 600px;
                    overflow-y: auto;
                    border: 1px solid #e9ecef;
                    border-radius: 4px;
                }
                .btn-secondary {
                    padding: 10px 20px;
                    background: #003781;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 14px;
                    font-weight: 500;
                    transition: all 0.2s;
                }
                .btn-secondary:hover {
                    background: #002d66;
                }
                """
        
        content = f"""
                <div class="header">
                    <h1>{bordereaux_file.filename}</h1>
                    <a href="/files" class="btn-link">Back to Files</a>
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
                    {f'<div class="info-card"><label>Error Message</label><value style="color: #842029;">{bordereaux_file.error_message}</value></div>' if bordereaux_file.error_message else ''}
                </div>
                
                <h2 class="section-title">Processed Rows</h2>
                <div class="table-container">
                    <table>
                        {rows_table}
                    </table>
                </div>
                
                {f'<h2 class="section-title">Validation Errors</h2><p><a href="/files/{file_id}/errors" class="btn-secondary">View {error_count} Error(s)</a></p>' if error_count > 0 else ''}
        """
        
        html_content = wrap_with_layout(
            content=content,
            page_title=f"File Details - {bordereaux_file.filename}",
            current_page="files",
            additional_css=page_css
        )
        
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
            errors_rows = '<tr><td colspan="6"><div class="empty-state"><p>No validation errors</p></div></td></tr>'
        
        page_css = """
                h1 {
                    color: #003781;
                    margin-bottom: 20px;
                    font-size: 28px;
                    font-weight: 600;
                    letter-spacing: -0.5px;
                }
                .header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 1px solid #e9ecef;
                }
                .btn-link {
                    color: #003781;
                    text-decoration: none;
                    font-weight: 500;
                    padding: 6px 12px;
                    border-radius: 4px;
                    transition: all 0.2s;
                }
                .btn-link:hover {
                    background: #f8f9fa;
                    color: #002d66;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                }
                th {
                    background: #f8f9fa;
                    padding: 14px 12px;
                    text-align: left;
                    font-weight: 600;
                    color: #003781;
                    border-bottom: 2px solid #dee2e6;
                    font-size: 13px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }
                td {
                    padding: 14px 12px;
                    border-bottom: 1px solid #e9ecef;
                    font-size: 14px;
                    color: #495057;
                }
                tr:hover {
                    background: #f8f9fa;
                }
                .error-code {
                    background: #f8d7da;
                    color: #842029;
                    padding: 4px 10px;
                    border-radius: 3px;
                    font-size: 11px;
                    font-weight: 600;
                    font-family: 'Courier New', monospace;
                    text-transform: uppercase;
                    letter-spacing: 0.3px;
                }
                .empty-state {
                    text-align: center;
                    padding: 60px 20px;
                    color: #6c757d;
                }
                .empty-state-icon {
                    font-size: 48px;
                    margin-bottom: 10px;
                }
                """
        
        content = f"""
                <div class="header">
                    <h1>Validation Errors - {bordereaux_file.filename}</h1>
                    <a href="/files/{file_id}" class="btn-link">Back to File</a>
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
        """
        
        html_content = wrap_with_layout(
            content=content,
            page_title=f"Validation Errors - {bordereaux_file.filename}",
            current_page="files",
            additional_css=page_css
        )
        
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
