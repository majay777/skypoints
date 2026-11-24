-- STEP 1: Deduplicate Staging Data with "Latest Record Wins"
-- When a member appears multiple times or moves countries, rank by:
-- 1. Flight_Dt DESC (latest flight activity indicates latest country of residence)
-- 2. Enroll_Dt DESC
-- 3. batch_timestamp DESC (latest file ingestion)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TEMPORARY TABLE tmp_deduped_latest_members AS
WITH ranked_members AS (
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
        FLAG,
        Age,
        Stale_Member,
        batch_timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY Mem_Id 
            ORDER BY 
                Flight_Dt DESC NULLS LAST,
                Enroll_Dt DESC NULLS LAST,
                batch_timestamp DESC
        ) AS rank_order
    FROM stg_member_profile
)
SELECT * 
FROM ranked_members 
WHERE rank_order = 1;

-- Purge moved members from Table_USA who now reside in another country
DELETE FROM Table_USA
WHERE Mem_Id IN (
    SELECT Mem_Id 
    FROM tmp_deduped_latest_members 
    WHERE Country_Code != 'USA'
);

-- Purge moved members from Table_India who now reside in another country
DELETE FROM Table_India
WHERE Mem_Id IN (
    SELECT Mem_Id 
    FROM tmp_deduped_latest_members 
    WHERE Country_Code != 'IND'
);

-- Purge moved members from Table_Australia who now reside in another country.
DELETE FROM Table_Australia
WHERE Mem_Id IN (
    SELECT Mem_Id 
    FROM tmp_deduped_latest_members 
    WHERE Country_Code NOT IN ('AU', 'AUS')
);

-- A. MERGE INTO Table_India
MERGE INTO Table_India AS target
USING (
    SELECT * FROM tmp_deduped_latest_members WHERE Country_Code = 'IND'
) AS source
ON target.Mem_Id = source.Mem_Id
WHEN MATCHED THEN UPDATE SET
    target.Name            = source.Name,
    target.Enroll_Dt       = source.Enroll_Dt,
    target.Flight_Dt       = source.Flight_Dt,
    target.TIER            = source.TIER,
    target.Agent_Name      = source.Agent_Name,
    target.State           = source.State,
    target.County          = source.County,
    target.DOB             = source.DOB,
    target.FLAG            = source.FLAG,
    target.Age             = source.Age,
    target.Stale_Member    = source.Stale_Member,
    target.last_updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    Name, Mem_Id, Enroll_Dt, Flight_Dt, TIER, Agent_Name,
    State, County, DOB, FLAG, Age, Stale_Member, last_updated_at
) VALUES (
    source.Name, source.Mem_Id, source.Enroll_Dt, source.Flight_Dt, source.TIER, source.Agent_Name,
    source.State, source.County, source.DOB, source.FLAG, source.Age, source.Stale_Member, CURRENT_TIMESTAMP()
);

-- B. MERGE INTO Table_USA
MERGE INTO Table_USA AS target
USING (
    SELECT * FROM tmp_deduped_latest_members WHERE Country_Code = 'USA'
) AS source
ON target.Mem_Id = source.Mem_Id
WHEN MATCHED THEN UPDATE SET
    target.Name            = source.Name,
    target.Enroll_Dt       = source.Enroll_Dt,
    target.Flight_Dt       = source.Flight_Dt,
    target.TIER            = source.TIER,
    target.Agent_Name      = source.Agent_Name,
    target.State           = source.State,
    target.County          = source.County,
    target.DOB             = source.DOB,
    target.FLAG            = source.FLAG,
    target.Age             = source.Age,
    target.Stale_Member    = source.Stale_Member,
    target.last_updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    Name, Mem_Id, Enroll_Dt, Flight_Dt, TIER, Agent_Name,
    State, County, DOB, FLAG, Age, Stale_Member, last_updated_at
) VALUES (
    source.Name, source.Mem_Id, source.Enroll_Dt, source.Flight_Dt, source.TIER, source.Agent_Name,
    source.State, source.County, source.DOB, source.FLAG, source.Age, source.Stale_Member, CURRENT_TIMESTAMP()
);

-- E. MERGE INTO Table_Australia
MERGE INTO Table_Australia AS target
USING (
    SELECT * FROM tmp_deduped_latest_members WHERE Country_Code IN ('AU', 'AUS')
) AS source
ON target.Mem_Id = source.Mem_Id
WHEN MATCHED THEN UPDATE SET
    target.Name            = source.Name,
    target.Enroll_Dt       = source.Enroll_Dt,
    target.Flight_Dt       = source.Flight_Dt,
    target.TIER            = source.TIER,
    target.Agent_Name      = source.Agent_Name,
    target.State           = source.State,
    target.County          = source.County,
    target.DOB             = source.DOB,
    target.FLAG            = source.FLAG,
    target.Age             = source.Age,
    target.Stale_Member    = source.Stale_Member,
    target.last_updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    Name, Mem_Id, Enroll_Dt, Flight_Dt, TIER, Agent_Name,
    State, County, DOB, FLAG, Age, Stale_Member, last_updated_at
) VALUES (
    source.Name, source.Mem_Id, source.Enroll_Dt, source.Flight_Dt, source.TIER, source.Agent_Name,
    source.State, source.County, source.DOB, source.FLAG, source.Age, source.Stale_Member, CURRENT_TIMESTAMP()
);
