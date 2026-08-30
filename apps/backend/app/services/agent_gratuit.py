"""Mode gratuit : rotation de lanes serveur sans clé côté utilisateur.

Différence fondamentale avec le mode découverte (``agent_discovery``) :
ici l'utilisateur doit **consentir explicitement** — les fournisseurs
gratuits (Z.ai tier gratuit aujourd'hui) se réservent le droit de conserver
les échanges et de les utiliser pour entraîner leurs modèles. Le consentement
est versionné : si le texte du warning change, il faut reconsentir.

Le routeur choisit la première lane disponible dans l'ordre de ``position``
en écartant celles dont le quota journalier est épuisé ou qui sont en
cooldown (429 récent). Les clés vivent exclusivement dans les settings ;
une lane sans clé configurée est invisible.

Réutilise ``AgentDiscoveryQuota`` comme compteur quotidien par utilisateur :
même forme (creator_id + date), même sémantique « budget plateforme » —
le mode gratuit a simplement son propre plafond dans les settings.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import NamedTuple

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.agent_discovery_quota import AgentDiscoveryQuota
from app.models.agent_lane import AgentGratuitConsent, AgentLane, AgentLaneUsage
from app.models.agent_provider import AgentProvider
from app.services import agent_repli

#: Version du texte du warning. Incrementer a chaque changement de fond :
#: un utilisateur qui a consenti a v1 ne couvre pas v2.
VERSION_WARNING = "2026-08-23-v1"

#: Duree du cooldown pose quand une lane renvoie un 429.
COOLDOWN_MINUTES = 10

#: Cooldown d'une lane dont la cle elle-meme est refusee (401/403). Reessayer
#: une cle revoquee toutes les dix minutes ne la ressuscite pas : ca noie la
#: vraie cause sous des echecs identiques, ce qui a coute une semaine de
#: diagnostic en aout 2026.
COOLDOWN_CLE_MINUTES = 120

#: Modeles gratuits proposables, par fournisseur. Le choix manuel (PUT
#: /modeles) et la validation du seed s'y restreignent : pas de modele payant
#: accessible par erreur sur la cle gratuite.
MODELES_GRATUITS: dict[str, dict[str, str]] = {
    "glm-4.7-flash": {"fournisseur": "zai", "label": "GLM 4.7 Flash"},
    "glm-4.5-flash": {"fournisseur": "zai", "label": "GLM 4.5 Flash"},
}


def _maintenant() -> datetime:
    """L'instant courant en UTC, sans fuseau attache.

    Les colonnes de ce module sont des `TIMESTAMP WITHOUT TIME ZONE`. Postgres
    refuse un datetime « aware » sur une telle colonne (`can't subtract
    offset-naive and offset-aware datetimes`), la ou SQLite l'accepte : le
    defaut ne se voit qu'en production, jamais dans les tests.
    """
    return datetime.now(UTC).replace(tzinfo=None)


class ErreurQuotaGratuit(Exception):  # noqa: N818
    """Quota quotidien gratuit de l'utilisateur epuise."""

    def __init__(self, quota: int) -> None:
        self.quota = quota
        super().__init__(f"Quota gratuit epuise ({quota} messages/jour).")


class LaneActive(NamedTuple):
    """Une lane retenue par le routeur, prete a servir un tour."""

    lane: AgentLane
    provider: AgentProvider  # transient, jamais insere en base


class Reaction(NamedTuple):
    """Ce qu'il faut faire d'une lane apres un echec du fournisseur."""

    #: Duree du repos a poser, ou None pour ne pas toucher a la lane.
    cooldown_minutes: int | None
    #: La cle est refusee (revoquee, expiree, sans droit sur le modele). Le
    #: createur doit l'apprendre : aucun delai ne repare ce cas.
    cle_refusee: bool


