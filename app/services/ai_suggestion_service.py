import json
from typing import List, Dict, Any, Tuple, Optional
import httpx
from app.config import get_settings
from app.core.logging import get_structured_logger


class AISuggestionService:
    """Service for AI-based column mapping suggestions using OpenRouter."""
    
    # Canonical field names and their descriptions
    CANONICAL_FIELDS = {
        'policy_number': 'Policy number or reference identifier',
        'insured_name': 'Name of the insured party or client',
        'inception_date': 'Policy start date or inception date',
        'expiry_date': 'Policy end date or expiry date',
        'premium_amount': 'Premium amount or total premium',
        'currency': 'Currency code (e.g., USD, EUR, GBP)',
        'claim_amount': 'Claim amount or loss amount',
        'commission_amount': 'Commission or brokerage amount',
        'net_premium': 'Net premium after deductions',
        'broker_name': 'Broker or intermediary name',
        'product_type': 'Insurance product type or line of business',
        'coverage_type': 'Type of coverage or class',
        'risk_location': 'Risk location or property address',
    }
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = get_structured_logger(__name__)
        self.api_key = self.settings.openrouter_api_key
        self.model = self.settings.openrouter_model
        self.base_url = "https://openrouter.ai/api/v1"
        
    def _build_prompt(self, file_headers: List[str], metadata: Optional[Dict[str, Any]] = None) -> str:
        """Build prompt for AI model.
        
        Args:
            file_headers: List of column names from the file
            metadata: Additional metadata (filename, sender, subject)
            
        Returns:
            Formatted prompt string
        """
        canonical_fields_list = "\n".join([
            f"- {field}: {description}"
            for field, description in self.CANONICAL_FIELDS.items()
        ])
        
        headers_list = "\n".join([f"- {header}" for header in file_headers])
        
        context = ""
        if metadata:
            context_parts = []
            if metadata.get("filename"):
                context_parts.append(f"Filename: {metadata['filename']}")
            if metadata.get("sender"):
                context_parts.append(f"Sender: {metadata['sender']}")
            if metadata.get("subject"):
                context_parts.append(f"Subject: {metadata['subject']}")
            if context_parts:
                context = "\n".join(context_parts) + "\n\n"
        
        prompt = f"""You are an expert at mapping insurance bordereaux file columns to standardized field names.

{context}The file has the following columns:
{headers_list}

Available canonical fields:
{canonical_fields_list}

Your task is to map each file column to the most appropriate canonical field. Consider:
1. Column name similarity and common variations
2. Context from filename, sender, or subject if provided
3. Insurance industry terminology
4. Common abbreviations and aliases

Return a JSON object with this exact structure:
{{
  "mappings": {{
    "column_name_from_file": "canonical_field_name",
    ...
  }},
  "confidence_scores": {{
    "column_name_from_file": 0.95,
    ...
  }},
  "reasoning": {{
    "column_name_from_file": "Brief explanation of why this mapping was chosen",
    ...
  }}
}}

Rules:
- Only map columns that have a clear match to a canonical field
- Confidence scores should be between 0.0 and 1.0
- If a column doesn't match any canonical field, omit it from mappings
- Be conservative with confidence scores - only use high scores (0.8+) for very clear matches
- Provide brief reasoning for each mapping

Return ONLY the JSON object, no additional text or explanation."""
        
        return prompt
    
    def suggest_mappings(
        self,
        file_headers: List[str],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> Tuple[Dict[str, str], Dict[str, float]]:
        """Get AI-based column mapping suggestions.
        
        Args:
            file_headers: List of column names from the file
            metadata: Additional metadata (filename, sender, subject)
            timeout: Request timeout in seconds
            
        Returns:
            Tuple of (column_mappings dict, confidence_scores dict)
            
        Raises:
            Exception: If API call fails
        """
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured. Set OPENROUTER_API_KEY environment variable.")
        
        prompt = self._build_prompt(file_headers, metadata)
        
        # Log with explicit flush
        self.logger.info(
            "Requesting AI suggestions",
            header_count=len(file_headers),
            model=self.model
        )
        # Force immediate write
        import logging
        root = logging.getLogger()
        for h in root.handlers:
            if hasattr(h, 'flush'):
                h.flush()
        # Also log to console directly as backup
        print(f"[AI] Requesting AI suggestions for {len(file_headers)} headers using {self.model}")
        
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/your-repo/bordereaux",  # Optional
                        "X-Title": "Bordereaux Template Mapper",  # Optional
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a helpful assistant that maps insurance bordereaux file columns to standardized field names. Always respond with valid JSON only."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.3,  # Lower temperature for more consistent results
                        "max_tokens": 2000,
                    }
                )
                
                response.raise_for_status()
                result = response.json()
                
                # Extract content from response
                content = result["choices"][0]["message"]["content"].strip()
                
                # Log raw response from LLM (at INFO level for visibility)
                self.logger.info(
                    "Raw LLM response received",
                    response_length=len(content),
                    response_preview=content[:500] if len(content) > 500 else content,
                    full_response=content  # Log full response for debugging
                )
                # Force immediate write
                import logging
                root = logging.getLogger()
                for h in root.handlers:
                    if hasattr(h, 'flush'):
                        h.flush()
                # Also log to console directly as backup
                print(f"[AI] Raw LLM response received ({len(content)} chars): {content[:200]}...")
                
                # Remove markdown code blocks if present
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
                # Parse JSON response
                ai_response = json.loads(content)
                
                # Log parsed response structure (at INFO level for visibility)
                self.logger.info(
                    "LLM response parsed",
                    has_mappings="mappings" in ai_response,
                    has_confidence_scores="confidence_scores" in ai_response,
                    has_reasoning="reasoning" in ai_response,
                    mappings_count=len(ai_response.get("mappings", {})),
                    response_keys=list(ai_response.keys()),
                    parsed_response=ai_response  # Log full parsed response
                )
                
                mappings = ai_response.get("mappings", {})
                confidence_scores = ai_response.get("confidence_scores", {})
                
                # Ensure confidence scores exist for all mappings
                for col in mappings:
                    if col not in confidence_scores:
                        confidence_scores[col] = 0.7  # Default confidence
                
                # Log full parsed response (at info level for visibility)
                self.logger.info(
                    "AI suggestions received",
                    mapped_count=len(mappings),
                    total_headers=len(file_headers),
                    mappings=mappings,
                    confidence_scores=confidence_scores,
                    reasoning=ai_response.get("reasoning", {})
                )
                # Force immediate write
                import logging
                root = logging.getLogger()
                for h in root.handlers:
                    if hasattr(h, 'flush'):
                        h.flush()
                # Also log to console directly as backup
                print(f"[AI] AI suggestions received: {len(mappings)} mappings")
                print(f"[AI] Mappings: {mappings}")
                print(f"[AI] Confidence scores: {confidence_scores}")
                
                return mappings, confidence_scores
                
        except httpx.HTTPStatusError as e:
            error_msg = f"OpenRouter API error: {e.response.status_code} - {e.response.text}"
            self.logger.error("OpenRouter API request failed", error=error_msg)
            raise Exception(error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse AI response as JSON: {str(e)}"
            self.logger.error("AI response parsing failed", error=error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Error calling OpenRouter API: {str(e)}"
            self.logger.exception("Unexpected error in AI suggestion", error=str(e))
            raise Exception(error_msg)

