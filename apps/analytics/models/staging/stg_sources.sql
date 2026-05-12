{{ config(materialized='ephemeral') }}

SELECT
    bc.id as biblio_card_id,
    bc.user_id,
    bc.title,
    bc.content_type,
    bc.content_url,
    bc.status,
    bc.published_at,
    bc.canonical_hash,
    bc.created_at as biblio_created_at,
    COUNT(s.id) as source_count,
    COUNT(CASE WHEN s.archive_status = 'archived' THEN 1 END) as archived_count,
    COUNT(CASE WHEN s.archive_status = 'pending' THEN 1 END) as pending_count,
    COUNT(CASE WHEN s.archive_status = 'failed' THEN 1 END) as failed_count
FROM {{ source('postgres', 'biblio_cards') }} bc
LEFT JOIN {{ source('postgres', 'sources') }} s ON bc.id = s.biblio_card_id
WHERE bc.deleted_at IS NULL
GROUP BY bc.id, bc.user_id, bc.title, bc.content_type, bc.content_url, bc.status, bc.published_at, bc.canonical_hash, bc.created_at