def reagir(statut: int | None, message: str) -> Reaction:
    """Classe un echec de lane, par statut HTTP plutot que par mots du message.

    Trois cas se ressemblent dans le texte et n'appellent pas la meme reponse :
    un pic de charge passe tout seul, une cle revoquee jamais, et un contenu
    refuse ne dit rien sur la sante de la lane. Les confondre, c'est mettre au
    repos une lane qui va bien, ou reessayer indefiniment une cle morte.

    Sans preuve (ni statut HTTP, ni motif reconnu), on ne touche a rien : une
    exception levee par notre propre code n'est pas une panne du fournisseur.
    """
    if statut is None and not agent_repli.motif_reconnu(message):
        return Reaction(None, False)
    decision = agent_repli.classer(statut, message)
    if decision.verdict is agent_repli.Verdict.ABANDONNER:
        if statut in (401, 403):
            return Reaction(COOLDOWN_CLE_MINUTES, True)
        # Demande refusee ou malformee : la lane est saine, la masquer derriere
        # « fournisseur indisponible » cacherait au createur ce qui cloche.
        return Reaction(None, False)
    return Reaction(COOLDOWN_MINUTES, False)


def cle_lane(slug: str, settings: Settings | None = None) -> str:
    """Cle API d'une lane depuis les settings (jamais en base).

    Toutes les lanes Z.ai (`zai`, `zai-alt`, ...) partagent la meme cle :
    le slug ne fait que distinguer les couples (endpoint, modele) que la
    rotation parcourt.
    """
    s = settings or get_settings()
    if slug == "zai" or slug.startswith("zai-"):
        return s.agent_gratuit_zai_api_key
    return ""


def mode_disponible(settings: Settings | None = None) -> bool:
    """Le mode existe-t-il sur cette instance ? (active ET au moins une cle)"""
    s = settings or get_settings()
    return bool(s.agent_gratuit_enabled and cle_lane("zai", s))


def _chiffrer_cle(api_key: str) -> str:
    from app.crypto.keygen import KeyManager

    return KeyManager(get_settings().master_encryption_key).encrypt_private_key(api_key)


def _provider_transient(lane: AgentLane, settings: Settings | None = None) -> AgentProvider:
    """Construit le provider ephemere qui porte la cle serveur.

    NE PAS inserer en base : valable le temps d'un appel a ``boucle``,
    exactement comme ``resoudre_provider_decouverte``.
    """
    s = settings or get_settings()
    provider = AgentProvider()
    provider.id = uuid.uuid4()
    # Valeur sentinelle pour que rien ne puisse confondre ce provider ephemere
    # avec le compte d'un vrai createur. Tout code qui persistait ce provider
    # creerait un enregistrement orphelin avec un faux creator_id : on l'interdit
    # a la source en marquant l'instance et en le verifiant a la sortie.
    provider.creator_id = uuid.UUID(int=0)
    provider._est_transient = True
    provider.provider = lane.provider_kind
    provider.display_name = f"Gratuit · {lane.label_public}"
    provider.base_url = lane.base_url
    provider.model = lane.model
    provider.api_key_enc = _chiffrer_cle(cle_lane(lane.slug, s))
    provider.is_default = True
    return provider


# ---------------------------------------------------------------------------
# Consentement
# ---------------------------------------------------------------------------


async def etat_consentement(
    db: AsyncSession, creator_id: uuid.UUID, settings: Settings | None = None
) -> dict:
    """Etat expose a l'UI : disponible sur l'instance ? active pour cet utilisateur ?"""
    s = settings or get_settings()
    row = await db.get(AgentGratuitConsent, str(creator_id))
    actif = bool(row and row.version == VERSION_WARNING)
    # Le nom du fournisseur (et le modele) qui serviraient le prochain tour :
    # l'UI les affiche a la place de la cle et du choix de modele pour ne pas
    # suggerer qu'ils comptent.
    fournisseur = None
    modele = None
    if actif:
        lane_active = await choisir_lane(db, s)
        if lane_active is not None:
            fournisseur = lane_active.lane.label_public
            modele = lane_active.lane.model
    return {
        "disponible": mode_disponible(s),
        "actif": actif,
        "version_warning": VERSION_WARNING,
        "fournisseur_actuel": fournisseur,
        "modele_actuel": modele,
    }


