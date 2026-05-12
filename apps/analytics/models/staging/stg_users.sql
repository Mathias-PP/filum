{{ config(materialized='ephemeral') }}

SELECT
    u.id as user_id,
    u.username,
    u.display_name,
    u.email,
    u.is_verified,
    u.created_at as user_created_at,
    COUNT(DISTINCT bc.id) as biblio_card_count,
    COUNT(DISTINCT s.id) as source_count,
    COUNT(DISTINCT CASE WHEN s.archive_status = 'archived' THEN s.id END) as archived_source_count
FROM {{ source('postgres', 'users') }} u
LEFT JOIN {{ source('postgres', 'biblio_cards') }} bc ON u.id = bc.user_id
LEFT JOIN {{ source('postgres', 'sources') }} s ON bc.id = s.biblio_card_id
WHERE u.deleted_at IS NULL
GROUP BY u.id, u.username, u.display_name, u.email, u.is_verified, u.created_at
