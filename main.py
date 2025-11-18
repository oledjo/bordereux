from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from app.config import get_settings
from app.routes import health, files, mappings
from app.core.logging import setup_logging, get_structured_logger
from app.core.migrations import run_migrations

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


@app.get("/", response_class=HTMLResponse)
async def root():
    """Home page with navigation links."""
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Bordereaux API - Home</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }}
            .container {{
                background: white;
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                padding: 60px 40px;
                max-width: 800px;
                width: 100%;
                text-align: center;
            }}
            h1 {{
                color: #333;
                font-size: 42px;
                margin-bottom: 10px;
                font-weight: 700;
            }}
            .subtitle {{
                color: #666;
                font-size: 18px;
                margin-bottom: 40px;
            }}
            .version {{
                color: #999;
                font-size: 14px;
                margin-bottom: 50px;
            }}
            .nav-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 30px;
                margin-top: 40px;
            }}
            .nav-card {{
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                border-radius: 12px;
                padding: 40px 30px;
                text-decoration: none;
                color: #333;
                transition: all 0.3s ease;
                border: 2px solid transparent;
            }}
            .nav-card:hover {{
                transform: translateY(-5px);
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
                border-color: #667eea;
            }}
            .nav-card-icon {{
                font-size: 64px;
                margin-bottom: 20px;
            }}
            .nav-card-title {{
                font-size: 24px;
                font-weight: 600;
                margin-bottom: 10px;
                color: #333;
            }}
            .nav-card-description {{
                font-size: 14px;
                color: #666;
                line-height: 1.6;
            }}
            .nav-card.files {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }}
            .nav-card.files .nav-card-title,
            .nav-card.files .nav-card-description {{
                color: white;
            }}
            .nav-card.templates {{
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                color: white;
            }}
            .nav-card.templates .nav-card-title,
            .nav-card.templates .nav-card-description {{
                color: white;
            }}
            .nav-card.upload {{
                background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                color: white;
            }}
            .nav-card.upload .nav-card-title,
            .nav-card.upload .nav-card-description {{
                color: white;
            }}
            .footer {{
                margin-top: 50px;
                padding-top: 30px;
                border-top: 1px solid #eee;
                color: #999;
                font-size: 14px;
            }}
            .footer-links {{
                margin-top: 15px;
            }}
            .footer-links a {{
                color: #667eea;
                text-decoration: none;
                margin: 0 10px;
            }}
            .footer-links a:hover {{
                text-decoration: underline;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Bordereaux API</h1>
            <p class="subtitle">Automated bordereaux file processing and management</p>
            <p class="version">Version {settings.app_version}</p>
            
            <div class="nav-grid">
                <a href="/files" class="nav-card files">
                    <div class="nav-card-icon">📄</div>
                    <div class="nav-card-title">Files</div>
                    <div class="nav-card-description">
                        View and manage bordereaux files. Upload new files, check processing status, and review validation errors.
                    </div>
                </a>
                
                <a href="/mappings" class="nav-card templates">
                    <div class="nav-card-icon">📋</div>
                    <div class="nav-card-title">Templates</div>
                    <div class="nav-card-description">
                        Manage column mapping templates. Create, edit, and delete templates for automatic file processing.
                    </div>
                </a>
                
                <a href="/files/upload" class="nav-card upload">
                    <div class="nav-card-icon">⬆️</div>
                    <div class="nav-card-title">Upload File</div>
                    <div class="nav-card-description">
                        Upload a new bordereaux file (Excel or CSV) for processing and validation.
                    </div>
                </a>
            </div>
            
            <div class="footer">
                <p>Bordereaux Processing System</p>
                <div class="footer-links">
                    <a href="/docs">API Docs</a>
                    <a href="/health">Health Check</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )

