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

-- @stg_skypoints_landing- 'External cloud storage stage (S3/GCS/Azure Blob) for daily files';
-- ff_pipe_delimited - File format 

