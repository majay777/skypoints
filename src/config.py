"""
SkyPoints Airline Loyalty ETL - Configuration and Constants
Incubyte Data Engineer Technical Assessment
"""

from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "source" / "inbound"
SAMPLE_FLAT_FILE = DATA_DIR / "sample_member_data_20240115.txt"
SAMPLE_JSON_FILE = DATA_DIR / "sample_redemption_feed_20240115.json"

# Business Constants
STALE_MEMBER_THRESHOLD_DAYS = 90

# Country Normalization Mapping (Addressing non-standard codes in source data)
COUNTRY_NORMALIZATION = {
    "USA": "USA",
    "IND": "IND",
    "CAN": "CAN",
    "PHIL": "PHL",     # Source anomaly: 4-letter code -> Standard ISO 3166-1 alpha-3
    "AU": "AUS",       # Source anomaly: 2-letter alpha-2 -> Standard ISO alpha-3
    "PHL": "PHL",
    "AUS": "AUS",
    "GBR": "GBR"
}

# Country Target Table Mapping
COUNTRY_TABLE_MAPPING = {
    "IND": "Table_India",
    "USA": "Table_USA",
    "CAN": "Table_Canada",
    "PHL": "Table_Phil",
    "PHIL": "Table_Phil",
    "AUS": "Table_Australia",
    "AU": "Table_Australia"
}

# Expected Flat File Header Schema
EXPECTED_HEADER = [
    "Member_Name",
    "Member_Id",
    "Enrollment_Date",
    "Last_Flight_Date",
    "Tier_Code",
    "Agent_Name",
    "State",
    "Country",
    "DOB",
    "Is_Active"
]
