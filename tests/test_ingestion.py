"""
Unit tests for SkyPoints Ingestion Module
"""

import pytest
from pathlib import Path
from src.config import SAMPLE_FLAT_FILE, SAMPLE_JSON_FILE
from src.ingestion import parse_pipe_delimited_file, parse_json_redemptions


def test_parse_pipe_delimited_file_header_and_rows():
    header_cols, df = parse_pipe_delimited_file(SAMPLE_FLAT_FILE)
    
    assert len(header_cols) == 10
    assert header_cols[0] == "Member_Name"
    assert header_cols[1] == "Member_Id"
    assert header_cols[-1] == "Is_Active"
    
    # 5 base sample rows + 1 Elena country move test row
    assert len(df) == 6
    assert "Elena" in df["raw_member_name"].values
    assert "Ravi" in df["raw_member_name"].values
    assert "Mateo" in df["raw_member_name"].values
    assert "Nora" in df["raw_member_name"].values
    assert "Jacob" in df["raw_member_name"].values


def test_parse_json_redemptions():
    parent_df, redemptions_df = parse_json_redemptions(SAMPLE_JSON_FILE)
    
    assert len(parent_df) == 2
    assert len(redemptions_df) == 3
    
    expected_txns = {"RX10091", "RX10092", "RX10093"}
    actual_txns = set(redemptions_df["txn_id"].tolist())
    assert actual_txns == expected_txns
    
    # Check data types
    assert redemptions_df["miles_redeemed"].dtype == "int64"
    assert (redemptions_df["miles_redeemed"] > 0).all()
