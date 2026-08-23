"""Serveur MCP Philum — lecture publique du graphe de fiches."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_maker
from app.mcp_server import tools, tools_write
from app.mcp_server.auth import exiger_utilisateur, utilisateur_courant
from app.mcp_server.schema_compat import aplatir_nullable

mcp = FastMCP(
    "philum",
    instructions=(
        "Philum expose des fiches bibliographiques publiques de createurs de contenu. "
        "Naviguer comme un graphe : search_cards pour trouver, get_card pour le detail "
        "compact d'une fiche, get_source pour une source precise, find_cards_citing "
        "pour decouvrir qui d'autre cite une URL. "
        "L'ecriture (create_card, add_source, add_excerpt, verify_excerpts, "
        "publish_card) exige un compte : sur /mcp-account/ le client ouvre la page "
        "d'autorisation au premier appel, sans token a copier. whoami verifie "
        "l'identite du porteur."
    ),
)


def outil():
    """`@mcp.tool()`, plus l'aplatissement des optionnels du schema d'entree.

    Passer par ce decorateur plutot que de reecrire 39 signatures : les
    annotations `X | None = None` restent la bonne facon d'ecrire du Python, et
    seule la forme publiee du schema change. Les `output_schema` ne sont pas
    touches : fastmcp valide les resultats contre eux, et un outil qui rend
    legitimement `None` echouerait.
    """

    def decore(fn):
        mcp.tool()(fn)
        # L'outil enregistre est dans _local_provider._components sous la cle
        # "tool:<nom>@". On mute ses parameters en place : c'est le meme objet
        # que list_tools() servira.
        key = f"tool:{fn.__name__}@"
        stored = mcp._local_provider._components.get(key)
        if stored is not None:
            stored.parameters = aplatir_nullable(stored.parameters)
        return fn

    return decore


def _session() -> AsyncSession:
    return async_session_maker()


@outil()
async def search_cards(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Cherche des fiches publiees par sujet, par createur, ou par un travail cite.

    Le terme est confronte au titre et a la description de la fiche, a l'auteur
    du contenu, au createur, et au titre comme aux auteurs des sources citees.
    Chercher le nom d'un chercheur ou le titre d'un article ramene donc les
    fiches qui s'y appuient. Accents indifferents. Resultats compacts :
    enchainer sur get_card pour le detail.
    """
    async with _session() as db:
        return await tools.search_cards(db, query=query, limit=limit)


@outil()
async def get_card(creator: str, slug: str) -> dict[str, Any] | None:
    """Detail d'une fiche : description et sources compactes.

    Chaque source porte `linked_card` : l'adresse `{creator, slug}` de la fiche
    Philum qui documente ce travail cite, ou `null`. C'est l'arete de fiche a
    fiche, a suivre par get_card pour lire ses extraits verifies.
    """
    async with _session() as db:
        return await tools.get_card(db, creator=creator, slug=slug)


@outil()
async def get_source(source_id: str) -> dict[str, Any] | None:
    """Detail complet d'une source : extraits verbatim, retractation, archive horodatee.

    Porte aussi `linked_card`, la fiche Philum qui documente ce travail cite,
    ou `null`.
    """
    async with _session() as db:
        return await tools.get_source(db, source_id=source_id)


