import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

from app.config import get_settings


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None
) -> None:
    """Setup structured logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                   If None, uses DEBUG if settings.debug is True, else INFO
        log_file: Optional path to log file. If None, logs only to console
    """
    settings = get_settings()
    
    # Determine log level
    if log_level is None:
        log_level = logging.DEBUG if settings.debug else logging.INFO
    else:
        log_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create formatter with structured format
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    root_logger.handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class StructuredLogger:
    """Helper class for structured logging with context."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def _format_message(self, message: str, **context) -> str:
        """Format message with context.
        
        Args:
            message: Log message
            **context: Additional context fields
            
        Returns:
            Formatted message with context
        """
        if not context:
            return message
        
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        return f"{message} | {context_str}" if context_str else message
    
    def debug(self, message: str, **context) -> None:
        """Log debug message with context."""
        self.logger.debug(self._format_message(message, **context))
    
    def info(self, message: str, **context) -> None:
        """Log info message with context."""
        self.logger.info(self._format_message(message, **context))
    
    def warning(self, message: str, **context) -> None:
        """Log warning message with context."""
        self.logger.warning(self._format_message(message, **context))
    
    def error(self, message: str, **context) -> None:
        """Log error message with context."""
        self.logger.error(self._format_message(message, **context))
    
    def exception(self, message: str, **context) -> None:
        """Log exception with context."""
        self.logger.exception(self._format_message(message, **context))
    
    def critical(self, message: str, **context) -> None:
        """Log critical message with context."""
        self.logger.critical(self._format_message(message, **context))


def get_structured_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        StructuredLogger instance
    """
    logger = get_logger(name)
    return StructuredLogger(logger)

