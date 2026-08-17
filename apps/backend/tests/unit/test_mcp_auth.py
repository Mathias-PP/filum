"""Un agent MCP prouve qui il est avec un token, comme au REST.

Le MCP en lecture reste ouvert : n'importe qui peut lire ce que Philum
publie. L'ecriture exige de savoir qui parle -- sinon une fiche naitrait
sans createur, ou un agent pourrait en publier sous le nom d'un autre.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from fastmcp.exceptions import ToolError

from app.mcp_server.auth import _user_depuis_token, exiger_utilisateur, utilisateur_courant
from app.services.auth import ALGORITHM


def _forger_token(user_id, secret, *, expire_in_hours=1):
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(hours=expire_in_hours)},
        secret,
        algorithm=ALGORITHM,
    )


@pytest.mark.asyncio
async def test_un_token_valide_identifie_l_utilisateur(db_session, test_user):
    from app.core.config import get_settings

    token = _forger_token(test_user.id, get_settings().session_secret)
    user = await _user_depuis_token(db_session, token)
    assert user is not None
    assert user.id == test_user.id


@pytest.mark.asyncio
async def test_un_token_absent_ne_donne_personne(db_session):
    assert await _user_depuis_token(db_session, None) is None
    assert await _user_depuis_token(db_session, "") is None


@pytest.mark.asyncio
async def test_un_token_expire_ne_donne_personne(db_session, test_user):
    from app.core.config import get_settings

    token = _forger_token(test_user.id, get_settings().session_secret, expire_in_hours=-1)
    assert await _user_depuis_token(db_session, token) is None


@pytest.mark.asyncio
async def test_un_token_signe_avec_le_mauvais_secret_ne_donne_personne(db_session, test_user):
    token = _forger_token(test_user.id, "autre-secret-imposteur")
    assert await _user_depuis_token(db_session, token) is None


@pytest.mark.asyncio
async def test_un_sujet_qui_ne_pointe_personne_ne_donne_personne(db_session):
    """Un JWT valide mais dont le sub ne correspond a aucun user en base.

    Cas concret : un token emis pour un user, le user est ensuite supprime.
    Le token reste valide au sens cryptographique mais ne doit designer personne.
    """
    from app.core.config import get_settings

    token = _forger_token(uuid4(), get_settings().session_secret)
    assert await _user_depuis_token(db_session, token) is None


@pytest.mark.asyncio
async def test_un_utilisateur_supprime_n_est_plus_reconnu(db_session, test_user):
    """Un token emis avant la suppression du compte ne peut plus servir."""
    from app.core.config import get_settings

    token = _forger_token(test_user.id, get_settings().session_secret)
    test_user.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await db_session.commit()
    assert await _user_depuis_token(db_session, token) is None


@pytest.mark.asyncio
async def test_utilisateur_courant_hors_contexte_http_renvoie_none(db_session):
    """Depuis un test unitaire (pas d'HTTP en cours), la lecture doit dire None."""
    assert await utilisateur_courant(db_session) is None


@pytest.mark.asyncio
async def test_exiger_utilisateur_leve_une_toolerror_avec_le_chemin_du_token(db_session):
    with pytest.raises(ToolError) as excinfo:
        await exiger_utilisateur(db_session)
    message = str(excinfo.value)
    assert "mcp-token" in message
    assert "Bearer" in message
