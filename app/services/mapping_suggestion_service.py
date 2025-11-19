import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from difflib import SequenceMatcher
from sqlalchemy.orm import Session

from app.models.bordereaux import BordereauxFile, FileStatus
from app.config import get_settings
from app.core.logging import get_structured_logger


class MappingSuggestionService:
    """Service for suggesting column mappings using fuzzy matching and heuristics."""
    
    # Canonical field names
    CANONICAL_FIELDS = [
        'policy_number',
        'insured_name',
        'inception_date',
        'expiry_date',
        'premium_amount',
        'currency',
        'claim_amount',
        'commission_amount',
        'net_premium',
        'broker_name',
        'product_type',
        'coverage_type',
        'risk_location',
    ]
    
    # Keyword heuristics for each canonical field
    FIELD_KEYWORDS = {
        'policy_number': ['policy', 'pol', 'policy_no', 'policy#', 'policy number', 'pol_no', 'pol#'],
        'insured_name': ['insured', 'client', 'customer', 'name', 'insured_name', 'client_name'],
        'inception_date': ['inception', 'start', 'start_date', 'effective', 'effective_date', 'incept', 'commence'],
        'expiry_date': ['expiry', 'expire', 'end', 'end_date', 'expiration', 'exp_date'],
        'premium_amount': ['premium', 'prem', 'premium_amount', 'premium_amt', 'premium_total', 'total_premium'],
        'currency': ['currency', 'curr', 'ccy', 'currency_code', 'curr_code'],
        'claim_amount': ['claim', 'claim_amount', 'claim_amt', 'claim_total', 'loss', 'loss_amount', 'paid'],
        'commission_amount': ['commission', 'comm', 'commission_amount', 'comm_amt', 'brokerage'],
        'net_premium': ['net', 'net_premium', 'net_prem', 'net_amount'],
        'broker_name': ['broker', 'broker_name', 'brokerage', 'intermediary', 'agent'],
        'product_type': ['product', 'product_type', 'product_name', 'line', 'line_of_business'],
        'coverage_type': ['coverage', 'cover', 'coverage_type', 'type', 'class'],
        'risk_location': ['location', 'loc', 'risk_location', 'address', 'premises', 'property'],
    }
    
    def __init__(self, proposals_dir: str = "templates/proposals"):
        self.proposals_dir = Path(proposals_dir)
        self.proposals_dir.mkdir(parents=True, exist_ok=True)
        self.settings = get_settings()
        self.logger = get_structured_logger(__name__)
        
        # Initialize AI service if configured
        self.ai_service = None
        if self.settings.use_ai_suggestions and self.settings.openrouter_api_key:
            try:
                from app.services.ai_suggestion_service import AISuggestionService
                self.ai_service = AISuggestionService()
                self.logger.info("AI suggestion service initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize AI service: {str(e)}, falling back to heuristic matching")
    
    def _normalize_string(self, s: str) -> str:
        """Normalize string for comparison.
        
        Args:
            s: String to normalize
            
        Returns:
            Normalized string
        """
        if not s:
            return ""
        # Lowercase, remove special chars, keep alphanumeric and spaces
        normalized = re.sub(r'[^a-z0-9\s]', '', s.lower())
        # Remove extra spaces
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def _fuzzy_match_score(self, str1: str, str2: str) -> float:
        """Calculate fuzzy match score between two strings.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Score between 0.0 and 1.0
        """
        if not str1 or not str2:
            return 0.0
        
        # Normalize strings
        norm1 = self._normalize_string(str1)
        norm2 = self._normalize_string(str2)
        
        if not norm1 or not norm2:
            return 0.0
        
        # Exact match
        if norm1 == norm2:
            return 1.0
        
        # Check if one contains the other
        if norm1 in norm2 or norm2 in norm1:
            return 0.9
        
        # Use SequenceMatcher for similarity
        similarity = SequenceMatcher(None, norm1, norm2).ratio()
        
        return similarity
    
    def _keyword_match_score(self, column_name: str, canonical_field: str) -> float:
        """Calculate keyword-based match score.
        
        Args:
            column_name: Column name from file
            canonical_field: Canonical field name
            
        Returns:
            Score between 0.0 and 1.0
        """
        if canonical_field not in self.FIELD_KEYWORDS:
            return 0.0
        
        normalized_col = self._normalize_string(column_name)
        if not normalized_col:
            return 0.0
        
        keywords = self.FIELD_KEYWORDS[canonical_field]
        best_score = 0.0
        
        for keyword in keywords:
            normalized_keyword = self._normalize_string(keyword)
            
            # Exact keyword match
            if normalized_keyword == normalized_col:
                return 1.0
            
            # Keyword contained in column name
            if normalized_keyword in normalized_col:
                score = len(normalized_keyword) / len(normalized_col)
                best_score = max(best_score, min(score, 0.9))
            
            # Column name contained in keyword (less likely but possible)
            if normalized_col in normalized_keyword:
                score = len(normalized_col) / len(normalized_keyword)
                best_score = max(best_score, min(score, 0.8))
            
            # Fuzzy match
            fuzzy_score = self._fuzzy_match_score(normalized_keyword, normalized_col)
            best_score = max(best_score, fuzzy_score * 0.7)
        
        return best_score
    
    def _calculate_confidence(
        self,
        column_name: str,
        canonical_field: str
    ) -> float:
        """Calculate overall confidence score for a mapping.
        
        Args:
            column_name: Column name from file
            canonical_field: Canonical field name
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Combine fuzzy match and keyword match
        fuzzy_score = self._fuzzy_match_score(column_name, canonical_field)
        keyword_score = self._keyword_match_score(column_name, canonical_field)
        
        # Weighted combination (keyword match is more reliable)
        confidence = (fuzzy_score * 0.3) + (keyword_score * 0.7)
        
        return min(confidence, 1.0)
    
    def suggest_mappings(
        self,
        file_headers: List[str],
        min_confidence: float = 0.3,
        metadata: Optional[Dict[str, Any]] = None,
        use_ai: Optional[bool] = None
    ) -> Tuple[Dict[str, str], Dict[str, float]]:
        """Suggest column mappings for file headers.
        
        Uses AI suggestions if available and enabled, otherwise falls back to heuristic matching.
        
        Args:
            file_headers: List of column names from the file
            min_confidence: Minimum confidence score to include (default: 0.3)
            metadata: Additional metadata (filename, sender, subject) for AI context
            use_ai: Force AI usage (True) or heuristic (False). If None, uses settings.
            
        Returns:
            Tuple of (column_mappings dict, confidence_scores dict)
        """
        # Determine if we should use AI
        should_use_ai = use_ai if use_ai is not None else (
            self.settings.use_ai_suggestions and self.ai_service is not None
        )
        
        # Try AI first if enabled
        if should_use_ai and self.ai_service:
            try:
                self.logger.info("Using AI for mapping suggestions", header_count=len(file_headers))
                # Force flush
                import logging
                for h in logging.getLogger().handlers:
                    if hasattr(h, 'flush'):
                        h.flush()
                print(f"[MAPPING] Using AI for mapping suggestions, headers: {len(file_headers)}")
                ai_mappings, ai_scores = self.ai_service.suggest_mappings(file_headers, metadata)
                
                # Filter by minimum confidence
                filtered_mappings = {}
                filtered_scores = {}
                for col, canonical_field in ai_mappings.items():
                    confidence = ai_scores.get(col, 0.0)
                    if confidence >= min_confidence:
                        filtered_mappings[col] = canonical_field
                        filtered_scores[col] = confidence
                
                self.logger.info(
                    "AI suggestions completed",
                    mapped_count=len(filtered_mappings),
                    total_headers=len(file_headers)
                )
                
                return filtered_mappings, filtered_scores
                
            except Exception as e:
                self.logger.warning(
                    f"AI suggestion failed, falling back to heuristic: {str(e)}",
                    error=str(e)
                )
                # Fall through to heuristic matching
        
        # Fallback to heuristic matching
        self.logger.info("Using heuristic matching for suggestions", header_count=len(file_headers))
        column_mappings = {}
        confidence_scores = {}
        
        # Track which canonical fields have been mapped
        mapped_fields = set()
        
        # For each file header, find best matching canonical field
        for header in file_headers:
            best_match = None
            best_score = 0.0
            
            for canonical_field in self.CANONICAL_FIELDS:
                # Skip if already mapped
                if canonical_field in mapped_fields:
                    continue
                
                confidence = self._calculate_confidence(header, canonical_field)
                
                if confidence > best_score and confidence >= min_confidence:
                    best_score = confidence
                    best_match = canonical_field
            
            if best_match:
                column_mappings[header] = best_match
                confidence_scores[header] = best_score
                mapped_fields.add(best_match)
        
        return column_mappings, confidence_scores
    
    def save_proposal(
        self,
        file_id: int,
        column_mappings: Dict[str, str],
        confidence_scores: Dict[str, float],
        file_headers: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Save mapping proposal to JSON file.
        
        Args:
            file_id: Bordereaux file ID
            column_mappings: Suggested column mappings
            confidence_scores: Confidence scores per column
            file_headers: Original file headers
            metadata: Additional metadata (optional)
            
        Returns:
            Path to saved proposal file
        """
        proposal_data = {
            "file_id": file_id,
            "created_at": datetime.utcnow().isoformat(),
            "file_headers": file_headers,
            "column_mappings": column_mappings,
            "confidence_scores": confidence_scores,
            "metadata": metadata or {},
        }
        
        # Generate filename
        filename = f"proposal_{file_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        proposal_path = self.proposals_dir / filename
        
        # Save to JSON
        with open(proposal_path, 'w', encoding='utf-8') as f:
            json.dump(proposal_data, f, indent=2, ensure_ascii=False)
        
        return proposal_path
    
    def process_file(
        self,
        db: Session,
        file_id: int,
        file_headers: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process file and create mapping proposal.
        
        Args:
            db: Database session
            file_id: Bordereaux file ID
            file_headers: List of column names from the file
            metadata: Additional metadata (optional)
            
        Returns:
            Dictionary with proposal information
        """
        # Suggest mappings (will use AI if available and enabled)
        column_mappings, confidence_scores = self.suggest_mappings(
            file_headers,
            metadata=metadata
        )
        
        # Save proposal
        proposal_path = self.save_proposal(
            file_id=file_id,
            column_mappings=column_mappings,
            confidence_scores=confidence_scores,
            file_headers=file_headers,
            metadata=metadata
        )
        
        # Update file status and proposal path
        bordereaux_file = db.query(BordereauxFile).filter(
            BordereauxFile.id == file_id
        ).first()
        
        if bordereaux_file:
            bordereaux_file.status = FileStatus.NEW_TEMPLATE_REQUIRED
            bordereaux_file.proposal_path = str(proposal_path)
            db.commit()
        
        return {
            "file_id": file_id,
            "proposal_path": str(proposal_path),
            "column_mappings": column_mappings,
            "confidence_scores": confidence_scores,
            "mapped_count": len(column_mappings),
            "total_headers": len(file_headers),
        }


def suggest_mappings(
    file_headers: List[str],
    min_confidence: float = 0.3
) -> Tuple[Dict[str, str], Dict[str, float]]:
    """Convenience function to suggest mappings.
    
    Args:
        file_headers: List of column names from the file
        min_confidence: Minimum confidence score to include
        
    Returns:
        Tuple of (column_mappings dict, confidence_scores dict)
    """
    service = MappingSuggestionService()
    return service.suggest_mappings(file_headers, min_confidence)

