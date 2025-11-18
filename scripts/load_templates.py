#!/usr/bin/env python3
"""Script to load templates from JSON files into the database."""

import json
from pathlib import Path
from app.core.database import get_db
from app.services.template_repository import TemplateRepository

def load_all_templates():
    """Load all templates from JSON files into the database."""
    db = next(get_db())
    template_repo = TemplateRepository(templates_dir="templates/sample_templates")
    
    # Get all JSON files in templates directory
    templates_dir = Path("templates/sample_templates")
    json_files = list(templates_dir.glob("*.json"))
    
    if not json_files:
        print("No template JSON files found in templates/sample_templates/")
        return
    
    print(f"Found {len(json_files)} template files")
    print("=" * 60)
    
    loaded_count = 0
    skipped_count = 0
    
    for json_file in json_files:
        template_id = json_file.stem  # filename without .json extension
        
        try:
            # Check if already exists
            existing = template_repo.get_by_id(db, template_id)
            if existing:
                print(f"⏭️  {template_id} - Already exists in database")
                skipped_count += 1
                continue
            
            # Load from JSON
            template = template_repo.load_from_json(db, template_id)
            
            if template:
                print(f"✅ {template_id} - Loaded successfully")
                print(f"   Name: {template.name}")
                print(f"   Type: {template.file_type}")
                print(f"   Columns: {len(template.column_mappings)}")
                loaded_count += 1
            else:
                print(f"❌ {template_id} - Failed to load")
        
        except Exception as e:
            print(f"❌ {template_id} - Error: {str(e)}")
    
    print("=" * 60)
    print(f"Summary: {loaded_count} loaded, {skipped_count} skipped")
    
    db.close()

if __name__ == "__main__":
    load_all_templates()