@outil()
async def find_cards_citing(url: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fiches publiees citant cette reference : les aretes du graphe de citations.

    L'ecriture de l'URL est indifferente (schema, `www.`, barre finale,
    parametres de campagne). Un DOI est reconnu comme l'URL de l'editeur, et
    reciproquement : passer `https://doi.org/10.1038/nature11028` ramene les
    fiches qui citent l'article sous son adresse Nature.
    """
    async with _session() as db:
        return await tools.find_cards_citing(db, url=url, limit=limit)


@outil()
async def whoami() -> dict[str, Any] | None:
    """L'utilisateur identifie par le token, ou `null` si personne.

    A appeler en premier apres avoir configure son token : verifie que
    l'authentification passe avant de tenter une action d'ecriture.
    """
    async with _session() as db:
        user = await utilisateur_courant(db)
        if user is None:
            return None
        return {"creator": user.username, "display_name": user.display_name}


@outil()
async def create_card(
    slug: str,
    title: str,
    card_kind: str = "contenu",
    content_url: str | None = None,
    description: str | None = None,
    content_authors: str | None = None,
    platform: str | None = None,
    content_type: str | None = None,
    visibility: str = "public",
) -> dict[str, Any]:
    """Cree une fiche brouillon chez l'utilisateur identifie par le token.

    `slug` : identifiant public court (lettres, chiffres, tirets ; 3-80).
    `card_kind` : contenu|sujet, c'est le premier choix a faire.
      - `contenu` documente une video, un article, un podcast qui existe
        ailleurs : `content_url` est OBLIGATOIRE et `content_authors` nomme
        les auteurs de ce contenu, qui ne sont pas le createur de la fiche.
      - `sujet` porte une bibliographie sur une question, ecrite par le
        createur : `content_url`, `content_authors`, `platform` et
        `content_type` sont interdits, il n'y a aucun contenu source.
    `platform` : youtube|podcast|blog|x|bluesky|revue-scientifique|other.
    `content_type` : video|article|post|podcast|other.
    `visibility` : public|private. La fiche naitra en brouillon dans tous les
    cas ; `publish_card` la rend visible sur le web.
    """
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.create_card(
            db,
            user,
            slug=slug,
            title=title,
            card_kind=card_kind,
            content_url=content_url,
            description=description,
            content_authors=content_authors,
            platform=platform,
            content_type=content_type,
            visibility=visibility,
        )


@outil()
async def add_source(
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
    """Ajoute une source citee a la fiche `card_slug`.

    `category` : article-scientifique|preprint|article-presse|communique|
      documentaire|interview|podcast|blog|post-social|livre|page-web|notes.
    `author_kind` : chercheur|media|institution-publique|gouvernement|ecole|
      laboratoire|entreprise|asso|individu.
    `format` : texte|video|image|audio|data.
    `stance` (optionnel) : appuie|nuance-contredit|mentionne|contexte.
    `published_at` : date de publication, ``2016``, ``2016-03`` ou
      ``2016-03-15``. A renseigner des que la source en porte une.

    La meme reference dans deux ecritures d'URL est refusee : l'identite est
    calculee sur le DOI ou l'URL normalisee. Enchaine `add_excerpt` pour
    coller un verbatim.
    """
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.add_source(
            db,
            user,
            card_slug=card_slug,
            url=url,
            title=title,
            authors=authors,
            doi=doi,
            category=category,
            author_kind=author_kind,
            format=format,
            stance=stance,
            annotation=annotation,
            journal=journal,
            published_at=published_at,
            archive_url=archive_url,
        )


@outil()
async def add_excerpt(
    source_id: str,
    text: str,
    title: str | None = None,
    context: str | None = None,
) -> dict[str, Any]:
    """Colle un extrait verbatim sur une source (obtenue via `add_source`).

    `text` : ce que la source dit exactement. `context` : la mise en
    situation qui n'appartient pas au verbatim (chapitre, thematique) --
    stockee separement, jamais recollee au texte pour ne pas attribuer a la
    source des mots qu'elle n'a pas ecrits. `title` : intitule court.

    Les extraits sont marques `suggested_by_ai` et `annotated_by_ai` : le
    lecteur voit que la selection vient d'une IA.
    """
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.add_excerpt(
            db, user, source_id=source_id, text=text, title=title, context=context
        )


@outil()
async def set_content_text(
    card_slug: str,
    text: str,
    confirm_publication_rights: bool = False,
) -> dict[str, Any]:
    """Pose le texte integral du contenu documente sur la fiche `card_slug`.

    Le texte est rendu tel quel sur la fiche publique et indexable par les
    outils de recherche par le sens.

    `confirm_publication_rights` doit valoir `true` : l'agent porte la meme
    responsabilite que l'utilisateur, il doit savoir que le contenu est
    publiable (contenu propre, libre de droit, ou droit de citation dans les
    limites). Passer `false` refuse la pose avec un message explicite.

    Chaine vide = retire le texte precedemment pose.
    """
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.set_content_text(
            db,
            user,
            card_slug=card_slug,
            text=text,
            confirm_publication_rights=confirm_publication_rights,
        )


@outil()
async def publish_card(slug: str) -> dict[str, Any]:
    """Rend la fiche `slug` visible sur le web public.

    Republier une fiche deja publiee n'ajoute pas une seconde entree au feed :
    le registre horodate le premier passage au public, pas les editions.
    """
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.publish_card(db, user, slug=slug)


# ---------------------------------------------------------------------------
# Mutations post-creation : corriger, retirer, verifier, gerer les connexions.
# Chacun de ces tools wrappe un endpoint REST deja teste. Sans eux, un agent
# qui detecte une erreur apres coup devait rebuild la fiche complete.
# ---------------------------------------------------------------------------


@outil()
async def update_card(
    slug: str,
    title: str | None = None,
    description: str | None = None,
    card_kind: str | None = None,
    content_url: str | None = None,
    content_authors: str | None = None,
    platform: str | None = None,
    content_type: str | None = None,
    visibility: str | None = None,
) -> dict[str, Any]:
    """Corrige les champs edituriaux d'une fiche existante (titre, description,
    nature, URL du contenu, auteurs, plateforme, type, visibilite). Un champ
    laisse a `None` reste inchange. Le slug n'est pas modifiable : l'identifiant
    public fait autorite dans les liens deja emis.

    `card_kind='sujet'` efface l'URL, les auteurs, la plateforme et le type du
    contenu documente : une bibliographie sur une question ne documente aucun
    contenu source.
    """
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.update_card(
            db,
            user,
            slug=slug,
            title=title,
            description=description,
            card_kind=card_kind,
            content_url=content_url,
            content_authors=content_authors,
            platform=platform,
            content_type=content_type,
            visibility=visibility,
        )


@outil()
async def update_source(
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
    """Corrige les champs edituriaux d'une source existante (titre, auteurs,
    DOI, revue, categorie, position declaree, annotation, statut pivot, date
    de publication, URL d'archive). Un champ laisse a `None` reste inchange.
    `published_at` : 2016, 2016-03 ou 2016-03-15 ; chaine vide pour effacer.
    L'URL de la source est immuable : pour la changer, `delete_source` puis
    `add_source`.
    """
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.update_source(
            db,
            user,
            source_id=source_id,
            title=title,
            authors=authors,
            doi=doi,
            journal=journal,
            category=category,
            author_kind=author_kind,
            format=format,
            stance=stance,
            annotation=annotation,
            is_pivot=is_pivot,
            published_at=published_at,
            archive_url=archive_url,
        )


@outil()
async def delete_source(source_id: str) -> dict[str, Any]:
    """Retire une source (soft-delete). La ligne reste en base pour preserver
    les references historiques (citations entrantes, attestations), elle
    disparait seulement des vues publiques."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.delete_source(db, user, source_id=source_id)


