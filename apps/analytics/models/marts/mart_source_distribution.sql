{{ config(materialized='view') }}

WITH source_distribution AS (
    SELECT
        user_id,
        source_type,
        COUNT(*) as count,
        COUNT(CASE WHEN archive_status = 'archived' THEN 1 END) as archived_count
    FROM {{ ref('stg_sources') }}
    GROUP BY user_id, source_type
)
SELECT
    user_id,
    source_type,
    count,
    archived_count,
    ROUND(archived_count * 100.0 / count, 2) as archive_rate
FROM source_distribution
ORDER BY count DESC