async def est_consentant(db: AsyncSession, creator_id: uuid.UUID) -> bool:
    row = await db.get(AgentGratuitConsent, str(creator_id))
    return bool(row and row.version == VERSION_WARNING)


# ---------------------------------------------------------------------------
# Choix manuel du modele (catalogue + lane primaire)
# ---------------------------------------------------------------------------


async def liste_modeles(db: AsyncSession) -> list[dict]:
    """Catalogue proposable, annote de l'etat des lanes connues.

    Un modele du catalogue sans lane en base reste listable (l'UI peut le
    proposer ; il sera servi si une lane le porte) mais marque non actif.
    Le role primaire/secours suit le slug (`zai` vs `zai-*`).

    Les lanes sont parcourues, jamais indexees par modele : deux lanes peuvent
    porter le meme modele, et un `{lane.model: lane}` en perdrait une en
    silence. C'est arrive en production, ou l'interface annoncait « secours »
    un modele que plus aucune lane ne portait.
    """
    lignes = (
        (await db.execute(select(AgentLane).where(AgentLane.slug.like("zai%")))).scalars().all()
    )
    sortie: list[dict] = []
    for model, meta in MODELES_GRATUITS.items():
        if meta["fournisseur"] != "zai":
            continue
        porteuses = [lane for lane in lignes if lane.model == model]
        primaire = next((lane for lane in porteuses if lane.slug == "zai"), None)
        retenue = primaire or (porteuses[0] if porteuses else None)
        sortie.append(
            {
                "model": model,
                "label": meta["label"],
                "role": "primaire" if primaire is not None else "secours",
                "actif": retenue is not None,
                "slug": retenue.slug if retenue is not None else None,
            }
        )
    return sortie


async def definir_modele_primaire(db: AsyncSession, model: str) -> dict:
    """Pointe la lane primaire (`zai`) sur un modele du catalogue.

    Le secours (`zai-alt`) n'est deplace que s'il porterait desormais le meme
    modele que le primaire : meme endpoint, meme cle, meme modele, il ne
    replierait alors sur rien et reproduirait le refus a l'identique. C'est
    l'etat dans lequel la production se trouvait le 2026-08-31.

    ValueError si le modele est inconnu du catalogue : jamais de modele payant
    sur la cle gratuite.
    """
    meta = MODELES_GRATUITS.get(model)
    if meta is None or meta["fournisseur"] != "zai":
        raise ValueError("modele_inconnu")
    lane = (await db.execute(select(AgentLane).where(AgentLane.slug == "zai"))).scalar_one_or_none()
    if lane is None:
        raise ValueError("lane_primaire_absente")
    lane.model = model
    deplace = await _ecarter_les_secours(db, model)
    await db.commit()
    return {"model": lane.model, "label": meta["label"], "slug": lane.slug, "secours": deplace}


async def _ecarter_les_secours(db: AsyncSession, model_primaire: str) -> list[dict[str, str]]:
    """Deplace les lanes de secours qui portent le modele du primaire.

    Ne commite pas : appele dans la transaction de son appelant.
    """
    autres = [
        m
        for m, meta in MODELES_GRATUITS.items()
        if m != model_primaire and meta["fournisseur"] == "zai"
    ]
    if not autres:
        return []
    secours = (
        (await db.execute(select(AgentLane).where(AgentLane.slug.like("zai-%")))).scalars().all()
    )
    deplacees: list[dict[str, str]] = []
    for lane in secours:
        if lane.model == model_primaire:
            lane.model = autres[0]
            deplacees.append({"slug": lane.slug, "model": lane.model})
    return deplacees


