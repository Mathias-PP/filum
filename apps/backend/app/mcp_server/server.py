"""Serveur MCP Philum — lecture publique du graphe de fiches."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_maker
from app.mcp_server import tools, tools_write
from app.mcp_server.auth import exiger_utilisateur, utilisateur_courant

mcp = FastMCP(
    "philum",
    instructions=(
        "Philum expose des fiches bibliographiques publiques de createurs de contenu. "
        "Naviguer comme un graphe : search_cards pour trouver, get_card pour le detail "
        "compact d'une fiche, get_source pour une source precise, find_cards_citing "
        "pour decouvrir qui d'autre cite une URL. "
        "Pour ecrire (create_card, add_source, add_excerpt, set_content_text, "
        "publish_card), obtenir "
        "un token via POST /api/v1/auth/mcp-token depuis un navigateur connecte, "
        "puis le passer en en-tete Authorization: Bearer. whoami verifie l'identite."
    ),
)


def _session() -> AsyncSession:
    return async_session_maker()


@mcp.tool()
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


@mcp.tool()
async def get_card(creator: str, slug: str) -> dict[str, Any] | None:
    """Detail d'une fiche : description et sources compactes.

    Chaque source porte `linked_card` : l'adresse `{creator, slug}` de la fiche
    Philum qui documente ce travail cite, ou `null`. C'est l'arete de fiche a
    fiche, a suivre par get_card pour lire ses extraits verifies.
    """
    async with _session() as db:
        return await tools.get_card(db, creator=creator, slug=slug)


@mcp.tool()
async def get_source(source_id: str) -> dict[str, Any] | None:
    """Detail complet d'une source : extraits verbatim, retractation, archive horodatee.

    Porte aussi `linked_card`, la fiche Philum qui documente ce travail cite,
    ou `null`.
    """
    async with _session() as db:
        return await tools.get_source(db, source_id=source_id)


@mcp.tool()
async def find_cards_citing(url: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fiches publiees citant cette reference : les aretes du graphe de citations.

    L'ecriture de l'URL est indifferente (schema, `www.`, barre finale,
    parametres de campagne). Un DOI est reconnu comme l'URL de l'editeur, et
    reciproquement : passer `https://doi.org/10.1038/nature11028` ramene les
    fiches qui citent l'article sous son adresse Nature.
    """
    async with _session() as db:
        return await tools.find_cards_citing(db, url=url, limit=limit)


@mcp.tool()
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


@mcp.tool()
async def create_card(
    slug: str,
    title: str,
    content_url: str | None = None,
    description: str | None = None,
    content_authors: str | None = None,
    platform: str = "other",
    content_type: str = "article",
    visibility: str = "public",
) -> dict[str, Any]:
    """Cree une fiche brouillon chez l'utilisateur identifie par le token.

    `slug` : identifiant public court (lettres, chiffres, tirets ; 3-80).
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
            content_url=content_url,
            description=description,
            content_authors=content_authors,
            platform=platform,
            content_type=content_type,
            visibility=visibility,
        )


@mcp.tool()
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
    archive_url: str | None = None,
) -> dict[str, Any]:
    """Ajoute une source citee a la fiche `card_slug`.

    `category` : article-scientifique|preprint|article-presse|communique|
      documentaire|interview|podcast|blog|post-social|livre|page-web|notes.
    `author_kind` : chercheur|media|institution-publique|gouvernement|ecole|
      laboratoire|entreprise|asso|individu.
    `format` : texte|video|image|audio|data.
    `stance` (optionnel) : appuie|nuance-contredit|mentionne|contexte.

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
            archive_url=archive_url,
        )


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
async def publish_card(slug: str) -> dict[str, Any]:
    """Rend la fiche `slug` visible sur le web public.

    Republier une fiche deja publiee n'ajoute pas une seconde entree au feed :
    le registre horodate le premier passage au public, pas les editions.
    """
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.publish_card(db, user, slug=slug)


mcp_http_app = mcp.http_app(path="/")
