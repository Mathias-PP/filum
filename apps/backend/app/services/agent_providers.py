"""Service des providers IA BYOK des créateurs.

Un créateur enregistre ses comptes IA (clé API, modèle, endpoint) ; Philum ne
fait jamais l'inférence lui-même. La clé est chiffrée AES-GCM à la création
(``KeyManager(master_encryption_key)``) et ne sort jamais en clair de ce
service — seule la forme masquée (``sk-…1234``) atteint les endpoints.

**Le provider est le cerveau, Philum est les mains et la preuve.**
"""

from __future__ import annotations

import logging
from time import monotonic
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.url_safety import UnsafeUrlError, assert_url_is_safe
from app.crypto.keygen import KeyManager
from app.models.agent_provider import AgentProvider
from app.schemas.agent_provider import (
    MODELES_SUGGERES,
    PROVIDER_DEFAULT_BASE_URLS,
    AgentProviderCreate,
    AgentProviderRead,
    AgentProviderTestResult,
    AgentProviderUpdate,
    ProviderKind,
    _api_key_masked,
)
from app.services.llm import url_chat

logger = logging.getLogger(__name__)

settings = get_settings()

_TIMEOUT = 20.0

# Cache in-memory de ``lister_modeles()``. Le catalogue d'un compte bouge
# rarement a l'echelle d'un utilisateur (nouveaux modeles publies par le
# fournisseur, changement de plan) ; un TTL de 15 minutes evite de brûler du
# rate-limit chez le fournisseur pour la meme information sur une session
# d'usage typique. Cle : (creator_id, provider_id). Invalide sur update et
# supprime. On ne monte pas Redis pour ce cache : le backend tourne en single
# node (VM e2-micro), et cette memoire disparait naturellement au redemarrage.
_MODELES_TTL_SECS = 15 * 60
_modeles_cache: dict[tuple[UUID, UUID], tuple[dict[str, Any], float]] = {}


def _invalider_cache_modeles(provider_id: UUID) -> None:
    """Retire toutes les entrees du cache concernant ce provider (tous createurs)."""
    for cle in list(_modeles_cache.keys()):
        if cle[1] == provider_id:
            del _modeles_cache[cle]


def _invalider_cache_modeles_tout() -> None:
    """Vide le cache. Utilise dans les tests pour isoler chaque cas."""
    _modeles_cache.clear()


class AgentProviderError(ValueError):
    """Erreur métier : payload invalide, doublon, ressource d'un autre créateur."""


class AgentProviderNotFoundError(AgentProviderError):
    """Le provider n'existe pas ou n'appartient pas à ce créateur."""


# --- Notice de souveraineté (factuelle, pour tous les providers) -------------
#
# Ce qui transite pendant un échange, c'est ce qui est envoyé au modèle :
# messages, contenu des fiches/sources/workspace consulté, résultats d'outils.
# L'endroit où le modèle est exécuté dépend du provider. Ton neutre, sans
# jugement : l'utilisateur décide, Philum informe.

DATA_SCOPE_NOTICE = (
    "Pendant un échange, ces données sont envoyées au fournisseur du modèle : vos "
    "messages, le contenu de vos fiches, de vos sources et de vos fichiers de "
    "workspace consultés, et les résultats des outils renvoyés au modèle. Le "
    "modèle est exécuté sur l'infrastructure du fournisseur indiquée ci-dessous. "
    "Votre clé API n'est envoyée qu'à ce fournisseur."
)

