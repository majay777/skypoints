-- Flat File Raw Landing Table
CREATE TABLE IF NOT EXISTS raw_member_landing (
    raw_record_type     VARCHAR(5),        -- 'H' for Header, 'D' for Detail
    raw_member_name     VARCHAR(255),
    raw_member_id       VARCHAR(50),
    raw_enrollment_date VARCHAR(20),       -- Format: YYYYMMDD (e.g. '20101012')
    raw_last_flight_date VARCHAR(20),      -- Format: YYYYMMDD (e.g. '20121013')
    raw_tier_code       VARCHAR(10),       -- 'GLD', 'SLV', 'PLT'
    raw_agent_name      VARCHAR(255),      -- 'Sam'
    raw_state           VARCHAR(50),       -- 'CA', 'TN', 'NCR', 'ONT', 'VIC'
    raw_country         VARCHAR(50),       -- 'USA', 'IND', 'PHIL', 'CAN', 'AU'
    raw_dob             VARCHAR(20),       -- Format: MMDDYYYY / DDMMYYYY ('03051985')
    raw_is_active       VARCHAR(5),        -- 'A'
    
    -- Ingestion Metadata
    source_file_name    VARCHAR(255) NOT NULL,
    file_row_number     BIGINT,
    ingestion_timestamp TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
)
CLUSTER BY (source_file_name, raw_record_type)
COMMENT = 'Raw landing table for daily pipe-delimited member profile flat files';

-- JSON Feed Raw Landing Table
CREATE TABLE IF NOT EXISTS raw_redemptions_landing (
    raw_payload         VARIANT,           -- Stores full JSON object
    source_file_name    VARCHAR(255) NOT NULL,
    ingestion_timestamp TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
)
CLUSTER BY (DATE(ingestion_timestamp))
COMMENT = 'Raw landing table for daily semi-structured partner redemption JSON feed';


-- ----------------------------------------------------------------------------
-- 3. STAGING / INTERMEDIATE LAYER (Silver)
-- Objective: Filter data rows ('D'), standardize types, derive Age and Stale_Member.
-- Matches intermediate structure requested: Name, Mem_Id, Enroll_Dt, Flight_Dt,
-- TIER, Agent_Name, State, County, DOB, FLAG, plus derived Age and Stale_Member.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg_member_profile (
    Name                VARCHAR(255) NOT NULL,
    Mem_Id              VARCHAR(50)  NOT NULL,
    Enroll_Dt           DATE         NOT NULL,
    Flight_Dt           DATE,
    TIER                VARCHAR(10),
    Agent_Name          VARCHAR(255),
    State               VARCHAR(50),
    County              VARCHAR(50),      -- Standardized/Mapped from Country
    Country_Code        VARCHAR(10),      -- ISO Standard Alpha-3 (USA, IND, PHL, CAN, AUS)
    DOB                 BIGINT,           -- 3051985 (leading zero stripped as requested)
    DOB_Date            DATE,             -- Validated calendar date for calculations
    FLAG                VARCHAR(5),       -- Active Flag ('A')
    
    -- Derived Business Columns (Deliverable 2)
    Age                 INTEGER,          -- Computed from DOB_Date vs CURRENT_DATE()
    Stale_Member        BOOLEAN,          -- TRUE if DATEDIFF('day', Flight_Dt, CURRENT_DATE()) > 90
    
    -- Audit & Lineage Columns
    source_file_name    VARCHAR(255),
    batch_timestamp     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_stg_member PRIMARY KEY (Mem_Id, source_file_name)
)
CLUSTER BY (Country_Code, Mem_Id)
COMMENT = 'Staged, cleaned, and enriched member profiles with derived metrics';


-- Flattened Intermediate Redemptions Table
CREATE TABLE IF NOT EXISTS stg_member_redemptions (
    txn_id              VARCHAR(50)  NOT NULL,
    member_id           VARCHAR(50)  NOT NULL,
    feed_date           DATE         NOT NULL,
    txn_date            DATE         NOT NULL,
    partner             VARCHAR(100) NOT NULL,
    miles_redeemed      INTEGER      NOT NULL,
    status              VARCHAR(20)  NOT NULL,   -- 'COMPLETED', 'PENDING'
    source_file_name    VARCHAR(255),
    ingestion_timestamp TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_stg_redemptions PRIMARY KEY (txn_id)
)
CLUSTER BY (member_id, txn_date)
COMMENT = 'Flattened partner mileage redemption transactions from JSON feed';

-- Table for India Members
CREATE TABLE IF NOT EXISTS Table_India (
    Name                VARCHAR(255) NOT NULL,
    Mem_Id              VARCHAR(50)  NOT NULL,
    Enroll_Dt           DATE         NOT NULL,
    Flight_Dt           DATE,
    TIER                VARCHAR(10),
    Agent_Name          VARCHAR(255),
    State               VARCHAR(50),
    County              VARCHAR(50),
    DOB                 BIGINT,
    FLAG                VARCHAR(5),
    Age                 INTEGER,
    Stale_Member        BOOLEAN,
    last_updated_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_table_india PRIMARY KEY (Mem_Id)
)
CLUSTER BY (Mem_Id)
COMMENT = 'Gold target table for loyalty members residing in India';

-- Table for USA Members
CREATE TABLE IF NOT EXISTS Table_USA (
    Name                VARCHAR(255) NOT NULL,
    Mem_Id              VARCHAR(50)  NOT NULL,
    Enroll_Dt           DATE         NOT NULL,
    Flight_Dt           DATE,
    TIER                VARCHAR(10),
    Agent_Name          VARCHAR(255),
    State               VARCHAR(50),
    County              VARCHAR(50),
    DOB                 BIGINT,
    FLAG                VARCHAR(5),
    Age                 INTEGER,
    Stale_Member        BOOLEAN,
    last_updated_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_table_usa PRIMARY KEY (Mem_Id)
)
CLUSTER BY (Mem_Id)
COMMENT = 'Gold target table for loyalty members residing in USA';


-- Table for Australia Members (Handles 'AU' source anomaly)
CREATE TABLE IF NOT EXISTS Table_Australia (
    Name                VARCHAR(255) NOT NULL,
    Mem_Id              VARCHAR(50)  NOT NULL,
    Enroll_Dt           DATE         NOT NULL,
    Flight_Dt           DATE,
    TIER                VARCHAR(10),
    Agent_Name          VARCHAR(255),
    State               VARCHAR(50),
    County              VARCHAR(50),
    DOB                 BIGINT,
    FLAG                VARCHAR(5),
    Age                 INTEGER,
    Stale_Member        BOOLEAN,
    last_updated_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_table_australia PRIMARY KEY (Mem_Id)
)
CLUSTER BY (Mem_Id)
COMMENT = 'Gold target table for loyalty members residing in Australia';