async def donner_consentement(db: AsyncSession, creator_id: uuid.UUID, version: str) -> None:
    """Enregistre le consentement. Refuse une version inconnue (texte perime)."""
    if version != VERSION_WARNING:
        raise ValueError("version_warning_inconnue")
    await db.merge(
        AgentGratuitConsent(
            creator_id=str(creator_id),
            version=version,
            consent_at=_maintenant(),
        )
    )
    await db.commit()


async def retirer_consentement(db: AsyncSession, creator_id: uuid.UUID) -> None:
    row = await db.get(AgentGratuitConsent, str(creator_id))
    if row is not None:
        await db.delete(row)
        await db.commit()


# ---------------------------------------------------------------------------
# Routeur de lanes
# ---------------------------------------------------------------------------


async def lanes_eligibles(db: AsyncSession, settings: Settings | None = None) -> list[LaneActive]:
    """Toutes les lanes utilisables, dans l'ordre ou les essayer.

    Utilisable : active, avec cle, hors quota journalier et hors cooldown.

    La liste entiere et pas seulement sa tete, parce que le cooldown ne repare
    que le tour suivant : sans repli disponible pendant le tour, un 429 sur le
    primaire rendait une erreur au createur alors qu'une seconde lane etait
    prete a repondre.
    """
    s = settings or get_settings()
    result = await db.execute(
        select(AgentLane).where(AgentLane.actif.is_(True)).order_by(AgentLane.position.asc())
    )
    today = date.today()
    now = _maintenant()
    retenues: list[LaneActive] = []
    for lane in result.scalars():
        if not cle_lane(lane.slug, s):
            continue
        usage = (
            await db.execute(
                select(AgentLaneUsage).where(
                    AgentLaneUsage.lane_id == lane.id,
                    AgentLaneUsage.date == today,
                )
            )
        ).scalar_one_or_none()
        if usage is not None:
            if usage.cooldown_until is not None and usage.cooldown_until > now:
                continue
            if lane.rpd_cap is not None and usage.requests_used >= lane.rpd_cap:
                continue
        retenues.append(LaneActive(lane=lane, provider=_provider_transient(lane, s)))
    return retenues


async def choisir_lane(db: AsyncSession, settings: Settings | None = None) -> LaneActive | None:
    """Premiere lane utilisable, ou `None` s'il n'y en a aucune."""
    lanes = await lanes_eligibles(db, settings)
    return lanes[0] if lanes else None


async def consommer_requete(db: AsyncSession, lane: AgentLane) -> None:
    """+1 requete sur la lane du jour. SELECT puis INSERT/UPDATE sequentiels :
    compatible SQLite (tests) et Postgres (prod), quota indicatif."""
    today = date.today()
    usage = (
        await db.execute(
            select(AgentLaneUsage).where(
                AgentLaneUsage.lane_id == lane.id,
                AgentLaneUsage.date == today,
            )
        )
    ).scalar_one_or_none()
    if usage is None:
        db.add(AgentLaneUsage(id=uuid.uuid4(), lane_id=lane.id, date=today, requests_used=1))
    else:
        await db.execute(
            update(AgentLaneUsage)
            .where(AgentLaneUsage.id == usage.id)
            .values(requests_used=usage.requests_used + 1)
        )
    await db.commit()


async def signaler_echec(
    db: AsyncSession, lane: AgentLane, minutes: int = COOLDOWN_MINUTES
) -> None:
    """Pose un cooldown sur la lane (rate limit, erreur fournisseur).

    Le routeur l'ecartera automatiquement pendant la fenetre ; les autres
    lanes prendront le relais sans intervention.
    """
    echeance = _maintenant() + timedelta(minutes=minutes)
    today = date.today()
    usage = (
        await db.execute(
            select(AgentLaneUsage).where(
                AgentLaneUsage.lane_id == lane.id,
                AgentLaneUsage.date == today,
            )
        )
    ).scalar_one_or_none()
    if usage is None:
        db.add(
            AgentLaneUsage(id=uuid.uuid4(), lane_id=lane.id, date=today, cooldown_until=echeance)
        )
    else:
        await db.execute(
            update(AgentLaneUsage)
            .where(AgentLaneUsage.id == usage.id)
            .values(cooldown_until=echeance)
        )
    await db.commit()


