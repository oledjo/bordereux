from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.models.bordereaux import BordereauxFile, FileStatus
from app.models.template import TemplateCreate, TemplateUpdate, FileType, Template
from app.services.template_repository import TemplateRepository
from app.services.parsing_service import ParsingService
from app.core.logging import get_structured_logger
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
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Edit Mappings - {bordereaux_file.filename}</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: #f5f5f5;
                padding: 20px;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                padding: 30px;
            }}
            h1 {{
                color: #333;
                margin-bottom: 10px;
            }}
            .file-info {{
                background: #f8f9fa;
                padding: 15px;
                border-radius: 6px;
                margin-bottom: 20px;
            }}
            .file-info p {{
                margin: 5px 0;
                color: #666;
            }}
            .file-info strong {{
                color: #333;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            th {{
                background: #f8f9fa;
                font-weight: 600;
                color: #333;
            }}
            .mapping-select {{
                width: 100%;
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
            }}
            .confidence {{
                padding: 4px 8px;
                border-radius: 4px;
                font-weight: 600;
                font-size: 12px;
            }}
            .confidence-high {{
                background: #d4edda;
                color: #155724;
            }}
            .confidence-medium {{
                background: #fff3cd;
                color: #856404;
            }}
            .confidence-low {{
                background: #f8d7da;
                color: #721c24;
            }}
            .actions {{
                margin-top: 30px;
                display: flex;
                gap: 10px;
            }}
            button {{
                padding: 12px 24px;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s;
            }}
            .btn-primary {{
                background: #007bff;
                color: white;
            }}
            .btn-primary:hover {{
                background: #0056b3;
            }}
            .btn-secondary {{
                background: #6c757d;
                color: white;
            }}
            .btn-secondary:hover {{
                background: #545b62;
            }}
            .form-group {{
                margin-bottom: 20px;
            }}
            .form-group label {{
                display: block;
                margin-bottom: 5px;
                font-weight: 600;
                color: #333;
            }}
            .form-group input, .form-group select {{
                width: 100%;
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
            }}
            .alert {{
                padding: 15px;
                border-radius: 6px;
                margin-bottom: 20px;
            }}
            .alert-info {{
                background: #d1ecf1;
                color: #0c5460;
                border: 1px solid #bee5eb;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📋 Edit Column Mappings</h1>
            
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
                    <small style="color: #666;">Lowercase letters, numbers, and underscores only</small>
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
                
                <h2 style="margin-top: 30px; margin-bottom: 15px;">Column Mappings</h2>
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
                    <button type="submit" class="btn-primary">💾 Save as Template</button>
                    <a href="/files/{file_id}" class="btn-secondary" style="text-decoration: none; display: inline-block;">← Back to File</a>
                </div>
            </form>
        </div>
        
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
    </body>
    </html>
    """
    
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
            <tr>
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
                    <button onclick="deleteTemplateWithConfirm({template.id}, {json.dumps(template.name)}, {json.dumps(template.template_id)})" class="btn-delete" style="margin-left: 10px;">Delete</button>
                </td>
            </tr>
            """
    else:
        template_rows = '<tr><td colspan="9"><div class="empty-state"><div class="empty-state-icon">📭</div><p>No templates found</p></div></td></tr>'
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Templates & Mappings</title>
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
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                padding: 30px;
            }}
            h1 {{
                color: #333;
                margin-bottom: 20px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            th {{
                background: #f8f9fa;
                font-weight: 600;
                color: #333;
            }}
            .badge {{
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
            }}
            .badge-active {{
                background: #d4edda;
                color: #155724;
            }}
            .badge-inactive {{
                background: #f8d7da;
                color: #721c24;
            }}
            .btn-link {{
                color: #007bff;
                text-decoration: none;
                font-weight: 600;
            }}
            .btn-link:hover {{
                text-decoration: underline;
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
            .empty-state {{
                text-align: center;
                padding: 40px;
                color: #666;
            }}
            .empty-state-icon {{
                font-size: 48px;
                margin-bottom: 10px;
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
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-actions">
                <h1>📋 Templates & Mappings</h1>
                <a href="/" class="btn-back">← Back to Home</a>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Template ID</th>
                        <th>Name</th>
                        <th>Carrier</th>
                        <th>File Type</th>
                        <th>Mappings</th>
                        <th>Status</th>
                        <th>Created</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {template_rows}
                </tbody>
            </table>
        </div>
        
        <script>
            async function deleteTemplateWithConfirm(templateDbId, templateName, templateId) {{
                const confirmed = confirm(`Are you sure you want to delete the template "${{templateName}}" (ID: ${{templateId}})?\\n\\nThis action cannot be undone.`);
                
                if (confirmed) {{
                    try {{
                        const response = await fetch(`/mappings/template/${{templateDbId}}/delete`, {{
                            method: 'DELETE',
                            headers: {{
                                'Content-Type': 'application/json',
                            }}
                        }});
                        
                        if (response.ok) {{
                            // Reload the page to show updated list
                            window.location.reload();
                        }} else {{
                            const error = await response.json();
                            alert(`Error deleting template: ${{error.detail || 'Unknown error'}}`);
                        }}
                    }} catch (error) {{
                        alert(`Error deleting template: ${{error.message}}`);
                    }}
                }}
            }}
        </script>
    </body>
    </html>
    """
    
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
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Template: {template.name}</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: #f5f5f5;
                padding: 20px;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                padding: 30px;
            }}
            h1 {{ color: #333; margin-bottom: 20px; }}
            .template-info {{
                background: #f8f9fa;
                padding: 15px;
                border-radius: 6px;
                margin-bottom: 20px;
            }}
            .template-info p {{ margin: 5px 0; color: #666; }}
            .template-info strong {{ color: #333; }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            th {{
                background: #f8f9fa;
                font-weight: 600;
                color: #333;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📋 {template.name}</h1>
            
            <div class="template-info">
                <p><strong>Template ID:</strong> {template.template_id}</p>
                <p><strong>Carrier:</strong> {template.carrier or "N/A"}</p>
                <p><strong>File Type:</strong> {template.file_type}</p>
                <p><strong>Status:</strong> {"Active" if template.active_flag else "Inactive"}</p>
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
                    {mapping_rows if mapping_rows else '<tr><td colspan="2">No mappings found</td></tr>'}
                </tbody>
            </table>
            
            <div style="margin-top: 20px;">
                <a href="/mappings/template/{template.id}/edit" class="btn-link" style="margin-right: 15px; background: #007bff; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; display: inline-block;">✏️ Edit Template</a>
                <a href="/mappings" class="btn-link">← Back to Templates</a>
            </div>
        </div>
    </body>
    </html>
    """
    
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
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Edit Template: {template.name}</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: #f5f5f5;
                padding: 20px;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                padding: 30px;
            }}
            h1 {{ color: #333; margin-bottom: 20px; }}
            .template-info {{
                background: #f8f9fa;
                padding: 15px;
                border-radius: 6px;
                margin-bottom: 20px;
            }}
            .template-info p {{ margin: 5px 0; color: #666; }}
            .template-info strong {{ color: #333; }}
            .form-group {{
                margin-bottom: 20px;
            }}
            .form-group label {{
                display: block;
                margin-bottom: 5px;
                font-weight: 600;
                color: #333;
            }}
            .form-group input, .form-group select {{
                width: 100%;
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            th {{
                background: #f8f9fa;
                font-weight: 600;
                color: #333;
            }}
            .mapping-select {{
                width: 100%;
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
            }}
            .btn-remove {{
                padding: 6px 12px;
                background: #dc3545;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 12px;
            }}
            .btn-remove:hover {{
                background: #c82333;
            }}
            .actions {{
                margin-top: 30px;
                display: flex;
                gap: 10px;
            }}
            button[type="submit"], .btn-link {{
                padding: 12px 24px;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
            }}
            button[type="submit"] {{
                background: #007bff;
                color: white;
            }}
            button[type="submit"]:hover {{
                background: #0056b3;
            }}
            .btn-link {{
                background: #6c757d;
                color: white;
            }}
            .btn-link:hover {{
                background: #545b62;
            }}
            .add-mapping {{
                margin-top: 20px;
                padding: 15px;
                background: #f8f9fa;
                border-radius: 6px;
            }}
            .add-mapping input {{
                margin-right: 10px;
                flex: 1;
            }}
            .add-mapping button {{
                padding: 8px 16px;
                background: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }}
            .add-mapping button:hover {{
                background: #218838;
            }}
            .flex-row {{
                display: flex;
                gap: 10px;
                align-items: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>✏️ Edit Template: {template.name}</h1>
            
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
                
                <h2 style="margin-top: 30px; margin-bottom: 15px;">Column Mappings</h2>
                <table id="mappingsTable">
                    <thead>
                        <tr>
                            <th>Source Column</th>
                            <th>Canonical Field</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {mapping_rows if mapping_rows else '<tr><td colspan="3">No mappings found</td></tr>'}
                    </tbody>
                </table>
                
                <div class="add-mapping">
                    <h3 style="margin-bottom: 10px;">Add New Mapping</h3>
                    <div class="flex-row">
                        <input type="text" id="newColumn" placeholder="Source column name" style="flex: 1;">
                        <select id="newCanonical" style="flex: 1;">
                            <option value="">-- Select Canonical Field --</option>
                            {canonical_options_html}
                        </select>
                        <button type="button" onclick="addMapping()">Add Mapping</button>
                    </div>
                </div>
                
                <div class="actions">
                    <button type="submit">💾 Save Changes</button>
                    <a href="/mappings/template/{template_id}" class="btn-link">Cancel</a>
                    <a href="/mappings" class="btn-link">← Back to Templates</a>
                </div>
            </form>
        </div>
        
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
    </body>
    </html>
    """
    
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