@outil()
async def delete_excerpt(source_id: str, excerpt_id: str) -> dict[str, Any]:
    """Supprime physiquement un extrait (irreversible). Preferer `update_excerpt` pour corriger."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.delete_excerpt(
            db, user, source_id=source_id, excerpt_id=excerpt_id
        )


@outil()
async def update_excerpt(
    source_id: str,
    excerpt_id: str,
    text: str | None = None,
    title: str | None = None,
    context: str | None = None,
) -> dict[str, Any]:
    """Corrige le texte, le titre ou le contexte d'un extrait ; modifier le texte annule la verification."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.update_excerpt(
            db,
            user,
            source_id=source_id,
            excerpt_id=excerpt_id,
            text=text,
            title=title,
            context=context,
        )


@outil()
async def verify_excerpts(
    source_id: str,
    provided_text: str | None = None,
) -> dict[str, Any]:
    """Relit chaque extrait d'une source vs le texte de la page.

    Fait passer les verdicts de `verified_status`: `found`, `moved`, `missing`
    ou `unreadable`. Sans cette passe, la fiche affirme qu'une source dit
    quelque chose sans que rien ne l'ait jamais confirme.

    `provided_text` : quand la page est bloquee anti-bot (403 sur ScienceDirect,
    IOP, PubMed), l'agent atteste le texte qu'il a recupere ailleurs. Le
    `text_source` de la reponse dit d'ou vient le texte de reference (`fetched`
    ou `provided`).
    """
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.verify_excerpts(
            db, user, source_id=source_id, provided_text=provided_text
        )


