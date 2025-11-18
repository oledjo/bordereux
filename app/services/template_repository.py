import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.template import Template, TemplateCreate, TemplateUpdate, FileType


class TemplateRepository:
    """Repository for managing bordereaux templates."""
    
    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_json_file_path(self, template_id: str) -> Path:
        """Get path to JSON file for a template.
        
        Args:
            template_id: Template identifier
            
        Returns:
            Path to JSON file
        """
        return self.templates_dir / f"{template_id}.json"
    
    def _save_template_to_json(self, template_data: Dict[str, Any], template_id: str) -> Path:
        """Save template data to JSON file.
        
        Args:
            template_data: Template data dictionary
            template_id: Template identifier
            
        Returns:
            Path to saved JSON file
        """
        file_path = self._get_json_file_path(template_id)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, indent=2, ensure_ascii=False)
        return file_path
    
    def _load_template_from_json(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Load template data from JSON file.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Template data dictionary or None if file doesn't exist
        """
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading template from {file_path}: {str(e)}")
            return None
    
    def create(self, db: Session, template: TemplateCreate) -> Template:
        """Create a new template.
        
        Args:
            db: Database session
            template: Template data
            
        Returns:
            Created Template instance
        """
        # Prepare template data for JSON
        template_data = {
            "template_id": template.template_id,
            "name": template.name,
            "carrier": template.carrier,
            "file_type": template.file_type.value,
            "pattern": template.pattern,
            "column_mappings": template.column_mappings,
            "version": template.version,
            "active_flag": template.active_flag,
        }
        
        # Save to JSON file
        json_file_path = self._save_template_to_json(template_data, template.template_id)
        
        # Create database record
        db_template = Template(
            template_id=template.template_id,
            name=template.name,
            carrier=template.carrier,
            file_type=template.file_type.value,
            pattern=json.dumps(template.pattern) if template.pattern else None,
            column_mappings=template.column_mappings,
            version=template.version,
            active_flag=template.active_flag,
            json_file_path=str(json_file_path),
        )
        
        db.add(db_template)
        db.commit()
        db.refresh(db_template)
        
        return db_template
    
    def get_by_id(self, db: Session, template_id: str) -> Optional[Template]:
        """Get template by template_id.
        
        Args:
            db: Database session
            template_id: Template identifier
            
        Returns:
            Template instance or None if not found
        """
        return db.query(Template).filter(
            Template.template_id == template_id
        ).first()
    
    def get_by_db_id(self, db: Session, id: int) -> Optional[Template]:
        """Get template by database ID.
        
        Args:
            db: Database session
            id: Database ID
            
        Returns:
            Template instance or None if not found
        """
        return db.query(Template).filter(Template.id == id).first()
    
    def list_all(self, db: Session) -> List[Template]:
        """List all templates.
        
        Args:
            db: Database session
            
        Returns:
            List of all templates
        """
        return db.query(Template).all()
    
    def list_active_templates(self, db: Session, file_type: Optional[FileType] = None) -> List[Template]:
        """List active templates, optionally filtered by file type.
        
        Args:
            db: Database session
            file_type: Optional file type filter
            
        Returns:
            List of active templates
        """
        query = db.query(Template).filter(Template.active_flag == True)
        
        if file_type:
            query = query.filter(Template.file_type == file_type.value)
        
        return query.all()
    
    def update(self, db: Session, template_id: str, template_update: TemplateUpdate) -> Optional[Template]:
        """Update a template.
        
        Args:
            db: Database session
            template_id: Template identifier
            template_update: Update data
            
        Returns:
            Updated Template instance or None if not found
        """
        db_template = self.get_by_id(db, template_id)
        
        if not db_template:
            return None
        
        # Update fields
        if template_update.name is not None:
            db_template.name = template_update.name
        if template_update.carrier is not None:
            db_template.carrier = template_update.carrier
        if template_update.file_type is not None:
            db_template.file_type = template_update.file_type.value
        if template_update.pattern is not None:
            db_template.pattern = json.dumps(template_update.pattern)
        if template_update.column_mappings is not None:
            db_template.column_mappings = template_update.column_mappings
        if template_update.version is not None:
            db_template.version = template_update.version
        if template_update.active_flag is not None:
            db_template.active_flag = template_update.active_flag
        if template_update.json_file_path is not None:
            db_template.json_file_path = template_update.json_file_path
        
        # Update JSON file
        template_data = {
            "template_id": db_template.template_id,
            "name": db_template.name,
            "carrier": db_template.carrier,
            "file_type": db_template.file_type,
            "pattern": json.loads(db_template.pattern) if db_template.pattern else None,
            "column_mappings": db_template.column_mappings,
            "version": db_template.version,
            "active_flag": db_template.active_flag,
        }
        
        json_file_path = self._save_template_to_json(template_data, db_template.template_id)
        db_template.json_file_path = str(json_file_path)
        
        db.commit()
        db.refresh(db_template)
        
        return db_template
    
    def delete(self, db: Session, template_id: str) -> bool:
        """Delete a template.
        
        Args:
            db: Database session
            template_id: Template identifier
            
        Returns:
            True if deleted, False if not found
        """
        db_template = self.get_by_id(db, template_id)
        
        if not db_template:
            return False
        
        # Delete JSON file
        if db_template.json_file_path:
            json_path = Path(db_template.json_file_path)
            if json_path.exists():
                try:
                    json_path.unlink()
                except Exception as e:
                    print(f"Error deleting JSON file {json_path}: {str(e)}")
        
        # Delete database record
        db.delete(db_template)
        db.commit()
        
        return True
    
    def load_from_json(self, db: Session, template_id: str) -> Optional[Template]:
        """Load template from JSON file and register in database.
        
        Args:
            db: Database session
            template_id: Template identifier (used as filename: {template_id}.json)
            
        Returns:
            Template instance or None if file not found
        """
        json_file_path = self._get_json_file_path(template_id)
        template_data = self._load_template_from_json(json_file_path)
        
        if not template_data:
            return None
        
        # Check if already exists in database
        existing = self.get_by_id(db, template_id)
        if existing:
            return existing
        
        # Create from JSON data
        template_create = TemplateCreate(
            template_id=template_data.get("template_id", template_id),
            name=template_data["name"],
            carrier=template_data.get("carrier"),
            file_type=FileType(template_data["file_type"]),
            pattern=template_data.get("pattern"),
            column_mappings=template_data["column_mappings"],
            version=template_data.get("version", "1.0.0"),
            active_flag=template_data.get("active_flag", True),
            json_file_path=str(json_file_path),
        )
        
        return self.create(db, template_create)
    
    def load_all_from_json(self, db: Session) -> List[Template]:
        """Load all templates from JSON files in templates directory.
        
        Args:
            db: Database session
            
        Returns:
            List of loaded templates
        """
        loaded_templates = []
        
        for json_file in self.templates_dir.glob("*.json"):
            template_id = json_file.stem  # filename without extension
            template = self.load_from_json(db, template_id)
            if template:
                loaded_templates.append(template)
        
        return loaded_templates

