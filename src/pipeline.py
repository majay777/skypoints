"""
SkyPoints Airline Loyalty ETL - Pipeline Orchestrator
Ties together ingestion, validation, staging, deduplication, country splitting,
and JSON redemptions joining.
"""

from datetime import date
from pathlib import Path
from typing import Dict, Any
import duckdb
import pandas as pd

from .config import SAMPLE_FLAT_FILE, SAMPLE_JSON_FILE
from .ingestion import parse_pipe_delimited_file, parse_json_redemptions
from .transformations import (
    transform_to_staging,
    deduplicate_latest_record_wins,
    split_members_by_country
)
from .validations import validate_schema_header, validate_member_records, DataValidationResult
from .redemptions import process_redemptions, join_redemptions_with_members, aggregate_member_redemptions


class SkyPointsPipeline:
    def __init__(self, flat_file_path: Path = SAMPLE_FLAT_FILE, json_file_path: Path = SAMPLE_JSON_FILE, reference_date: date = None):
        self.flat_file_path = flat_file_path
        self.json_file_path = json_file_path
        self.reference_date = reference_date or date.today()
        self.db = duckdb.connect(database=":memory:")
        
        # State
        self.header_cols = []
        self.raw_members_df = pd.DataFrame()
        self.raw_redemptions_parent_df = pd.DataFrame()
        self.raw_redemptions_txns_df = pd.DataFrame()
        
        self.validation_result = DataValidationResult()
        self.schema_valid = False
        self.schema_issues = []
        self.quarantine_df = pd.DataFrame()
        
        self.staged_df = pd.DataFrame()
        self.deduped_df = pd.DataFrame()
        self.country_tables: Dict[str, pd.DataFrame] = {}
        self.joined_redemptions_df = pd.DataFrame()
        self.member_redemption_summary_df = pd.DataFrame()

    def run(self) -> Dict[str, Any]:
        """Executes the complete pipeline end-to-end."""
        # 1. Ingestion
        self.header_cols, self.raw_members_df = parse_pipe_delimited_file(self.flat_file_path)
        self.raw_redemptions_parent_df, self.raw_redemptions_txns_df = parse_json_redemptions(self.json_file_path)
        
        # 2. Schema Drift & Data Validation
        self.schema_valid, self.schema_issues = validate_schema_header(self.header_cols)
        self.validation_result, valid_raw_df, self.quarantine_df = validate_member_records(self.raw_members_df)
        
        # 3. Intermediate Staging Enrichment (Age, Stale_Member, DOB leading-zero truncation)
        self.staged_df = transform_to_staging(valid_raw_df, reference_date=self.reference_date)
        
        # 4. Deduplication: Latest Record Wins
        self.deduped_df = deduplicate_latest_record_wins(self.staged_df)
        
        # 5. Split by Country into Target Tables
        self.country_tables = split_members_by_country(self.deduped_df)
        
        # 6. JSON Redemptions Processing & Member Profile Join
        self.joined_redemptions_df = join_redemptions_with_members(
            self.raw_redemptions_txns_df,
            self.deduped_df
        )
        self.member_redemption_summary_df = aggregate_member_redemptions(self.joined_redemptions_df)
        
        # 7. Register tables into in-memory DuckDB SQL engine for ad-hoc querying
        self._register_sql_tables()
        
        return {
            "status": "SUCCESS",
            "schema_valid": self.schema_valid,
            "schema_issues": self.schema_issues,
            "validation_summary": self.validation_result.summary(),
            "raw_count": len(self.raw_members_df),
            "staged_count": len(self.staged_df),
            "deduped_count": len(self.deduped_df),
            "quarantine_count": len(self.quarantine_df),
            "country_tables": {k: len(v) for k, v in self.country_tables.items()},
            "redemptions_count": len(self.raw_redemptions_txns_df),
            "joined_redemptions_count": len(self.joined_redemptions_df)
        }

    def _register_sql_tables(self):
        """Registers pandas DataFrames as SQL tables in DuckDB for querying."""
        self.db.register("raw_members", self.raw_members_df)
        self.db.register("stg_member_profile", self.staged_df)
        self.db.register("dim_member_master", self.deduped_df)
        self.db.register("fct_member_redemptions", self.raw_redemptions_txns_df)
        self.db.register("analytics_member_redemptions", self.joined_redemptions_df)
        
        for table_name, df in self.country_tables.items():
            self.db.register(table_name, df)

    def query(self, sql: str) -> pd.DataFrame:
        """Executes a SQL query against the in-memory engine and returns a DataFrame."""
        return self.db.execute(sql).df()
