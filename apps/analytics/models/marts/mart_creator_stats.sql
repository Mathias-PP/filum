{{ config(materialized='view') }}

SELECT
    DATE_TRUNC('day', user_created_at) as date,
    COUNT(*) as new_users,
    SUM(biblio_card_count) as total_biblio_cards,
    SUM(source_count) as total_sources
FROM {{ ref('stg_users') }}
GROUP BY DATE_TRUNC('day', user_created_at)
ORDER BY date DESC
