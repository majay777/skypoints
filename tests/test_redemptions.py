"""
Unit tests for SkyPoints Redemptions and Validations Modules
"""

import pytest
import pandas as pd
from src.redemptions import join_redemptions_with_members, aggregate_member_redemptions
from src.validations import validate_schema_header, validate_member_records


def test_join_redemptions_with_members():
    redemptions_data = [
        {"txn_id": "TXN_1", "member_id": "223457", "miles_redeemed": 1000, "status": "COMPLETED", "txn_date": "20240110", "partner": "AeroLink", "feed_date": "20240115"},
        {"txn_id": "TXN_2", "member_id": "999999", "miles_redeemed": 500, "status": "PENDING", "txn_date": "20240111", "partner": "SkyPoints", "feed_date": "20240115"}
    ]
    members_data = [
        {"Mem_Id": "223457", "Name": "Elena", "TIER": "GLD", "County": "CAN", "State": "ON", "Age": 39, "FLAG": "A", "Stale_Member": False}
    ]
    
    red_df = pd.DataFrame(redemptions_data)
    mem_df = pd.DataFrame(members_data)
    
    joined = join_redemptions_with_members(red_df, mem_df)
    assert len(joined) == 1
    assert joined.iloc[0]["txn_id"] == "TXN_1"
    assert joined.iloc[0]["Name"] == "Elena"
    assert joined.iloc[0]["TIER"] == "GLD"


def test_validate_schema_header_detects_missing_post_code():
    header = ["Member_Name", "Member_Id", "Enrollment_Date", "Last_Flight_Date", "Tier_Code", "Agent_Name", "State", "Country", "DOB", "Is_Active"]
    valid, issues = validate_schema_header(header)
    assert any("Post Code" in issue for issue in issues)


def test_validate_member_records_quarantine_mandatory_fields():
    bad_data = [
        {"raw_member_name": "", "raw_member_id": "123", "raw_enrollment_date": "20200101", "raw_country": "USA", "raw_dob": "01011990", "raw_last_flight_date": "20200201"},
        {"raw_member_name": "Valid User", "raw_member_id": "223457", "raw_enrollment_date": "20200101", "raw_country": "USA", "raw_dob": "01011990", "raw_last_flight_date": "20200201"}
    ]
    df = pd.DataFrame(bad_data)
    result, valid_df, quarantine_df = validate_member_records(df)
    
    assert len(quarantine_df) == 1
    assert len(valid_df) == 1
    assert valid_df.iloc[0]["raw_member_name"] == "Valid User"