PROVIDER_META: dict[str, dict[str, str]] = {
    "openai": {
        "hosting_country": "États-Unis",
        "hosting_note": "Infrastructure d'OpenAI, principalement aux États-Unis.",
    },
    "anthropic": {
        "hosting_country": "États-Unis",
        "hosting_note": "Infrastructure d'Anthropic, principalement aux États-Unis.",
    },
    "deepseek": {
        "hosting_country": "Chine",
        "hosting_note": "Infrastructure de DeepSeek, principalement en Chine.",
    },
    "gemini": {
        "hosting_country": "États-Unis",
        "hosting_note": "Infrastructure de Google, répartie mondialement (siège aux États-Unis).",
    },
    "groq": {
        "hosting_country": "États-Unis",
        "hosting_note": "Infrastructure de Groq, principalement aux États-Unis.",
    },
    "openrouter": {
        "hosting_country": "Variable",
        "hosting_note": (
            "OpenRouter route vers le fournisseur du modele choisi : "
            "l'hebergement depend de ce modele."
        ),
    },
    "mistral": {
        "hosting_country": "France",
        "hosting_note": "Infrastructure de Mistral AI, en Europe.",
    },
    "cerebras": {
        "hosting_country": "États-Unis",
        "hosting_note": "Infrastructure de Cerebras, principalement aux États-Unis.",
    },
    "custom": {
        "hosting_country": "Selon l'endpoint configuré",
        "hosting_note": (
            "Endpoint tiers : l'emplacement d'hébergement dépend du fournisseur "
            "que vous configurez."
        ),
    },
}


def _key_manager() -> KeyManager:
    return KeyManager(settings.master_encryption_key)


def _decrypt(key_enc: str) -> str:
    return _key_manager().decrypt_private_key(key_enc)


