#!/usr/bin/env python3
"""Script to generate sample bordereaux files and templates."""

import pandas as pd
import json
from pathlib import Path
from datetime import date, timedelta
import random

# Create directories
sample_dir = Path("sample_files")
templates_dir = Path("templates/sample_templates")
sample_dir.mkdir(exist_ok=True)
templates_dir.mkdir(exist_ok=True)

# Sample data generators
def generate_policy_number(prefix="POL"):
    return f"{prefix}{random.randint(1000, 9999)}"

def generate_insured_name():
    first_names = ["John", "Jane", "Robert", "Mary", "David", "Sarah", "Michael", "Emily"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]
    return f"{random.choice(first_names)} {random.choice(last_names)}"

def generate_date(start_date=date(2023, 1, 1), days_range=365):
    return start_date + timedelta(days=random.randint(0, days_range))

def generate_amount(min_val=100, max_val=10000):
    return round(random.uniform(min_val, max_val), 2)

def generate_currency():
    return random.choice(["USD", "EUR", "GBP", "NGN", "GHS", "KES"])

# Template definitions
templates_config = [
    {
        "template_id": "standard_claims_1",
        "name": "Standard Claims Template 1",
        "file_type": "claims",
        "columns": {
            "Policy Number": "policy_number",
            "Insured Name": "insured_name",
            "Inception Date": "inception_date",
            "Expiry Date": "expiry_date",
            "Premium Amount": "premium_amount",
            "Currency": "currency",
            "Claim Amount": "claim_amount",
        }
    },
    {
        "template_id": "standard_claims_2",
        "name": "Standard Claims Template 2",
        "file_type": "claims",
        "columns": {
            "Policy #": "policy_number",
            "Client Name": "insured_name",
            "Start Date": "inception_date",
            "End Date": "expiry_date",
            "Premium": "premium_amount",
            "Curr": "currency",
            "Claims": "claim_amount",
            "Commission": "commission_amount",
        }
    },
    {
        "template_id": "premium_bordereaux_1",
        "name": "Premium Bordereaux Template 1",
        "file_type": "premium",
        "columns": {
            "POLICY_NO": "policy_number",
            "INSURED": "insured_name",
            "INCEPTION": "inception_date",
            "EXPIRY": "expiry_date",
            "PREMIUM": "premium_amount",
            "CURRENCY_CODE": "currency",
            "NET_PREMIUM": "net_premium",
            "BROKER": "broker_name",
        }
    },
    {
        "template_id": "premium_bordereaux_2",
        "name": "Premium Bordereaux Template 2",
        "file_type": "premium",
        "columns": {
            "Policy Ref": "policy_number",
            "Insured Party": "insured_name",
            "Cover Start": "inception_date",
            "Cover End": "expiry_date",
            "Gross Premium": "premium_amount",
            "CCY": "currency",
            "Net Premium": "net_premium",
            "Broker Name": "broker_name",
            "Product": "product_type",
        }
    },
    {
        "template_id": "exposure_bordereaux_1",
        "name": "Exposure Bordereaux Template 1",
        "file_type": "exposure",
        "columns": {
            "Policy Number": "policy_number",
            "Insured": "insured_name",
            "Inception": "inception_date",
            "Expiry": "expiry_date",
            "Sum Insured": "premium_amount",
            "Currency": "currency",
            "Location": "risk_location",
            "Coverage": "coverage_type",
        }
    },
    {
        "template_id": "comprehensive_claims_1",
        "name": "Comprehensive Claims Template 1",
        "file_type": "claims",
        "columns": {
            "POL_NUM": "policy_number",
            "INSURED_NAME": "insured_name",
            "INCEPT_DATE": "inception_date",
            "EXPIRY_DATE": "expiry_date",
            "PREMIUM_AMT": "premium_amount",
            "CURR": "currency",
            "CLAIM_AMOUNT": "claim_amount",
            "COMMISSION": "commission_amount",
            "BROKER": "broker_name",
        }
    },
    {
        "template_id": "simple_premium_1",
        "name": "Simple Premium Template 1",
        "file_type": "premium",
        "columns": {
            "Policy": "policy_number",
            "Name": "insured_name",
            "Start": "inception_date",
            "End": "expiry_date",
            "Amount": "premium_amount",
            "CCY": "currency",
        }
    },
    {
        "template_id": "detailed_claims_1",
        "name": "Detailed Claims Template 1",
        "file_type": "claims",
        "columns": {
            "Policy Reference": "policy_number",
            "Insured Name": "insured_name",
            "Inception Date": "inception_date",
            "Expiry Date": "expiry_date",
            "Premium Amount": "premium_amount",
            "Currency Code": "currency",
            "Claim Amount": "claim_amount",
            "Commission Amount": "commission_amount",
            "Net Premium": "net_premium",
            "Broker": "broker_name",
            "Product Type": "product_type",
        }
    },
    {
        "template_id": "exposure_detailed_1",
        "name": "Exposure Detailed Template 1",
        "file_type": "exposure",
        "columns": {
            "Policy #": "policy_number",
            "Client": "insured_name",
            "Cover Start Date": "inception_date",
            "Cover End Date": "expiry_date",
            "Exposure Value": "premium_amount",
            "Currency": "currency",
            "Risk Location": "risk_location",
            "Coverage Type": "coverage_type",
            "Product": "product_type",
        }
    },
    {
        "template_id": "mixed_format_1",
        "name": "Mixed Format Template 1",
        "file_type": "premium",
        "columns": {
            "POLICY": "policy_number",
            "INSURED_NAME": "insured_name",
            "START_DATE": "inception_date",
            "END_DATE": "expiry_date",
            "PREMIUM": "premium_amount",
            "CUR": "currency",
            "NET": "net_premium",
            "BROKER_NAME": "broker_name",
            "PRODUCT": "product_type",
            "COVERAGE": "coverage_type",
        }
    },
]

