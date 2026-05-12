-- init.sql
-- Extension UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Optimizations
CREATE INDEX IF NOT EXISTS idx_users_email_lower ON users (lower(email));
CREATE INDEX IF NOT EXISTS idx_users_username_lower ON users (lower(username));
CREATE INDEX IF NOT EXISTS idx_biblio_cards_user_status ON biblio_cards (user_id, status);
CREATE INDEX IF NOT EXISTS idx_biblio_cards_canonical ON biblio_cards (canonical_hash);
CREATE INDEX IF NOT EXISTS idx_sources_url_trgm ON sources (url);
CREATE INDEX IF NOT EXISTS idx_sources_archive ON sources (archive_status);

-- Audit function
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_biblio_cards_updated_at
    BEFORE UPDATE ON biblio_cards
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_sources_updated_at
    BEFORE UPDATE ON sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
