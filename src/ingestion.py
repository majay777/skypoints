

import json
from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd


def parse_pipe_delimited_file(file_path: Path) -> Tuple[List[str], pd.DataFrame]:
    """
    Parses a pipe-delimited flat file where lines begin with '|H|' or '|D|'.
    
    Handles:
    - Leading pipe '|' causing index shift
    - Separating Header record ('H') and Detail records ('D')
    - Column trimming and empty string normalization
    """
    header_cols: List[str] = []
    data_rows: List[Dict[str, str]] = []
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            
            # Split by pipe delimiter
            # Example: "|D|Elena|223457|20101012|..." -> parts[0] is empty, parts[1] is 'D'
            parts = [p.strip() for p in line.split("|")]
            
            # If leading pipe was present, drop the first empty token
            if parts and parts[0] == "":
                parts = parts[1:]
            
            if not parts:
                continue
            
            record_type = parts[0].upper()
            fields = parts[1:]
            
            if record_type == "H":
                header_cols = fields
            elif record_type == "D":
                data_rows.append({
                    "record_type": record_type,
                    "line_number": line_num,
                    "fields": fields
                })
    
    # Map detail rows to columns
    # Expected standard columns: Member_Name, Member_Id, Enrollment_Date, Last_Flight_Date,
    # Tier_Code, Agent_Name, State, Country, DOB, Is_Active
    expected_cols = [
        "raw_member_name",
        "raw_member_id",
        "raw_enrollment_date",
        "raw_last_flight_date",
        "raw_tier_code",
        "raw_agent_name",
        "raw_state",
        "raw_country",
        "raw_dob",
        "raw_is_active"
    ]
    
    records = []
    for item in data_rows:
        row_fields = item["fields"]
        row_dict = {
            "source_file_name": file_path.name,
            "file_line_num": item["line_number"],
            "raw_record_type": item["record_type"]
        }
        for i, col_name in enumerate(expected_cols):
            row_dict[col_name] = row_fields[i] if i < len(row_fields) else None
        records.append(row_dict)
    
    df = pd.DataFrame(records)
    return header_cols, df


def parse_json_redemptions(file_path: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Parses daily JSON redemption transactions.
    
    Returns:
    - raw_df: Top-level feed metadata (member_id, feed_date)
    - redemptions_df: Flattened redemption transactions (txn_id, member_id, etc.)
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    if isinstance(data, dict):
        data = [data]
        
    parent_records = []
    txn_records = []
    
    for item in data:
        member_id = str(item.get("member_id", "")).strip()
        feed_date = str(item.get("feed_date", "")).strip()
        
        parent_records.append({
            "member_id": member_id,
            "feed_date": feed_date,
            "source_file_name": file_path.name
        })
        
        for txn in item.get("redemptions", []):
            txn_records.append({
                "txn_id": str(txn.get("txn_id", "")).strip(),
                "member_id": member_id,
                "feed_date": feed_date,
                "txn_date": str(txn.get("txn_date", "")).strip(),
                "partner": str(txn.get("partner", "")).strip(),
                "miles_redeemed": int(txn.get("miles_redeemed", 0)),
                "status": str(txn.get("status", "")).strip(),
                "source_file_name": file_path.name
            })
            
    return pd.DataFrame(parent_records), pd.DataFrame(txn_records)
