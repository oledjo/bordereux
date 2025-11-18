# Bordereaux API

FastAPI backend application for automated bordereaux file processing, validation, and management.

## Overview

The Bordereaux API is designed to automatically ingest, process, validate, and store bordereaux files (insurance premium/claims data) from email attachments. It supports multiple file formats (Excel, CSV), template-based mapping, validation rules, and provides a read-only API for monitoring and debugging.

## Architecture

### Core Components

1. **Email Ingestion** (`app/services/email_service.py`)
   - IMAP client for fetching emails
   - Extracts attachments from emails
   - Marks emails as read after successful processing

2. **File Storage** (`app/services/storage_service.py`)
   - Stores raw files on filesystem
   - SHA-256 hash-based de-duplication
   - Metadata tracking in database

3. **File Parsing** (`app/services/parsing_service.py`)
   - Supports Excel (.xlsx, .xls) and CSV files
   - Normalizes column names
   - Returns pandas DataFrames

4. **Template System** (`app/services/template_repository.py`)
   - Stores column mapping templates
   - Supports multiple file types (claims, premium, exposure)
   - Active/inactive template management

5. **Mapping Service** (`app/services/mapping_service.py`)
   - Maps file columns to canonical schema using templates
   - Normalizes data (dates, currencies, decimals)
   - Creates canonical row objects

6. **Mapping Suggestions** (`app/services/mapping_suggestion_service.py`)
   - Generates mapping suggestions for unknown file formats
   - **AI-powered suggestions** using OpenRouter (OpenAI models)
   - Falls back to heuristic matching (fuzzy matching and keyword-based)
   - Creates proposal JSON files for review

7. **Validation Service** (`app/services/validation_service.py`)
   - Rules-based validation engine
   - Configurable rules via `rules.json`
   - Validates required fields, date order, numeric ranges
   - Generates detailed error reports

8. **Processing Service** (`app/services/processing_service.py`)
   - Orchestrates validation and persistence
   - Saves valid rows to database
   - Stores validation errors
   - Updates file statistics and status

9. **Pipeline Service** (`app/services/pipeline_service.py`)
   - End-to-end file processing workflow
   - Template matching
   - Error handling and status updates

10. **Jobs** (`app/jobs/`)
    - `poll_mailbox.py` - Polls email inbox for new attachments
    - `process_new_files.py` - Processes all unprocessed files

### Data Flow

```
Email → Attachment → Storage → Parsing → Template Matching
                                              ↓
                                    Template Found?
                                    /           \
                                  Yes            No
                                  /               \
                          Mapping → Validation → Persist    Generate Suggestion
```

### Database Schema

- **bordereaux_files** - File metadata and status
- **bordereaux_rows** - Processed canonical rows
- **bordereaux_templates** - Column mapping templates
- **bordereaux_validation_errors** - Validation error records

## Setup

### Prerequisites

- Python 3.11+
- Poetry
- SQLite (default) or PostgreSQL

### Installation

1. Clone the repository and install dependencies:
```bash
poetry install
```

2. Create a `.env` file from `.env.example`:
```bash
cp .env.example .env
```

3. Configure environment variables (see Configuration section)

4. Run database migrations:
```bash
poetry run alembic upgrade head
```

5. Run the application:
```bash
poetry run python main.py
```

Or using uvicorn directly:
```bash
poetry run uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

## Configuration

### Environment Variables

Create a `.env` file with the following variables:

```bash
# Database
DATABASE_URL=sqlite:///./bordereaux.db

# IMAP Settings
IMAP_HOST=imap.example.com
IMAP_PORT=993
IMAP_USERNAME=your-email@example.com
IMAP_PASSWORD=your-password
# OR use OAuth token
# IMAP_OAUTH_TOKEN=your-oauth-token

# Storage
STORAGE_BASE_PATH=./storage

# Polling
POLLING_INTERVAL=300  # seconds (default: 5 minutes)

# Logging
LOG_LEVEL=INFO
# LOG_FILE=logs/bordereaux.log  # Optional

