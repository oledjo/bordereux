from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from app.config import get_settings
from app.routes import health, files, mappings
from app.core.logging import setup_logging, get_structured_logger
from app.core.migrations import run_migrations
from app.core.layout import wrap_with_layout

settings = get_settings()

# Setup logging
setup_logging(log_level=settings.log_level, log_file=settings.log_file)
logger = get_structured_logger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)


@app.on_event("startup")
async def startup_event():
    """Run database migrations on application startup."""
    try:
        logger.info("Application starting up...")
        run_migrations()
        logger.info("Application startup completed")
    except Exception as e:
        logger.error("Error during application startup", error=str(e), exc_info=True)
        # Don't raise - allow app to start even if migrations fail
        # This prevents the app from crashing if there's a migration issue
        # The error will be logged and can be investigated


# Include routers
app.include_router(health.router)
app.include_router(files.router)
app.include_router(mappings.router)


@app.get("/")
async def root():
    """Home page redirects to files page."""
    return RedirectResponse(url="/files", status_code=302)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )

