"""Fonctions d'ecriture cote MCP.

Une IA connectee au MCP doit pouvoir produire une fiche complete sans
detour par le web : creer un brouillon, y ajouter les sources qu'elle a
lues, coller un extrait verbatim quand elle en tient un, publier. Chacune
de ces fonctions delegue au meme modele que le REST plutot que d'inventer
un chemin parallele : une seule fois la logique metier, une seule fois
les invariants (unicite du slug, propriete de la ressource, capacite
maximale, dedup de source par identite du contenu).

Le retour est volontairement compact : l'agent enchaine `add_source` puis
`add_excerpt` sur des dizaines de references, et charger a chaque appel le
detail complet gaspille sa fenetre de tokens.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from fastmcp.exceptions import ToolError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.biblio_card import BiblioCard, CardStatus
from app.models.source import AuthorKind, Source, SourceCategory, SourceFormat, SourceStance
from app.models.source_excerpt import SourceExcerpt
from app.models.user import User
from app.schemas.biblio_card import CardCreate, ContentType, Platform, Visibility
from app.services.card import CardService
from app.services.card_link import effective_linked_card_id
from app.services.content_identity import extract_doi, normalize_url
from app.services.excerpt_guards import LONGUEUR_MIN_AUTONOME_MOTS, passage_a_besoin_de_contexte
from app.services.excerpt_indexing import indexer_sans_bruit
from app.services.wayback import horodatage_wayback

# Meme limite que l'endpoint REST : au dela, l'agent noie sa fenetre et le
# lecteur perd de vue le fil du passage.
_EXTRAITS_MAX_PAR_SOURCE = 12


_ENUMS_VOISINS: dict[str, list[tuple[str, type[Enum]]]] = {
    "category": [("content_type", ContentType), ("platform", Platform)],
    "content_type": [("category", SourceCategory)],
    "platform": [("category", SourceCategory), ("content_type", ContentType)],
    "author_kind": [("category", SourceCategory)],
    "format": [("category", SourceCategory)],
}


def _valeur_enum(champ: str, valeur: str | None, cls: type[Enum]) -> str | None:
    """Valide `valeur` contre l'enum et rend la valeur canonique (None si vide).

    Les colonnes `format`/`category`/`author_kind`/`stance` sont des VARCHAR
    libres en base : une valeur hors vocabulaire s'y inscrit sans erreur, puis
    fait echouer TOUTE relecture de la fiche -- `SourceResponse` valide les enums
    a la sortie, et une seule source fautive repond 500 sur la vue publique,
    l'editeur et le graphe. Lecon de la fiche creatine (2026-08-21) : valider a
    l'entree comme `create_card` le fait deja, en rendant a l'agent la liste
    exacte de ce qui est acceptable pour qu'il corrige seul.
    """
    if valeur is None or valeur == "":
        return None
    try:
        canonique = cls(valeur).value
        return canonique if isinstance(canonique, str) else str(canonique)
    except ValueError:
        autorisees = ", ".join(m.value for m in cls)
        # Verifier si la valeur appartient a un enum voisin pour guider la correction.
        for champ_voisin, cls_voisine in _ENUMS_VOISINS.get(champ, []):
            try:
                cls_voisine(valeur)
                raise ToolError(
                    f"{champ}={valeur!r} : cette valeur appartient a {champ_voisin!r}, "
                    f"pas a {champ!r}. Pour {champ!r}, utilisez : {autorisees}."
                ) from None
            except (ValueError, ToolError) as exc:
                if isinstance(exc, ToolError):
                    raise
        raise ToolError(
            f"{champ}={valeur!r} : valeur inconnue. Valeurs acceptees : {autorisees}."
        ) from None


def _valeur_date(valeur: str | None) -> datetime | None:
    """Parse une date de publication souple : ``2016``, ``2016-03``, ``2016-03-15``.

    Une chaine vide ou None rend None (silence explicite, permet aussi
    d'effacer via `update_source`). Un format illisible leve ToolError tout
    de suite : une date perdue en silence serait une source sans annee,
    exactement le defaut que ce champ existe pour reparer.
    """
    if valeur is None:
        return None
    texte = valeur.strip()
    if not texte:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(texte, fmt)
        except ValueError:
            continue
    raise ToolError(
        f"published_at={valeur!r} : format illisible. Formats acceptes : 2016, 2016-03, 2016-03-15."
    )


async def _fiche_du_createur(db: AsyncSession, user: User, slug: str) -> BiblioCard:
    """La fiche `slug` de `user`. Leve si elle n'existe pas ou appartient a autrui.

    On refuse de dire « existe mais pas a vous » : cela revelerait indirectement
    l'existence d'une fiche privee d'un autre createur.
    """
    stmt = select(BiblioCard).where(
        BiblioCard.user_id == user.id,
        BiblioCard.slug == slug,
        BiblioCard.deleted_at.is_(None),
    )
    card = (await db.execute(stmt)).scalar_one_or_none()
    if card is None:
        raise ToolError(f"Aucune fiche {slug!r} chez {user.username}.")
    return card


def _identite(url: str | None, doi: str | None) -> str | None:
    """La cle d'identite d'une source : DOI en priorite, URL normalisee sinon."""
    if key := extract_doi(doi) or extract_doi(url):
        return f"doi:{key}"
    if norm := normalize_url(url):
        return f"url:{norm}"
    return None


async def _identites_deja_citees(db: AsyncSession, card_id: UUID) -> set[str]:
    stmt = select(Source.url, Source.doi).where(
        Source.biblio_card_id == card_id, Source.deleted_at.is_(None)
    )
    return {k for (u, d) in (await db.execute(stmt)).all() if (k := _identite(u, d))}


async def _source_du_createur(db: AsyncSession, user: User, source_id: str) -> Source:
    """La source `source_id`, si elle appartient a une fiche du createur.

    Meme discretion que `_fiche_du_createur` : on refuse de dire « existe mais
    pas a vous », qui revelerait indirectement l'existence de sources d'autrui.
    """
    try:
        sid = UUID(source_id)
    except ValueError as exc:
        raise ToolError(f"Identifiant de source invalide : {source_id!r}.") from exc
    stmt = (
        select(Source)
        .join(BiblioCard, Source.biblio_card_id == BiblioCard.id)
        .where(
            Source.id == sid,
            Source.deleted_at.is_(None),
            BiblioCard.user_id == user.id,
            BiblioCard.deleted_at.is_(None),
        )
    )
    source = (await db.execute(stmt)).scalar_one_or_none()
    if source is None:
        raise ToolError(f"Aucune source {source_id!r} chez {user.username}.")
    return source


async def create_card(
    db: AsyncSession,
    user: User,
    *,
    slug: str,
    title: str,
    content_url: str | None = None,
    description: str | None = None,
    content_authors: str | None = None,
    platform: str = "other",
    content_type: str = "article",
    visibility: str = "public",
) -> dict[str, Any]:
    """Cree un brouillon. La publication est un geste distinct (`publish_card`)."""
    try:
        payload = CardCreate(
            slug=slug,
            title=title,
            description=description,
            content_url=content_url,
            content_authors=content_authors,
            platform=Platform(platform),
            content_type=ContentType(content_type),
            visibility=Visibility(visibility),
        )
    except ValueError as exc:
        # Un slug invalide ou une enumeration hors du vocabulaire est un
        # message que l'agent peut lire et corriger : le lui rendre en clair.
        raise ToolError(str(exc)) from exc
    service = CardService(db)
    #: Pas de contrainte d'unicite en base : c'est l'endpoint REST qui refuse
    #: le doublon, et le MCP doit le refuser pareil.
    if await service.get_card_by_slug(user.username, payload.slug, published_only=False):
        raise ToolError(f"Une fiche {slug!r} existe deja chez {user.username}.")
    try:
        card = await service.create_card(user.id, payload)
    except IntegrityError as exc:
        await db.rollback()
        raise ToolError(f"Une fiche {slug!r} existe deja chez {user.username}.") from exc
    return {
        "creator": user.username,
        "slug": card.slug,
        "status": card.status,
        "public_url_when_published": (
            f"https://philum-eight.vercel.app/@{user.username}/{card.slug}"
        ),
    }


async def add_source(
    db: AsyncSession,
    user: User,
    *,
    card_slug: str,
    url: str = "",
    title: str | None = None,
    authors: str | None = None,
    doi: str | None = None,
    category: str = "article-scientifique",
    author_kind: str = "chercheur",
    format: str = "texte",
    stance: str | None = None,
    annotation: str | None = None,
    journal: str | None = None,
    published_at: str | None = None,
    archive_url: str | None = None,
) -> dict[str, Any]:
    """Ajoute une source a la fiche. Ne declenche pas l'archivage automatique :
    un agent qui tient une capture Wayback peut la donner via `archive_url`,
    sinon la source reste `pending` et sera archivee au prochain passage cote UI.

    `published_at` : date de publication de la source, ``2016``, ``2016-03``
    ou ``2016-03-15``. A renseigner des que la source en porte une : une
    bibliographie sans dates n'est pas une bibliographie.
    """
    card = await _fiche_du_createur(db, user, card_slug)

    cle = _identite(url, doi)
    if cle and cle in await _identites_deja_citees(db, card.id):
        raise ToolError(f"Cette source figure deja dans {card_slug!r}.")

    max_position = await db.scalar(
        select(func.max(Source.position)).where(Source.biblio_card_id == card.id)
    )
    manual_archive = (archive_url or "").strip() or None

    # Validation enum avant ecriture (cf. _valeur_enum) : refuser ici plutot
    # que de rendre la fiche entiere illisible a la prochaine lecture.
    fmt = _valeur_enum("format", format, SourceFormat) or SourceFormat.TEXTE.value
    categorie = (
        _valeur_enum("category", category, SourceCategory)
        or SourceCategory.ARTICLE_SCIENTIFIQUE.value
    )
    nature_auteur = (
        _valeur_enum("author_kind", author_kind, AuthorKind) or AuthorKind.CHERCHEUR.value
    )
    position_declaree = _valeur_enum("stance", stance, SourceStance)
    date_publication = _valeur_date(published_at)

    try:
        linked_card_id = await effective_linked_card_id(
            db,
            chosen=None,
            url=url,
            user_id=user.id,
            current_card_id=card.id,
            doi=doi,
        )
    except ValueError as exc:
        raise ToolError(str(exc)) from exc

    source = Source(
        biblio_card_id=card.id,
        position=(max_position or 0) + 1,
        url=url,
        title=title,
        authors=authors,
        format=fmt,
        category=categorie,
        author_kind=nature_auteur,
        stance=position_declaree,
        annotation=annotation,
        journal=journal,
        published_at=date_publication,
        doi=doi,
        linked_card_id=linked_card_id,
        archive_url=manual_archive,
        archive_status="archived" if manual_archive else "pending",
        archive_timestamp=horodatage_wayback(manual_archive),
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return {
        "id": str(source.id),
        "card_slug": card.slug,
        "position": source.position,
        "linked_card_id": str(source.linked_card_id) if source.linked_card_id else None,
    }


async def add_excerpt(
    db: AsyncSession,
    user: User,
    *,
    source_id: str,
    text: str,
    title: str | None = None,
    context: str | None = None,
) -> dict[str, Any]:
    """Ajoute un verbatim a une source. Marque `annotated_by_ai=True` : cette
    reponse porte les extraits qu'un modele a produits, le distinguer preserve
    la separation entre ce que la source dit et ce qu'une IA en dit."""
    source = await _source_du_createur(db, user, source_id)

    corps = (text or "").strip()
    if not corps:
        raise ToolError("Un extrait vide ne cite rien.")

    # Garde-fou anti extrait hors-contexte : un extrait court qui commence
    # par un pronom ou un demonstratif sans referent visible devient un
    # contresens cite seul (« cela ameliore la memoire » sans « cela »
    # nomme). L'agent doit alors soit elargir le passage pour inclure
    # l'antecedent, soit fournir une mise en situation explicite via
    # `context` (qui nomme le referent en clair).
    contexte_donne = (context or "").strip()
    if (
        len(corps.split()) < LONGUEUR_MIN_AUTONOME_MOTS
        and passage_a_besoin_de_contexte(corps)
        and not contexte_donne
    ):
        raise ToolError(
            "Extrait trop court et referentiel (commence par « cela »/« ces »/etc. "
            "sans antecedent visible). Soit elargir l'extrait pour inclure la "
            "phrase qui donne le sens, soit fournir un `context` qui nomme en "
            "clair ce a quoi renvoient les pronoms et les demonstratifs. Cite "
            "seul, un tel extrait pousse au contresens."
        )

    count = await db.scalar(
        select(func.count()).select_from(SourceExcerpt).where(SourceExcerpt.source_id == source.id)
    )
    if (count or 0) >= _EXTRAITS_MAX_PAR_SOURCE:
        raise ToolError(f"Une source ne porte pas plus de {_EXTRAITS_MAX_PAR_SOURCE} extraits.")

    max_pos = await db.scalar(
        select(func.max(SourceExcerpt.position)).where(SourceExcerpt.source_id == source.id)
    )
    excerpt = SourceExcerpt(
        source_id=source.id,
        position=(max_pos or 0) + 1,
        text=corps,
        title=(title or "").strip() or None,
        context=(context or "").strip() or None,
        # L'agent qui appelle ce tool est une IA : le dire au consommateur.
        suggested_by_ai=True,
        annotated_by_ai=True,
    )
    db.add(excerpt)
    await db.commit()
    await db.refresh(excerpt)
    await indexer_sans_bruit(db, [excerpt])
    return {
        "id": str(excerpt.id),
        "source_id": str(source.id),
        "position": excerpt.position,
    }


#: Meme borne que le schema CardBase.content_text. 500 000 caracteres = un
#: roman entier ; au-dela, c'est un corpus, sa voie est le decoupage en fiches.
_MAX_CONTENT_TEXT = 500_000


async def set_content_text(
    db: AsyncSession,
    user: User,
    *,
    card_slug: str,
    text: str,
    confirm_publication_rights: bool,
) -> dict[str, Any]:
    """Ecrase le texte integral de la fiche (sans confirmation, le precedent est perdu).

    Le texte est rendu tel quel sur la fiche publique. Un agent qui l'appelle
    a la place de l'utilisateur porte la meme responsabilite que lui : il doit
    savoir avoir le droit de publier ce texte (contenu propre, libre de droit,
    ou extrait sous droit de citation). Le drapeau `confirm_publication_rights`
    exige que ce choix soit explicite -- passer `False` refuse la pose, passer
    `True` engage la responsabilite du compte qui appelle.

    Chaine vide = retire le texte precedemment pose (l'affichage sur la fiche
    publique disparait).
    """
    if not confirm_publication_rights:
        raise ToolError(
            "Passer confirm_publication_rights=true pour publier ce texte. "
            "L'agent doit avoir constate que le contenu est publiable (contenu "
            "propre, libre de droit, ou droit de citation dans les limites)."
        )
    if len(text) > _MAX_CONTENT_TEXT:
        raise ToolError(
            f"Texte trop long ({len(text)} caracteres, maximum {_MAX_CONTENT_TEXT:_}). "
            "Decoupez le contenu en plusieurs fiches (une par chapitre / episode)."
        )
    card = await _fiche_du_createur(db, user, card_slug)
    card.content_text = text or None
    await db.commit()
    return {
        "creator": user.username,
        "slug": card.slug,
        "content_text_length": len(text),
        "content_text_cleared": not bool(text),
    }


async def publish_card(db: AsyncSession, user: User, *, slug: str) -> dict[str, Any]:
    """Rend la fiche visible sur le web. Republier une fiche deja publique est
    un no-op cote feed : le registre du premier passage au public reste unique."""
    stmt = (
        select(BiblioCard)
        .options(selectinload(BiblioCard.user))
        .where(
            BiblioCard.user_id == user.id,
            BiblioCard.slug == slug,
            BiblioCard.deleted_at.is_(None),
        )
    )
    card = (await db.execute(stmt)).scalar_one_or_none()
    if card is None:
        raise ToolError(f"Aucune fiche {slug!r} chez {user.username}.")
    service = CardService(db)
    published = await service.publish_card(card)
    return {
        "creator": user.username,
        "slug": slug,
        "status": CardStatus.PUBLISHED.value,
        "published_at": published["published_at"].isoformat(),
        "public_url": published["public_url"],
    }


# ---------------------------------------------------------------------------
# Mutations d'une fiche existante : corriger sans avoir a tout redetruire.
#
# L'API REST expose deja PATCH et DELETE sur les cartes, sources et extraits ;
# ces tools les rendent accessibles au MCP. Sans eux, un agent qui detecte une
# erreur apres publication (annotation a reformuler, source hors sujet, extrait
# posé sans le bon `context`) devait rebuild toute la fiche par delete+recreate,
# ce qui cassait les UUID (perdus par les eventuels liens externes) et laissait
# la fiche vide pendant l'operation.
# ---------------------------------------------------------------------------


async def update_card(
    db: AsyncSession,
    user: User,
    *,
    slug: str,
    title: str | None = None,
    description: str | None = None,
    content_url: str | None = None,
    content_authors: str | None = None,
    platform: str | None = None,
    content_type: str | None = None,
    visibility: str | None = None,
) -> dict[str, Any]:
    """Corrige les champs editoriaux d'une fiche existante.

    Un champ laisse a `None` reste inchange. Passer explicitement une chaine
    vide sur `content_authors` retire les auteurs (rend la main a la
    reconstitution depuis les fiches citantes). Le slug ne se change pas ici :
    l'identifiant public d'une fiche fait autorite dans les liens deja emis.
    """
    card = await _fiche_du_createur(db, user, slug)
    if title is not None:
        card.title = title
    if description is not None:
        card.description = description
    if content_url is not None:
        card.content_url = content_url or None
    if content_authors is not None:
        card.content_authors = content_authors.strip() or None
    if platform is not None:
        try:
            card.platform = Platform(platform).value
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
    if content_type is not None:
        try:
            card.content_type = ContentType(content_type).value
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
    if visibility is not None:
        try:
            card.visibility = Visibility(visibility).value
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
    await db.commit()
    return {
        "creator": user.username,
        "slug": card.slug,
        "title": card.title,
        "description": card.description,
        "visibility": card.visibility,
    }


async def update_source(
    db: AsyncSession,
    user: User,
    *,
    source_id: str,
    title: str | None = None,
    authors: str | None = None,
    doi: str | None = None,
    journal: str | None = None,
    category: str | None = None,
    author_kind: str | None = None,
    format: str | None = None,
    stance: str | None = None,
    annotation: str | None = None,
    is_pivot: bool | None = None,
    published_at: str | None = None,
    archive_url: str | None = None,
) -> dict[str, Any]:
    """Corrige les champs edituriaux d'une source existante.

    L'URL d'une source est immuable (elle fait autorite dans les liens deja
    emis) : pour changer l'URL, `delete_source` puis `add_source`. Un champ
    laisse a `None` reste inchange. Passer une chaine vide sur `archive_url`
    retire l'archive et remet le statut en `pending`. Sur `published_at`,
    une chaine vide efface la date ; formats : 2016, 2016-03, 2016-03-15.
    """
    source = await _source_du_createur(db, user, source_id)
    if title is not None:
        source.title = title or None
    if authors is not None:
        source.authors = authors or None
    if doi is not None:
        source.doi = doi or None
    if journal is not None:
        source.journal = journal or None
    if category is not None:
        source.category = (
            _valeur_enum("category", category, SourceCategory)
            or SourceCategory.ARTICLE_SCIENTIFIQUE.value
        )
    if author_kind is not None:
        source.author_kind = (
            _valeur_enum("author_kind", author_kind, AuthorKind) or AuthorKind.CHERCHEUR.value
        )
    if format is not None:
        source.format = _valeur_enum("format", format, SourceFormat) or SourceFormat.TEXTE.value
    if stance is not None:
        # Chaine vide = retire la position declaree, revient au silence
        # explicite.
        source.stance = _valeur_enum("stance", stance, SourceStance)
    if annotation is not None:
        source.annotation = annotation or None
    if published_at is not None:
        source.published_at = _valeur_date(published_at)
    if is_pivot is not None:
        source.is_pivot = is_pivot
    if archive_url is not None:
        new_archive = (archive_url or "").strip() or None
        source.archive_url = new_archive
        if new_archive:
            source.archive_status = "archived"
            source.archive_timestamp = horodatage_wayback(new_archive)
        else:
            source.archive_status = "pending"
            source.archive_timestamp = None
    await db.commit()
    await db.refresh(source)
    return {
        "id": str(source.id),
        "title": source.title,
        "stance": source.stance,
        "is_pivot": source.is_pivot,
        "annotation": source.annotation,
    }


async def delete_source(db: AsyncSession, user: User, *, source_id: str) -> dict[str, Any]:
    """Retire une source de la fiche ; tous ses extraits deviennent invisibles avec elle (soft-delete).

    La ligne est conservee en base pour ne pas casser les references
    historiques (citations entrantes, attestations horodatees) : elle
    disparait juste des vues publiques. Les extraits associes restent
    en base mais ne s'affichent plus. Preferer `update_source` pour corriger
    une source ; utiliser `delete_source` uniquement si la reference est hors sujet.
    """
    from datetime import datetime

    source = await _source_du_createur(db, user, source_id)
    source.deleted_at = datetime.now().replace(tzinfo=None)
    await db.commit()
    return {"id": str(source.id), "deleted": True}


async def delete_excerpt(
    db: AsyncSession, user: User, *, source_id: str, excerpt_id: str
) -> dict[str, Any]:
    """Supprime physiquement un extrait (irreversible). Preferer `update_excerpt` pour corriger.

    Un extrait n'a pas de citation entrante propre : le retirer n'invalide
    aucune reference externe. La suppression est physique (pas de corbeille).
    Pour corriger le texte, utiliser `update_excerpt` qui remet la verification
    a zero sans perdre l'historique de la source.
    """
    try:
        eid = UUID(excerpt_id)
    except ValueError as exc:
        raise ToolError(f"Identifiant d'extrait invalide : {excerpt_id!r}.") from exc
    source = await _source_du_createur(db, user, source_id)
    excerpt = await db.scalar(
        select(SourceExcerpt).where(SourceExcerpt.id == eid, SourceExcerpt.source_id == source.id)
    )
    if excerpt is None:
        raise ToolError(f"Aucun extrait {excerpt_id!r} sur la source {source_id!r}.")
    await db.delete(excerpt)
    await db.commit()
    return {"excerpt_id": excerpt_id, "source_id": source_id, "deleted": True}


async def update_excerpt(
    db: AsyncSession,
    user: User,
    *,
    source_id: str,
    excerpt_id: str,
    text: str | None = None,
    title: str | None = None,
    context: str | None = None,
) -> dict[str, Any]:
    """Corrige le texte, le titre ou le contexte d'un extrait ; modifier le texte annule la verification.

    Modifier `text` remet verified_at, verified_text_source et les ancres a zero :
    le passage verifie n'est plus le meme. Relancer `verify_excerpts` apres
    modification pour reetablir le verdict. Un champ laisse a None reste inchange.
    """
    try:
        eid = UUID(excerpt_id)
    except ValueError as exc:
        raise ToolError(f"Identifiant d'extrait invalide : {excerpt_id!r}.") from exc
    source = await _source_du_createur(db, user, source_id)
    excerpt = await db.scalar(
        select(SourceExcerpt).where(SourceExcerpt.id == eid, SourceExcerpt.source_id == source.id)
    )
    if excerpt is None:
        raise ToolError(f"Aucun extrait {excerpt_id!r} sur la source {source_id!r}.")
    text_modifie = False
    if text is not None:
        corps = text.strip()
        if not corps:
            raise ToolError("Un extrait vide ne cite rien.")
        excerpt.text = corps
        text_modifie = True
    if title is not None:
        excerpt.title = title.strip() or None
    if context is not None:
        excerpt.context = context.strip() or None
    if text_modifie:
        excerpt.verified_at = None
        excerpt.verified_status = None
        excerpt.verified_text_source = None
        excerpt.anchor_prefix = None
        excerpt.anchor_suffix = None
        excerpt.anchor_offset = None
    await db.commit()
    await db.refresh(excerpt)
    return {
        "id": str(excerpt.id),
        "source_id": source_id,
        "text": excerpt.text,
        "title": excerpt.title,
        "context": excerpt.context,
        "verified_status": excerpt.verified_status,
    }


async def verify_excerpts(
    db: AsyncSession,
    user: User,
    *,
    source_id: str,
    provided_text: str | None = None,
) -> dict[str, Any]:
    """Relit chaque extrait vs le texte de la source, fait passer les verdicts.

    Sans cette passe, la fiche affirme qu'une source dit quelque chose sans
    que rien ne l'ait jamais confirme (les extraits restent `verified_status=null`,
    la fiche publique les rend « non verifiee »). Chaque extrait ressort avec
    un statut :

    - `found` : passage retrouve verbatim dans la page ;
    - `moved` : passage retrouve mais les mots ont legerement bouge ;
    - `missing` : passage introuvable dans la page (accuse la citation) ;
    - `unreadable` : la page ne rend rien (accuse le site, pas la citation).

    `provided_text` optionnel : quand la page est bloquee anti-bot (403 sur
    ScienceDirect, IOP, PubMed), l'agent atteste le texte qu'il a recupere
    ailleurs (NASA ADS, Semantic Scholar, Crossref abstract). Le champ
    `text_source` de la reponse dit d'ou vient le texte de reference.
    """
    from datetime import UTC, datetime

    from app.services.excerpt_anchor import Selecteurs, ancrer

    source = await _source_du_createur(db, user, source_id)
    excerpts = list(
        (
            await db.scalars(
                select(SourceExcerpt)
                .where(SourceExcerpt.source_id == source.id)
                .order_by(SourceExcerpt.position)
            )
        ).all()
    )
    if not excerpts:
        return {
            "source_id": source_id,
            "checks": [],
            "page_text_length": 0,
            "text_source": "fetched",
        }

    page_text = (provided_text or "").strip()
    provenance = "provided" if page_text else "fetched"
    # Un texte fourni par la personne est tenu pour entier : c'est elle qui a
    # choisi ce qu'elle donnait a relire. Sans texte fourni, on lit la page.
    complet = True
    if not page_text:
        from app.api.v1.endpoints.excerpts import _texte_de_la_source

        page_text, _refuse, complet = await _texte_de_la_source(source.url)

    releve_le = datetime.now(UTC).replace(tzinfo=None)
    checks: list[dict[str, Any]] = []

    if not page_text.strip():
        for extrait in excerpts:
            extrait.verified_at = releve_le
            extrait.verified_status = "unreadable"
            extrait.verified_text_source = provenance
            checks.append({"excerpt_id": str(extrait.id), "status": "unreadable"})
        await db.commit()
        return {
            "source_id": source_id,
            "checks": checks,
            "page_text_length": 0,
            "text_source": provenance,
        }

    for extrait in excerpts:
        ancrage = ancrer(
            page_text,
            Selecteurs(
                quote=extrait.text,
                prefix=extrait.anchor_prefix or "",
                suffix=extrait.anchor_suffix or "",
                offset=extrait.anchor_offset,
            ),
        )
        extrait.verified_at = releve_le
        extrait.verified_text_source = provenance
        if ancrage is None:
            verdict = "missing" if complet else "unreadable"
            extrait.verified_status = verdict
            checks.append({"excerpt_id": str(extrait.id), "status": verdict})
            continue
        extrait.verified_status = "found" if ancrage.exact else "moved"
        checks.append(
            {
                "excerpt_id": str(extrait.id),
                "status": extrait.verified_status,
                "start": ancrage.start,
                "end": ancrage.end,
            }
        )
    await db.commit()
    return {
        "source_id": source_id,
        "checks": checks,
        "page_text_length": len(page_text),
        "text_source": provenance,
    }


async def list_connections(db: AsyncSession, user: User, *, card_slug: str) -> dict[str, Any]:
    """Liste les connexions entrantes et sortantes d'une fiche.

    `outgoing` : les sources de la fiche qui designent une autre fiche Philum
    (le geste de citation partant de moi). `incoming` : les sources d'autres
    fiches qui me citent (que je vois mais ne peux pas modifier). Chaque
    entree porte `confirmed` (le lien a-t-il ete valide par son auteur ?) et
    `editable` (puis-je le trancher ?).
    """
    card = await _fiche_du_createur(db, user, card_slug)

    outgoing = await db.execute(
        select(Source, BiblioCard, User)
        .join(BiblioCard, Source.linked_card_id == BiblioCard.id)
        .join(User, BiblioCard.user_id == User.id)
        .where(
            Source.biblio_card_id == card.id,
            Source.linked_card_id.is_not(None),
            Source.deleted_at.is_(None),
        )
        .order_by(Source.position)
    )
    incoming = await db.execute(
        select(Source, BiblioCard, User)
        .join(BiblioCard, Source.biblio_card_id == BiblioCard.id)
        .join(User, BiblioCard.user_id == User.id)
        .where(
            Source.linked_card_id == card.id,
            Source.deleted_at.is_(None),
            BiblioCard.deleted_at.is_(None),
        )
        .order_by(Source.created_at)
    )

    def _row(src: Source, other: BiblioCard, creator: User, editable: bool) -> dict[str, Any]:
        return {
            "source_id": str(src.id),
            "source_title": src.title,
            "source_url": src.url,
            "card_slug": other.slug,
            "card_title": other.title,
            "card_creator_slug": creator.username,
            "confirmed": src.link_confirmed_at is not None,
            "editable": editable,
        }

    return {
        "outgoing": [_row(s, c, u, True) for s, c, u in outgoing.all()],
        "incoming": [_row(s, c, u, False) for s, c, u in incoming.all()],
    }


async def confirm_connection(
    db: AsyncSession, user: User, *, card_slug: str, source_id: str
) -> dict[str, Any]:
    """Confirme qu'une source de la fiche pointe bien vers une fiche Philum.

    Une source peut avoir un `linked_card_id` suggere par le serveur (URL/DOI
    en commun avec une fiche existante) : ce tool le fige comme choix de
    l'auteur. Refuse si la source n'appartient pas a la fiche indiquee, ou si
    la source ne pointe encore vers aucune fiche.
    """
    from datetime import UTC, datetime

    card = await _fiche_du_createur(db, user, card_slug)
    source = await _source_du_createur(db, user, source_id)
    if source.biblio_card_id != card.id:
        raise ToolError(f"La source {source_id!r} n'appartient pas a la fiche {card_slug!r}.")
    if source.linked_card_id is None:
        raise ToolError(f"La source {source_id!r} ne designe aucune fiche.")
    source.link_confirmed_at = datetime.now(UTC).replace(tzinfo=None)
    linked = await db.get(BiblioCard, source.linked_card_id)
    if linked is None:
        raise ToolError("La fiche designee n'existe plus.")
    await db.commit()
    return {
        "source_id": source_id,
        "card_slug": card.slug,
        "linked_card_slug": linked.slug,
        "confirmed": True,
    }


async def remove_connection(
    db: AsyncSession, user: User, *, card_slug: str, source_id: str
) -> dict[str, Any]:
    """Retire le lien fiche-a-fiche porte par une source, sans retirer la source.

    La reference reste dans la bibliographie de la fiche ; elle cesse
    seulement de designer une fiche Philum comme sa fiche cible.
    """
    card = await _fiche_du_createur(db, user, card_slug)
    source = await _source_du_createur(db, user, source_id)
    if source.biblio_card_id != card.id:
        raise ToolError(f"La source {source_id!r} n'appartient pas a la fiche {card_slug!r}.")
    source.linked_card_id = None
    source.link_origin = None
    source.link_confirmed_at = None
    await db.commit()
    return {"source_id": source_id, "card_slug": card.slug, "linked_card_removed": True}


# ---------------------------------------------------------------------------
# Import, aide LLM, listing, cycle de vie (chantier C - P2).
#
# 12 tools qui donnent au MCP la parite avec les fonctions non-mutatives de
# l'UI : extraction auto de sources depuis l'URL du contenu, suggestions LLM
# d'extraits et d'annotations, listing des fiches/sources/extraits, archivage
# Wayback, cycle de vie corbeille.
# ---------------------------------------------------------------------------


async def list_my_cards(
    db: AsyncSession, user: User, *, status: str | None = None, limit: int = 20
) -> dict[str, Any]:
    """Liste les fiches de l'utilisateur avec indicateur de troncature.

    `status` optionnel : `draft` ou `published`. Absent = les deux. `limit`
    plafonne le nombre d'entrees rendues (max 200). Retourne `{cards, total, truncated}` :
    `total` est le nombre reel de fiches (avant troncature), `truncated` indique
    si `limit` a coupe la liste -- augmenter `limit` pour tout voir.
    """
    plafond = max(1, min(limit, 200))
    stmt_base = select(BiblioCard).where(
        BiblioCard.user_id == user.id, BiblioCard.deleted_at.is_(None)
    )
    if status is not None:
        stmt_base = stmt_base.where(BiblioCard.status == status)
    total = await db.scalar(select(func.count()).select_from(stmt_base.subquery()))
    cards = (
        await db.scalars(stmt_base.order_by(BiblioCard.updated_at.desc()).limit(plafond))
    ).all()
    return {
        "cards": [
            {
                "slug": c.slug,
                "title": c.title,
                "status": c.status,
                "visibility": c.visibility,
                "published_at": c.published_at.isoformat() if c.published_at else None,
            }
            for c in cards
        ],
        "total": total or 0,
        "truncated": (total or 0) > plafond,
    }


async def list_sources(db: AsyncSession, user: User, *, card_slug: str) -> list[dict[str, Any]]:
    """Liste les sources d'une fiche dans leur ordre d'affichage.

    Chaque entree porte les champs edituriaux + l'identifiant a utiliser dans
    les tools d'ecriture (`id`).
    """
    card = await _fiche_du_createur(db, user, card_slug)
    sources = (
        await db.scalars(
            select(Source)
            .where(Source.biblio_card_id == card.id, Source.deleted_at.is_(None))
            .order_by(Source.position)
        )
    ).all()
    return [
        {
            "id": str(s.id),
            "position": s.position,
            "url": s.url,
            "title": s.title,
            "authors": s.authors,
            "doi": s.doi,
            "journal": s.journal,
            "category": s.category,
            "author_kind": s.author_kind,
            "stance": s.stance,
            "is_pivot": s.is_pivot,
            "annotation": s.annotation,
            "archive_status": s.archive_status,
        }
        for s in sources
    ]


async def search_my_excerpts(
    db: AsyncSession, user: User, *, query: str, limit: int = 20
) -> list[dict[str, Any]]:
    """Recherche full-text dans les extraits de l'utilisateur.

    Cherche `query` dans le `text` des extraits des fiches du user. Rend
    l'extrait, la source qui le porte et la fiche parente.
    """
    q = query.strip()
    if not q:
        return []
    stmt = (
        select(SourceExcerpt, Source, BiblioCard)
        .join(Source, SourceExcerpt.source_id == Source.id)
        .join(BiblioCard, Source.biblio_card_id == BiblioCard.id)
        .where(
            BiblioCard.user_id == user.id,
            BiblioCard.deleted_at.is_(None),
            Source.deleted_at.is_(None),
            SourceExcerpt.text.ilike(f"%{q}%"),
        )
        .order_by(SourceExcerpt.created_at.desc())
        .limit(max(1, min(limit, 100)))
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "excerpt_id": str(ex.id),
            "text": ex.text,
            "title": ex.title,
            "context": ex.context,
            "source_id": str(src.id),
            "source_title": src.title,
            "card_slug": card.slug,
            "verified_status": ex.verified_status,
        }
        for ex, src, card in rows
    ]


async def delete_card(db: AsyncSession, user: User, *, slug: str) -> dict[str, Any]:
    """Envoie la fiche et toutes ses sources en corbeille (reversible via `restore_card`).

    La fiche et ses sources disparaissent des vues publiques et de l'editeur.
    Les extraits et attestations restent en base. Utiliser `restore_card` pour
    annuler. Irreversible au-dela de la politique de retention (90 jours).
    """
    from datetime import datetime

    card = await _fiche_du_createur(db, user, slug)
    card.deleted_at = datetime.now().replace(tzinfo=None)
    await db.commit()
    return {"slug": slug, "deleted": True}


async def restore_card(db: AsyncSession, user: User, *, slug: str) -> dict[str, Any]:
    """Sort une fiche de la corbeille (annule un `delete_card`)."""
    stmt = select(BiblioCard).where(
        BiblioCard.user_id == user.id,
        BiblioCard.slug == slug,
        BiblioCard.deleted_at.is_not(None),
    )
    card = (await db.execute(stmt)).scalar_one_or_none()
    if card is None:
        raise ToolError(f"Aucune fiche {slug!r} en corbeille chez {user.username}.")
    card.deleted_at = None
    await db.commit()
    return {"slug": slug, "restored": True}


async def archive_sources(db: AsyncSession, user: User, *, source_ids: list[str]) -> dict[str, Any]:
    """Declenche l'archivage Wayback pour les sources donnees.

    Chaque source est verifiee comme appartenant a l'utilisateur avant. Le
    passage a `archive_status=pending` marque la source pour le worker.
    """
    accepted: list[str] = []
    refused: list[dict[str, str]] = []
    for sid_str in source_ids:
        try:
            source = await _source_du_createur(db, user, sid_str)
        except ToolError as exc:
            refused.append({"source_id": sid_str, "reason": str(exc)})
            continue
        source.archive_status = "pending"
        accepted.append(sid_str)
    await db.commit()
    return {"accepted": accepted, "refused": refused}