# OpenRouter/AI Settings (for automatic template suggestions)
# Get your API key from https://openrouter.ai/
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_MODEL=openai/gpt-3.5-turbo  # Default: free OpenAI model
USE_AI_SUGGESTIONS=True  # Set to False to disable AI and use heuristic matching only

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=False
```

### IMAP Configuration

#### Gmail Setup

1. Enable 2-Step Verification
2. Generate an App Password:
   - Go to Google Account → Security → 2-Step Verification → App passwords
   - Generate password for "Mail"
   - Use this password in `IMAP_PASSWORD`

3. Configure `.env`:
```bash
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USERNAME=your-email@gmail.com
IMAP_PASSWORD=your-app-password
```

#### Outlook/Office 365 Setup

1. Enable IMAP in account settings
2. Use your regular password or generate an app password
3. Configure `.env`:
```bash
IMAP_HOST=outlook.office365.com
IMAP_PORT=993
IMAP_USERNAME=your-email@outlook.com
IMAP_PASSWORD=your-password
```

#### OAuth Authentication

For OAuth-based authentication (recommended for production):
```bash
IMAP_OAUTH_TOKEN=your-oauth-token
```

### AI-Powered Template Suggestions

The application can use AI (via OpenRouter) to automatically suggest column mappings for unknown file formats. This provides more accurate suggestions than heuristic matching alone.

#### Setup

1. Get an OpenRouter API key:
   - Sign up at https://openrouter.ai/
   - Navigate to Keys section
   - Create a new API key

2. Configure in `.env`:
```bash
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_MODEL=openai/gpt-3.5-turbo  # Free OpenAI model (default)
USE_AI_SUGGESTIONS=True  # Enable AI suggestions
```

3. The system will automatically:
   - Use AI suggestions when a file doesn't match any template
   - Fall back to heuristic matching if AI is unavailable or fails
   - Generate mapping proposals with confidence scores

**Note**: If `OPENROUTER_API_KEY` is not set, the system will automatically use heuristic matching only.

## Database Migrations

### Running Migrations

Apply all pending migrations:
```bash
poetry run alembic upgrade head
```

Rollback one migration:
```bash
poetry run alembic downgrade -1
```

View current migration status:
```bash
poetry run alembic current
```

View migration history:
```bash
poetry run alembic history
```

### Creating New Migrations

After modifying models, create a new migration:
```bash
poetry run alembic revision --autogenerate -m "description of changes"
```

Review the generated migration file in `alembic/versions/`, then apply:
```bash
poetry run alembic upgrade head
```

## Running Jobs

### Mailbox Polling Job

Poll the email inbox for new attachments:

```bash
poetry run python -c "from app.jobs.poll_mailbox import run_poll_mailbox_job; run_poll_mailbox_job()"
```

Or create a script `scripts/poll_mailbox.py`:
```python
from app.jobs.poll_mailbox import run_poll_mailbox_job

if __name__ == "__main__":
    result = run_poll_mailbox_job()
    print(f"Processed: {result['processed_count']}")
    print(f"Duplicates: {result['duplicate_count']}")
    print(f"Failed: {result['failed_count']}")
```

### Process New Files Job

Process all files with status `RECEIVED`:

```bash
poetry run python -c "from app.jobs.process_new_files import run_process_new_files_job; run_process_new_files_job()"
```

Or create a script `scripts/process_files.py`:
```python
from app.jobs.process_new_files import run_process_new_files_job

if __name__ == "__main__":
    result = run_process_new_files_job()
    print(f"Processed: {result['processed_count']}")
    print(f"Successful: {result['success_count']}")
    print(f"Failed: {result['failed_count']}")
    print(f"New template required: {result['new_template_count']}")
```

### Scheduling Jobs

#### Using Cron (Linux/Mac)

Add to crontab (`crontab -e`):
```bash
# Poll mailbox every 5 minutes
*/5 * * * * cd /path/to/bordereaux && poetry run python -c "from app.jobs.poll_mailbox import run_poll_mailbox_job; run_poll_mailbox_job()"