def _to_read(provider: AgentProvider) -> AgentProviderRead:
    return AgentProviderRead(
        id=provider.id,
        provider=ProviderKind(provider.provider),
        display_name=provider.display_name,
        base_url=provider.base_url,
        model=provider.model,
        is_default=provider.is_default,
        api_key_masked=_api_key_masked(_decrypt(provider.api_key_enc)),
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


def _resolve_base_url(provider: ProviderKind, base_url: str | None) -> str:
    """La base_url à enregistrer, assainie si elle vient de l'utilisateur.

    Une base_url fournie (custom, ou surcharge d'un provider intégré) passe par
    ``assert_url_is_safe`` : Philum appellera cet endpoint, il ne doit pas
    pouvoir viser une adresse interne (SSRF). Les défauts intégrés sont des
    constantes de confiance.
    """
    if base_url is not None:
        try:
            assert_url_is_safe(base_url)
        except UnsafeUrlError as exc:
            raise AgentProviderError(f"base_url non sûre : {exc}") from exc
        return base_url
    if provider == ProviderKind.CUSTOM:
        raise AgentProviderError("Un provider custom exige une base_url.")
    return PROVIDER_DEFAULT_BASE_URLS[provider.value]


async def _get_owned(
    db: AsyncSession,
    creator_id: UUID,
    provider_id: UUID,
) -> AgentProvider:
    result = await db.execute(
        select(AgentProvider).where(
            AgentProvider.id == provider_id,
            AgentProvider.creator_id == creator_id,
        )
    )
    provider = result.scalar_one_or_none()
    if provider is None:
        raise AgentProviderNotFoundError("Provider introuvable.")
    return provider


async def _clear_default(db: AsyncSession, creator_id: UUID) -> None:
    """Un seul défaut par créateur : efface les marques existantes."""
    result = await db.execute(
        select(AgentProvider).where(
            AgentProvider.creator_id == creator_id,
            AgentProvider.is_default.is_(True),
        )
    )
    for provider in result.scalars().all():
        provider.is_default = False


async def lister(db: AsyncSession, creator_id: UUID) -> list[AgentProviderRead]:
    result = await db.execute(
        select(AgentProvider)
        .where(AgentProvider.creator_id == creator_id)
        .order_by(AgentProvider.created_at)
    )
    return [_to_read(p) for p in result.scalars().all()]


async def creer(
    db: AsyncSession,
    creator_id: UUID,
    payload: AgentProviderCreate,
) -> AgentProviderRead:
    base_url = _resolve_base_url(payload.provider, payload.base_url)
    display_name = (payload.display_name or "").strip() or payload.provider.value
    key_enc = _key_manager().encrypt_private_key(payload.api_key)

    if payload.is_default:
        await _clear_default(db, creator_id)

    provider = AgentProvider(
        creator_id=creator_id,
        provider=payload.provider.value,
        display_name=display_name,
        base_url=base_url,
        model=payload.model.strip(),
        api_key_enc=key_enc,
        is_default=payload.is_default,
    )
    db.add(provider)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AgentProviderError(
            "Un provider identique (même provider, même base_url, même modèle) existe déjà."
        ) from exc
    await db.refresh(provider)
    return _to_read(provider)


async def mettre_a_jour(
    db: AsyncSession,
    creator_id: UUID,
    provider_id: UUID,
    payload: AgentProviderUpdate,
) -> AgentProviderRead:
    provider = await _get_owned(db, creator_id, provider_id)

    if payload.display_name is not None:
        display_name = payload.display_name.strip()
        if not display_name:
            raise AgentProviderError("display_name ne peut pas être vide.")
        provider.display_name = display_name
    if payload.base_url is not None:
        base_url = _resolve_base_url(ProviderKind(provider.provider), payload.base_url)
        provider.base_url = base_url
    if payload.model is not None:
        model = payload.model.strip()
        if not model:
            raise AgentProviderError("model ne peut pas être vide.")
        provider.model = model
    if payload.api_key is not None:
        provider.api_key_enc = _key_manager().encrypt_private_key(payload.api_key)
    if payload.is_default is True:
        await _clear_default(db, creator_id)
        provider.is_default = True
    elif payload.is_default is False:
        provider.is_default = False

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AgentProviderError(
            "Un provider identique (même provider, même base_url, même modèle) existe déjà."
        ) from exc
    await db.refresh(provider)
    # Toute mutation peut rendre le catalogue en cache faux (nouvelle clé =
    # potentiellement nouveau plan, nouveau base_url = endpoint différent).
    # Invalidation systématique : ne pas essayer de deviner ce qui a bougé.
    _invalider_cache_modeles(provider_id)
    return _to_read(provider)


async def supprimer(
    db: AsyncSession,
    creator_id: UUID,
    provider_id: UUID,
) -> None:
    provider = await _get_owned(db, creator_id, provider_id)
    await db.delete(provider)
    await db.commit()
    _invalider_cache_modeles(provider_id)


async def resoudre_defaut(
    db: AsyncSession,
    creator_id: UUID,
) -> AgentProvider | None:
    """Le provider par défaut du créateur, s'il en a désigné un."""
    result = await db.execute(
        select(AgentProvider).where(
            AgentProvider.creator_id == creator_id,
            AgentProvider.is_default.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def tester(
    db: AsyncSession,
    creator_id: UUID,
    provider_id: UUID,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AgentProviderTestResult:
    """Un appel minimal (1 token, prompt « ping ») avec la clé du créateur.

    ``transport`` est injectable pour les tests (``httpx.MockTransport``) :
    aucun appel réseau dans les tests. Pour Anthropic, la surface
    OpenAI-compatible est tentée d'abord ; si elle est absente (400/404), on
    bascule sur l'adapter natif ``/v1/messages`` (``x-api-key`` +
    ``anthropic-version``). Ne lève jamais : retourne un résultat classifiable.
    """
    provider = await _get_owned(db, creator_id, provider_id)
    key = _decrypt(provider.api_key_enc)
    url = url_chat(provider.base_url)
    openai_payload = {
        "model": provider.model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {key}"}

    try:
        t0 = monotonic()
        async with httpx.AsyncClient(timeout=_TIMEOUT, transport=transport) as client:
            r = await client.post(url, json=openai_payload, headers=headers)
            if provider.provider == ProviderKind.ANTHROPIC.value and r.status_code in (400, 404):
                r = await client.post(
                    f"{provider.base_url.rstrip('/')}/v1/messages",
                    json={
                        "model": provider.model,
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "ping"}],
                    },
                    headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                )
        latency_ms = int((monotonic() - t0) * 1000)
        result = _classify(provider.model, url, r)
    except httpx.HTTPError as exc:
        return AgentProviderTestResult(
            ok=False,
            http_status=None,
            model_resolved=provider.model,
            url=url,
            message=f"Impossible de joindre l'endpoint : {exc}",
        )

    # Sur succès, on chauffe le cache /models pour ce provider : le sélecteur
    # de modèle sera instantané au prochain affichage. On rafraîchit toujours
    # (refresh=True) car un test réussi signale que la clé/base_url viennent
    # potentiellement d'être fixées — la ligne de cache précédente peut être
    # périmée. `lister_modeles` ne lève jamais, on peut donc chaîner sans try.
    if result.ok:
        modeles = await lister_modeles(
            db, creator_id, provider_id, transport=transport, refresh=True
        )
        result = result.model_copy(update={"models": modeles["models"], "latency_ms": latency_ms})
    return result


def _detail_provider(r: httpx.Response) -> str | None:
    """Le texte que le fournisseur a reellement renvoye, ou ``None``.

    Cinq formes rencontrees, testees en prod le 2026-08-21 :
    - ``{"error": {"message": ...}}`` (OpenAI, Gemini, Groq, OpenRouter)
    - ``[{"error": {"message": ...}}]`` (Gemini renvoie parfois une liste)
    - ``{"detail": "..."}`` (Mistral, convention FastAPI)
    - ``{"message": "...", "type": "..."}`` (Cerebras, message a la racine)
    - HTML brut derriere un proxy (fallback texte)

    Ne leve jamais : un test de cle qui plante en lisant un corps d'erreur ne
    diagnostique plus rien.
    """
    try:
        corps = r.json()
    except ValueError:
        corps = None

    if isinstance(corps, list) and corps:
        corps = corps[0]
    if isinstance(corps, dict):
        erreur = corps.get("error")
        if isinstance(erreur, dict):
            message = erreur.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        if isinstance(erreur, str) and erreur.strip():
            return erreur.strip()
        # Mistral : {"detail": "..."}
        detail = corps.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        # Cerebras : {"message": "...", "type": "...", "code": "..."}
        # Note : ne s'active que si `error` et `detail` sont absents, pour ne pas
        # confondre avec {"error": {..., "message": "..."}} deja traite ci-dessus.
        message = corps.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

    # Eviter de renvoyer un corps JSON syntaxiquement valide mais sans information
    # utile (ex: "{}") comme si c'etait un message du provider.
    if corps is not None:
        return None
    texte = " ".join(r.text.split())
    return texte[:300] or None


_CADRAGES: dict[int, str] = {
    400: "Requête refusée par le provider.",
    401: "Clé API invalide ou révoquée.",
    403: "Accès refusé par le provider (clé sans autorisation).",
    404: "Le provider ne connaît pas ce modèle à cette adresse.",
    429: "Le provider refuse : crédit insuffisant, quota épuisé, ou limite de débit.",
}

# Codes d'erreur normalises par les fournisseurs OpenAI-compat. Le code precise
# ce que le status HTTP ne dit pas : HTTP 429 recouvre à la fois "crédit épuisé"
# (recharger) et "limite de débit" (attendre) — deux réponses opposées pour
# l'utilisateur. Verifie en prod le 2026-08-21 chez OpenAI, Groq, Cerebras.
_CADRAGES_CODE: dict[str, str] = {
    "invalid_api_key": "Clé API invalide ou révoquée.",
    "authentication_error": "Clé API invalide ou révoquée.",
    "wrong_api_key": "Clé API invalide ou révoquée.",
    "insufficient_quota": "Crédit épuisé sur le compte du fournisseur.",
    "billing_hard_limit_reached": "Crédit épuisé sur le compte du fournisseur.",
    "rate_limit_exceeded": "Limite de débit atteinte. Réessayer dans quelques secondes.",
    "requests_rate_limit_exceeded": ("Limite de débit atteinte. Réessayer dans quelques secondes."),
    "model_not_found": "Le modèle demandé n'existe pas chez ce fournisseur.",
    "context_length_exceeded": "Conversation trop longue pour la fenêtre de ce modèle.",
}


def _extraire_code_erreur(r: httpx.Response) -> str | None:
    """Le champ ``code`` d'un corps d'erreur, ou ``None``.

    Deux emplacements observes en prod : ``error.code`` (OpenAI, Groq,
    OpenRouter) et ``code`` a la racine (Cerebras). Ne leve jamais.
    """
    try:
        corps = r.json()
    except ValueError:
        return None
    if isinstance(corps, list) and corps:
        corps = corps[0]
    if not isinstance(corps, dict):
        return None
    erreur = corps.get("error")
    if isinstance(erreur, dict):
        code = erreur.get("code")
        if isinstance(code, str) and code.strip():
            return code.strip()
    code = corps.get("code")
    if isinstance(code, str) and code.strip():
        return code.strip()
    return None


def _classify(
    model: str,
    url: str,
    r: httpx.Response,
) -> AgentProviderTestResult:
    """Un cadrage lisible, suivi du texte exact du provider quand il en donne un.

    Priorite : code d'erreur du corps (specifique, actionnable) > cadrage HTTP
    (generique). Le message brut du fournisseur suit dans les deux cas pour ne
    pas perdre l'information particulière que la reformulation gomme toujours.
    """
    if r.status_code == 200:
        return AgentProviderTestResult(
            ok=True,
            http_status=200,
            model_resolved=model,
            url=url,
            message=f"Clé valide, le modèle {model} répond.",
        )

    code = _extraire_code_erreur(r)
    cadrage: str | None = _CADRAGES_CODE.get(code) if code else None
    if cadrage is None:
        cadrage = _CADRAGES.get(
            r.status_code,
            f"Réponse inattendue du provider (HTTP {r.status_code}).",
        )
    detail = _detail_provider(r)
    return AgentProviderTestResult(
        ok=False,
        http_status=r.status_code,
        model_resolved=model,
        url=url,
        message=f"{cadrage} {detail}" if detail else cadrage,
        provider_message=detail,
    )


async def lister_modeles(
    db: AsyncSession,
    creator_id: UUID,
    provider_id: UUID,
    transport: httpx.AsyncBaseTransport | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Les modeles auxquels *ce* compte a droit, demandes au fournisseur.

    Tous les fournisseurs OpenAI-compatibles servent ``GET /models`` avec la cle
    du porteur, et la reponse depend du plan souscrit. Ne leve jamais : un echec
    se replie sur ``MODELES_SUGGERES``.

    Cache TTL 15 min par (createur, provider) : le sélecteur de modèle sera
    servi depuis la mémoire à la deuxième ouverture. Seuls les résultats
    ``source == "provider"`` sont mis en cache — une erreur ne colle jamais,
    l'utilisateur qui vient de fixer sa clé doit voir le résultat immédiatement.
    ``refresh=True`` force le rappel réseau (utilisé par ``tester()``).
    """
    cle_cache = (creator_id, provider_id)
    if not refresh:
        entree = _modeles_cache.get(cle_cache)
        if entree is not None and entree[1] > monotonic():
            return entree[0]

    provider = await _get_owned(db, creator_id, provider_id)
    repli = MODELES_SUGGERES.get(provider.provider, [])
    url = f"{provider.base_url.rstrip('/')}/models"

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, transport=transport) as client:
            r = await client.get(
                url,
                headers={"Authorization": f"Bearer {_decrypt(provider.api_key_enc)}"},
            )
    except httpx.HTTPError as exc:
        return {"models": repli, "source": "repli", "message": f"Fournisseur injoignable : {exc}"}

    if r.status_code != 200:
        detail = _detail_provider(r)
        msg = f"Le fournisseur n'a pas liste ses modeles (HTTP {r.status_code})."
        if detail:
            msg = f"{msg} {detail}"
        return {"models": repli, "source": "repli", "message": msg}

    try:
        entrees = r.json().get("data", [])
    except ValueError:
        return {"models": repli, "source": "repli", "message": "Reponse illisible du fournisseur."}

    noms = sorted(
        {e["id"] for e in entrees if isinstance(e, dict) and isinstance(e.get("id"), str)}
    )
    if not noms:
        return {
            "models": repli,
            "source": "repli",
            "message": "Le fournisseur n'a liste aucun modele.",
        }
    resultat = {"models": noms, "source": "provider"}
    _modeles_cache[cle_cache] = (resultat, monotonic() + _MODELES_TTL_SECS)
    return resultat
