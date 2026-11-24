"""
SkyPoints Airline Loyalty ETL - Redemptions Module
Parses, flattens, and joins semi-structured JSON redemption feed with member profile data.
"""

from pathlib import Path
from typing import Tuple
import pandas as pd
from .ingestion import parse_json_redemptions


def process_redemptions(json_path: Path) -> pd.DataFrame:
    """Loads and flattens the JSON redemption feed into a tabular DataFrame."""
    _, redemptions_df = parse_json_redemptions(json_path)
    return redemptions_df


def join_redemptions_with_members(
    redemptions_df: pd.DataFrame,
    members_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Joins flattened redemption transactions with member profile data on Member ID.
    
    Enriches redemptions with:
    - Member Name, Tier, Country, State, Age, Active Status, Stale Member flag
    """
    if redemptions_df.empty or members_df.empty:
        return pd.DataFrame()
    
    # Standardize join key as string
    redemptions_df = redemptions_df.copy()
    members_df = members_df.copy()
    redemptions_df["member_id"] = redemptions_df["member_id"].astype(str).str.strip()
    members_df["Mem_Id"] = members_df["Mem_Id"].astype(str).str.strip()
    
    joined_df = pd.merge(
        redemptions_df,
        members_df,
        left_on="member_id",
        right_on="Mem_Id",
        how="inner"
    )
    
    # Select and order business analytical columns
    output_cols = [
        "txn_id",
        "member_id",
        "Name",
        "TIER",
        "County",
        "State",
        "Age",
        "FLAG",
        "Stale_Member",
        "txn_date",
        "partner",
        "miles_redeemed",
        "status",
        "feed_date"
    ]
    available_cols = [c for c in output_cols if c in joined_df.columns]
    return joined_df[available_cols]


def aggregate_member_redemptions(joined_df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes summary metrics per member:
    - Total miles redeemed
    - Number of transactions
    - Completed vs Pending miles
    """
    if joined_df.empty:
        return pd.DataFrame()
        
    summary = joined_df.groupby(["member_id", "Name", "TIER", "County"]).agg(
        total_txns=("txn_id", "count"),
        total_miles=("miles_redeemed", "sum"),
        completed_miles=("miles_redeemed", lambda s: s[joined_df.loc[s.index, "status"] == "COMPLETED"].sum()),
        pending_miles=("miles_redeemed", lambda s: s[joined_df.loc[s.index, "status"] == "PENDING"].sum())
    ).reset_index()
    
    return summary