async def suggest_excerpts(
    db: AsyncSession,
    user: User,
    *,
    source_id: str,
    provided_text: str | None = None,
    include_annotation: bool = True,
    include_existing: bool = True,
    include_card_context: bool = True,
) -> dict[str, Any]:
    """Le LLM propose des extraits verbatim pour une source.

    `provided_text` : quand la page est bloquee anti-bot ou qu'on tient un
    meilleur texte. Sinon le serveur fetch l'URL. Trois flags orientent ce
    que voit le modele en plus du texte de la source.

    Chaque candidat est deja verifie contre le texte (anti-hallucination).
    A l'agent de trancher lesquels poser via `add_excerpt`.
    """
    from app.api.v1.endpoints.excerpts import _texte_de_la_source, verify_quote
    from app.services.llm import suggest_excerpts as llm_suggest

    source = await _source_du_createur(db, user, source_id)

    page_text = (provided_text or "").strip()
    if not page_text:
        page_text, _refuse, _complet = await _texte_de_la_source(source.url)
    if not page_text:
        return {"suggestions": [], "page_text_length": 0, "llm_enabled": False}

    morceaux: list[str] = []
    if source.title:
        morceaux.append(source.title)
    if include_annotation and source.annotation:
        morceaux.append(source.annotation)
    if include_card_context:
        card = await db.scalar(select(BiblioCard).where(BiblioCard.id == source.biblio_card_id))
        if card:
            entete = " - ".join(filter(None, [card.title, card.description]))
            if entete:
                morceaux.append(f"Fiche du createur : {entete}")
    contexte = " - ".join(morceaux) or None

    deja: list[str] | None = None
    if include_existing:
        existants = await db.scalars(
            select(SourceExcerpt).where(SourceExcerpt.source_id == source.id)
        )
        textes = [e.text for e in existants if e.text]
        if textes:
            deja = textes

    proposes = await llm_suggest(page_text, contexte, existing_excerpts=deja)
    if proposes is None:
        return {
            "suggestions": [],
            "page_text_length": len(page_text),
            "llm_enabled": False,
        }

    suggestions: list[dict[str, Any]] = []
    for quote in proposes:
        m = verify_quote(page_text, quote)
        if not m:
            continue
        suggestions.append({"text": m.group(0), "char_offset": m.start()})
    return {
        "suggestions": suggestions,
        "page_text_length": len(page_text),
        "llm_enabled": True,
    }


async def annotate_excerpt(
    db: AsyncSession,
    user: User,
    *,
    source_id: str,
    excerpt_text: str,
    provided_text: str | None = None,
) -> dict[str, Any]:
    """Le LLM suggere un titre court et un `context` pour un extrait donne.

    A appeler apres avoir choisi le verbatim mais avant `add_excerpt`. A
    l'agent de valider ce qu'il pose ensuite.
    """
    from app.services.llm import suggest_annotation as llm_annotate

    source = await _source_du_createur(db, user, source_id)
    entourage = (provided_text or "").strip()
    if not entourage:
        entourage = " - ".join(filter(None, [source.title, source.annotation]))
    annotation = await llm_annotate(excerpt_text, entourage)
    if annotation is None:
        return {"title": None, "context": None, "llm_enabled": False}
    return {
        "title": annotation.title,
        "context": annotation.context,
        "llm_enabled": True,
    }


async def chunk_text(
    db: AsyncSession,
    user: User,
    *,
    source_id: str,
    text: str,
    size: int | None = None,
) -> dict[str, Any]:
    """Decoupe un texte long en chunks candidats pour poser des extraits.

    Utile sur une source dont le texte fait plusieurs milliers de mots : le
    LLM ne peut pas traiter d'un coup, on decoupe d'abord.
    """
    from app.services.chunker import Unite, suggerer_taille
    from app.services.chunker import chunk_text as chunker_fn

    source = await _source_du_createur(db, user, source_id)
    unit = Unite.CARACTERES
    suggeree = suggerer_taille(text, unit)
    taille = size or suggeree
    chunks = chunker_fn(text, taille=taille, unite=unit)
    return {
        "source_id": str(source.id),
        "chunks": [{"text": c.text, "start": c.start, "end": c.end} for c in chunks],
        "suggested_size": suggeree,
    }


