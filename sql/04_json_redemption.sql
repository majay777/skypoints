COPY INTO raw_redemptions_landing (raw_payload, source_file_name)
FROM (
    SELECT $1, METADATA$FILENAME
    FROM @stg_skypoints_landing/redemptions/ (FILE_FORMAT => 'ff_json_feed')
);


-- ----------------------------------------------------------------------------
-- 2. PARSE & FLATTEN JSON INTO QUERYABLE FACT TABLE
-- Uses LATERAL FLATTEN on the nested 'redemptions' array
-- ----------------------------------------------------------------------------
INSERT INTO stg_member_redemptions (
    txn_id,
    member_id,
    feed_date,
    txn_date,
    partner,
    miles_redeemed,
    status,
    source_file_name
)
SELECT 
    TRIM(r.value:txn_id::VARCHAR)             AS txn_id,
    TRIM(raw_payload:member_id::VARCHAR)       AS member_id,
    TRY_TO_DATE(raw_payload:feed_date::VARCHAR, 'YYYYMMDD') AS feed_date,
    TRY_TO_DATE(r.value:txn_date::VARCHAR, 'YYYYMMDD')     AS txn_date,
    TRIM(r.value:partner::VARCHAR)            AS partner,
    r.value:miles_redeemed::INTEGER           AS miles_redeemed,
    TRIM(r.value:status::VARCHAR)             AS status,
    source_file_name
FROM raw_redemptions_landing,
LATERAL FLATTEN(input => raw_payload:redemptions) r
WHERE r.value:txn_id IS NOT NULL;


-- ----------------------------------------------------------------------------
-- 3. JOINING BACK TO MEMBER PROFILE DATA
-- Business Use Cases:
-- - Analyze redemption activity by member tier, country, and active status
-- - Identify high-value members vs inactive/stale members redeeming points
-- - Cross-border partner loyalty analysis
-- ----------------------------------------------------------------------------

-- Enriched Analytical View: Redemptions with Member Profile Context
CREATE OR REPLACE VIEW vw_member_redemption_analysis AS
SELECT 
    -- Transaction Details
    r.txn_id,
    r.txn_date,
    r.partner,
    r.miles_redeemed,
    r.status                AS txn_status,
    r.feed_date,
    
    -- Member Profile Context (from Gold Layer)
    m.Mem_Id,
    m.Name                  AS member_name,
    m.TIER                  AS tier_code,
    m.Agent_Name,
    m.State                 AS member_state,
    m.County                AS member_country_name,
    m.Country_Code          AS member_country_code,
    m.Age                   AS member_age,
    m.Stale_Member          AS is_stale_member,
    m.FLAG                  AS member_active_flag
FROM stg_member_redemptions r
INNER JOIN dim_member_master m
    ON r.member_id = m.Mem_Id;
