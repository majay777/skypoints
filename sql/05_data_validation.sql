
-- ----------------------------------------------------------------------------
-- 1. DEAD LETTER QUEUE / QUARANTINE TABLE
-- Billions of records cannot afford a hard pipeline crash due to 0.01% malformed rows.
-- Malformed rows are routed here for data ops alerting and manual remediation.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS err_member_quarantine (
    raw_record_type     VARCHAR(5),
    raw_member_name     VARCHAR(255),
    raw_member_id       VARCHAR(50),
    raw_enrollment_date VARCHAR(20),
    raw_last_flight_date VARCHAR(20),
    raw_tier_code       VARCHAR(10),
    raw_agent_name      VARCHAR(255),
    raw_state           VARCHAR(50),
    raw_country         VARCHAR(50),
    raw_dob             VARCHAR(20),
    raw_is_active       VARCHAR(5),
    source_file_name    VARCHAR(255),
    error_code          VARCHAR(50),
    error_reason        VARCHAR(500),
    quarantine_ts       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
)
COMMENT = 'Dead-letter quarantine table for rejected rows failing data validations';


-- ----------------------------------------------------------------------------
-- 2. DATA QUALITY VALIDATION SUITE (Pre-Staging Gatekeeper)
-- Evaluates every incoming row against data contract rules.
-- ----------------------------------------------------------------------------
INSERT INTO err_member_quarantine (
    raw_record_type, raw_member_name, raw_member_id, raw_enrollment_date,
    raw_last_flight_date, raw_tier_code, raw_agent_name, raw_state,
    raw_country, raw_dob, raw_is_active, source_file_name,
    error_code, error_reason
)
SELECT 
    raw_record_type, raw_member_name, raw_member_id, raw_enrollment_date,
    raw_last_flight_date, raw_tier_code, raw_agent_name, raw_state,
    raw_country, raw_dob, raw_is_active, source_file_name,
    validation.error_code,
    validation.error_reason
FROM raw_member_landing r,
LATERAL (
    SELECT 'MANDATORY_NAME_NULL', 'Member_Name is mandatory but found NULL or empty'
    WHERE r.raw_member_name IS NULL OR TRIM(r.raw_member_name) = ''
    
    UNION ALL
    
    SELECT 'MANDATORY_ID_NULL', 'Member_Id is mandatory but found NULL or empty'
    WHERE r.raw_member_id IS NULL OR TRIM(r.raw_member_id) = ''
    
    UNION ALL
    
    SELECT 'MANDATORY_ENROLL_NULL', 'Enrollment_Date is mandatory but found NULL or invalid'
    WHERE TRY_TO_DATE(r.raw_enrollment_date, 'YYYYMMDD') IS NULL
    
    UNION ALL
    
    SELECT 'INVALID_FLIGHT_DATE', 'Last_Flight_Date is non-null but has invalid date format'
    WHERE r.raw_last_flight_date IS NOT NULL 
      AND TRIM(r.raw_last_flight_date) != '' 
      AND TRY_TO_DATE(r.raw_last_flight_date, 'YYYYMMDD') IS NULL
      
    UNION ALL
    
    SELECT 'TEMPORAL_ORDER_VIOLATION', 'Enrollment_Date is after Last_Flight_Date'
    WHERE TRY_TO_DATE(r.raw_enrollment_date, 'YYYYMMDD') > TRY_TO_DATE(r.raw_last_flight_date, 'YYYYMMDD')
    
    UNION ALL
    
    SELECT 'INVALID_DOB_FORMAT', 'DOB cannot be parsed as a valid calendar date'
    WHERE TRY_TO_DATE(LPAD(r.raw_dob, 8, '0'), 'MMDDYYYY') IS NULL
      AND TRY_TO_DATE(LPAD(r.raw_dob, 8, '0'), 'DDMMYYYY') IS NULL
      
    UNION ALL
    
    SELECT 'AGE_SANITY_VIOLATION', 'Member age is negative or exceeds 120 years'
    WHERE FLOOR(DATEDIFF('month', COALESCE(TRY_TO_DATE(LPAD(r.raw_dob, 8, '0'), 'MMDDYYYY'), TRY_TO_DATE(LPAD(r.raw_dob, 8, '0'), 'DDMMYYYY')), CURRENT_DATE()) / 12) NOT BETWEEN 0 AND 120
    
    UNION ALL
    
    SELECT 'INVALID_COUNTRY_CODE', 'Country code length or format is invalid'
    WHERE r.raw_country IS NULL OR LENGTH(TRIM(r.raw_country)) < 2 OR LENGTH(TRIM(r.raw_country)) > 4
    
    UNION ALL
    
    SELECT 'ID_LENGTH_ANOMALY', 'Member_Id length is shorter than standard 6-digit schema (e.g. Nora: 22345, Jacob: 2256)'
    WHERE LENGTH(TRIM(r.raw_member_id)) < 6
) AS validation(error_code, error_reason)
WHERE r.raw_record_type = 'D';