async def get_youtube_transcript(db: AsyncSession, user: User, *, url: str) -> dict[str, Any]:
    """Recupere le transcript d'une video YouTube (via l'API interne).

    Aucun controle proprietaire : tout transcript public est accessible.
    """
    from app.extractors.youtube_transcript import fetch_youtube_transcript

    transcript = await fetch_youtube_transcript(url)
    if transcript is None:
        raise ToolError(f"Aucun transcript disponible pour {url!r}.")
    return {"url": url, "transcript": transcript}


async def get_url_metadata(db: AsyncSession, user: User, *, url: str) -> dict[str, Any]:
    """Metadonnees editoriales d'une URL : titre, description, auteurs, date."""
    import asyncio

    from app.core.url_safety import UnsafeUrlError, assert_url_is_safe
    from app.extractors.url_extractor import extract as extract_meta

    # L'URL vient d'un agent, pas d'un formulaire : sans cette garde, un
    # `http://169.254.169.254/...` remonterait les identifiants de la VM dans
    # le titre. `assert_url_is_safe` resout le DNS en bloquant, d'ou le thread.
    try:
        await asyncio.to_thread(assert_url_is_safe, url)
    except UnsafeUrlError as exc:
        raise ToolError(f"URL refusee : {exc}") from exc

    meta = await extract_meta(url)
    if meta is None:
        raise ToolError(f"Impossible d'extraire les metadonnees de {url!r}.")
    return {
        "url": url,
        "title": meta.title,
        "description": meta.description,
        "authors": meta.authors,
        "published_at": meta.published_at,
    }


