"""
SkyPoints Airline Loyalty ETL - Transformations Module
Implements:
1. Intermediate Staging enrichment:
   - DOB leading zero removal (03051985 -> 3051985)
   - Country normalization
   - Derived Age computation
   - Derived Stale_Member computation (> 90 days since Flight_Date)
2. Deduplication with "Latest Record Wins" (member moving countries)
3. Country target routing
"""

from datetime import datetime, date
from typing import Dict, Optional, Tuple
import pandas as pd
from .config import COUNTRY_NORMALIZATION, COUNTRY_TABLE_MAPPING, STALE_MEMBER_THRESHOLD_DAYS


def parse_date_safe(val: Optional[str], date_format: str = "%Y%m%d") -> Optional[date]:
    """Safely parses date strings into datetime.date objects."""
    if not val or pd.isna(val) or str(val).strip() in ("", "NULL", "null"):
        return None
    val_clean = str(val).strip()
    try:
        return datetime.strptime(val_clean, date_format).date()
    except ValueError:
        return None


def parse_dob(dob_str: Optional[str]) -> Tuple[Optional[int], Optional[date]]:
    """
    Parses DOB string (e.g. '03051985').
    Returns:
    - dob_int: 3051985 (leading zero stripped as shown in intermediate specification)
    - dob_date: date object for exact Age calculation
    """
    if not dob_str or pd.isna(dob_str) or str(dob_str).strip() == "":
        return None, None
    
    clean_str = str(dob_str).strip()
    
    # Numeric conversion drops leading zero: '03051985' -> 3051985
    dob_int = int(clean_str) if clean_str.isdigit() else None
    
    # Pad back to 8 digits to test calendar formats MMDDYYYY or DDMMYYYY
    padded = clean_str.zfill(8)
    dob_date = None
    for fmt in ("%m%d%Y", "%d%m%Y"):
        try:
            dob_date = datetime.strptime(padded, fmt).date()
            break
        except ValueError:
            continue
            
    return dob_int, dob_date


def calculate_age(dob_date: Optional[date], reference_date: Optional[date] = None) -> Optional[int]:
    """
    Calculates exact age in completed years.
    """
    if dob_date is None:
        return None
    
    ref = reference_date or date.today()
    # Check if birthday has occurred this year
    has_had_birthday = (ref.month, ref.day) >= (dob_date.month, dob_date.day)
    return (ref.year - dob_date.year) - (0 if has_had_birthday else 1)


def is_stale_member(flight_date: Optional[date], reference_date: Optional[date] = None, threshold_days: int = STALE_MEMBER_THRESHOLD_DAYS) -> bool:
    """
    Returns True if days since flight_date > threshold_days (90 days)
    or if member has never flown (flight_date is None).
    """
    if flight_date is None:
        return True
    ref = reference_date or date.today()
    days_since_flight = (ref - flight_date).days
    return days_since_flight > threshold_days


def transform_to_staging(raw_df: pd.DataFrame, reference_date: Optional[date] = None) -> pd.DataFrame:
    """
    Transforms raw landing flat file DataFrame into intermediate staging DataFrame.
    Matches exact columns: Name, Mem_Id, Enroll_Dt, Flight_Dt, TIER, Agent_Name, State, County, DOB, FLAG
    Plus derived columns: Age, Stale_Member.
    """
    ref_dt = reference_date or date.today()
    staged_records = []
    
    for _, row in raw_df.iterrows():
        # Dates
        enroll_dt = parse_date_safe(row.get("raw_enrollment_date"))
        flight_dt = parse_date_safe(row.get("raw_last_flight_date"))
        
        # DOB and Age
        dob_int, dob_date = parse_dob(row.get("raw_dob"))
        age = calculate_age(dob_date, reference_date=ref_dt)
        
        # Stale Member Flag
        stale = is_stale_member(flight_dt, reference_date=ref_dt)
        
        # Country Normalization
        raw_country = str(row.get("raw_country", "")).strip().upper()
        country_code = COUNTRY_NORMALIZATION.get(raw_country, raw_country)
        
        staged_records.append({
            "Name": str(row.get("raw_member_name", "")).strip(),
            "Mem_Id": str(row.get("raw_member_id", "")).strip(),
            "Enroll_Dt": enroll_dt.strftime("%Y%m%d") if enroll_dt else None,
            "Flight_Dt": flight_dt.strftime("%Y%m%d") if flight_dt else None,
            "TIER": str(row.get("raw_tier_code", "")).strip() or None,
            "Agent_Name": str(row.get("raw_agent_name", "")).strip() or None,
            "State": str(row.get("raw_state", "")).strip() or None,
            "County": str(row.get("raw_country", "")).strip(),  # Retain original County as requested
            "Country_Code": country_code,
            "DOB": dob_int,
            "DOB_Date": dob_date,
            "FLAG": str(row.get("raw_is_active", "")).strip() or None,
            "Age": age,
            "Stale_Member": stale,
            "source_file_name": row.get("source_file_name"),
            "flight_dt_obj": flight_dt,
            "enroll_dt_obj": enroll_dt
        })
        
    return pd.DataFrame(staged_records)


def deduplicate_latest_record_wins(staged_df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies the 'Latest Record Wins' rule.
    When a member appears multiple times (e.g. moved countries),
    we select the latest record ordered by:
    1. Flight_Dt (most recent flight activity)
    2. Enroll_Dt (enrollment recency)
    """
    if staged_df.empty:
        return staged_df
    
    # Sort so that the latest record is first
    sorted_df = staged_df.sort_values(
        by=["Mem_Id", "flight_dt_obj", "enroll_dt_obj"],
        ascending=[True, False, False]
    )
    
    # Drop duplicates keeping the first (latest)
    deduped_df = sorted_df.drop_duplicates(subset=["Mem_Id"], keep="first").copy()
    
    # Clean up internal helper sort columns
    deduped_df.drop(columns=["flight_dt_obj", "enroll_dt_obj"], inplace=True, errors="ignore")
    return deduped_df


def split_members_by_country(deduped_df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Splits the deduplicated member DataFrame into country-specific target DataFrames.
    Maps to tables like Table_India, Table_USA, Table_Canada, Table_Phil, Table_Australia.
    """
    country_tables: Dict[str, pd.DataFrame] = {}
    
    for country_code, group in deduped_df.groupby("Country_Code"):
        table_name = COUNTRY_TABLE_MAPPING.get(country_code, f"Table_{country_code}")
        # Clean export columns matching intermediate specification
        export_cols = [
            "Name", "Mem_Id", "Enroll_Dt", "Flight_Dt", "TIER",
            "Agent_Name", "State", "County", "DOB", "FLAG", "Age", "Stale_Member"
        ]
        available_cols = [c for c in export_cols if c in group.columns]
        country_tables[table_name] = group[available_cols].reset_index(drop=True)
        
    return country_tables
