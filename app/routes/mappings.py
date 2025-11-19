from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.models.bordereaux import BordereauxFile, FileStatus
from app.models.template import TemplateCreate, TemplateUpdate, FileType, Template
from app.services.template_repository import TemplateRepository
from app.services.parsing_service import ParsingService
from app.core.logging import get_structured_logger
from app.core.layout import wrap_with_layout
import json
from pathlib import Path


router = APIRouter(prefix="/mappings", tags=["mappings"])
logger = get_structured_logger(__name__)
template_repository = TemplateRepository()
parsing_service = ParsingService()

# Canonical fields for dropdown
CANONICAL_FIELDS = [
    ('policy_number', 'Policy Number'),
    ('insured_name', 'Insured Name'),
    ('inception_date', 'Inception Date'),
    ('expiry_date', 'Expiry Date'),
    ('premium_amount', 'Premium Amount'),
    ('currency', 'Currency'),
    ('claim_amount', 'Claim Amount'),
    ('commission_amount', 'Commission Amount'),
    ('net_premium', 'Net Premium'),
    ('broker_name', 'Broker Name'),
    ('product_type', 'Product Type'),
    ('coverage_type', 'Coverage Type'),
    ('risk_location', 'Risk Location'),
]


def load_proposal(file_id: int) -> Optional[Dict[str, Any]]:
    """Load proposal JSON file for a file.
    
    Args:
        file_id: File ID
        
    Returns:
        Proposal data or None if not found
    """
    proposals_dir = Path("templates/proposals")
    if not proposals_dir.exists():
        return None
    
    # Find proposal file for this file_id
    proposal_files = list(proposals_dir.glob(f"proposal_{file_id}_*.json"))
    if not proposal_files:
        return None
    
    # Get the most recent proposal
    proposal_file = sorted(proposal_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    
    try:
        with open(proposal_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading proposal: {str(e)}")
        return None


@router.get("/file/{file_id}", response_class=HTMLResponse)
async def view_file_mappings(
    file_id: int,
    db: Session = Depends(get_db)
):
    """View and edit mappings for a file with NEW_TEMPLATE_REQUIRED status."""
    bordereaux_file = db.query(BordereauxFile).filter(BordereauxFile.id == file_id).first()
    
    if not bordereaux_file:
        raise HTTPException(status_code=404, detail=f"File with ID {file_id} not found")
    
    if bordereaux_file.status != FileStatus.NEW_TEMPLATE_REQUIRED:
        raise HTTPException(
            status_code=400,
            detail=f"File status is {bordereaux_file.status.value}, not NEW_TEMPLATE_REQUIRED"
        )
    
    # Load proposal
    proposal = load_proposal(file_id)
    if not proposal:
        raise HTTPException(
            status_code=404,
            detail="No mapping proposal found for this file"
        )
    
    # Get file headers
    file_headers = proposal.get("file_headers", [])
    column_mappings = proposal.get("column_mappings", {})
    confidence_scores = proposal.get("confidence_scores", {})
    metadata = proposal.get("metadata", {})
    
    # Build canonical fields options HTML
    canonical_options = "".join([
        f'<option value="{field}">{label}</option>'
        for field, label in CANONICAL_FIELDS
    ])
    
    # Build mapping rows HTML
    mapping_rows = ""
    for header in file_headers:
        current_mapping = column_mappings.get(header, "")
        confidence = confidence_scores.get(header, 0.0)
        confidence_percent = int(confidence * 100)
        confidence_class = "high" if confidence >= 0.8 else "medium" if confidence >= 0.5 else "low"
        
        mapping_rows += f"""
        <tr>
            <td><strong>{header}</strong></td>
            <td>
                <select name="mapping_{header}" class="mapping-select" data-header="{header}">
                    <option value="">-- Not Mapped --</option>
                    {canonical_options}
                </select>
            </td>
            <td>
                <span class="confidence confidence-{confidence_class}">{confidence_percent}%</span>
            </td>
        </tr>
        """
    
    # Set initial values via JavaScript
    initial_mappings_js = json.dumps(column_mappings)
    
    page_css = """
            h1 {
                color: #003781;
                margin-bottom: 20px;
                font-size: 28px;
                font-weight: 600;
                letter-spacing: -0.5px;
            }
            h2 {
                color: #003781;
                margin-top: 30px;
                margin-bottom: 15px;
                font-size: 20px;
                font-weight: 600;
            }
            .file-info {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 4px;
                margin-bottom: 20px;
                border: 1px solid #e9ecef;
            }
            .file-info p {
                margin: 5px 0;
                color: #495057;
                font-size: 14px;
            }
            .file-info strong {
                color: #003781;
                font-weight: 600;
            }
            .alert {
                padding: 15px;
                border-radius: 4px;
                margin-bottom: 20px;
                border: 1px solid #bee5eb;
            }
            .alert-info {
                background: #d1ecf1;
                color: #0c5460;
            }
            .alert-info strong {
                color: #0c5460;
            }
            .form-group {
                margin-bottom: 20px;
            }
            .form-group label {
                display: block;
                margin-bottom: 8px;
                font-weight: 500;
                color: #495057;
                font-size: 14px;
            }
            .form-group input[type="text"],
            .form-group select {
                width: 100%;
                padding: 8px 12px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                font-size: 14px;
                color: #495057;
                background: white;
            }
            .form-group input[type="text"]:focus,
            .form-group select:focus {
                outline: none;
                border-color: #003781;
                box-shadow: 0 0 0 2px rgba(0, 55, 129, 0.1);
            }
            .form-group small {
                display: block;
                margin-top: 5px;
                color: #6c757d;
                font-size: 12px;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }
            th, td {
                padding: 14px 12px;
                text-align: left;
                border-bottom: 1px solid #e9ecef;
            }
            th {
                background: #f8f9fa;
                font-weight: 600;
                color: #003781;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                border-bottom: 2px solid #dee2e6;
            }
            td {
                font-size: 14px;
                color: #495057;
            }
            tr:hover {
                background: #f8f9fa;
            }
            .mapping-select {
                width: 100%;
                padding: 8px 12px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                font-size: 14px;
                color: #495057;
                background: white;
            }
            .mapping-select:focus {
                outline: none;
                border-color: #003781;
                box-shadow: 0 0 0 2px rgba(0, 55, 129, 0.1);
            }
            .confidence {
                padding: 4px 10px;
                border-radius: 3px;
                font-weight: 600;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.3px;
            }
            .confidence-high {
                background: #d1e7dd;
                color: #0f5132;
            }
            .confidence-medium {
                background: #fff3cd;
                color: #856404;
            }
            .confidence-low {
                background: #f8d7da;
                color: #842029;
            }
            .actions {
                margin-top: 30px;
                display: flex;
                gap: 12px;
                align-items: center;
            }
            button[type="submit"] {
                padding: 10px 20px;
                background: #003781;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s;
            }
            button[type="submit"]:hover {
                background: #002d66;
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
            """
    
    content = f"""
            <h1>Edit Column Mappings</h1>
            
            <div class="file-info">
                <p><strong>File:</strong> {bordereaux_file.filename}</p>
                <p><strong>File ID:</strong> {file_id}</p>
                <p><strong>Status:</strong> {bordereaux_file.status.value}</p>
                {f'<p><strong>Sender:</strong> {metadata.get("sender", "N/A")}</p>' if metadata.get("sender") else ''}
                {f'<p><strong>Subject:</strong> {metadata.get("subject", "N/A")}</p>' if metadata.get("subject") else ''}
            </div>
            
            <div class="alert alert-info">
                <strong>AI Suggestions:</strong> The mappings below were suggested by AI. You can edit them before saving as a template.
            </div>
            
            <form id="mappingForm" method="POST" action="/mappings/file/{file_id}/save">
                <div class="form-group">
                    <label for="template_name">Template Name *</label>
                    <input type="text" id="template_name" name="template_name" required 
                           value="{metadata.get('filename', bordereaux_file.filename).replace('.xlsx', '').replace('.xls', '').replace('.csv', '')} Template">
                </div>
                
                <div class="form-group">
                    <label for="template_id">Template ID *</label>
                    <input type="text" id="template_id" name="template_id" required 
                           pattern="[a-z0-9_]+" 
                           value="{bordereaux_file.filename.lower().replace('.xlsx', '').replace('.xls', '').replace('.csv', '').replace(' ', '_').replace('-', '_')}">
                    <small>Lowercase letters, numbers, and underscores only</small>
                </div>
                
                <div class="form-group">
                    <label for="file_type">File Type *</label>
                    <select id="file_type" name="file_type" required>
                        <option value="claims">Claims</option>
                        <option value="premium">Premium</option>
                        <option value="exposure">Exposure</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="carrier">Carrier (Optional)</label>
                    <input type="text" id="carrier" name="carrier" 
                           value="{metadata.get('sender', '').split('@')[0] if metadata.get('sender') else ''}">
                </div>
                
                <h2>Column Mappings</h2>
                <table>
                    <thead>
                        <tr>
                            <th>File Column</th>
                            <th>Canonical Field</th>
                            <th>AI Confidence</th>
                        </tr>
                    </thead>
                    <tbody>
                        {mapping_rows}
                    </tbody>
                </table>
                
                <div class="actions">
                    <button type="submit">Save as Template</button>
                    <a href="/files/{file_id}" class="btn-link">Back to File</a>
                </div>
            </form>
            
            <script>
                // Set initial mapping values
                const initialMappings = {initial_mappings_js};
                document.querySelectorAll('.mapping-select').forEach(select => {{
                    const header = select.dataset.header;
                    if (initialMappings[header]) {{
                        select.value = initialMappings[header];
                    }}
                }});
            </script>
    """
    
    html_content = wrap_with_layout(
        content=content,
        page_title=f"Edit Mappings - {bordereaux_file.filename}",
        current_page="templates",
        additional_css=page_css
    )
    
    return HTMLResponse(content=html_content)


@router.post("/file/{file_id}/save")
async def save_mappings_as_template(
    file_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Save corrected mappings as a template."""
    bordereaux_file = db.query(BordereauxFile).filter(BordereauxFile.id == file_id).first()
    
    if not bordereaux_file:
        raise HTTPException(status_code=404, detail=f"File with ID {file_id} not found")
    
    # Load proposal to get file headers
    proposal = load_proposal(file_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="No mapping proposal found")
    
    file_headers = proposal.get("file_headers", [])
    
    # Get form data
    form_data = await request.form()
    
    template_name = form_data.get("template_name", "")
    template_id = form_data.get("template_id", "")
    file_type = form_data.get("file_type", "")
    carrier = form_data.get("carrier") or None
    
    if not template_name or not template_id or not file_type:
        raise HTTPException(status_code=400, detail="template_name, template_id, and file_type are required")
    
    # Extract mappings from form data
    column_mappings = {}
    
    for header in file_headers:
        mapping_key = f"mapping_{header}"
        if mapping_key in form_data:
            mapped_field = form_data[mapping_key]
            if mapped_field:  # Only include non-empty mappings
                column_mappings[header] = mapped_field
    
    if not column_mappings:
        raise HTTPException(status_code=400, detail="At least one column mapping is required")
    
    # Check if template_id already exists
    existing_template = template_repository.get_by_id(db, template_id)
    if existing_template:
        raise HTTPException(
            status_code=400,
            detail=f"Template with ID '{template_id}' already exists"
        )
    
    # Create template
    try:
        file_type_enum = FileType(file_type.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid file_type: {file_type}")
    
    template_create = TemplateCreate(
        template_id=template_id,
        name=template_name,
        carrier=carrier,
        file_type=file_type_enum,
        column_mappings=column_mappings,
        active_flag=True,
        version="1.0.0"
    )
    
    template = template_repository.create(db, template_create)
    
    logger.info(
        "Template created from mappings",
        file_id=file_id,
        template_id=template_id,
        mapping_count=len(column_mappings)
    )
    
    # Redirect to templates page
    return RedirectResponse(url=f"/mappings", status_code=303)




@router.get("/upload/modal", response_class=HTMLResponse)
async def upload_template_modal():
    """Serve the template upload modal content."""
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
            .example-link {
                margin-top: 20px;
                padding: 15px;
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 4px;
                font-size: 12px;
                color: #495057;
            }
            .example-link code {
                background: #e9ecef;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
            }
            """
    
    modal_content = f"""
        <div class="modal-header">
            <h2>Upload Template</h2>
            <button class="modal-close" onclick="closeModal()">×</button>
        </div>
        <div class="modal-body">
            <p class="subtitle">Upload a template JSON file to add it to the system</p>
            
            <div class="upload-area" id="uploadArea" onclick="document.getElementById('fileInput').click()">
                <div class="upload-icon">📄</div>
                <div class="upload-text">Click to select or drag and drop</div>
                <div class="upload-hint">JSON template file</div>
            </div>
            
            <input type="file" id="fileInput" accept=".json" />
            
            <div class="file-info" id="fileInfo">
                <div class="file-name" id="fileName"></div>
                <div class="file-size" id="fileSize"></div>
            </div>
            
            <div class="error" id="errorMessage"></div>
            <div class="success" id="successMessage"></div>
            
            <button id="uploadButton" onclick="uploadTemplate()" disabled>Upload Template</button>
            
            <div class="example-link">
                <strong>Template JSON Format:</strong><br>
                <code>template_id</code>, <code>name</code>, <code>file_type</code> (claims/premium/exposure), 
                <code>column_mappings</code> (source → canonical), <code>carrier</code> (optional), 
                <code>version</code> (optional), <code>active_flag</code> (optional)
            </div>
        </div>
        <style>
            {modal_css}
        </style>
        <script>
            const fileInput = document.getElementById('fileInput');
            const uploadArea = document.getElementById('uploadArea');
            const fileInfo = document.getElementById('fileInfo');
            const fileName = document.getElementById('fileName');
            const fileSize = document.getElementById('fileSize');
            const uploadButton = document.getElementById('uploadButton');
            const errorMessage = document.getElementById('errorMessage');
            const successMessage = document.getElementById('successMessage');
            let selectedFile = null;
            
            fileInput.addEventListener('change', function(e) {{
                handleFileSelect(e.target.files[0]);
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
                if (e.dataTransfer.files.length > 0) {{
                    handleFileSelect(e.dataTransfer.files[0]);
                }}
            }});
            
            function handleFileSelect(file) {{
                if (!file) return;
                
                if (!file.name.endsWith('.json')) {{
                    showError('Please select a JSON file');
                    return;
                }}
                
                selectedFile = file;
                fileName.textContent = file.name;
                fileSize.textContent = formatFileSize(file.size);
                fileInfo.classList.add('show');
                uploadButton.disabled = false;
                hideError();
                hideSuccess();
            }}
            
            function formatFileSize(bytes) {{
                if (bytes === 0) return '0 Bytes';
                const k = 1024;
                const sizes = ['Bytes', 'KB', 'MB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
            }}
            
            async function uploadTemplate() {{
                if (!selectedFile) {{
                    showError('Please select a file first');
                    return;
                }}
                
                const formData = new FormData();
                formData.append('file', selectedFile);
                
                uploadButton.disabled = true;
                uploadButton.textContent = 'Uploading...';
                hideError();
                hideSuccess();
                
                try {{
                    const response = await fetch('/mappings/upload', {{
                        method: 'POST',
                        body: formData
                    }});
                    
                    const result = await response.json();
                    
                    if (response.ok) {{
                        showSuccess(`Template "${{result.template.name}}" uploaded successfully! Redirecting...`);
                        setTimeout(() => {{
                            window.location.reload();
                        }}, 2000);
                    }} else {{
                        showError(result.detail || 'Error uploading template');
                        uploadButton.disabled = false;
                        uploadButton.textContent = 'Upload Template';
                    }}
                }} catch (error) {{
                    showError('Error uploading template: ' + error.message);
                    uploadButton.disabled = false;
                    uploadButton.textContent = 'Upload Template';
                }}
            }}
            
            function showError(message) {{
                errorMessage.textContent = message;
                errorMessage.classList.add('show');
            }}
            
            function hideError() {{
                errorMessage.classList.remove('show');
            }}
            
            function showSuccess(message) {{
                successMessage.textContent = message;
                successMessage.classList.add('show');
            }}
            
            function hideSuccess() {{
                successMessage.classList.remove('show');
            }}
        </script>
    """
    return HTMLResponse(content=modal_content)


@router.get("/upload", response_class=HTMLResponse)
async def upload_template_page():
    """Serve the template upload page."""
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
            .example-link {
                margin-top: 20px;
                padding: 15px;
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 4px;
                font-size: 12px;
                color: #495057;
            }
            .example-link code {
                background: #e9ecef;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
            }
            """
    
    content = """
            <h1>Upload Template</h1>
            <p class="subtitle">Upload a template JSON file to add it to the system</p>
            
            <div class="upload-area" id="uploadArea" onclick="document.getElementById('fileInput').click()">
                <div class="upload-icon">📄</div>
                <div class="upload-text">Click to select or drag and drop</div>
                <div class="upload-hint">JSON template file</div>
            </div>
            
            <input type="file" id="fileInput" accept=".json" />
            
            <div class="file-info" id="fileInfo">
                <div class="file-name" id="fileName"></div>
                <div class="file-size" id="fileSize"></div>
            </div>
            
            <div class="error" id="errorMessage"></div>
            <div class="success" id="successMessage"></div>
            
            <button id="uploadButton" onclick="uploadTemplate()" disabled>Upload Template</button>
            
            <div class="example-link">
                <strong>Template JSON Format:</strong><br>
                <code>template_id</code>, <code>name</code>, <code>file_type</code> (claims/premium/exposure), 
                <code>column_mappings</code> (source → canonical), <code>carrier</code> (optional), 
                <code>version</code> (optional), <code>active_flag</code> (optional)
            </div>
            
            <script>
            const fileInput = document.getElementById('fileInput');
            const uploadArea = document.getElementById('uploadArea');
            const fileInfo = document.getElementById('fileInfo');
            const fileName = document.getElementById('fileName');
            const fileSize = document.getElementById('fileSize');
            const uploadButton = document.getElementById('uploadButton');
            const errorMessage = document.getElementById('errorMessage');
            const successMessage = document.getElementById('successMessage');
            let selectedFile = null;
            
            fileInput.addEventListener('change', function(e) {
                handleFileSelect(e.target.files[0]);
            });
            
            uploadArea.addEventListener('dragover', function(e) {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });
            
            uploadArea.addEventListener('dragleave', function(e) {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
            });
            
            uploadArea.addEventListener('drop', function(e) {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                if (e.dataTransfer.files.length > 0) {
                    handleFileSelect(e.dataTransfer.files[0]);
                }
            });
            
            function handleFileSelect(file) {
                if (!file) return;
                
                if (!file.name.endsWith('.json')) {
                    showError('Please select a JSON file');
                    return;
                }
                
                selectedFile = file;
                fileName.textContent = file.name;
                fileSize.textContent = formatFileSize(file.size);
                fileInfo.classList.add('show');
                uploadButton.disabled = false;
                hideError();
                hideSuccess();
            }
            
            function formatFileSize(bytes) {
                if (bytes === 0) return '0 Bytes';
                const k = 1024;
                const sizes = ['Bytes', 'KB', 'MB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
            }
            
            async function uploadTemplate() {
                if (!selectedFile) {
                    showError('Please select a file first');
                    return;
                }
                
                const formData = new FormData();
                formData.append('file', selectedFile);
                
                uploadButton.disabled = true;
                uploadButton.textContent = 'Uploading...';
                hideError();
                hideSuccess();
                
                try {
                    const response = await fetch('/mappings/upload', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        showSuccess(`Template "${result.template.name}" uploaded successfully! Redirecting...`);
                        setTimeout(() => {
                            window.location.href = '/mappings';
                        }, 2000);
                    } else {
                        showError(result.detail || 'Error uploading template');
                        uploadButton.disabled = false;
                        uploadButton.textContent = 'Upload Template';
                    }
                } catch (error) {
                    showError('Error uploading template: ' + error.message);
                    uploadButton.disabled = false;
                    uploadButton.textContent = 'Upload Template';
                }
            }
            
            function showError(message) {
                errorMessage.textContent = message;
                errorMessage.classList.add('show');
            }
            
            function hideError() {
                errorMessage.classList.remove('show');
            }
            
            function showSuccess(message) {
                successMessage.textContent = message;
                successMessage.classList.add('show');
            }
            
            function hideSuccess() {
                successMessage.classList.remove('show');
            }
        </script>
    """
    
    html_content = wrap_with_layout(
        content=content,
        page_title="Upload Template",
        current_page="upload_template",
        additional_css=page_css
    )
    return HTMLResponse(content=html_content)


@router.post("/upload")
async def upload_template(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a template from a JSON file."""
    logger = get_structured_logger(__name__)
    
    try:
        # Read file content
        content = await file.read()
        
        # Parse JSON
        try:
            template_data = json.loads(content.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in template file", error=str(e))
            raise HTTPException(status_code=400, detail=f"Invalid JSON file: {str(e)}")
        
        # Validate required fields
        required_fields = ['template_id', 'name', 'file_type', 'column_mappings']
        missing_fields = [field for field in required_fields if field not in template_data]
        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        # Check if template already exists
        existing_template = template_repository.get_by_id(db, template_data['template_id'])
        if existing_template:
            raise HTTPException(
                status_code=409,
                detail=f"Template with ID '{template_data['template_id']}' already exists"
            )
        
        # Validate file_type
        try:
            file_type = FileType(template_data['file_type'])
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file_type: {template_data['file_type']}. Must be one of: claims, premium, exposure"
            )
        
        # Validate column_mappings
        if not isinstance(template_data['column_mappings'], dict):
            raise HTTPException(
                status_code=400,
                detail="column_mappings must be a dictionary"
            )
        
        # Create TemplateCreate object
        template_create = TemplateCreate(
            template_id=template_data['template_id'],
            name=template_data['name'],
            carrier=template_data.get('carrier'),
            file_type=file_type,
            pattern=template_data.get('pattern'),
            column_mappings=template_data['column_mappings'],
            version=template_data.get('version', '1.0.0'),
            active_flag=template_data.get('active_flag', True),
        )
        
        # Create template
        created_template = template_repository.create(db, template_create)
        
        logger.info(
            "Template uploaded successfully",
            template_id=created_template.template_id,
            name=created_template.name
        )
        
        return JSONResponse(
            content={
                "success": True,
                "message": f"Template '{created_template.name}' uploaded successfully",
                "template": {
                    "id": created_template.id,
                    "template_id": created_template.template_id,
                    "name": created_template.name,
                    "carrier": created_template.carrier,
                    "file_type": created_template.file_type,
                }
            },
            status_code=201
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error uploading template", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error uploading template: {str(e)}")


@router.get("/", response_class=HTMLResponse)
async def list_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """View all templates/mappings."""
    templates = db.query(Template).order_by(Template.created_at.desc()).offset(skip).limit(limit).all()
    
    template_rows = ""
    if templates:
        for template in templates:
            mapping_count = len(template.column_mappings) if template.column_mappings else 0
            status_badge = "Active" if template.active_flag else "Inactive"
            status_class = "active" if template.active_flag else "inactive"
            
            template_rows += f"""
            <tr data-template-id="{template.id}">
                <td>{template.id}</td>
                <td><strong>{template.template_id}</strong></td>
                <td>{template.name}</td>
                <td>{template.carrier or "N/A"}</td>
                <td>{template.file_type}</td>
                <td>{mapping_count}</td>
                <td><span class="badge badge-{status_class}">{status_badge}</span></td>
                <td>{template.created_at.strftime("%Y-%m-%d %H:%M") if template.created_at else "N/A"}</td>
                <td>
                    <a href="/mappings/template/{template.id}" class="btn-link">View</a>
                    <a href="/mappings/template/{template.id}/edit" class="btn-link" style="margin-left: 10px;">Edit</a>
                    <button class="btn-delete delete-template-btn" style="margin-left: 10px;" 
                            data-template-id="{template.id}" 
                            data-template-name="{template.name.replace(chr(34), '&quot;').replace(chr(39), '&#39;')}" 
                            data-template-template-id="{template.template_id}">Delete</button>
                </td>
            </tr>
            """
    else:
        template_rows = '<tr><td colspan="9"><div class="empty-state"><div class="empty-state-icon">📭</div><p>No templates found</p></div></td></tr>'
    
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
                margin: 20px 0;
            }
            th, td {
                padding: 14px 12px;
                text-align: left;
                border-bottom: 1px solid #e9ecef;
            }
            th {
                background: #f8f9fa;
                font-weight: 600;
                color: #003781;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                border-bottom: 2px solid #dee2e6;
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
                font-size: 14px;
                color: #495057;
            }
            tr:hover {
                background: #f8f9fa;
            }
            .badge {
                padding: 4px 10px;
                border-radius: 3px;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.3px;
            }
            .badge-active {
                background: #d1e7dd;
                color: #0f5132;
            }
            .badge-inactive {
                background: #f8d7da;
                color: #842029;
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
    
    content = f"""
            <h1>Templates & Mappings</h1>
            
            <table id="templatesTable">
                <thead>
                    <tr>
                        <th class="sortable" data-column="id">ID</th>
                        <th class="sortable" data-column="template_id">Template ID</th>
                        <th class="sortable" data-column="name">Name</th>
                        <th class="sortable" data-column="carrier">Carrier</th>
                        <th class="sortable" data-column="file_type">File Type</th>
                        <th class="sortable" data-column="mappings">Mappings</th>
                        <th class="sortable" data-column="status">Status</th>
                        <th class="sortable" data-column="created_at">Created</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="templatesTableBody">
                    {template_rows}
                </tbody>
            </table>
    """
    
    additional_scripts = """
        <script>
            let allTemplatesData = [];
            let currentSort = { column: 'created_at', direction: 'desc' };
            
            document.addEventListener('DOMContentLoaded', function() {
                // Store original data
                document.querySelectorAll('#templatesTableBody tr').forEach(row => {
                    if (row.cells.length > 0) {
                        const data = {
                            id: row.cells[0].textContent.trim(),
                            template_id: row.cells[1].querySelector('strong') ? row.cells[1].querySelector('strong').textContent.trim() : row.cells[1].textContent.trim(),
                            name: row.cells[2].textContent.trim(),
                            carrier: row.cells[3].textContent.trim(),
                            file_type: row.cells[4].textContent.trim(),
                            mappings: parseInt(row.cells[5].textContent.trim()) || 0,
                            status: row.cells[6].querySelector('.badge') ? row.cells[6].querySelector('.badge').textContent.trim() : row.cells[6].textContent.trim(),
                            created_at: row.cells[7].textContent.trim(),
                            html: row.outerHTML
                        };
                        allTemplatesData.push(data);
                    }
                });
                
                // Sorting functionality
                document.querySelectorAll('th.sortable').forEach(header => {
                    header.addEventListener('click', function() {
                        const column = this.dataset.column;
                        
                        // Toggle sort direction
                        if (currentSort.column === column) {
                            currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
                        } else {
                            currentSort.column = column;
                            currentSort.direction = 'asc';
                        }
                        
                        // Update header classes
                        document.querySelectorAll('th.sortable').forEach(h => {
                            h.classList.remove('sort-asc', 'sort-desc');
                        });
                        this.classList.add(`sort-${currentSort.direction}`);
                        
                        applySort();
                    });
                });
                
                // Initialize sort indicator
                document.querySelector('th[data-column="created_at"]').classList.add('sort-desc');
                
                // Attach initial delete button listeners
                attachDeleteListeners();
            });
            
            function applySort() {
                // Sort data
                const sortedData = [...allTemplatesData].sort((a, b) => {
                    let aVal = a[currentSort.column];
                    let bVal = b[currentSort.column];
                    
                    // Handle numeric columns
                    if (currentSort.column === 'id' || currentSort.column === 'mappings') {
                        aVal = parseInt(aVal) || 0;
                        bVal = parseInt(bVal) || 0;
                    } else {
                        aVal = String(aVal || '').toLowerCase();
                        bVal = String(bVal || '').toLowerCase();
                    }
                    
                    if (currentSort.direction === 'asc') {
                        return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
                    } else {
                        return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
                    }
                });
                
                // Update table
                const tbody = document.getElementById('templatesTableBody');
                tbody.innerHTML = sortedData.map(template => template.html).join('');
                // Re-attach delete button listeners
                attachDeleteListeners();
            }
            
            function attachDeleteListeners() {
                // Add event listeners to all delete buttons
                document.querySelectorAll('.delete-template-btn').forEach(button => {
                    if (!button.hasAttribute('data-listener-attached')) {
                        button.setAttribute('data-listener-attached', 'true');
                        button.addEventListener('click', async function() {
                            const templateDbId = this.getAttribute('data-template-id');
                            const templateName = this.getAttribute('data-template-name');
                            const templateId = this.getAttribute('data-template-template-id');
                            
                            const confirmed = confirm(`Are you sure you want to delete the template "${templateName}" (ID: ${templateId})?\\n\\nThis action cannot be undone.`);
                            
                            if (confirmed) {
                                try {
                                    const response = await fetch(`/mappings/template/${templateDbId}/delete`, {
                                        method: 'DELETE',
                                        headers: {
                                            'Content-Type': 'application/json',
                                        }
                                    });
                                    
                                    if (response.ok) {
                                        // Reload the page to show updated list
                                        window.location.reload();
                                    } else {
                                        const error = await response.json();
                                        alert(`Error deleting template: ${error.detail || 'Unknown error'}`);
                                    }
                                } catch (error) {
                                    alert(`Error deleting template: ${error.message}`);
                                }
                            }
                        });
                    }
                });
            }
        </script>
    """
    
    html_content = wrap_with_layout(
        content=content,
        page_title="Templates & Mappings",
        current_page="templates",
        additional_css=page_css,
        additional_scripts=additional_scripts
    )
    
    return HTMLResponse(content=html_content)


@router.get("/template/{template_id}", response_class=HTMLResponse)
async def view_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    """View a specific template's mappings."""
    template = template_repository.get_by_db_id(db, template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail=f"Template with ID {template_id} not found")
    
    # Build mappings table
    mapping_rows = ""
    if template.column_mappings:
        for source_col, canonical_field in template.column_mappings.items():
            mapping_rows += f"""
            <tr>
                <td><strong>{source_col}</strong></td>
                <td>{canonical_field}</td>
            </tr>
            """
    
    status_badge = "Active" if template.active_flag else "Inactive"
    status_class = "active" if template.active_flag else "inactive"
    
    page_css = """
            h1 {
                color: #003781;
                margin-bottom: 20px;
                font-size: 28px;
                font-weight: 600;
                letter-spacing: -0.5px;
            }
            h2 {
                color: #003781;
                margin-top: 30px;
                margin-bottom: 15px;
                font-size: 20px;
                font-weight: 600;
            }
            .template-info {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 4px;
                margin-bottom: 20px;
                border: 1px solid #e9ecef;
            }
            .template-info p {
                margin: 5px 0;
                color: #495057;
                font-size: 14px;
            }
            .template-info strong {
                color: #003781;
                font-weight: 600;
            }
            .badge {
                padding: 4px 10px;
                border-radius: 3px;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.3px;
            }
            .badge-active {
                background: #d1e7dd;
                color: #0f5132;
            }
            .badge-inactive {
                background: #f8d7da;
                color: #842029;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }
            th, td {
                padding: 14px 12px;
                text-align: left;
                border-bottom: 1px solid #e9ecef;
            }
            th {
                background: #f8f9fa;
                font-weight: 600;
                color: #003781;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                border-bottom: 2px solid #dee2e6;
            }
            td {
                font-size: 14px;
                color: #495057;
            }
            tr:hover {
                background: #f8f9fa;
            }
            .actions {
                margin-top: 30px;
                display: flex;
                gap: 12px;
                align-items: center;
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
            """
    
    content = f"""
            <h1>{template.name}</h1>
            
            <div class="template-info">
                <p><strong>Template ID:</strong> {template.template_id}</p>
                <p><strong>Carrier:</strong> {template.carrier or "N/A"}</p>
                <p><strong>File Type:</strong> {template.file_type}</p>
                <p><strong>Status:</strong> <span class="badge badge-{status_class}">{status_badge}</span></p>
                <p><strong>Version:</strong> {template.version}</p>
                <p><strong>Created:</strong> {template.created_at.strftime("%Y-%m-%d %H:%M") if template.created_at else "N/A"}</p>
            </div>
            
            <h2>Column Mappings</h2>
            <table>
                <thead>
                    <tr>
                        <th>Source Column</th>
                        <th>Canonical Field</th>
                    </tr>
                </thead>
                <tbody>
                    {mapping_rows if mapping_rows else '<tr><td colspan="2" style="text-align: center; color: #6c757d; padding: 40px;">No mappings found</td></tr>'}
                </tbody>
            </table>
            
            <div class="actions">
                <a href="/mappings/template/{template.id}/edit" class="btn-link">Edit Template</a>
                <a href="/mappings" class="btn-link">Back to Templates</a>
            </div>
    """
    
    html_content = wrap_with_layout(
        content=content,
        page_title=f"Template: {template.name}",
        current_page="templates",
        additional_css=page_css
    )
    
    return HTMLResponse(content=html_content)


@router.get("/template/{template_id}/edit", response_class=HTMLResponse)
async def edit_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    """Edit a template's mappings and metadata."""
    template = template_repository.get_by_db_id(db, template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail=f"Template with ID {template_id} not found")
    
    # Build canonical fields options HTML
    canonical_options_html = "".join([
        f'<option value="{field}">{label}</option>'
        for field, label in CANONICAL_FIELDS
    ])
    
    # Build mappings rows HTML with editable dropdowns
    mapping_rows = ""
    if template.column_mappings:
        for source_col, canonical_field in template.column_mappings.items():
            options_html = "".join([
                f'<option value="{field}" {"selected" if field == canonical_field else ""}>{label}</option>'
                for field, label in CANONICAL_FIELDS
            ])
            
            mapping_rows += f"""
            <tr>
                <td><strong>{source_col}</strong></td>
                <td>
                    <select name="mapping_{source_col}" class="mapping-select">
                        <option value="">-- Not Mapped --</option>
                        {options_html}
                    </select>
                </td>
                <td>
                    <button type="button" class="btn-remove" onclick="removeMapping(this)" data-column="{source_col}">Remove</button>
                </td>
            </tr>
            """
    
    # File type options
    file_type_options = ""
    for ft in ["claims", "premium", "exposure"]:
        selected = "selected" if template.file_type.lower() == ft else ""
        file_type_options += f'<option value="{ft}" {selected}>{ft.title()}</option>'
    
    page_css = """
            h1 {
                color: #003781;
                margin-bottom: 20px;
                font-size: 28px;
                font-weight: 600;
                letter-spacing: -0.5px;
            }
            h2 {
                color: #003781;
                margin-top: 30px;
                margin-bottom: 15px;
                font-size: 20px;
                font-weight: 600;
            }
            h3 {
                color: #495057;
                margin-bottom: 10px;
                font-size: 16px;
                font-weight: 600;
            }
            .template-info {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 4px;
                margin-bottom: 20px;
                border: 1px solid #e9ecef;
            }
            .template-info p {
                margin: 5px 0;
                color: #495057;
                font-size: 14px;
            }
            .template-info strong {
                color: #003781;
                font-weight: 600;
            }
            .template-info em {
                color: #6c757d;
                font-size: 12px;
            }
            .form-group {
                margin-bottom: 20px;
            }
            .form-group label {
                display: block;
                margin-bottom: 8px;
                font-weight: 500;
                color: #495057;
                font-size: 14px;
            }
            .form-group input[type="text"],
            .form-group input[type="checkbox"],
            .form-group select {
                width: 100%;
                padding: 8px 12px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                font-size: 14px;
                color: #495057;
                background: white;
            }
            .form-group input[type="text"]:focus,
            .form-group select:focus {
                outline: none;
                border-color: #003781;
                box-shadow: 0 0 0 2px rgba(0, 55, 129, 0.1);
            }
            .form-group input[type="checkbox"] {
                width: auto;
                margin-right: 8px;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }
            th, td {
                padding: 14px 12px;
                text-align: left;
                border-bottom: 1px solid #e9ecef;
            }
            th {
                background: #f8f9fa;
                font-weight: 600;
                color: #003781;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                border-bottom: 2px solid #dee2e6;
            }
            td {
                font-size: 14px;
                color: #495057;
            }
            tr:hover {
                background: #f8f9fa;
            }
            .mapping-select {
                width: 100%;
                padding: 8px 12px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                font-size: 14px;
                color: #495057;
                background: white;
            }
            .mapping-select:focus {
                outline: none;
                border-color: #003781;
                box-shadow: 0 0 0 2px rgba(0, 55, 129, 0.1);
            }
            .btn-remove {
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
            .btn-remove:hover {
                background: #bb2d3b;
            }
            .actions {
                margin-top: 30px;
                display: flex;
                gap: 12px;
                align-items: center;
            }
            button[type="submit"] {
                padding: 10px 20px;
                background: #003781;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s;
            }
            button[type="submit"]:hover {
                background: #002d66;
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
            .add-mapping {
                margin-top: 20px;
                padding: 20px;
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 4px;
            }
            .add-mapping input[type="text"],
            .add-mapping select {
                padding: 8px 12px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                font-size: 14px;
                color: #495057;
                background: white;
            }
            .add-mapping input[type="text"]:focus,
            .add-mapping select:focus {
                outline: none;
                border-color: #003781;
                box-shadow: 0 0 0 2px rgba(0, 55, 129, 0.1);
            }
            .add-mapping button {
                padding: 8px 16px;
                background: #198754;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
                transition: all 0.2s;
            }
            .add-mapping button:hover {
                background: #157347;
            }
            .flex-row {
                display: flex;
                gap: 12px;
                align-items: center;
            }
            .flex-row input,
            .flex-row select {
                flex: 1;
            }
            """
    
    content = f"""
            <h1>Edit Template: {template.name}</h1>
            
            <div class="template-info">
                <p><strong>Template ID:</strong> {template.template_id} <em>(cannot be changed)</em></p>
                <p><strong>Version:</strong> {template.version}</p>
                <p><strong>Created:</strong> {template.created_at.strftime("%Y-%m-%d %H:%M") if template.created_at else "N/A"}</p>
            </div>
            
            <form id="templateForm" method="POST" action="/mappings/template/{template_id}/edit">
                <div class="form-group">
                    <label for="template_name">Template Name *</label>
                    <input type="text" id="template_name" name="template_name" required value="{template.name}">
                </div>
                
                <div class="form-group">
                    <label for="carrier">Carrier</label>
                    <input type="text" id="carrier" name="carrier" value="{template.carrier or ""}">
                </div>
                
                <div class="form-group">
                    <label for="file_type">File Type *</label>
                    <select id="file_type" name="file_type" required>
                        {file_type_options}
                    </select>
                </div>
                
                <div class="form-group">
                    <label>
                        <input type="checkbox" name="active_flag" value="true" {"checked" if template.active_flag else ""}>
                        Active
                    </label>
                </div>
                
                <h2>Column Mappings</h2>
                <table id="mappingsTable">
                    <thead>
                        <tr>
                            <th>Source Column</th>
                            <th>Canonical Field</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {mapping_rows if mapping_rows else '<tr><td colspan="3" style="text-align: center; color: #6c757d; padding: 40px;">No mappings found</td></tr>'}
                    </tbody>
                </table>
                
                <div class="add-mapping">
                    <h3>Add New Mapping</h3>
                    <div class="flex-row">
                        <input type="text" id="newColumn" placeholder="Source column name">
                        <select id="newCanonical">
                            <option value="">-- Select Canonical Field --</option>
                            {canonical_options_html}
                        </select>
                        <button type="button" onclick="addMapping()">Add Mapping</button>
                    </div>
                </div>
                
                <div class="actions">
                    <button type="submit">Save Changes</button>
                    <a href="/mappings/template/{template_id}" class="btn-link">Cancel</a>
                    <a href="/mappings" class="btn-link">Back to Templates</a>
                </div>
            </form>
            
            <script>
                function removeMapping(btn) {{
                    const row = btn.closest('tr');
                    row.remove();
                }}
                
                function addMapping() {{
                    const columnName = document.getElementById('newColumn').value.trim();
                    const canonicalField = document.getElementById('newCanonical').value;
                    
                    if (!columnName) {{
                        alert('Please enter a column name');
                        return;
                    }}
                    
                    if (!canonicalField) {{
                        alert('Please select a canonical field');
                        return;
                    }}
                    
                    // Check if column already exists
                    const existingRows = document.querySelectorAll('#mappingsTable tbody tr');
                    for (let row of existingRows) {{
                        const colName = row.querySelector('td:first-child strong')?.textContent;
                        if (colName === columnName) {{
                            alert('This column is already mapped');
                            return;
                        }}
                    }}
                    
                    const canonicalLabel = document.querySelector(`#newCanonical option[value="${{canonicalField}}"]`).textContent;
                    const optionsHtml = `{canonical_options_html}`;
                    const selectedOptions = optionsHtml.replace(`value="${{canonicalField}}"`, `value="${{canonicalField}}" selected`);
                    
                    const tbody = document.querySelector('#mappingsTable tbody');
                    const newRow = document.createElement('tr');
                    newRow.innerHTML = `
                        <td><strong>${{columnName}}</strong></td>
                        <td>
                            <select name="mapping_${{columnName}}" class="mapping-select">
                                <option value="">-- Not Mapped --</option>
                                ${{selectedOptions}}
                            </select>
                        </td>
                        <td>
                            <button type="button" class="btn-remove" onclick="removeMapping(this)" data-column="${{columnName}}">Remove</button>
                        </td>
                    `;
                    
                    // Remove "No mappings found" message if present
                    if (tbody.querySelector('td[colspan]')) {{
                        tbody.innerHTML = '';
                    }}
                    
                    tbody.appendChild(newRow);
                    
                    // Clear inputs
                    document.getElementById('newColumn').value = '';
                    document.getElementById('newCanonical').value = '';
                }}
            </script>
    """
    
    html_content = wrap_with_layout(
        content=content,
        page_title=f"Edit Template: {template.name}",
        current_page="templates",
        additional_css=page_css
    )
    
    return HTMLResponse(content=html_content)


@router.post("/template/{template_id}/edit")
async def save_template_edit(
    template_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Save edited template."""
    template = template_repository.get_by_db_id(db, template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail=f"Template with ID {template_id} not found")
    
    # Get form data
    form_data = await request.form()
    
    template_name = form_data.get("template_name", "")
    carrier = form_data.get("carrier") or None
    file_type = form_data.get("file_type", "")
    active_flag = form_data.get("active_flag") == "true"
    
    if not template_name or not file_type:
        raise HTTPException(status_code=400, detail="template_name and file_type are required")
    
    # Extract mappings from form data
    column_mappings = {}
    for key, value in form_data.items():
        if key.startswith("mapping_") and value:  # Only include non-empty mappings
            source_column = key.replace("mapping_", "")
            column_mappings[source_column] = value
    
    if not column_mappings:
        raise HTTPException(status_code=400, detail="At least one column mapping is required")
    
    # Create update object
    try:
        file_type_enum = FileType(file_type.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid file_type: {file_type}")
    
    template_update = TemplateUpdate(
        name=template_name,
        carrier=carrier,
        file_type=file_type_enum,
        column_mappings=column_mappings,
        active_flag=active_flag
    )
    
    # Update template
    updated_template = template_repository.update(db, template.template_id, template_update)
    
    if not updated_template:
        raise HTTPException(status_code=500, detail="Failed to update template")
    
    logger.info(
        "Template updated",
        template_id=template.template_id,
        mapping_count=len(column_mappings)
    )
    
    # Redirect to template view
    return RedirectResponse(url=f"/mappings/template/{template_id}", status_code=303)


@router.delete("/template/{template_id}/delete")
async def delete_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    """Delete a template."""
    template = template_repository.get_by_db_id(db, template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail=f"Template with ID {template_id} not found")
    
    template_template_id = template.template_id
    
    # Delete template using repository
    deleted = template_repository.delete(db, template_template_id)
    
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete template")
    
    logger.info(
        "Template deleted",
        template_id=template_template_id,
        db_id=template_id
    )
    
    # Return success response
    return JSONResponse(
        content={
            "success": True,
            "message": f"Template '{template_template_id}' deleted successfully"
        },
        status_code=200
    )

