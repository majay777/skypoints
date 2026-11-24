"""
Unit tests for SkyPoints Transformations Module
"""

import pytest
from datetime import date
import pandas as pd
from src.transformations import (
    parse_dob,
    calculate_age,
    is_stale_member,
    transform_to_staging,
    deduplicate_latest_record_wins,
    split_members_by_country
)


def test_parse_dob_leading_zero_strip():
    # '03051985' -> 3051985 as an int, plus valid date object
    dob_int, dob_date = parse_dob("03051985")
    assert dob_int == 3051985
    assert dob_date is not None
    assert dob_date.year == 1985


def test_calculate_age():
    # Person born March 5, 1985
    dob = date(1985, 3, 5)
    # Before birthday in 2024
    ref_before = date(2024, 2, 1)
    assert calculate_age(dob, ref_before) == 38
    # After birthday in 2024
    ref_after = date(2024, 4, 1)
    assert calculate_age(dob, ref_after) == 39


def test_stale_member_flag():
    # Flight within 90 days
    ref = date(2024, 4, 15)
    recent_flight = date(2024, 3, 1)  # ~45 days ago
    assert is_stale_member(recent_flight, reference_date=ref) is False
    
    # Flight older than 90 days
    old_flight = date(2012, 10, 13)
    assert is_stale_member(old_flight, reference_date=ref) is True
    
    # Null flight date
    assert is_stale_member(None, reference_date=ref) is True


def test_latest_record_wins_deduplication():
    # Elena with two records: older in USA, newer in CAN
    data = [
        {
            "Name": "Elena", "Mem_Id": "223457", "Enroll_Dt": "20101012",
            "Flight_Dt": "20121013", "Country_Code": "USA", "County": "USA",
            "flight_dt_obj": date(2012, 10, 13), "enroll_dt_obj": date(2010, 10, 12)
        },
        {
            "Name": "Elena", "Mem_Id": "223457", "Enroll_Dt": "20101012",
            "Flight_Dt": "20240115", "Country_Code": "CAN", "County": "CAN",
            "flight_dt_obj": date(2024, 1, 15), "enroll_dt_obj": date(2010, 10, 12)
        }
    ]
    df = pd.DataFrame(data)
    deduped = deduplicate_latest_record_wins(df)
    
    assert len(deduped) == 1
    winner = deduped.iloc[0]
    assert winner["Mem_Id"] == "223457"
    assert winner["Country_Code"] == "CAN"
    assert winner["Flight_Dt"] == "20240115"


def test_split_members_by_country():
    data = [
        {"Name": "Ravi", "Mem_Id": "223458", "Country_Code": "IND", "County": "IND"},
        {"Name": "Mateo", "Mem_Id": "223459", "Country_Code": "PHL", "County": "PHIL"},
        {"Name": "Jacob", "Mem_Id": "2256", "Country_Code": "AUS", "County": "AU"}
    ]
    df = pd.DataFrame(data)
    tables = split_members_by_country(df)
    
    assert "Table_India" in tables
    assert len(tables["Table_India"]) == 1
    assert tables["Table_India"].iloc[0]["Name"] == "Ravi"
    
    assert "Table_Phil" in tables
    assert len(tables["Table_Phil"]) == 1
    assert tables["Table_Phil"].iloc[0]["Name"] == "Mateo"
    
    assert "Table_Australia" in tables
    assert len(tables["Table_Australia"]) == 1
    assert tables["Table_Australia"].iloc[0]["Name"] == "Jacob"
