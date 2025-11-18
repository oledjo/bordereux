import pytest
import pandas as pd
import tempfile
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, date

from app.core.database import Base, get_db
from app.models.bordereaux import BordereauxFile, FileStatus
from app.models.template import Template, FileType
from app.config import get_settings


@pytest.fixture(scope="session")
def test_db():
    """Create a test database."""
    settings = get_settings()
    # Use in-memory SQLite for tests
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    yield TestingSessionLocal
    
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_db):
    """Create a database session for testing."""
    session = test_db()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def sample_excel_file():
    """Create a sample Excel file for testing."""
    data = {
        "Policy Number": ["POL001", "POL002", "POL003"],
        "Insured Name": ["John Doe", "Jane Smith", "Bob Johnson"],
        "Inception Date": ["2024-01-01", "2024-02-01", "2024-03-01"],
        "Expiry Date": ["2025-01-01", "2025-02-01", "2025-03-01"],
        "Premium Amount": [1000.50, 2000.75, 3000.00],
        "Currency": ["USD", "USD", "USD"],
        "Claim Amount": [500.00, 0, 1000.00],
        "Commission Amount": [100.00, 200.00, 300.00],
    }
    
    df = pd.DataFrame(data)
    
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        file_path = f.name
        df.to_excel(file_path, index=False)
    
    yield file_path
    
    # Cleanup
    if os.path.exists(file_path):
        os.unlink(file_path)


@pytest.fixture
def sample_csv_file():
    """Create a sample CSV file for testing."""
    data = {
        "Policy Number": ["POL001", "POL002", "POL003"],
        "Insured Name": ["John Doe", "Jane Smith", "Bob Johnson"],
        "Inception Date": ["2024-01-01", "2024-02-01", "2024-03-01"],
        "Expiry Date": ["2025-01-01", "2025-02-01", "2025-03-01"],
        "Premium Amount": [1000.50, 2000.75, 3000.00],
        "Currency": ["USD", "USD", "USD"],
    }
    
    df = pd.DataFrame(data)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix=".csv", delete=False) as f:
        file_path = f.name
        df.to_csv(file_path, index=False)
    
    yield file_path
    
    # Cleanup
    if os.path.exists(file_path):
        os.unlink(file_path)


@pytest.fixture
def sample_template(db_session):
    """Create a sample template for testing."""
    template = Template(
        template_id="test_template",
        name="Test Template",
        file_type=FileType.CLAIMS.value,
        column_mappings={
            "Policy Number": "policy_number",
            "Insured Name": "insured_name",
            "Inception Date": "inception_date",
            "Expiry Date": "expiry_date",
            "Premium Amount": "premium_amount",
            "Currency": "currency",
            "Claim Amount": "claim_amount",
            "Commission Amount": "commission_amount",
        },
        active_flag=True,
    )
    
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    
    return template


@pytest.fixture
def sample_bordereaux_file(db_session):
    """Create a sample bordereaux file record for testing."""
    bordereaux_file = BordereauxFile(
        filename="test_file.xlsx",
        file_path="/tmp/test_file.xlsx",
        file_size=1024,
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        status=FileStatus.RECEIVED,
        sender="test@example.com",
        subject="Test Bordereaux",
        total_rows=3,
        processed_rows=0,
    )
    
    db_session.add(bordereaux_file)
    db_session.commit()
    db_session.refresh(bordereaux_file)
    
    return bordereaux_file