async def import_from_content_url(
    db: AsyncSession, user: User, *, card_slug: str
) -> dict[str, Any]:
    """Extrait automatiquement les sources depuis l'URL du contenu de la fiche.

    Equivalent du bouton « Extraire les sources » de l'UI. Lit
    `card.content_url` et rend les references citees. NE POSE PAS les
    sources : l'agent decide ensuite lesquelles retenir via `add_source`.
    """
    from types import SimpleNamespace

    from app.api.v1.endpoints.imports import ImportFromUrlRequest, parse_content_url

    card = await _fiche_du_createur(db, user, card_slug)
    if not card.content_url:
        raise ToolError(f"La fiche {card_slug!r} n'a pas de content_url : impossible d'extraire.")
    # Simule le Request FastAPI que l'endpoint attend (seul .headers /
    # .client peuvent etre lus par slowapi ; MCP contourne le rate-limit).
    fake_request = SimpleNamespace(headers={}, client=SimpleNamespace(host="mcp"), scope={})
    payload = ImportFromUrlRequest(url=card.content_url)
    try:
        response = await parse_content_url(fake_request, payload, current_user=user)  # type: ignore[arg-type]
    except Exception as exc:
        raise ToolError(f"Extraction impossible : {exc}") from exc
    return {
        "card_slug": card.slug,
        "content_url": card.content_url,
        "sources": [
            {
                "url": ref.url,
                "title": ref.title,
                "authors": ref.authors,
                "doi": ref.doi,
                "score": ref.score,
                "kind": ref.kind,
            }
            for ref in response.refs
        ],
    }


