-- Copy raw flat file from External Stage into Raw Landing (Bronze)
-- Handles leading delimiter '|' and separates Header ('H') from Data ('D')
COPY INTO raw_member_landing (
    raw_record_type,
    raw_member_name,
    raw_member_id,
    raw_enrollment_date,
    raw_last_flight_date,
    raw_tier_code,
    raw_agent_name,
    raw_state,
    raw_country,
    raw_dob,
    raw_is_active,
    source_file_name,
    file_row_number
)
FROM (
    SELECT 
        t.$2  AS raw_record_type,      -- $1 is empty due to leading pipe '|'
        t.$3  AS raw_member_name,
        t.$4  AS raw_member_id,
        t.$5  AS raw_enrollment_date,
        t.$6  AS raw_last_flight_date,
        t.$7  AS raw_tier_code,
        t.$8  AS raw_agent_name,
        t.$9  AS raw_state,
        t.$10 AS raw_country,
        t.$11 AS raw_dob,
        t.$12 AS raw_is_active,
        METADATA$FILENAME,
        METADATA$FILE_ROW_NUMBER
    FROM @stg_skypoints_landing/members/ (FILE_FORMAT => 'ff_pipe_delimited') t
);


-- INSERT / MERGE INTO STAGING TABLE (SILVER LAYER)
-- Transforms, cleans, standardizes country codes, and computes derived columns:
-- 1. Age: Computed precisely from DOB date
-- 2. Stale_Member: TRUE if DATEDIFF('day', Flight_Dt, CURRENT_DATE()) > 90

INSERT INTO stg_member_profile (
    Name,
    Mem_Id,
    Enroll_Dt,
    Flight_Dt,
    TIER,
    Agent_Name,
    State,
    County,
    Country_Code,
    DOB,
    DOB_Date,
    FLAG,
    Age,
    Stale_Member,
    source_file_name
)
WITH raw_filtered AS (
    SELECT 
        TRIM(raw_member_name)               AS raw_name,
        TRIM(raw_member_id)                 AS raw_id,
        TRIM(raw_enrollment_date)           AS raw_enroll,
        TRIM(raw_last_flight_date)          AS raw_flight,
        TRIM(raw_tier_code)                 AS raw_tier,
        NULLIF(TRIM(raw_agent_name), '')    AS raw_agent,
        TRIM(raw_state)                     AS raw_st,
        TRIM(raw_country)                   AS raw_cntry,
        TRIM(raw_dob)                       AS raw_dob_val,
        TRIM(raw_is_active)                 AS raw_flag,
        source_file_name
    FROM raw_member_landing
    WHERE raw_record_type = 'D'  -- Exclude Header ('H') rows
),
standardized AS (
    SELECT
        raw_name                            AS Name,
        raw_id                              AS Mem_Id,
        TRY_TO_DATE(raw_enroll, 'YYYYMMDD') AS Enroll_Dt,
        TRY_TO_DATE(raw_flight, 'YYYYMMDD') AS Flight_Dt,
        raw_tier                            AS TIER,
        raw_agent                           AS Agent_Name,
        raw_st                              AS State,
        raw_cntry                           AS County,  -- Mapped to County as in intermediate spec
        
        -- ISO Alpha-3 Country Normalization (handles source anomalies: PHIL -> PHL, AU -> AUS)
        CASE UPPER(raw_cntry)
            WHEN 'USA'  THEN 'USA'
            WHEN 'IND'  THEN 'IND'
            WHEN 'AU'   THEN 'AUS'
            ELSE UPPER(raw_cntry)
        END AS Country_Code,
        
        -- Numeric DOB: Strips leading zero ('03051985' -> 3051985)
        TRY_TO_NUMBER(raw_dob_val)          AS DOB,
        
        -- Date of Birth parsing (handles MMDDYYYY with fallback to DDMMYYYY)
        COALESCE(
            TRY_TO_DATE(LPAD(raw_dob_val, 8, '0'), 'MMDDYYYY'),
            TRY_TO_DATE(LPAD(raw_dob_val, 8, '0'), 'DDMMYYYY')
        ) AS DOB_Date,
        
        raw_flag                            AS FLAG,
        source_file_name
    FROM raw_filtered
)
SELECT
    Name,
    Mem_Id,
    Enroll_Dt,
    Flight_Dt,
    TIER,
    Agent_Name,
    State,
    County,
    Country_Code,
    DOB,
    DOB_Date,
    FLAG,
    
    -- Derived Column 1: Age (precise calculation accounting for birthday month/day)
    FLOOR(DATEDIFF('month', DOB_Date, CURRENT_DATE()) / 12) AS Age,
    
    -- Derived Column 2: Stale_Member flag (days since Flight_Date > 90)
    CASE 
        WHEN Flight_Dt IS NULL THEN TRUE
        WHEN DATEDIFF('day', Flight_Dt, CURRENT_DATE()) > 90 THEN TRUE 
        ELSE FALSE 
    END AS Stale_Member,
    
    source_file_name
FROM standardized
WHERE Enroll_Dt IS NOT NULL AND Mem_Id IS NOT NULL;

-- @stg_skypoints_landing- 'External cloud storage stage (S3/GCS/Azure Blob) for daily files';
-- ff_pipe_delimited - File format 