# Process new files every 10 minutes
*/10 * * * * cd /path/to/bordereaux && poetry run python -c "from app.jobs.process_new_files import run_process_new_files_job; run_process_new_files_job()"
```

#### Using Windows Task Scheduler

1. Create batch files:
   - `scripts/poll_mailbox.bat`:
     ```batch
     @echo off
     cd /d C:\path\to\bordereaux
     poetry run python -c "from app.jobs.poll_mailbox import run_poll_mailbox_job; run_poll_mailbox_job()"
     ```
   - `scripts/process_files.bat`:
     ```batch
     @echo off
     cd /d C:\path\to\bordereaux
     poetry run python -c "from app.jobs.process_new_files import run_process_new_files_job; run_process_new_files_job()"
     ```

2. Schedule tasks in Task Scheduler to run these batch files periodically

#### Using Celery (Advanced)

For production environments, consider using Celery for distributed task processing.

## API Endpoints

### Health Check
- `GET /health` - Health check endpoint

### Files (Read-only)
- `GET /files` - List files with status, sender, created_at
  - Query params: `status`, `skip`, `limit`
- `GET /files/{id}` - Get file details with summary stats
- `GET /files/{id}/errors` - Get validation errors for a file
  - Query params: `skip`, `limit`

### API Documentation

Interactive API documentation available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Validation Rules

Validation rules are configured in `rules.json`. Default rules include:

- **Required Fields**: `policy_number` must be present
- **Date Rules**: `inception_date <= expiry_date`
- **Numeric Rules**: Amounts must be non-negative

Example `rules.json`:
```json
{
  "required_fields": ["policy_number"],
  "date_rules": [
    {
      "name": "inception_before_expiry",
      "inception_field": "inception_date",
      "expiry_field": "expiry_date",
      "message": "Inception date must be before or equal to expiry date"
    }
  ],
  "numeric_rules": [
    {
      "name": "premium_non_negative",
      "field": "premium_amount",
      "min_value": 0,
      "message": "Premium amount must be greater than or equal to 0"
    }
  ]
}
```

## Templates

Templates define column mappings for different file formats. Templates are stored in the database and can be created via the API or directly in the database.

Example template structure:
```json
{
  "template_id": "example_claims_template",
  "name": "Example Claims Template",
  "file_type": "claims",
  "column_mappings": {
    "Policy Number": "policy_number",
    "Insured Name": "insured_name",
    "Inception Date": "inception_date",
    "Expiry Date": "expiry_date",
    "Premium Amount": "premium_amount",
    "Currency": "currency"
  },
  "active_flag": true
}
```

## Testing

Run all tests:
```bash
poetry run pytest
```

Run specific test file:
```bash
poetry run pytest app/tests/test_parsing.py
```

Run with coverage:
```bash
poetry run pytest --cov=app --cov-report=html
```

### Test Coverage

Tests cover:
- File parsing (Excel, CSV)
- Template matching
- Column mapping
- Data validation
- Pipeline processing

## Development

### Code Formatting

Format code with Black:
```bash
poetry run black .
```

### Linting

Lint code with Ruff:
```bash
poetry run ruff check .
```

Auto-fix issues:
```bash
poetry run ruff check --fix .
```

### Project Structure

```
.
├── alembic/              # Database migrations
│   └── versions/         # Migration files
├── app/
│   ├── core/             # Core functionality
│   │   ├── database.py   # Database setup
│   │   └── logging.py    # Logging configuration
│   ├── jobs/              # Background jobs
│   │   ├── poll_mailbox.py
│   │   └── process_new_files.py
│   ├── models/            # SQLAlchemy models
│   │   ├── bordereaux.py
│   │   ├── template.py
│   │   └── validation.py
│   ├── routes/             # API routes
│   │   ├── files.py
│   │   └── health.py
│   ├── services/           # Business logic
│   │   ├── email_service.py
│   │   ├── parsing_service.py
│   │   ├── mapping_service.py
│   │   ├── validation_service.py
│   │   ├── processing_service.py
│   │   └── pipeline_service.py
│   └── tests/              # Test files
├── storage/                # Stored files
├── templates/              # Template examples
├── validation_reports/     # Validation error reports
├── main.py                 # Application entry point
├── rules.json              # Validation rules
└── pyproject.toml          # Poetry configuration
```

## Logging

Structured logging is configured with context fields (file_id, template_id, etc.).

Log levels:
- `DEBUG` - Detailed debugging information
- `INFO` - General informational messages
- `WARNING` - Warning messages
- `ERROR` - Error messages
- `CRITICAL` - Critical errors

Logs are written to console by default. To enable file logging, set `LOG_FILE` in `.env`.

## Troubleshooting

### Database Issues

If migrations fail:
1. Check database connection string in `.env`
2. Ensure database file/directory is writable
3. Try recreating database: `rm bordereaux.db && alembic upgrade head`

### IMAP Connection Issues

1. Verify IMAP credentials
2. Check firewall/network settings
3. For Gmail, ensure "Less secure app access" is enabled or use App Password
4. Check IMAP is enabled in email account settings

### File Processing Issues

1. Check file format is supported (Excel, CSV)
2. Verify template exists and is active
3. Check validation rules in `rules.json`
4. Review logs for detailed error messages

## License

[Your License Here]
