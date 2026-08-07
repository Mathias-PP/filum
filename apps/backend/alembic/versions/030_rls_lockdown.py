"""Verrouille le schema public contre l'API PostgREST de Supabase.

Revision ID: 030_rls_lockdown
Revises: 029_feed_backfl
"""

from __future__ import annotations

from alembic import op

revision: str = "030_rls_lockdown"
down_revision: str | None = "029_feed_backfl"
branch_labels: str | None = None
depends_on: str | None = None


# Supabase expose automatiquement le schema `public` en REST (PostgREST) et
# accorde tout aux roles `anon` et `authenticated`. La cle `anon` est publique
# par conception : elle est faite pour etre embarquee dans un navigateur. Sans
# ce verrou, quiconque la possede lit et modifie `users` et les cles privees
# chiffrees de `linked_accounts`.
#
# Philum n'utilise pas PostgREST : le backend se connecte en `postgres`, qui
# porte BYPASSRLS. Les deux operations ci-dessous lui sont donc transparentes.
#
# Les deux couches sont necessaires, pas redondantes :
#   - REVOKE  : TRUNCATE n'est PAS soumis a RLS. Sans revocation, `anon`
#               pourrait encore vider chaque table malgre RLS active.
#   - RLS     : filet de securite si un GRANT etait re-accorde un jour (les
#               operations Supabase le font parfois). Aucune policy = zero ligne.
_ROLES = ("anon", "authenticated")


def _tables(conn) -> list[str]:
    rows = conn.exec_driver_sql(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
    ).fetchall()
    return [r[0] for r in rows]


def _role_exists(conn, role: str) -> bool:
    # Les roles `anon`/`authenticated` sont propres a Supabase : absents en
    # local et en CI, ou cette migration doit rester silencieuse.
    return bool(conn.exec_driver_sql(f"SELECT 1 FROM pg_roles WHERE rolname = '{role}'").fetchone())


def upgrade() -> None:
    conn = op.get_bind()
    for table in _tables(conn):
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')

    for role in _ROLES:
        if not _role_exists(conn, role):
            continue
        op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role}")
        op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {role}")
        op.execute(f"REVOKE ALL ON SCHEMA public FROM {role}")
        # Sans ceci, toute table creee par une migration future re-accorderait
        # les memes privileges via les default privileges de Supabase.
        op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {role}")
        op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {role}")


def downgrade() -> None:
    conn = op.get_bind()
    for table in _tables(conn):
        op.execute(f'ALTER TABLE public."{table}" DISABLE ROW LEVEL SECURITY')

    for role in _ROLES:
        if not _role_exists(conn, role):
            continue
        op.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
        op.execute(f"GRANT ALL ON ALL TABLES IN SCHEMA public TO {role}")
        op.execute(f"GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO {role}")
