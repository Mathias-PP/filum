"""Verrouille l'alias de la colonne ``metadata`` de ``audit_events``.

Le modèle Python nomme l'attribut ``event_metadata`` parce que ``metadata``
est réservé par ``sqlalchemy.orm.DeclarativeBase``. La colonne en base
s'appelle bien ``metadata`` (nom historique, présent en prod depuis la
migration initiale). Sans alias explicite, SQLAlchemy émet du SQL contre
une colonne ``event_metadata`` qui n'existe pas — toute lecture ou tout
delete cascade sur ``User`` échoue en ``UndefinedColumnError``. Vécu en prod
le 2026-08-21 sur un test E2E.
"""

from __future__ import annotations

from app.models.audit_event import AuditEvent


def test_event_metadata_est_aliasee_sur_la_colonne_metadata():
    # L'attribut Python s'appelle event_metadata, la colonne SQL 'metadata'
    colonne_sql = AuditEvent.event_metadata.property.columns[0]
    assert colonne_sql.name == "metadata", (
        f"attribut event_metadata doit être aliasé sur la colonne DB 'metadata', "
        f"pas '{colonne_sql.name}' — sinon SELECT/DELETE plante en prod (Postgres "
        f"a 'metadata', SQLite des tests créerait la colonne au nom qu'on veut)."
    )
    # Cote table : c'est bien 'metadata' qui existe, pas 'event_metadata'
    assert "metadata" in AuditEvent.__table__.c
    assert "event_metadata" not in AuditEvent.__table__.c