-- ----------------------------------------------------------------------------
-- 3. SPECIFIC DATA ANOMALY CHECKS
-- ----------------------------------------------------------------------------

-- Check 1: Key-Column Duplicate Detection in Staging
-- Detects if multiple records exist for the same member_id in the current batch
SELECT 
    raw_member_id,
    COUNT(*) AS record_count,
    COUNT(DISTINCT raw_country) AS country_count,
    ARRAY_AGG(raw_country) AS countries_seen
FROM raw_member_landing
WHERE raw_record_type = 'D'
GROUP BY raw_member_id
HAVING COUNT(*) > 1;

-- Check 2: Schema Drift Detection (Spec mentions Post Code at Pos 9, but file omitted it)
-- Verifies that header line matches expected layout:
SELECT 
    source_file_name,
    raw_member_name AS header_col1,
    raw_member_id   AS header_col2,
    CASE 
        WHEN raw_member_name = 'Member_Name' AND raw_member_id = 'Member_Id' THEN 'HEADER_VALID'
        ELSE 'SCHEMA_DRIFT_ALERT: Unexpected header format or column shift'
    END AS schema_audit_status
FROM raw_member_landing
WHERE raw_record_type = 'H';

-- Check 3: Non-Standard Country Code Detection
-- Highlights values like 'PHIL' (non-standard 4-letter) and 'AU' (alpha-2 instead of alpha-3)
SELECT DISTINCT 
    raw_country,
    LENGTH(raw_country) AS code_len,
    CASE 
        WHEN raw_country IN ('USA', 'IND', 'CAN', 'GBR', 'DEU', 'FRA', 'JPN') THEN 'STANDARD_ISO3'
        WHEN raw_country = 'PHIL' THEN 'ANOMALY_MAP_TO_PHL'
        WHEN raw_country = 'AU'   THEN 'ANOMALY_MAP_TO_AUS'
        ELSE 'UNRECOGNIZED_COUNTRY_NEEDS_MAPPING'
    END AS country_standardization_status
FROM raw_member_landing
WHERE raw_record_type = 'D';

-- Check 4: Suspicious Uniformity / Mock Data Detection
-- When 100% of rows have identical DOB, Enrollment Date, or Flight Date
SELECT 
    COUNT(DISTINCT raw_enrollment_date) AS unique_enroll_dates,
    COUNT(DISTINCT raw_last_flight_date) AS unique_flight_dates,
    COUNT(DISTINCT raw_dob)              AS unique_dobs,
    COUNT(*)                             AS total_records,
    CASE 
        WHEN COUNT(DISTINCT raw_dob) = 1 AND COUNT(*) > 3 
        THEN 'SUSPICIOUS_UNIFORMITY_WARNING: All members share identical DOB (mock data risk)'
        ELSE 'NORMAL_DISTRIBUTION'
    END AS distribution_check
FROM raw_member_landing
WHERE raw_record_type = 'D';
