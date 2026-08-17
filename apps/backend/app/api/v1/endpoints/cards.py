from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_401_UNAUTHORIZED

from app.core.rate_limit import limiter
from app.db.database import get_db
from app.db.text_search import contient
from app.models.biblio_card import BiblioCard
from app.models.claim_request import ClaimRequest
from app.models.source import Source
from app.models.user import User
from app.schemas.biblio_card import (
    CardCreate,
    CardDetail,
    CardGraphResponse,
    CardResponse,
    CardSearchResult,
    CardUpdate,
    CreatorInfo,
    GraphEdgeResponse,
    GraphNodeResponse,
    IncomingCitationResponse,
    IncomingCitationsResponse,
)
from app.schemas.claim import ClaimRequestCreate, ClaimRequestResponse
from app.schemas.source import SourceResponse
from app.services.auth import AuthService
from app.services.card import CardService
from app.services.card_graph import MAX_DEPTH, build_card_graph
from app.services.citations import list_incoming_citations, mark_citations_seen
from app.services.source_enrichment import needs_recheck, schedule_source_enrichment
from app.services.wayback import least_recently_attempted, schedule_archiving

logger = logging.getLogger(__name__)

router = APIRouter(tags=["cards"])


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


async def get_card_service(db: AsyncSession = Depends(get_db)) -> CardService:
    return CardService(db)


async def get_current_user(
    request: Request, auth_service: AuthService = Depends(get_auth_service)
) -> User:
    user = await auth_service.get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Not authenticated"},
        )
    return user


@router.get("/cards/citations", response_model=IncomingCitationsResponse)
async def list_incoming_citations_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Qui s'appuie sur mes fiches.

    Comme /cards/deleted, cette route DOIT preceder /cards/{card_id} : sinon
    FastAPI lirait 'citations' comme un UUID et repondrait 422.
    """
    result = await list_incoming_citations(db, current_user)
    return IncomingCitationsResponse(
        citations=[IncomingCitationResponse(**vars(c)) for c in result.citations],
        new_count=result.new_count,
        seen_at=result.seen_at,
        truncated=result.truncated,
    )


@router.post("/cards/citations/seen", response_model=IncomingCitationsResponse)
async def mark_incoming_citations_seen(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Marque les citations entrantes comme vues et renvoie la liste a jour.

    On renvoie la liste plutot qu'un 204 : le frontend doit pouvoir afficher
    d'un seul coup ce qui vient d'etre marque, sans re-interroger et sans
    reconstruire l'etat de son cote.
    """
    # La liste est calculee AVANT le marquage : l'utilisateur doit voir ce qui
    # etait neuf, pas une liste ou tout vient d'etre eteint par son propre clic.
    result = await list_incoming_citations(db, current_user)
    seen_at = mark_citations_seen(current_user)
    await db.flush()
    return IncomingCitationsResponse(
        citations=[IncomingCitationResponse(**vars(c)) for c in result.citations],
        new_count=result.new_count,
        seen_at=seen_at,
        truncated=result.truncated,
    )


@router.get("/cards/deleted", response_model=list[CardResponse])
async def list_my_deleted_cards(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    card_service: CardService = Depends(get_card_service),
):
    """Liste les fiches soft-deletees de l'utilisateur (corbeille).

    Chaque fiche est restaurable via POST /cards/{id}/restore. IMPORTANT :
    cette route DOIT etre declaree AVANT /cards/{card_id} pour que FastAPI
    ne matche pas 'deleted' comme un UUID (retournerait 422 sinon).
    """
    return await card_service.get_user_deleted_cards(current_user.id, limit, offset)


