"""Database migration utilities."""
from pathlib import Path
from alembic import command
from alembic.config import Config
from app.config import get_settings
from app.core.logging import get_structured_logger

logger = get_structured_logger(__name__)


def run_migrations():
    """Run database migrations to the latest version."""
    try:
        settings = get_settings()
        
        # For SQLite, ensure the database directory exists
        if "sqlite" in settings.database_url.lower():
            # Extract database path from URL
            # Handle formats: sqlite:///./data/bordereaux.db, sqlite:///data/bordereaux.db, sqlite:///bordereaux.db
            db_path = settings.database_url.replace("sqlite:///", "").replace("sqlite://", "")
            # Remove query parameters if any
            if "?" in db_path:
                db_path = db_path.split("?")[0]
            
            # Handle relative paths (./data/bordereaux.db -> data/bordereaux.db)
            if db_path.startswith("./"):
                db_path = db_path[2:]
            
            db_file = Path(db_path)
            # Create parent directory if it doesn't exist and path has a parent
            if db_file.parent and str(db_file.parent) != "." and not db_file.parent.exists():
                db_file.parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created database directory: {db_file.parent}")
        
        # Create Alembic config
        alembic_cfg = Config("alembic.ini")
        
        # Set database URL from settings
        alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
        
        logger.info("Running database migrations...")
        
        # Run migrations
        command.upgrade(alembic_cfg, "head")
        
        logger.info("Database migrations completed successfully")
        return True
    except Exception as e:
        logger.error("Error running database migrations", error=str(e), exc_info=True)
        raise