@outil()
async def list_connections(card_slug: str) -> dict[str, Any]:
    """Liste les connexions d'une fiche vers d'autres fiches Philum et
    inversement. `outgoing` = fiches que celle-ci cite (avec verdict a rendre
    via `confirm_connection` ou `remove_connection`). `incoming` = fiches qui
    citent celle-ci (lecture seule, elles appartiennent a d'autres createurs).
    """
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.list_connections(db, user, card_slug=card_slug)


@outil()
async def confirm_connection(card_slug: str, source_id: str) -> dict[str, Any]:
    """Confirme qu'une source pointe bien vers la fiche Philum designee.

    A appeler apres avoir constate via `list_connections` qu'une source a un
    `linked_card_id` suggere par le serveur (URL/DOI en commun avec une fiche
    existante). Refuse si la source n'appartient pas a `card_slug` ou si elle
    ne designe encore aucune fiche.
    """
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.confirm_connection(
            db, user, card_slug=card_slug, source_id=source_id
        )


@outil()
async def remove_connection(card_slug: str, source_id: str) -> dict[str, Any]:
    """Retire le lien fiche-a-fiche porte par une source, sans retirer la
    source elle-meme. La reference reste dans la bibliographie ; elle cesse
    seulement de designer une fiche Philum comme sa fiche cible."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.remove_connection(
            db, user, card_slug=card_slug, source_id=source_id
        )


# ---------------------------------------------------------------------------
# Chantier C - P2 : import, aide LLM, listing, archivage, cycle de vie.
# ---------------------------------------------------------------------------


@outil()
async def list_my_cards(status: str | None = None, limit: int = 20) -> dict[str, Any]:
    """Liste les fiches de l'utilisateur avec total et indicateur de troncature. `status` optionnel: draft|published."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.list_my_cards(db, user, status=status, limit=limit)


@outil()
async def list_sources(card_slug: str) -> list[dict[str, Any]]:
    """Liste les sources d'une fiche dans leur ordre d'affichage."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.list_sources(db, user, card_slug=card_slug)


@outil()
async def search_my_excerpts(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Recherche full-text dans les extraits de l'utilisateur."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.search_my_excerpts(db, user, query=query, limit=limit)


@outil()
async def delete_card(slug: str) -> dict[str, Any]:
    """Soft-delete d'une fiche (rejoint la corbeille, reversible via `restore_card`)."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.delete_card(db, user, slug=slug)


@outil()
async def restore_card(slug: str) -> dict[str, Any]:
    """Sort une fiche de la corbeille."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.restore_card(db, user, slug=slug)


@outil()
async def archive_sources(source_ids: list[str]) -> dict[str, Any]:
    """Declenche l'archivage Wayback pour les sources donnees."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.archive_sources(db, user, source_ids=source_ids)


@outil()
async def suggest_excerpts(
    source_id: str,
    provided_text: str | None = None,
    include_annotation: bool = True,
    include_existing: bool = True,
    include_card_context: bool = True,
) -> dict[str, Any]:
    """Le LLM propose des extraits verbatim pour une source. Chaque candidat
    est deja verifie contre le texte (anti-hallucination)."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.suggest_excerpts(
            db,
            user,
            source_id=source_id,
            provided_text=provided_text,
            include_annotation=include_annotation,
            include_existing=include_existing,
            include_card_context=include_card_context,
        )


@outil()
async def annotate_excerpt(
    source_id: str, excerpt_text: str, provided_text: str | None = None
) -> dict[str, Any]:
    """Le LLM suggere titre + `context` pour un extrait donne."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.annotate_excerpt(
            db,
            user,
            source_id=source_id,
            excerpt_text=excerpt_text,
            provided_text=provided_text,
        )


