import re
from pathlib import Path
from typing import Optional, List
import pandas as pd

from app.config import get_settings
from app.services.mapping_service import map_to_canonical
from app.models.template import Template
from app.models.bordereaux import BordereauxRowCreate


class ParsingService:
    """Service for parsing bordereaux files into DataFrames."""
    
    def __init__(self):
        self.settings = get_settings()
    
    def _normalize_column_name(self, column_name: str) -> str:
        """Normalize column name: strip, lowercase, remove spaces/special chars.
        
        Args:
            column_name: Original column name
            
        Returns:
            Normalized column name
        """
        if not column_name:
            return ""
        
        # Convert to string and strip whitespace
        normalized = str(column_name).strip()
        
        # Convert to lowercase
        normalized = normalized.lower()
        
        # Replace spaces and special characters with underscores
        # Keep alphanumeric characters and underscores
        normalized = re.sub(r'[^a-z0-9_]', '_', normalized)
        
        # Remove multiple consecutive underscores
        normalized = re.sub(r'_+', '_', normalized)
        
        # Remove leading/trailing underscores
        normalized = normalized.strip('_')
        
        return normalized
    
    def _normalize_dataframe_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize all column names in a DataFrame.
        
        Handles duplicate column names after normalization by appending numbers.
        
        Args:
            df: DataFrame with original column names
            
        Returns:
            DataFrame with normalized column names
        """
        # Create mapping of old to new column names
        column_mapping = {}
        seen_normalized = {}
        
        for old_col in df.columns:
            normalized = self._normalize_column_name(old_col)
            
            # Handle duplicate normalized names
            if normalized in seen_normalized:
                seen_normalized[normalized] += 1
                normalized = f"{normalized}_{seen_normalized[normalized]}"
            else:
                seen_normalized[normalized] = 0
            
            column_mapping[old_col] = normalized
        
        # Rename columns
        df = df.rename(columns=column_mapping)
        
        return df
    
    def _parse_excel(self, file_path: Path) -> pd.DataFrame:
        """Parse Excel file (.xlsx, .xls) into DataFrame.
        
        Uses first sheet only (MVP).
        
        Args:
            file_path: Path to Excel file
            
        Returns:
            DataFrame with parsed data
        """
        try:
            # Read first sheet only
            df = pd.read_excel(
                file_path,
                sheet_name=0,  # First sheet
                engine='openpyxl' if file_path.suffix == '.xlsx' else None
            )
            
            return df
        except Exception as e:
            raise ValueError(f"Error parsing Excel file {file_path}: {str(e)}")
    
    def _parse_csv(self, file_path: Path) -> pd.DataFrame:
        """Parse CSV file into DataFrame.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            DataFrame with parsed data
        """
        try:
            # Try different encodings
            encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(
                        file_path,
                        encoding=encoding,
                        on_bad_lines='skip'  # Skip bad lines instead of failing
                    )
                    return df
                except UnicodeDecodeError:
                    continue
            
            # If all encodings fail, try with error handling
            df = pd.read_csv(
                file_path,
                encoding='utf-8',
                errors='replace',
                on_bad_lines='skip'
            )
            
            return df
        except Exception as e:
            raise ValueError(f"Error parsing CSV file {file_path}: {str(e)}")
    
    def parse_file(
        self,
        file_path: str,
        extension: Optional[str] = None
    ) -> pd.DataFrame:
        """Parse file into Pandas DataFrame with normalized column names.
        
        Args:
            file_path: Path to the file to parse
            extension: File extension (e.g., 'xlsx', 'csv'). If None, inferred from file_path
            
        Returns:
            DataFrame with parsed data and normalized column names
            
        Raises:
            ValueError: If file type is not supported or parsing fails
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Get extension if not provided
        if extension is None:
            extension = path.suffix.lstrip('.').lower()
        else:
            extension = extension.lstrip('.').lower()
        
        # Check if file type is allowed
        if extension not in self.settings.allowed_file_types:
            raise ValueError(
                f"File type '{extension}' is not allowed. "
                f"Allowed types: {', '.join(self.settings.allowed_file_types)}"
            )
        
        # Parse based on file type
        if extension in ['xlsx', 'xls']:
            df = self._parse_excel(path)
        elif extension == 'csv':
            df = self._parse_csv(path)
        else:
            raise ValueError(f"Unsupported file type: {extension}")
        
        # Normalize column names
        df = self._normalize_dataframe_columns(df)
        
        return df
    
    def get_file_info(self, file_path: str) -> dict:
        """Get basic information about a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with file information:
                - extension: File extension
                - row_count: Number of rows
                - column_count: Number of columns
                - column_names: List of column names (normalized)
        """
        df = self.parse_file(file_path)
        
        return {
            "extension": Path(file_path).suffix.lstrip('.').lower(),
            "row_count": len(df),
            "column_count": len(df.columns),
            "column_names": list(df.columns),
        }
    
    def parse_and_map(
        self,
        file_path: str,
        template: Template,
        file_id: Optional[int] = None
    ) -> List[BordereauxRowCreate]:
        """Parse file and map to canonical rows using template.
        
        Convenience method that combines parsing and mapping.
        
        Args:
            file_path: Path to the file to parse
            template: Template with column mappings
            file_id: Optional file ID to associate with rows
            
        Returns:
            List of BordereauxRowCreate objects
        """
        df = self.parse_file(file_path)
        return map_to_canonical(df, template, file_id)

