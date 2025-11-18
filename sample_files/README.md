# Sample Bordereaux Files

This directory contains sample bordereaux files for testing and development.

## Generated Files

10 sample Excel files with different column structures and formats:

1. **standard_claims_1.xlsx** - Standard claims format with common column names
2. **standard_claims_2.xlsx** - Alternative claims format with abbreviated columns
3. **premium_bordereaux_1.xlsx** - Premium bordereaux with uppercase columns
4. **premium_bordereaux_2.xlsx** - Premium bordereaux with descriptive column names
5. **exposure_bordereaux_1.xlsx** - Exposure bordereaux with location and coverage
6. **comprehensive_claims_1.xlsx** - Comprehensive claims with all fields
7. **simple_premium_1.xlsx** - Minimal premium bordereaux
8. **detailed_claims_1.xlsx** - Detailed claims with all optional fields
9. **exposure_detailed_1.xlsx** - Detailed exposure with product and coverage
10. **mixed_format_1.xlsx** - Mixed format with various field combinations

## Corresponding Templates

Each sample file has a corresponding template in `templates/sample_templates/`:

- `standard_claims_1.json`
- `standard_claims_2.json`
- `premium_bordereaux_1.json`
- `premium_bordereaux_2.json`
- `exposure_bordereaux_1.json`
- `comprehensive_claims_1.json`
- `simple_premium_1.json`
- `detailed_claims_1.json`
- `exposure_detailed_1.json`
- `mixed_format_1.json`

## File Types

- **Claims** (4 files): Files focused on claims data
- **Premium** (4 files): Files focused on premium data
- **Exposure** (2 files): Files focused on exposure data

## Usage

These files can be used for:
- Testing the upload functionality
- Testing template matching
- Testing validation rules
- Development and debugging

## Regenerating Files

To regenerate the sample files:

```bash
poetry run python scripts/generate_sample_files.py
```

This will create new files with different random data each time.