@outil()
async def chunk_text(source_id: str, text: str, size: int | None = None) -> dict[str, Any]:
    """Decoupe un texte long en chunks candidats pour poser des extraits."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.chunk_text(db, user, source_id=source_id, text=text, size=size)


@outil()
async def get_youtube_transcript(url: str) -> dict[str, Any]:
    """Recupere le transcript d'une video YouTube (via l'API interne)."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.get_youtube_transcript(db, user, url=url)


@outil()
async def get_url_metadata(url: str) -> dict[str, Any]:
    """Metadonnees editoriales d'une URL : titre, description, auteurs, date."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.get_url_metadata(db, user, url=url)


@outil()
async def import_from_content_url(card_slug: str) -> dict[str, Any]:
    """Extrait automatiquement les sources depuis l'URL du contenu de la fiche.

    Equivalent du bouton « Extraire les sources » de l'UI. Ne pose PAS les
    sources : rend la liste des candidates a l'agent qui appelle ensuite
    `add_source` sur celles qu'il retient.
    """
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.import_from_content_url(db, user, card_slug=card_slug)


# ---------------------------------------------------------------------------
# Chantier D - P3 : attestations, citations entrantes, batch, claim, parsers.
# ---------------------------------------------------------------------------


@outil()
async def create_content_attestation(card_slug: str) -> dict[str, Any]:
    """Signe cryptographiquement (Ed25519) le content_url d'une fiche.

    Etablit l'attestation immuable qui prouve l'engagement initial du createur
    sur le contenu documente. Meme si la fiche est ensuite modifiee,
    l'attestation reste et se verifie via `verify_attestation`.
    """
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.create_content_attestation(db, user, card_slug=card_slug)


@outil()
async def get_attestation(attestation_id: str) -> dict[str, Any]:
    """Recupere une attestation par son ID (lecture publique)."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.get_attestation(db, user, attestation_id=attestation_id)


@outil()
async def verify_attestation(attestation_id: str) -> dict[str, Any]:
    """Verifie la signature Ed25519 d'une attestation. Rend `valid` + raison."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.verify_attestation(db, user, attestation_id=attestation_id)


@outil()
async def list_incoming_citations() -> dict[str, Any]:
    """Liste les fiches d'autres createurs qui citent une de mes fiches."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.list_incoming_citations(db, user)


@outil()
async def mark_citations_seen() -> dict[str, Any]:
    """Marque les citations entrantes comme vues (arrete d'afficher `is_new`)."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.mark_citations_seen(db, user)


@outil()
async def list_deleted_cards(limit: int = 50) -> list[dict[str, Any]]:
    """Liste les fiches en corbeille (restaurables via `restore_card`)."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.list_deleted_cards(db, user, limit=limit)


@outil()
async def add_sources_batch(card_slug: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Ajoute plusieurs sources a une fiche en un appel.

    Chaque entree suit la meme signature que `add_source`. Utile pour les
    fiches longues : un seul commit au lieu de N.
    """
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.add_sources_batch(db, user, card_slug=card_slug, sources=sources)


@outil()
async def create_claim_request(card_id: str, message: str | None = None) -> dict[str, Any]:
    """Revendique une fiche seed (fiche automatique sans compte proprietaire).

    Ouvre une demande manuelle. Refuse si la fiche n'est pas seed.
    """
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.create_claim_request(db, user, card_id=card_id, message=message)


@outil()
async def parse_biblio(text: str) -> dict[str, Any]:
    """Parse une bibliographie collee (BibTeX, CSL, markdown, texte libre).

    Rend la liste des references detectees avec leurs metadonnees. Utile en
    amont de `add_sources_batch` pour ingerer une biblio d'un coup.
    """
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.parse_biblio(db, user, text=text)


mcp_http_app = mcp.http_app(path="/")
