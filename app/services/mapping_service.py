import json
from datetime import date, datetime
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np
from decimal import Decimal

from app.models.bordereaux import BordereauxRowCreate, Currency
from app.models.template import Template
from app.services.normalization import parse_date, parse_decimal, normalize_currency


class MappingService:
    """Service for mapping DataFrames to canonical bordereaux rows."""
    
    def __init__(self):
        pass
    
    
    def _parse_string(self, value: Any) -> Optional[str]:
        """Parse value to string.
        
        Args:
            value: Value to parse
            
        Returns:
            String or None if value is empty/NaN
        """
        if value is None or pd.isna(value):
            return None
        
        if isinstance(value, str):
            value = value.strip()
            return value if value else None
        
        return str(value).strip() if str(value).strip() else None
    
    def _normalize_column_name(self, column_name: str) -> str:
        """Normalize column name to match parsing service normalization.
        
        Args:
            column_name: Original column name
            
        Returns:
            Normalized column name
        """
        import re
        if not column_name:
            return ""
        
        normalized = str(column_name).strip().lower()
        normalized = re.sub(r'[^a-z0-9_]', '_', normalized)
        normalized = re.sub(r'_+', '_', normalized)
        normalized = normalized.strip('_')
        
        return normalized
    
    def _find_matching_column(self, df: pd.DataFrame, source_column: str) -> Optional[str]:
        """Find matching column in DataFrame using normalized names.
        
        Args:
            df: DataFrame with normalized column names
            source_column: Source column name from template mapping
            
        Returns:
            Matching column name from DataFrame or None
        """
        normalized_source = self._normalize_column_name(source_column)
        
        # First try exact match
        if normalized_source in df.columns:
            return normalized_source
        
        # Try case-insensitive match
        for col in df.columns:
            if col.lower() == normalized_source.lower():
                return col
        
        # Try partial match (contains)
        for col in df.columns:
            if normalized_source in col or col in normalized_source:
                return col
        
        return None
    
    def map_to_canonical(
        self,
        df: pd.DataFrame,
        template: Template,
        file_id: Optional[int] = None
    ) -> List[BordereauxRowCreate]:
        """Map DataFrame rows to canonical BordereauxRow objects using template mappings.
        
        Args:
            df: DataFrame with parsed bordereaux data
            template: Template with column mappings
            file_id: Optional file ID to associate with rows
            
        Returns:
            List of BordereauxRowCreate objects
        """
        canonical_rows = []
        
        # Get column mappings from template
        column_mappings = template.column_mappings if isinstance(template.column_mappings, dict) else {}
        
        # Build reverse mapping: canonical_field -> DataFrame column
        # Handle multiple source columns mapping to same canonical field
        canonical_to_df_columns: Dict[str, List[str]] = {}
        
        for source_column, canonical_field in column_mappings.items():
            df_column = self._find_matching_column(df, source_column)
            if df_column:
                if canonical_field not in canonical_to_df_columns:
                    canonical_to_df_columns[canonical_field] = []
                canonical_to_df_columns[canonical_field].append(df_column)
        
        # Process each row in DataFrame
        for idx, row in df.iterrows():
            row_data = {}
            
            # Map each canonical field
            canonical_fields = {
                'policy_number': self._parse_string,
                'insured_name': self._parse_string,
                'inception_date': lambda v: parse_date(v),
                'expiry_date': lambda v: parse_date(v),
                'premium_amount': lambda v: float(parse_decimal(v)) if parse_decimal(v) is not None else None,
                'currency': lambda v: normalize_currency(v),
                'claim_amount': lambda v: float(parse_decimal(v)) if parse_decimal(v) is not None else None,
                'commission_amount': lambda v: float(parse_decimal(v)) if parse_decimal(v) is not None else None,
                'net_premium': lambda v: float(parse_decimal(v)) if parse_decimal(v) is not None else None,
                'broker_name': self._parse_string,
                'product_type': self._parse_string,
                'coverage_type': self._parse_string,
                'risk_location': self._parse_string,
            }
            
            for canonical_field, parser_func in canonical_fields.items():
                value = None
                
                # Check if we have a mapping for this field
                if canonical_field in canonical_to_df_columns:
                    # Try each mapped column (take first non-null value)
                    for df_column in canonical_to_df_columns[canonical_field]:
                        col_value = row.get(df_column)
                        if col_value is not None and not pd.isna(col_value):
                            value = parser_func(col_value)
                            if value is not None:
                                break
                
                row_data[canonical_field] = value
            
            # Create raw_data JSON from original row
            raw_data_dict = row.to_dict()
            # Convert non-serializable types
            for key, val in raw_data_dict.items():
                if pd.isna(val):
                    raw_data_dict[key] = None
                elif isinstance(val, (pd.Timestamp, datetime)):
                    raw_data_dict[key] = val.isoformat()
                elif isinstance(val, date):
                    raw_data_dict[key] = val.isoformat()
                elif isinstance(val, (np.integer, np.floating)):
                    raw_data_dict[key] = float(val)
            
            raw_data = json.dumps(raw_data_dict, default=str)
            
            # Create BordereauxRowCreate object
            canonical_row = BordereauxRowCreate(
                file_id=file_id or 0,  # Default to 0 if not provided
                row_number=int(idx) + 1 if isinstance(idx, (int, np.integer)) else None,
                raw_data=raw_data,
                **row_data
            )
            
            canonical_rows.append(canonical_row)
        
        return canonical_rows


def map_to_canonical(
    df: pd.DataFrame,
    template: Template,
    file_id: Optional[int] = None
) -> List[BordereauxRowCreate]:
    """Convenience function to map DataFrame to canonical rows.
    
    Args:
        df: DataFrame with parsed bordereaux data
        template: Template with column mappings
        file_id: Optional file ID to associate with rows
        
    Returns:
        List of BordereauxRowCreate objects
    """
    service = MappingService()
    return service.map_to_canonical(df, template, file_id)