# ---------------------------------------------------------------------------
# Attestations Ed25519, citations entrantes, batch, claim, parsers (chantier D).
#
# Derniere vague de la parite MCP <-> UI : ce qui reste apres P1 (mutations)
# et P2 (import/LLM/listing). Attestations = ADN cryptographique de Philum.
# ---------------------------------------------------------------------------


async def create_content_attestation(
    db: AsyncSession, user: User, *, card_slug: str
) -> dict[str, Any]:
    """Signe cryptographiquement le contenu documente par la fiche (Ed25519).

    L'attestation lie l'auteur (via sa cle publique) au `content_url` de la
    fiche, avec un horodatage. C'est la couche verifiable de Philum : meme si
    la fiche est modifiee, l'attestation reste immuable et prouve l'engagement
    initial. Refuse si la fiche n'a pas de `content_url`.
    """
    from app.services.attestation import AttestationService

    card = await _fiche_du_createur(db, user, card_slug)
    if not card.content_url:
        raise ToolError(f"La fiche {card_slug!r} n'a pas de content_url : rien a attester.")
    service = AttestationService(db)
    attestation = await service.create_attestation(user, card.content_url)
    return {
        "id": str(attestation.id),
        "content_url": attestation.content_url,
        "attested_at": attestation.attested_at.isoformat(),
        "canonical_hash": attestation.canonical_hash,
        "signature": attestation.signature,
    }


async def get_attestation(db: AsyncSession, user: User, *, attestation_id: str) -> dict[str, Any]:
    """Recupere une attestation par son ID (lecture publique)."""
    from app.services.attestation import AttestationService

    try:
        aid = UUID(attestation_id)
    except ValueError as exc:
        raise ToolError(f"Identifiant d'attestation invalide : {attestation_id!r}.") from exc
    service = AttestationService(db)
    attestation = await service.get_attestation(aid)
    if attestation is None:
        raise ToolError(f"Aucune attestation {attestation_id!r}.")
    return {
        "id": str(attestation.id),
        "content_url": attestation.content_url,
        "attested_at": attestation.attested_at.isoformat(),
        "canonical_hash": attestation.canonical_hash,
        "signature": attestation.signature,
    }


async def verify_attestation(
    db: AsyncSession, user: User, *, attestation_id: str
) -> dict[str, Any]:
    """Verifie la signature Ed25519 d'une attestation. Rend `valid` + raison."""
    from app.services.attestation import AttestationService

    try:
        aid = UUID(attestation_id)
    except ValueError as exc:
        raise ToolError(f"Identifiant d'attestation invalide : {attestation_id!r}.") from exc
    service = AttestationService(db)
    attestation = await service.get_attestation(aid)
    if attestation is None:
        raise ToolError(f"Aucune attestation {attestation_id!r}.")
    result = await service.verify_attestation(attestation)
    return {
        "attestation_id": str(aid),
        "valid": result["valid"],
        "content_url": attestation.content_url,
        "creator_slug": result.get("creator_slug"),
        "reason": result.get("reason"),
    }


async def list_incoming_citations(db: AsyncSession, user: User) -> dict[str, Any]:
    """Liste les fiches d'autres createurs qui citent une de tes fiches.

    Chaque entree porte le nom du createur qui cite, la fiche qui cite, et
    ta source qui est citee. Un `is_new` marque les entrees apparues depuis
    la derniere consultation via `mark_citations_seen`.
    """
    from app.services.citations import list_incoming_citations as list_svc

    result = await list_svc(db, user)
    return {
        "citations": [
            {
                "source_id": str(c.source_id),
                "citing_creator_slug": c.citing_creator_slug,
                "citing_creator_name": c.citing_creator_name,
                "citing_card_slug": c.citing_card_slug,
                "citing_card_title": c.citing_card_title,
                "cited_card_slug": c.cited_card_slug,
                "cited_card_title": c.cited_card_title,
                "cited_at": c.cited_at.isoformat() if c.cited_at else None,
                "stance": c.stance,
                "is_new": c.is_new,
            }
            for c in result.citations
        ],
        "new_count": result.new_count,
        "seen_at": result.seen_at.isoformat() if result.seen_at else None,
        "truncated": result.truncated,
    }


