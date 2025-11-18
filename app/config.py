from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from functools import lru_cache
from typing import List, Optional
import logging


class Settings(BaseSettings):
    """Application settings."""
    
    # App settings
    app_name: str = "Bordereaux API"
    app_version: str = "0.1.0"
    debug: bool = False
    
    # Database settings
    database_url: str = "sqlite:///./bordereaux.db"
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    
    # IMAP settings
    imap_host: Optional[str] = Field(None, description="IMAP server hostname")
    imap_port: int = Field(993, description="IMAP server port (default: 993 for SSL)")
    imap_username: Optional[str] = Field(None, description="IMAP username/email")
    imap_password: Optional[str] = Field(None, description="IMAP password (if using password auth)")
    imap_oauth_token: Optional[str] = Field(None, description="OAuth token (if using OAuth auth)")
    
    # Storage settings
    storage_base_path: str = Field("./storage", description="Base path for file storage")
    
    # Polling settings
    polling_interval: int = Field(300, description="Polling interval in seconds (default: 300 = 5 minutes)")
    
    # File type settings
    allowed_file_types: List[str] = Field(
        default=["xlsx", "xls", "csv"],
        description="List of allowed file extensions (without dot)"
    )
    
    # Logging settings
    log_level: str = Field("INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    log_file: Optional[str] = Field(None, description="Path to log file (optional)")
    
    # OpenRouter/AI settings
    openrouter_api_key: Optional[str] = Field(None, description="OpenRouter API key for AI suggestions")
    openrouter_model: str = Field("openai/gpt-3.5-turbo", description="OpenRouter model to use (default: free OpenAI model)")
    use_ai_suggestions: bool = Field(True, description="Use AI for template suggestions (requires OpenRouter API key)")
    
    @field_validator("allowed_file_types", mode="before")
    @classmethod
    def parse_file_types(cls, v):
        """Parse comma-separated string from environment variable."""
        if isinstance(v, str):
            return [item.strip().lower() for item in v.split(",") if item.strip()]
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    def validate_auth(self) -> None:
        """Validate that either password or OAuth token is provided."""
        if not self.imap_password and not self.imap_oauth_token:
            raise ValueError("Either IMAP_PASSWORD or IMAP_OAUTH_TOKEN must be provided")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

