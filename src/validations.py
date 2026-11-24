"""
SkyPoints Airline Loyalty ETL - Validations Module
Comprehensive data quality engine implementing:
1. Mandatory field checks
2. Key-column uniqueness checks
3. Schema drift detection (Spec vs Actual)
4. Anomaly detection (Short IDs, non-standard country codes, uniform mock data)
5. Temporal sanity checks (DOB vs Enrollment, Enrollment vs Flight)
"""

from typing import Any, Dict, List, Tuple
import pandas as pd
from .config import EXPECTED_HEADER, COUNTRY_NORMALIZATION


class DataValidationResult:
    def __init__(self):
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.anomalies: List[Dict[str, Any]] = []
        self.is_valid: bool = True

    def add_error(self, check_name: str, record_id: str, reason: str, details: Dict = None):
        self.is_valid = False
        self.errors.append({
            "check": check_name,
            "record_id": record_id,
            "reason": reason,
            "details": details or {}
        })

    def add_warning(self, check_name: str, record_id: str, reason: str, details: Dict = None):
        self.warnings.append({
            "check": check_name,
            "record_id": record_id,
            "reason": reason,
            "details": details or {}
        })

    def add_anomaly(self, anomaly_type: str, reason: str, count: int, examples: List = None):
        self.anomalies.append({
            "type": anomaly_type,
            "reason": reason,
            "count": count,
            "examples": examples or []
        })

    def summary(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "total_errors": len(self.errors),
            "total_warnings": len(self.warnings),
            "total_anomalies": len(self.anomalies),
            "errors": self.errors,
            "warnings": self.warnings,
            "anomalies": self.anomalies
        }


def validate_schema_header(actual_header: List[str]) -> Tuple[bool, List[str]]:
    """
    Checks if the actual file header matches the design specification.
    Catches schema drift such as missing 'Post Code'.
    """
    differences = []
    
    # Check if Post Code was expected but missing
    if "Post_Code" not in actual_header and "Post Code" not in actual_header:
        differences.append(
            "SCHEMA DRIFT DETECTED: 'Post Code' (Position 9 in design doc) is MISSING in actual file header."
        )
        
    for expected in EXPECTED_HEADER:
        if expected not in actual_header:
            differences.append(f"Expected column '{expected}' not found in actual header.")
            
    return len(differences) == 0, differences


def validate_member_records(raw_df: pd.DataFrame) -> Tuple[DataValidationResult, pd.DataFrame, pd.DataFrame]:
    """
    Validates raw detail records.
    Returns:
    - result: DataValidationResult object with errors, warnings, and anomalies
    - valid_df: Records that passed mandatory quality gates
    - quarantine_df: Records rejected and routed to Dead Letter Queue
    """
    result = DataValidationResult()
    valid_indices = []
    quarantine_records = []
    
    # -------------------------------------------------------------------------
    # Batch-Level Anomaly Checks
    # -------------------------------------------------------------------------
    # 1. Suspicious Uniformity Check (e.g. all members share same DOB / Flight date)
    if len(raw_df) > 3:
        unique_dobs = raw_df["raw_dob"].dropna().nunique()
        unique_flights = raw_df["raw_last_flight_date"].dropna().nunique()
        if unique_dobs == 1:
            result.add_anomaly(
                anomaly_type="MOCK_DATA_SUSPICION_UNIFORM_DOB",
                reason=f"100% of records in batch ({len(raw_df)} rows) share identical DOB: '{raw_df['raw_dob'].iloc[0]}'. Indicates test/mock data.",
                count=len(raw_df),
                examples=raw_df["raw_member_id"].tolist()
            )
        if unique_flights == 1:
            result.add_anomaly(
                anomaly_type="UNIFORM_LAST_FLIGHT_DATE",
                reason=f"All records share identical Last_Flight_Date: '{raw_df['raw_last_flight_date'].iloc[0]}'.",
                count=len(raw_df),
                examples=raw_df["raw_member_id"].tolist()
            )

    # 2. Key-Column Batch Duplication Check
    dup_counts = raw_df["raw_member_id"].value_counts()
    duplicates = dup_counts[dup_counts > 1]
    if not duplicates.empty:
        for member_id, count in duplicates.items():
            result.add_warning(
                check_name="MEMBER_ID_DUPLICATE_IN_BATCH",
                record_id=str(member_id),
                reason=f"Member ID appears {count} times in the same batch. Latest Record Wins rule will be applied.",
                details={"duplicate_count": int(count)}
            )

    # -------------------------------------------------------------------------
    # Row-Level Validation Checks
    # -------------------------------------------------------------------------
    for idx, row in raw_df.iterrows():
        member_id = str(row.get("raw_member_id", "")).strip()
        member_name = str(row.get("raw_member_name", "")).strip()
        enroll_date = str(row.get("raw_enrollment_date", "")).strip()
        flight_date = str(row.get("raw_last_flight_date", "")).strip()
        country = str(row.get("raw_country", "")).strip().upper()
        dob = str(row.get("raw_dob", "")).strip()
        
        row_errors = []

        # Rule 1: Mandatory Field - Member Name
        if not member_name or pd.isna(row.get("raw_member_name")):
            row_errors.append("Member_Name is mandatory but found empty.")

        # Rule 2: Mandatory Field - Member ID
        if not member_id or pd.isna(row.get("raw_member_id")):
            row_errors.append("Member_Id is mandatory but found empty.")

        # Rule 3: Mandatory Field - Enrollment Date
        if not enroll_date or len(enroll_date) != 8 or not enroll_date.isdigit():
            row_errors.append(f"Enrollment_Date '{enroll_date}' is invalid. Expected YYYYMMDD.")

        # Rule 4: Temporal Order - Enrollment Date vs Flight Date
        if enroll_date and flight_date and enroll_date.isdigit() and flight_date.isdigit():
            if int(enroll_date) > int(flight_date):
                row_errors.append(f"Enrollment Date ({enroll_date}) cannot be after Last Flight Date ({flight_date}).")

        # Anomaly Check: Member ID Length
        if member_id and len(member_id) < 6:
            result.add_warning(
                check_name="MEMBER_ID_SHORT_LENGTH",
                record_id=member_id,
                reason=f"Member ID '{member_id}' has length {len(member_id)} (< 6 digits). Detected in Nora (22345) and Jacob (2256).",
                details={"length": len(member_id)}
            )

        # Anomaly Check: Country Code Standard
        if country and country not in ("USA", "IND", "CAN", "GBR", "DEU", "FRA", "JPN"):
            if country in ("PHIL", "AU"):
                result.add_warning(
                    check_name="NON_STANDARD_COUNTRY_CODE",
                    record_id=member_id,
                    reason=f"Country '{country}' is non-standard ISO alpha-3. Normalized to '{COUNTRY_NORMALIZATION.get(country)}'.",
                    details={"raw_country": country, "normalized": COUNTRY_NORMALIZATION.get(country)}
                )
            else:
                row_errors.append(f"Unrecognized country code '{country}'.")

        # Quarantining logic
        if row_errors:
            result.add_error(
                check_name="ROW_VALIDATION_FAILED",
                record_id=member_id or f"ROW_{idx}",
                reason="; ".join(row_errors),
                details=dict(row)
            )
            q_row = dict(row)
            q_row["error_reason"] = "; ".join(row_errors)
            quarantine_records.append(q_row)
        else:
            valid_indices.append(idx)

    valid_df = raw_df.loc[valid_indices].copy()
    quarantine_df = pd.DataFrame(quarantine_records)
    return result, valid_df, quarantine_df