async def mark_citations_seen(db: AsyncSession, user: User) -> dict[str, Any]:
    """Marque les citations entrantes comme vues (arrete d'afficher `is_new`)."""
    from app.services.citations import mark_citations_seen as mark_svc

    seen_at = mark_svc(user)
    await db.flush()
    await db.commit()
    return {"seen_at": seen_at.isoformat() if seen_at else None}


async def list_deleted_cards(
    db: AsyncSession, user: User, *, limit: int = 50
) -> list[dict[str, Any]]:
    """Liste les fiches en corbeille du user (restaurables via `restore_card`)."""
    stmt = (
        select(BiblioCard)
        .where(BiblioCard.user_id == user.id, BiblioCard.deleted_at.is_not(None))
        .order_by(BiblioCard.deleted_at.desc())
        .limit(max(1, min(limit, 200)))
    )
    cards = (await db.scalars(stmt)).all()
    return [
        {
            "slug": c.slug,
            "title": c.title,
            "status": c.status,
            "deleted_at": c.deleted_at.isoformat() if c.deleted_at else None,
        }
        for c in cards
    ]


async def add_sources_batch(
    db: AsyncSession,
    user: User,
    *,
    card_slug: str,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """Ajoute plusieurs sources a une fiche en un appel.

    Chaque entree suit la meme signature que `add_source` (url, title,
    authors, doi, category, author_kind, format, stance, annotation,
    journal, published_at, archive_url). Ce qui echoue est retourne dans
    `failed` avec la raison, ce qui reussit dans `created` (avec les IDs).

    Utilise ce tool quand tu poses 5+ sources d'affilee : un seul commit
    au lieu de N, une seule verification de dedup en amont.
    """
    card = await _fiche_du_createur(db, user, card_slug)
    connues = await _identites_deja_citees(db, card.id)

    max_position = await db.scalar(
        select(func.max(Source.position)).where(Source.biblio_card_id == card.id)
    )
    next_pos = (max_position or 0) + 1

    created: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for i, sd in enumerate(sources):
        url = sd.get("url", "") or ""
        doi = sd.get("doi")
        cle = _identite(url, doi)
        if cle and cle in connues:
            failed.append({"index": i, "url": url, "reason": "Deja citee dans cette fiche."})
            continue
        try:
            linked_card_id = await effective_linked_card_id(
                db,
                chosen=None,
                url=url,
                user_id=user.id,
                current_card_id=card.id,
                doi=doi,
            )
        except ValueError as exc:
            failed.append({"index": i, "url": url, "reason": str(exc)})
            continue

        # Meme validation enum que `add_source` : une entree fautive est
        # rejetee dans `failed`, le lot continue sans elle.
        try:
            fmt = _valeur_enum("format", sd.get("format"), SourceFormat) or SourceFormat.TEXTE.value
            categorie = (
                _valeur_enum("category", sd.get("category"), SourceCategory)
                or SourceCategory.ARTICLE_SCIENTIFIQUE.value
            )
            nature_auteur = (
                _valeur_enum("author_kind", sd.get("author_kind"), AuthorKind)
                or AuthorKind.CHERCHEUR.value
            )
            position_declaree = _valeur_enum("stance", sd.get("stance"), SourceStance)
            date_publication = _valeur_date(sd.get("published_at"))
        except ToolError as exc:
            failed.append({"index": i, "url": url, "reason": str(exc)})
            continue

        manual_archive = (sd.get("archive_url") or "").strip() or None
        source = Source(
            biblio_card_id=card.id,
            position=next_pos,
            url=url,
            title=sd.get("title"),
            authors=sd.get("authors"),
            format=fmt,
            category=categorie,
            author_kind=nature_auteur,
            stance=position_declaree,
            annotation=sd.get("annotation"),
            journal=sd.get("journal"),
            published_at=date_publication,
            doi=doi,
            linked_card_id=linked_card_id,
            archive_url=manual_archive,
            archive_status="archived" if manual_archive else "pending",
            archive_timestamp=horodatage_wayback(manual_archive),
        )
        db.add(source)
        await db.flush()
        created.append(
            {
                "id": str(source.id),
                "position": source.position,
                "url": url,
            }
        )
        next_pos += 1
        if cle:
            connues.add(cle)

    await db.commit()
    return {
        "card_slug": card.slug,
        "created": created,
        "failed": failed,
    }


async def create_claim_request(
    db: AsyncSession, user: User, *, card_id: str, message: str | None = None
) -> dict[str, Any]:
    """Revendique une fiche seed (fiche automatique sans compte proprietaire).

    Un claim ouvre une demande manuelle : l'utilisateur du contenu documente
    prouve son identite hors ligne, et un admin transfere la propriete.
    Refuse si la fiche n'est pas seed ou n'existe pas.
    """
    from app.models.claim_request import ClaimRequest

    try:
        cid = UUID(card_id)
    except ValueError as exc:
        raise ToolError(f"Identifiant de fiche invalide : {card_id!r}.") from exc
    card = await db.get(BiblioCard, cid)
    if card is None or card.deleted_at is not None or card.status != "published":
        raise ToolError(f"Aucune fiche publique {card_id!r}.")
    if not card.is_seed:
        raise ToolError(f"La fiche {card_id!r} n'est pas une fiche seed revendicable.")
    claim = ClaimRequest(
        card_id=cid,
        claimant_id=user.id,
        message=message,
    )
    db.add(claim)
    await db.commit()
    await db.refresh(claim)
    return {
        "id": str(claim.id),
        "card_id": card_id,
        "created_at": claim.created_at.isoformat(),
    }


async def parse_biblio(db: AsyncSession, user: User, *, text: str) -> dict[str, Any]:
    """Parse une bibliographie collee (texte libre : BibTeX, CSL, markdown, ...).

    Rend la liste des references detectees avec leurs metadonnees.
    Enrichit avec le parseur de citations nues et le LLM (comme l'endpoint
    REST /import/paste).
    """
    from app.services.import_parsers import parse_freetext_citations, parse_markdown

    if not text.strip():
        return {"refs": []}
    result = parse_markdown(text)
    freetext = parse_freetext_citations(text)
    if freetext.refs:
        known = {
            f"{(r.title or '').strip().lower()}|{(r.authors or '').strip().lower()}"
            for r in result.refs
        }
        for ref in freetext.refs:
            key = f"{(ref.title or '').strip().lower()}|{(ref.authors or '').strip().lower()}"
            if key not in known:
                result.refs.append(ref)
                known.add(key)
    return {
        "refs": [
            {
                "url": r.url,
                "title": r.title,
                "authors": r.authors,
                "year": r.year,
                "doi": r.doi,
                "journal": r.journal,
            }
            for r in result.refs
        ],
    }