@router.get("/cards/search", response_model=list[CardSearchResult])
async def search_cards(
    q: str = Query("", max_length=200),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fiches selectionnables comme parent : celles de l'user + les publiques.

    Sert le picker de meta-fiches. Comme /cards/deleted, DOIT etre declaree
    avant /cards/{card_id} sinon FastAPI matche 'search' comme un UUID.
    """
    term = q.strip()
    visible = or_(
        BiblioCard.user_id == current_user.id,
        and_(BiblioCard.status == "published", BiblioCard.visibility == "public"),
    )
    stmt = (
        select(BiblioCard, User.username)
        .join(User, User.id == BiblioCard.user_id)
        .where(BiblioCard.deleted_at.is_(None), visible)
    )
    if term:
        # `contient` echappe aussi « % » et « _ », qui sans cela sont des
        # jokers SQL : chercher « % » ramenait tout le corps de la table.
        stmt = stmt.where(contient(BiblioCard.title, term))
    # Les fiches de l'utilisateur d'abord : c'est le cas d'usage dominant.
    stmt = stmt.order_by(
        (BiblioCard.user_id == current_user.id).desc(),
        BiblioCard.updated_at.desc().nullslast(),
        BiblioCard.created_at.desc(),
    ).limit(limit)
    rows = (await db.execute(stmt)).all()
    return [
        CardSearchResult(
            id=card.id,
            title=card.title,
            slug=card.slug,
            creator_slug=username,
            status=card.status,
            is_own=card.user_id == current_user.id,
        )
        for card, username in rows
    ]


@router.get("/cards", response_model=list[CardResponse])
async def list_my_cards(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    card_service: CardService = Depends(get_card_service),
):
    from app.models.biblio_card import CardStatus

    status_enum = CardStatus(status_filter) if status_filter else None
    cards = await card_service.get_user_cards(current_user.id, status_enum, limit, offset)
    return cards


@router.post("/cards", response_model=CardResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/hour")
async def create_card(
    request: Request,
    card_data: CardCreate,
    current_user: User = Depends(get_current_user),
    card_service: CardService = Depends(get_card_service),
):
    existing = await card_service.get_card_by_slug(
        current_user.username, card_data.slug, published_only=False
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "conflict",
                "message": f"Card with slug '{card_data.slug}' already exists",
            },
        )
    # Auto-remplissage des auteurs du contenu quand ils sont connus mais non
    # renseignes. Sans cette securite, une fiche cree via un chemin qui saute
    # le bouton « Suggerer » de la wizard atterrit avec content_authors=NULL,
    # et le graphe finit par retomber sur le createur -- ce qui laisse croire
    # qu'il est l'auteur de l'article documente (cas vecu : fiche seed
    # « Early detection of multiple cancers » chez mathias-pinault, articles
    # ou Crossref connaissait pourtant les cinq auteurs). Best-effort, non
    # bloquant : un extract qui echoue ne casse pas la creation.
    if not card_data.content_authors and card_data.content_url:
        try:
            from app.extractors.url_extractor import extract

            meta = await extract(card_data.content_url)
            if meta and meta.authors:
                card_data = card_data.model_copy(update={"content_authors": meta.authors[:500]})
        except Exception as e:
            logger.info("auto-fill content_authors failed for %s: %s", card_data.content_url, e)
    card = await card_service.create_card(current_user.id, card_data)
    return card


@router.get("/cards/{card_id}", response_model=CardResponse)
async def get_card(
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    card_service: CardService = Depends(get_card_service),
):
    card = await card_service.get_card_by_id(card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Card not found"},
        )
    if card.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Access denied"},
        )
    return card


@router.patch("/cards/{card_id}", response_model=CardResponse)
async def update_card(
    card_id: UUID,
    card_data: CardUpdate,
    current_user: User = Depends(get_current_user),
    card_service: CardService = Depends(get_card_service),
):
    card = await card_service.get_card_by_id(card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Card not found"},
        )
    if card.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Access denied"},
        )

    # Note (2026-07-21) : les fiches publiees sont editables par leur owner.
    # La *fiche* (vue produit) est mutable ; l'engagement public est porte
    # par l'*attestation Ed25519* dans content_attestations, qui reste
    # immuable et verifiable via son id (ADR-019 revisitee).
    if card_data.title is not None:
        card.title = card_data.title
    if card_data.description is not None:
        card.description = card_data.description
    if card_data.content_url is not None:
        card.content_url = card_data.content_url
    if card_data.content_text is not None:
        # Chaine vide = l'utilisateur retire le texte (l'affichage sur la
        # fiche publique disparaitra). C'est le geste que l'UI propose
        # explicitement apres un warning « publier ce texte engage ta
        # responsabilite de droit ».
        card.content_text = card_data.content_text or None
    if card_data.content_authors is not None:
        # Chaine vide = l'utilisateur efface les auteurs, ce qui rend la main a
        # la reconstitution depuis les fiches citantes.
        card.content_authors = card_data.content_authors.strip() or None
    if card_data.platform is not None:
        card.platform = card_data.platform.value
    if card_data.content_type is not None:
        card.content_type = card_data.content_type.value
    if card_data.is_seed is not None:
        card.is_seed = card_data.is_seed
    if card_data.visibility is not None:
        card.visibility = card_data.visibility.value
    if card_data.format is not None:
        card.format = card_data.format.value
    if card_data.category is not None:
        card.category = card_data.category.value
    if card_data.author_kind is not None:
        card.author_kind = card_data.author_kind.value

    # The card is already attached to the request session (via CardService);
    # opening a second session here raised InvalidRequestError. Commit in place.
    return await card_service.save_card(card)


@router.post("/cards/{card_id}/content-text/upload", response_model=CardResponse)
@limiter.limit("30/hour")
async def upload_content_text(
    request: Request,
    card_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    card_service: CardService = Depends(get_card_service),
):
    """Depose un document (PDF, DOCX, ODT, TXT, MD) et remplit content_text.

    Le fichier est lu, son texte extrait, puis jete : rien du fichier lui-meme
    n'est conserve. Seul le texte l'est. Meme borne de taille et memes formats
    que /excerpts/chunk-file.

    L'utilisateur est cense avoir le droit de publier ce texte (contenu propre,
    libre de droit, ou extrait sous droit de citation) ; l'UI l'en avertit
    explicitement avant l'upload, le backend fait confiance.
    """
    import asyncio

    from app.services.document_text import MAX_BYTES, DocumentError, extract_text

    card = await card_service.get_card_by_id(card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Card not found"},
        )
    if card.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Access denied"},
        )

    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "code": "file_too_large",
                "message": f"Fichier trop volumineux (maximum {MAX_BYTES // (1024 * 1024)} Mo).",
            },
        )

    try:
        texte = await asyncio.to_thread(extract_text, file.filename or "", data)
    except DocumentError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "unreadable_document", "message": str(e)},
        ) from e

    # Meme borne que le schema : au-dela d'un demi-million de caracteres, une
    # fiche unique n'est plus la bonne granularite.
    if len(texte) > 500_000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "text_too_long",
                "message": (
                    "Texte trop long apres extraction (limite 500 000 caracteres). "
                    "Decoupez le contenu en plusieurs fiches (une par chapitre / episode)."
                ),
            },
        )

    card.content_text = texte
    await card_service.save_card(card)
    return card


@router.post("/cards/{card_id}/publish", response_model=dict)
async def publish_card(
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    card_service: CardService = Depends(get_card_service),
):
    card = await card_service.get_card_by_id(card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Card not found"},
        )
    if card.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Access denied"},
        )

    if not card.sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "validation_error", "message": "Cannot publish a card without sources"},
        )

    # Belt-and-suspenders: any exception raised during publish (MissingGreenlet,
    # asyncpg DataError, crypto error, etc.) must surface as a clean JSON 500
    # with CORS headers. Without this wrapper, an exception that aborts the
    # SQLAlchemy transaction leaves `get_db`'s post-yield `await session.commit()`
    # to raise a second time AFTER the response is being constructed, killing
    # the response stream so the browser receives no CORS header (visible as
    # "blocked by CORS policy" + ERR_FAILED, indistinguishable from a network
    # outage). See agent/PITFALLS.md §1.4 and §1.5.
    try:
        return await card_service.publish_card(card)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "publish_card failed: card_id=%s user_id=%s sources=%d type=%s",
            card_id,
            current_user.id,
            len(card.sources),
            type(exc).__name__,
        )
        # Rollback so `get_db`'s cleanup `commit()` doesn't trip on the aborted
        # transaction and corrupt the response stream.
        try:
            await card_service._db.rollback()
        except Exception:
            logger.exception("rollback after publish failure also failed")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "publish_failed",
                    "message": f"Publish failed: {type(exc).__name__}: {exc}",
                }
            },
        )


@router.post("/cards/{card_id}/restore", response_model=CardResponse)
async def restore_card(
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    card_service: CardService = Depends(get_card_service),
):
    card = await card_service.restore_card(card_id, current_user.id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Card not found or not deleted"},
        )
    return card


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    card_service: CardService = Depends(get_card_service),
):
    deleted = await card_service.delete_card(card_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Card not found or already deleted"},
        )


async def _load_public_card(
    creator_slug: str,
    card_slug: str,
    request: Request,
    card_service: CardService,
    auth_service: AuthService,
) -> BiblioCard:
    """Charge une fiche par son adresse publique, ou leve 404.

    « Publiee » dit que le travail est acheve, « publique » qu'il est offert au
    monde : une fiche peut etre l'un sans etre l'autre. Chaque porte de sortie
    doit donc verifier les deux — et repondre 404 plutot que 403, pour ne pas
    confirmer a un visiteur non autorise qu'une fiche existe a cette adresse.

    Ce controle etait recopie a chaque route publique. L'export l'avait oublie
    et servait en huit formats la bibliographie complete de fiches que leur
    auteur avait gardees privees. Passer par ici rend l'oubli impossible.
    """
    not_found = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "not_found", "message": "Card not found"},
    )
    card = await card_service.get_card_by_slug(creator_slug, card_slug)
    if not card:
        raise not_found
    if card.visibility == "private":
        viewer = await auth_service.get_current_user(request)
        if viewer is None or viewer.id != card.user_id:
            raise not_found
    return card


@router.get("/@{creator_slug}/{card_slug}", response_model=CardDetail)
async def get_public_card(
    creator_slug: str,
    card_slug: str,
    request: Request,
    card_service: CardService = Depends(get_card_service),
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    card = await _load_public_card(creator_slug, card_slug, request, card_service, auth_service)

    stats = card_service.compute_stats(card)
    sources_response = [SourceResponse.model_validate(s) for s in card.sources]

    # Verification paresseuse : sans elle, seules les sources creees apres les
    # migrations auraient un badge, et toutes les fiches deja publiees
    # resteraient muettes sur les retractations comme sur l'acces libre. Le
    # premier affichage declenche le controle, le suivant le montre.
    #
    # Le verdict est aussi repris quand il a vieilli : un papier est corrige
    # des annees apres sa parution, un article ferme bascule en acces libre a
    # la fin de son embargo. Ne repecher que les verdicts *absents* gelait
    # chaque source dans son premier etat -- 117 bascules d'acces libre non
    # refletees et 2 papiers corriges affiches « non verifiable » (mesure du
    # 2026-08-07 sur les 643 sources publiees).
    unchecked = [
        (s.id, s.doi)
        for s in card.sources
        if needs_recheck(s.retraction_checked_at, s.retraction_status, s.doi)
        or needs_recheck(s.oa_checked_at, s.oa_status, s.doi)
    ]
    if unchecked:
        schedule_source_enrichment(unchecked)

    # Meme principe pour l'archivage : Save Page Now travaille en differe et
    # peut n'avoir rien produit au moment de l'import. Sans cette reprise,
    # `pending` serait un etat definitif deguise en attente.
    # Un lot est borne par un budget de temps : servi toujours dans le meme
    # ordre, il ne traiterait qu'un prefixe et la queue ne serait jamais
    # atteinte. Les sources tentees le moins recemment passent donc d'abord.
    unarchived = [
        (s.id, s.url)
        for s in least_recently_attempted(
            [s for s in card.sources if s.archive_status == "pending"]
        )
    ]
    if unarchived:
        schedule_archiving(unarchived)

    # Badge "Fiche Philum" : enrichit chaque source liee a une autre fiche
    # avec le nombre de sources de cette fiche.
    linked_ids = {s.linked_card_id for s in card.sources if s.linked_card_id}
    if linked_ids:
        counts_result = await db.execute(
            select(Source.biblio_card_id, func.count(Source.id))
            .where(Source.biblio_card_id.in_(linked_ids), Source.deleted_at.is_(None))
            .group_by(Source.biblio_card_id)
        )
        counts: dict[UUID, int] = {row[0]: row[1] for row in counts_result.all()}
        for src in sources_response:
            if src.linked_card_id:
                src.linked_card_sources_count = counts.get(src.linked_card_id, 0)

    return CardDetail(
        id=card.id,
        slug=card.slug,
        title=card.title,
        description=card.description,
        content_url=card.content_url,
        content_text=card.content_text,
        content_authors=card.content_authors,
        platform=card.platform,
        content_type=card.content_type,
        status=card.status,
        is_seed=card.is_seed,
        visibility=card.visibility,
        published_at=card.published_at,
        created_at=card.created_at,
        updated_at=card.updated_at,
        creator=CreatorInfo(
            slug=card.user.username,
            display_name=card.user.display_name,
            bio=card.user.bio,
            avatar_url=card.user.avatar_url,
            public_key=card.user.public_key,
        ),
        sources=sources_response,
        stats=stats,
    )


@router.get("/@{creator_slug}/{card_slug}/graph", response_model=CardGraphResponse)
async def get_public_card_graph(
    creator_slug: str,
    card_slug: str,
    request: Request,
    depth: int = Query(1, ge=0, le=MAX_DEPTH),
    include_sources: bool = Query(True),
    card_service: CardService = Depends(get_card_service),
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    """Meta-graphe autour d'une fiche : ses sources et les fiches qu'elles citent.

    ``include_sources=false`` renvoie le graphe fiches-seules (constellation).
    Le parcours ne traverse que des fiches publiees et publiques.
    """
    card = await _load_public_card(creator_slug, card_slug, request, card_service, auth_service)

    graph = await build_card_graph(db, card, depth=depth, include_sources=include_sources)
    return CardGraphResponse(
        root_id=graph.root_id,
        nodes=[GraphNodeResponse(**vars(n)) for n in graph.nodes],
        edges=[GraphEdgeResponse(**vars(e)) for e in graph.edges],
        truncated=graph.truncated,
    )


#: Formats de fichier. Le style de citation (APA, Harvard, etc.) est un axe
#: separe : passer par la query `?style=harvard`, applique par `format=txt`.
#: Les six anciens formats-styles (`apa`, `harvard`, ...) restent supportes
#: comme alias retrocompatibles vers `format=txt&style=<name>`.
_EXPORT_FORMATS = {
    "json": ("application/json; charset=utf-8", "json"),
    # Cible primaire des agents IA : JSON-LD schema.org + champs Philum
    # explicites (stance, retraction, archive). Un client qui envoie
    # `Accept: application/vnd.philum+json` sur l'URL canonique arrive
    # ici via la reecriture dans hooks.server.ts cote frontend.
    "philum": ("application/vnd.philum+json; charset=utf-8", "philum.json"),
    "csv": ("text/csv; charset=utf-8", "csv"),
    "xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xlsx",
    ),
    "bibtex": ("application/x-bibtex; charset=utf-8", "bib"),
    "ris": ("application/x-research-info-systems; charset=utf-8", "ris"),
    "csl": ("application/vnd.citationstyles.csl+json; charset=utf-8", "csl.json"),
    # Plain text : la bibliographie rendue dans le style choisi (`?style=`).
    # Par defaut APA (le premier style historiquement offert).
    "txt": ("text/plain; charset=utf-8", "txt"),
    "markdown": ("text/markdown; charset=utf-8", "md"),
    "docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx",
    ),
}

#: Alias historiques : chaque style de citation etait un format a part. On
#: garde ces alias pour les liens qui circulent deja et pour l'API publique
#: qui les documente. Un alias est traite comme `format=txt&style=<name>`.
_STYLE_ALIASES = {"apa", "harvard", "mla", "chicago", "vancouver", "ieee"}


@router.get("/@{creator_slug}/{card_slug}/export")
async def export_public_card(
    creator_slug: str,
    card_slug: str,
    request: Request,
    format: str = Query("json"),
    style: str | None = Query(
        None,
        description=(
            "Style de citation quand le format le porte. Valeurs : apa, harvard, "
            "mla, chicago, vancouver, ieee. Applique uniquement a `format=txt` "
            "(les autres formats ont leur propre grammaire et l'ignorent). Par "
            "defaut : apa quand `format=txt`."
        ),
    ),
    include: str | None = Query(
        None,
        description=(
            "Sections a emporter, separees par des virgules. Absent : tout. "
            "Vide : les references seules. Ignore par les formats "
            "bibliographiques (BibTeX, RIS, CSL, styles de citation)."
        ),
    ),
    cited: str | None = Query(
        None,
        description=(
            "Fiches citees par celle-ci. « 2 » : degres 1 et 2, complets. "
            "« 1:excerpts|2: » : un perimetre par degre, meme grammaire "
            "qu'`include`. Absent : aucune."
        ),
    ),
    citing: str | None = Query(
        None,
        description="Fiches qui citent celle-ci. Meme grammaire que `cited`.",
    ),
    card_service: CardService = Depends(get_card_service),
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    from app.services import citation_styles

    # Retrocompat : `?format=harvard` reste supporte en alias de
    # `?format=txt&style=harvard`. Les liens deja emis (partages, exports
    # sauves) continuent de repondre le meme contenu.
    if format in _STYLE_ALIASES:
        style = style or format
        format = "txt"

    if format not in _EXPORT_FORMATS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "validation_error",
                "message": f"Unknown format '{format}'. "
                f"Supported: {', '.join(sorted(_EXPORT_FORMATS))}",
            },
        )
    if style is not None and style not in citation_styles.STYLES:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "validation_error",
                "message": f"Unknown style '{style}'. "
                f"Supported: {', '.join(sorted(citation_styles.STYLES))}",
            },
        )

    from app.core.config import get_settings
    from app.services import export as export_service
    from app.services.export_neighbourhood import collect_neighbourhood, parse_degrees
    from app.services.export_scope import parse_scope

    try:
        scope = parse_scope(include)
        cited_degrees = parse_degrees(cited)
        citing_degrees = parse_degrees(citing)
    except ValueError as err:
        raise HTTPException(
            status_code=422,
            detail={"code": "validation_error", "message": str(err)},
        ) from err

    card = await _load_public_card(creator_slug, card_slug, request, card_service, auth_service)

    # `None` plutot qu'un voisinage vide quand rien n'est demande : un export
    # qui porterait « connected_cards: {cited: [], citing: []} » ferait croire
    # que la fiche n'a pas de voisines, alors qu'on ne les a pas cherchees.
    neighbourhood = None
    if cited_degrees or citing_degrees:
        neighbourhood = await collect_neighbourhood(
            db, card, cited=cited_degrees, citing=citing_degrees
        )

    public_url = f"{get_settings().frontend_base_url}/@{creator_slug}/{card_slug}"
    content: str | bytes
    if format == "json":
        content = export_service.export_json(card, public_url, scope, neighbourhood)
    elif format == "philum":
        content = export_service.export_philum_json(card, public_url, scope, neighbourhood)
    elif format == "csv":
        # BOM UTF-8 : Excel n'interprete pas l'UTF-8 sans lui.
        content = "\ufeff" + export_service.export_csv(card, scope)
    elif format == "xlsx":
        content = export_service.export_xlsx(
            card, scope, neighbourhood, public_url.rsplit("/@", 1)[0]
        )
    elif format == "bibtex":
        content = export_service.export_bibtex(card)
    elif format == "ris":
        content = export_service.export_ris(card)
    elif format == "csl":
        content = export_service.export_csl_json(card)
    elif format == "txt":
        # Style APA par defaut quand rien n'est demande : c'etait la seule
        # option historiquement offerte et beaucoup d'utilisateurs attendent
        # ce style par convention.
        content = export_service.export_bibliography(card, public_url, style or "apa")
    elif format == "docx":
        content = export_service.export_docx(card, public_url, scope, neighbourhood)
    else:
        content = export_service.export_markdown(card, public_url, scope, neighbourhood)

    media_type, ext = _EXPORT_FORMATS[format]
    # Extension enrichie du style quand c'est txt : `card-slug.harvard.txt` dit
    # au lecteur ce qu'il vient de telecharger, `card-slug.txt` ne dit rien.
    if format == "txt":
        ext = f"{style or 'apa'}.txt"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{card_slug}.{ext}"',
            "Cache-Control": "public, max-age=300",
        },
    )


@router.post(
    "/cards/{card_id}/claim-requests",
    response_model=ClaimRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/hour")
async def create_claim_request(
    request: Request,
    card_id: UUID,
    payload: ClaimRequestCreate,
    db: AsyncSession = Depends(get_db),
):
    card = await db.get(BiblioCard, card_id)
    if card is None or card.deleted_at is not None or card.status != "published":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Card not found"},
        )
    if not card.is_seed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "not_claimable", "message": "This card is not a seed card"},
        )
    db.add(
        ClaimRequest(
            card_id=card.id,
            email=payload.email.lower().strip(),
            channel_url=payload.channel_url.strip(),
            message=payload.message,
        )
    )
    await db.commit()
    return ClaimRequestResponse()


# Card-level /verify endpoint removed (ADR-019 pivot to content attestations).
# Verification now lives at GET /attestations/{id}/verify. The frontend no
# longer calls /verify on cards — removing the dead endpoint avoids confusion.
