{{ config(materialized='incremental', unique_key='source_url') }}

SELECT
    url as source_url,
    COUNT(*) as usage_count,
    COUNT(DISTINCT user_id) as unique_creators,
    COLLECT(DISTINCT source_type) as source_types,
    MIN(created_at) as first_seen,
    MAX(created_at) as last_seen
FROM {{ source('postgres', 'sources') }}
GROUP BY url