# ---------------------------------------------------------------------------
# Quota quotidien par utilisateur (compteur plateforme partage)
# ---------------------------------------------------------------------------


async def verifier_quota_utilisateur(
    db: AsyncSession, creator_id: uuid.UUID, settings: Settings | None = None
) -> int:
    """Rend le nombre de messages restants aujourd'hui. Leve ErreurQuotaGratuit."""
    s = settings or get_settings()
    quota = s.agent_gratuit_daily_quota_messages
    row = (
        await db.execute(
            select(AgentDiscoveryQuota).where(
                AgentDiscoveryQuota.creator_id == str(creator_id),
                AgentDiscoveryQuota.date == date.today(),
            )
        )
    ).scalar_one_or_none()
    used = row.messages_used if row else 0
    remaining = max(0, quota - used)
    if remaining <= 0:
        raise ErreurQuotaGratuit(quota)
    return remaining


async def consommer_message_utilisateur(db: AsyncSession, creator_id: uuid.UUID) -> None:
    """Incrément atomique du compteur quotidien utilisateur.

    UPSERT PostgreSQL : l'insert et l'incrément sont une seule instruction,
    sans fenêtre entre un SELECT et un UPDATE. Évite la race TOCTOU où deux
    requêtes concurrentes lisaient le même compteur et en écrasaient l'un
    l'autre.
    """
    today = date.today()
    creator_str = str(creator_id)
    stmt = (
        pg_insert(AgentDiscoveryQuota)
        .values(id=uuid.uuid4(), creator_id=creator_str, date=today, messages_used=1)
        .on_conflict_do_update(
            constraint="uq_discovery_quota_creator_date",
            set_={"messages_used": AgentDiscoveryQuota.messages_used + 1},
        )
    )
    await db.execute(stmt)
    await db.commit()


# ---------------------------------------------------------------------------
# Test de la lane (diagnostic, comme « Tester » sur les cles personnelles)
# ---------------------------------------------------------------------------


async def tester_lane(db: AsyncSession, settings: Settings | None = None) -> dict:
    """Ping minimal de la lane qui servirait le prochain tour.

    N'incremente PAS les compteurs : c'est un diagnostic, pas un tour. Le
    ping passe par le meme chemin d'appel que le chat (``_appel_provider``),
    donc il valide aussi le formatage du payload et l'authentification.
    """
    import time

    from app.services import agent as agent_module

    s = settings or get_settings()
    lane_active = await choisir_lane(db, s)
    if lane_active is None:
        return {
            "ok": False,
            "detail": "aucune lane disponible (cle absente, quota lane epuise ou cooldown)",
            "modele": None,
            "latence_ms": None,
        }
    debut = time.perf_counter()
    try:
        reponse = await agent_module._appel_provider(
            lane_active.provider,
            [{"role": "user", "content": "Reponds uniquement : ok"}],
            [],
            transport=None,
        )
    except Exception as exc:  # erreur reseau brute (DNS, TLS, timeout)
        return {
            "ok": False,
            "detail": str(exc)[:300],
            "modele": lane_active.lane.model,
            "latence_ms": int((time.perf_counter() - debut) * 1000),
        }
    latence_ms = int((time.perf_counter() - debut) * 1000)
    if isinstance(reponse, str):
        return {
            "ok": False,
            "detail": reponse[:300],
            "modele": lane_active.lane.model,
            "latence_ms": latence_ms,
        }
    return {
        "ok": True,
        "detail": "reponse recue",
        "modele": lane_active.lane.model,
        "latence_ms": latence_ms,
    }