# Generate sample files and templates
for i, template_config in enumerate(templates_config, 1):
    print(f"Generating template {i}/10: {template_config['template_id']}")
    
    # Generate sample data
    num_rows = random.randint(5, 15)
    data = {}
    
    for col_name in template_config["columns"].keys():
        canonical_field = template_config["columns"][col_name]
        
        if canonical_field == "policy_number":
            data[col_name] = [generate_policy_number() for _ in range(num_rows)]
        elif canonical_field == "insured_name":
            data[col_name] = [generate_insured_name() for _ in range(num_rows)]
        elif canonical_field == "inception_date":
            dates = [generate_date() for _ in range(num_rows)]
            data[col_name] = [d.strftime("%Y-%m-%d") for d in dates]
        elif canonical_field == "expiry_date":
            # Expiry should be after inception
            inception_dates = [generate_date() for _ in range(num_rows)]
            expiry_dates = [d + timedelta(days=random.randint(180, 730)) for d in inception_dates]
            data[col_name] = [d.strftime("%Y-%m-%d") for d in expiry_dates]
        elif canonical_field == "premium_amount":
            data[col_name] = [generate_amount() for _ in range(num_rows)]
        elif canonical_field == "currency":
            data[col_name] = [generate_currency() for _ in range(num_rows)]
        elif canonical_field == "claim_amount":
            data[col_name] = [generate_amount(0, 5000) for _ in range(num_rows)]
        elif canonical_field == "commission_amount":
            data[col_name] = [round(generate_amount(10, 500), 2) for _ in range(num_rows)]
        elif canonical_field == "net_premium":
            # Net premium is typically less than gross premium
            data[col_name] = [round(generate_amount(50, 8000), 2) for _ in range(num_rows)]
        elif canonical_field == "broker_name":
            brokers = ["ABC Insurance", "XYZ Brokers", "Global Insurance", "Premier Brokers", "Elite Insurance"]
            data[col_name] = [random.choice(brokers) for _ in range(num_rows)]
        elif canonical_field == "product_type":
            products = ["Motor", "Property", "Liability", "Health", "Life"]
            data[col_name] = [random.choice(products) for _ in range(num_rows)]
        elif canonical_field == "coverage_type":
            coverages = ["Comprehensive", "Third Party", "Full Coverage", "Basic", "Extended"]
            data[col_name] = [random.choice(coverages) for _ in range(num_rows)]
        elif canonical_field == "risk_location":
            locations = ["Lagos", "Abuja", "Kano", "Port Harcourt", "Ibadan", "Accra", "Nairobi"]
            data[col_name] = [random.choice(locations) for _ in range(num_rows)]
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Save Excel file
    excel_file = sample_dir / f"{template_config['template_id']}.xlsx"
    df.to_excel(excel_file, index=False)
    print(f"  Created: {excel_file}")
    
    # Create template JSON
    template_data = {
        "template_id": template_config["template_id"],
        "name": template_config["name"],
        "file_type": template_config["file_type"],
        "column_mappings": template_config["columns"],
        "active_flag": True,
        "version": "1.0",
        "carrier": "Sample Carrier",
        "pattern": None
    }
    
    template_file = templates_dir / f"{template_config['template_id']}.json"
    with open(template_file, 'w', encoding='utf-8') as f:
        json.dump(template_data, f, indent=2, ensure_ascii=False)
    print(f"  Created: {template_file}")

print(f"\n✅ Generated {len(templates_config)} sample files and templates!")
print(f"   Sample files: {sample_dir}")
print(f"   Templates: {templates_dir}")

