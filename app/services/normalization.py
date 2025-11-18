from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Union
import pandas as pd
import numpy as np

from app.models.bordereaux import Currency


def parse_date(value: Union[str, date, datetime, pd.Timestamp, None]) -> Optional[date]:
    """Parse date value to date object.
    
    Supports multiple date formats and input types.
    
    Args:
        value: Date value (string, date, datetime, pandas Timestamp, or None)
        
    Returns:
        Parsed date or None if parsing fails or value is None/NaN
        
    Examples:
        >>> parse_date("2024-01-15")
        datetime.date(2024, 1, 15)
        >>> parse_date("15/01/2024")
        datetime.date(2024, 1, 15)
        >>> parse_date(None)
        None
    """
    if value is None:
        return None
    
    # Handle pandas NaN
    if isinstance(value, (float, int)) and (pd.isna(value) or np.isnan(value)):
        return None
    
    if pd.isna(value):
        return None
    
    # If already a date object
    if isinstance(value, date):
        return value
    
    # If datetime, extract date
    if isinstance(value, datetime):
        return value.date()
    
    # If pandas Timestamp
    if isinstance(value, pd.Timestamp):
        return value.date()
    
    # Try to parse string
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        
        # Try common date formats
        date_formats = [
            '%Y-%m-%d',      # 2024-01-15
            '%d/%m/%Y',      # 15/01/2024
            '%m/%d/%Y',      # 01/15/2024
            '%d-%m-%Y',      # 15-01-2024
            '%Y/%m/%d',      # 2024/01/15
            '%d.%m.%Y',      # 15.01.2024
            '%Y.%m.%d',      # 2024.01.15
            '%d %B %Y',      # 15 January 2024
            '%d %b %Y',      # 15 Jan 2024
            '%B %d, %Y',     # January 15, 2024
            '%b %d, %Y',     # Jan 15, 2024
            '%Y%m%d',        # 20240115
            '%d/%m/%y',      # 15/01/24
            '%m/%d/%y',      # 01/15/24
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        
        # Try pandas to_datetime as fallback
        try:
            dt = pd.to_datetime(value, errors='raise')
            return dt.date()
        except Exception:
            pass
    
    return None


def parse_decimal(value: Union[str, int, float, Decimal, None]) -> Optional[Decimal]:
    """Parse value to Decimal.
    
    Handles currency symbols, commas, and various number formats.
    
    Args:
        value: Value to parse (string, int, float, Decimal, or None)
        
    Returns:
        Parsed Decimal or None if parsing fails or value is None/NaN
        
    Examples:
        >>> parse_decimal("1,234.56")
        Decimal('1234.56')
        >>> parse_decimal("$1,234.56")
        Decimal('1234.56')
        >>> parse_decimal("1.234,56")  # European format
        Decimal('1234.56')
        >>> parse_decimal(None)
        None
    """
    if value is None:
        return None
    
    # Handle pandas NaN
    if isinstance(value, (float, int)) and (pd.isna(value) or np.isnan(value)):
        return None
    
    if pd.isna(value):
        return None
    
    # If already a Decimal
    if isinstance(value, Decimal):
        return value
    
    # If numeric type, convert directly
    if isinstance(value, (int, float)):
        if np.isnan(value):
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None
    
    # Parse string
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        
        # Remove common currency symbols
        currency_symbols = ['$', '€', '£', '¥', '₹', 'R', 'ZAR', 'USD', 'EUR', 'GBP']
        cleaned = value
        for symbol in currency_symbols:
            cleaned = cleaned.replace(symbol, '').strip()
        
        # Handle European number format (1.234,56)
        if ',' in cleaned and '.' in cleaned:
            # Determine format: if last comma before decimal, it's European
            comma_pos = cleaned.rfind(',')
            dot_pos = cleaned.rfind('.')
            if comma_pos > dot_pos:
                # European format: 1.234,56
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else:
                # US format: 1,234.56
                cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            # Could be thousands separator or decimal
            # If only one comma and it's not at the end, assume thousands
            if cleaned.count(',') == 1 and not cleaned.endswith(','):
                cleaned = cleaned.replace(',', '')
            else:
                # Multiple commas = thousands separator
                cleaned = cleaned.replace(',', '')
        
        # Remove any remaining non-numeric characters except decimal point and minus
        cleaned = ''.join(c for c in cleaned if c.isdigit() or c in '.-')
        
        if not cleaned or cleaned == '.' or cleaned == '-':
            return None
        
        try:
            return Decimal(cleaned)
        except (ValueError, TypeError):
            return None
    
    return None


def normalize_currency(value: Union[str, Currency, None]) -> Optional[Currency]:
    """Normalize currency value to Currency enum.
    
    Supports currency codes, names, and common variations.
    
    Args:
        value: Currency value (string, Currency enum, or None)
        
    Returns:
        Currency enum or None if parsing fails or value is None
        
    Examples:
        >>> normalize_currency("USD")
        <Currency.USD: 'USD'>
        >>> normalize_currency("US Dollar")
        <Currency.USD: 'USD'>
        >>> normalize_currency("eur")
        <Currency.EUR: 'EUR'>
        >>> normalize_currency(None)
        None
    """
    if value is None:
        return None
    
    # Handle pandas NaN
    if isinstance(value, (float, int)) and (pd.isna(value) or np.isnan(value)):
        return None
    
    if pd.isna(value):
        return None
    
    # If already a Currency enum
    if isinstance(value, Currency):
        return value
    
    # Parse string
    if isinstance(value, str):
        value = value.strip().upper()
        if not value:
            return None
        
        # Try direct enum match first
        try:
            return Currency(value)
        except ValueError:
            pass
        
        # Try common currency name mappings
        currency_map = {
            # USD variations
            'USD': Currency.USD,
            'US DOLLAR': Currency.USD,
            'US$': Currency.USD,
            'DOLLAR': Currency.USD,
            'DOLLARS': Currency.USD,
            '$': Currency.USD,  # Default to USD for $ symbol
            
            # EUR variations
            'EUR': Currency.EUR,
            'EURO': Currency.EUR,
            'EUROS': Currency.EUR,
            '€': Currency.EUR,
            
            # GBP variations
            'GBP': Currency.GBP,
            'POUND': Currency.GBP,
            'POUNDS': Currency.GBP,
            'POUND STERLING': Currency.GBP,
            '£': Currency.GBP,
            
            # CAD variations
            'CAD': Currency.CAD,
            'CANADIAN DOLLAR': Currency.CAD,
            'CAN$': Currency.CAD,
            
            # AUD variations
            'AUD': Currency.AUD,
            'AUSTRALIAN DOLLAR': Currency.AUD,
            'A$': Currency.AUD,
            
            # JPY variations
            'JPY': Currency.JPY,
            'YEN': Currency.JPY,
            'YENS': Currency.JPY,
            '¥': Currency.JPY,
            
            # CHF variations
            'CHF': Currency.CHF,
            'SWISS FRANC': Currency.CHF,
            'SWISS FRANCS': Currency.CHF,
            
            # ZAR variations
            'ZAR': Currency.ZAR,
            'SOUTH AFRICAN RAND': Currency.ZAR,
            'RAND': Currency.ZAR,
            'R': Currency.ZAR,
            
            # NGN variations
            'NGN': Currency.NGN,
            'NIGERIAN NAIRA': Currency.NGN,
            'NAIRA': Currency.NGN,
            
            # GHS variations
            'GHS': Currency.GHS,
            'GHANAIAN CEDI': Currency.GHS,
            'GHANA CEDI': Currency.GHS,
            'CEDI': Currency.GHS,
            
            # KES variations
            'KES': Currency.KES,
            'KENYAN SHILLING': Currency.KES,
            'SHILLING': Currency.KES,
        }
        
        # Try exact match
        if value in currency_map:
            return currency_map[value]
        
        # Try partial match (contains)
        for key, currency in currency_map.items():
            if key in value or value in key:
                return currency
        
        # Try case-insensitive match with common names
        value_lower = value.lower()
        for key, currency in currency_map.items():
            if key.lower() in value_lower or value_lower in key.lower():
                return currency
    
    return None

