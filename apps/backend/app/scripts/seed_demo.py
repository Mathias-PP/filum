"""Idempotent seed: publishes the public demo card at /@example/memoire-et-cerveau.

Run via `uv run python -m app.scripts.seed_demo`. Re-running is safe (no
duplicates). Invoked from the Dockerfile CMD after `alembic upgrade head`.

The demo is a realistic bibliography that a science vulgariser (the
project's primary persona) might attach to a video about the
neuroscience of memory. It exercises every source type
(peer-reviewed / institutional / press / original / image / video) and the
`parent_source_id` citation graph (7 edges among 16 sources).

On first run, it also creates a ContentAttestation for the demo video URL.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.crypto.hashing import HashService
from app.crypto.keygen import KeyManager
from app.crypto.signing import Canonicalizer, SigningService
from app.db.database import async_session_maker
from app.models.biblio_card import BiblioCard, CardStatus, ContentType, Platform
from app.models.content_attestation import ContentAttestation
from app.models.source import ArchiveStatus, AuthorKind, Source, SourceCategory, SourceFormat
from app.models.source_excerpt import SourceExcerpt
from app.models.user import User


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


logger = logging.getLogger(__name__)

DEMO_USERNAME = "example"
DEMO_CARD_SLUG = "memoire-et-cerveau"
DEMO_DISPLAY_NAME = "Léa Marchand"
DEMO_BIO = (
    "Vulgarisation scientifique en neurobiologie. ENS Lyon · Doctorat en neurosciences cognitives."
)


async def _get_or_create_demo_user(db: AsyncSession, key_manager: KeyManager) -> User:
    result = await db.execute(select(User).where(User.username == DEMO_USERNAME))
    user = result.scalar_one_or_none()

    if user is None:
        private_pem, _public_pem, public_key_raw = KeyManager.generate_keypair()
        encrypted_private = key_manager.encrypt_private_key(private_pem)
        user = User(
            email="lea.marchand@filum.app",
            username=DEMO_USERNAME,
            display_name=DEMO_DISPLAY_NAME,
            bio=DEMO_BIO,
            public_key=public_key_raw,
            encrypted_private_key=encrypted_private,
            is_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    # Idempotent identity refresh: bring legacy demo user (Filum Demo) up to
    # the current realistic identity without breaking FK referenced from
    # any existing card.
    updated = False
    if user.display_name != DEMO_DISPLAY_NAME:
        user.display_name = DEMO_DISPLAY_NAME
        updated = True
    if user.bio != DEMO_BIO:
        user.bio = DEMO_BIO
        updated = True
    if updated:
        await db.commit()
        await db.refresh(user)
    return user


def _demo_sources() -> list[dict]:
    """18 realistic sources for a memory-and-brain vulgarization video.

    Includes academic (peer-reviewed, institutional, press) and non-academic
    (documentary, video, image) sources to demonstrate Filum beyond pure academia.

    Order is meaningful: parent_index references the 1-based position of
    a previously-listed source (so parents are always created before
    their children).
    """
    return [
        # --- Tier 1 — Foundational peer-reviewed ---
        {
            "url": "https://www.science.org/doi/10.1126/science.1067020",
            "title": "The Molecular Biology of Memory Storage: A Dialogue Between Genes and Synapses",
            "authors": "Eric R. Kandel",
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.ARTICLE_SCIENTIFIQUE.value,
            "author_kind": AuthorKind.CHERCHEUR.value,
            "annotation": (
                "Conférence Nobel 2000. Pose les fondations moléculaires de la "
                "consolidation mnésique (CREB, synapses, protéines)."
            ),
            "is_pivot": True,
            "parent_index": None,
            "citations_count": 12423,
            "impact_factor": 49.8,
            # Pre-populated Wayback snapshots for a few demo sources so the
            # "Voir l'archive" CTA is exercised on the public card without
            # waiting for the background Save-Page-Now task to land. Wayback
            # URLs with a full timestamp resolve to the closest snapshot, so
            # these stay valid even if the exact moment isn't archived.
            "archive_url": (
                "https://web.archive.org/web/20240601000000/"
                "https://www.science.org/doi/10.1126/science.1067020"
            ),
            "excerpts": [
                (
                    "La mémoire à long terme requiert la synthèse de nouvelles protéines "
                    "et un remodelage durable des connexions synaptiques."
                ),
                (
                    "CREB agit comme un commutateur génétique reliant l'activité neuronale "
                    "à l'expression de gènes de stabilisation synaptique."
                ),
            ],
        },
        {
            "url": "https://www.cell.com/current-biology/fulltext/S0960-9822(10)01007-0",
            "title": "The Hippocampus Plays a Selective Role in the Retrieval of Detailed Contextual Memories",
            "authors": "Brian J. Wiltgen et al.",
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.ARTICLE_SCIENTIFIQUE.value,
            "author_kind": AuthorKind.CHERCHEUR.value,
            "annotation": "Démonstration du rôle sélectif de l'hippocampe pour les détails contextuels.",
            "is_pivot": True,
            "parent_index": None,
            "citations_count": 987,
            "impact_factor": 8.1,
        },
        {
            "url": "https://www.nature.com/articles/35021052",
            "title": "Fear Memories Require Protein Synthesis in the Amygdala for Reconsolidation After Retrieval",
            "authors": "Karim Nader, Glenn E. Schafe, Joseph E. LeDoux",
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.ARTICLE_SCIENTIFIQUE.value,
            "author_kind": AuthorKind.CHERCHEUR.value,
            "annotation": (
                "Article 2000 qui relance le débat sur la reconsolidation : se souvenir "
                "rouvre la mémoire à modification. Cite Kandel comme socle."
            ),
            "is_pivot": False,
            "parent_index": 1,
            "citations_count": 4567,
            "impact_factor": 50.5,
            "archive_url": (
                "https://web.archive.org/web/20240601000000/"
                "https://www.nature.com/articles/35021052"
            ),
        },
        {
            "url": "https://www.nature.com/articles/nature11028",
            "title": "Optogenetic Stimulation of a Hippocampal Engram Activates Fear Memory Recall",
            "authors": "Xu Liu, Steve Ramirez, Susumu Tonegawa et al.",
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.ARTICLE_SCIENTIFIQUE.value,
            "author_kind": AuthorKind.CHERCHEUR.value,
            "annotation": (
                "Première preuve causale d'un engramme dans l'hippocampe par optogénétique. "
                "S'appuie sur Wiltgen 2010 pour le rôle de l'hippocampe."
            ),
            "is_pivot": False,
            "parent_index": 2,
            "citations_count": 2890,
            "impact_factor": 50.5,
            "excerpts": [
                (
                    "L'activation optogénétique d'un sous-ensemble de neurones du gyrus denté "
                    "suffit à déclencher le rappel d'une mémoire de peur."
                )
            ],
        },
        {
            "url": "https://learnmem.cshlp.org/content/12/4/361.full",
            "title": "Planting Misinformation in the Human Mind: A 30-Year Investigation of the Misinformation Effect",
            "authors": "Elizabeth F. Loftus",
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.ARTICLE_SCIENTIFIQUE.value,
            "author_kind": AuthorKind.CHERCHEUR.value,
            "annotation": "Synthèse des 30 ans de recherche sur les faux souvenirs.",
            "is_pivot": False,
            "parent_index": None,
            "citations_count": 3120,
            "impact_factor": 3.3,
            "conflict_of_interest": (
                "L'auteure a témoigné comme experte rémunérée dans plusieurs procès "
                "(défense, identification oculaire). Cette activité est documentée "
                "publiquement et fait partie de son parcours académique."
            ),
            "excerpts": [
                (
                    "De simples mots après l'événement suffisent à introduire des détails "
                    "qui n'existaient pas, sans que le témoin perçoive la moindre altération."
                )
            ],
        },
        # --- Tier 2 — Institutional ---
        {
            "url": "https://www.ninds.nih.gov/health-information/public-education/brain-basics/brain-basics-understanding-sleep",
            "title": "Brain Basics: Understanding Sleep",
            "authors": "NIH — National Institute of Neurological Disorders and Stroke",
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.PAGE_WEB.value,
            "author_kind": AuthorKind.INSTITUTION_PUBLIQUE.value,
            "annotation": "Ressource pédagogique NIH sur le sommeil et son rôle dans la consolidation mnésique.",
            "is_pivot": False,
            "parent_index": None,
            "excerpts": [
                (
                    "Le sommeil, en particulier les phases lentes profondes et le REM, "
                    "joue un rôle actif dans la consolidation des apprentissages récents."
                )
            ],
        },
        {
            "url": "https://memorylab.stanford.edu/",
            "title": "Stanford Memory Lab — Anthony Wagner, Principal Investigator",
            "authors": "Stanford University",
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.PAGE_WEB.value,
            "author_kind": AuthorKind.ECOLE.value,
            "annotation": "Site du laboratoire de référence sur l'encodage et le rappel chez l'humain.",
            "is_pivot": False,
            "parent_index": None,
        },
        {
            "url": "https://www.inserm.fr/dossier/memoire/",
            "title": "Mémoire : Quand nos souvenirs façonnent notre cerveau",
            "authors": "Inserm",
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.PAGE_WEB.value,
            "author_kind": AuthorKind.LABORATOIRE.value,
            "annotation": "Dossier de synthèse Inserm sur la mémoire, en français, à destination grand public.",
            "is_pivot": False,
            "parent_index": None,
        },
        # --- Tier 3 — Press ---
        {
            "url": "https://www.nytimes.com/2023/03/30/well/mind/memory-brain-science.html",
            "title": "How Your Brain Builds Memories",
            "authors": "Dana G. Smith — The New York Times",
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.ARTICLE_PRESSE.value,
            "author_kind": AuthorKind.MEDIA.value,
            "annotation": (
                "Vulgarisation grand public des travaux de Kandel et successeurs. "
                "Cite l'article fondateur de 2001 comme socle."
            ),
            "is_pivot": False,
            "parent_index": 1,
            "archive_url": (
                "https://web.archive.org/web/20240601000000/"
                "https://www.nytimes.com/2023/03/30/well/mind/memory-brain-science.html"
            ),
            "excerpts": [
                (
                    "Chaque souvenir rappelé est en partie reconstruit ; les neurosciences "
                    "y voient moins un magnétoscope qu'un atelier d'assemblage."
                )
            ],
        },
        {
            "url": "https://www.lemonde.fr/sciences/article/2024/03/15/le-sommeil-gardien-de-la-memoire.html",
            "title": "Le sommeil, gardien de la mémoire",
            "authors": "Hervé Morin — Le Monde Sciences",
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.ARTICLE_PRESSE.value,
            "author_kind": AuthorKind.MEDIA.value,
            "annotation": "Article 2024 reprenant les ressources NIH sur sommeil et consolidation.",
            "is_pivot": False,
            "parent_index": 6,
            "archive_url": (
                "https://web.archive.org/web/20240601000000/"
                "https://www.lemonde.fr/sciences/article/2024/03/15/"
                "le-sommeil-gardien-de-la-memoire.html"
            ),
        },
        {
            "url": "https://www.nature.com/articles/d41586-022-04123-3",
            "title": "The Neuroscience of Forgetting",
            "authors": "Lauren Gravitz — Nature News",
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.ARTICLE_PRESSE.value,
            "author_kind": AuthorKind.MEDIA.value,
            "annotation": (
                "Synthèse Nature News sur l'oubli comme processus actif. "
                "Reprend l'effet de désinformation de Loftus."
            ),
            "is_pivot": False,
            "parent_index": 5,
        },
        # --- Tier 4 — Original ---
        {
            "url": "https://lexfridman.com/karim-nader/",
            "title": "Lex Fridman Podcast #310 — Karim Nader on Memory Reconsolidation",
            "authors": "Lex Fridman & Karim Nader",
            "format": SourceFormat.AUDIO.value,
            "category": SourceCategory.PODCAST.value,
            "author_kind": AuthorKind.INDIVIDU.value,
            "annotation": (
                "Entretien long format avec l'auteur de l'article 2000. "
                "Source primaire complémentaire au papier scientifique."
            ),
            "is_pivot": False,
            "parent_index": 3,
            "subscribers_count": 4_500_000,
            "views_count": 2_300_000,
            "conflict_of_interest": (
                "Lex Fridman est un podcasteur indépendant financé par des sponsors. "
                "Il n'est pas chercheur ; ses entretiens sont éditorialisés."
            ),
        },
        {
            "url": "https://lea-marchand.filum.app/notes/tonegawa-tokyo-2024",
            "title": "Notes de tournage : interview Susumu Tonegawa, Tokyo, mars 2024",
            "authors": "Léa Marchand",
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.NOTES.value,
            "author_kind": AuthorKind.INDIVIDU.value,
            "annotation": (
                "Notes personnelles prises pendant l'interview de Tonegawa. "
                "Citations brutes utilisées dans la vidéo en voix off."
            ),
            "is_pivot": False,
            "parent_index": None,
        },
        {
            "url": "https://www.simonandschuster.com/books/Remember/Lisa-Genova/9781982171544",
            "title": "Remember: The Science of Memory and the Art of Forgetting",
            "authors": "Lisa Genova",
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.LIVRE.value,
            "author_kind": AuthorKind.CHERCHEUR.value,
            "annotation": (
                "Livre 2021 d'une neuroscientifique pour le grand public. "
                "Référence narrative pour la structure de la vidéo."
            ),
            "is_pivot": False,
            "parent_index": None,
            "conflict_of_interest": (
                "Auteure également romancière à succès ; le livre est commercialisé "
                "par un éditeur grand public, ce qui peut orienter le ton vulgarisateur."
            ),
            "excerpts": [
                (
                    "Oublier n'est pas un défaut du cerveau — c'est une fonction qui "
                    "préserve l'essentiel en éliminant le bruit du quotidien."
                )
            ],
        },
        # --- Tier 5 — Non-academic (video, documentary, image) ---
        {
            "url": "https://www.pbs.org/wgbh/nova/video/memory-hackers/",
            "title": "Memory Hackers",
            "authors": "NOVA PBS — Documentaire",
            "format": SourceFormat.VIDEO.value,
            "category": SourceCategory.DOCUMENTAIRE.value,
            "author_kind": AuthorKind.MEDIA.value,
            "annotation": (
                "Documentaire vidéo sur la plasticité de la mémoire qui illustre "
                "par des cas cliniques et des expériences les concepts de reconsolidation "
                "et d'engramme vus dans les articles de Nader et Tonegawa."
            ),
            "is_pivot": False,
            "parent_index": 4,
            "views_count": 2_100_000,
            "archive_url": (
                "https://web.archive.org/web/20240601000000/"
                "https://www.pbs.org/wgbh/nova/video/memory-hackers/"
            ),
            "excerpts": [
                (
                    "Chez certains individus, la mémoire n'est pas une histoire figée : "
                    "chaque rappel la réécrit, et cette malléabilité est la clé "
                    "de notre capacité à apprendre."
                )
            ],
        },
        {
            "url": "https://www.youtube.com/watch?v=H8UQdB3vG6A",
            "title": "How Memories Are Made: The Neuroscience of Memory Formation",
            "authors": "Artem Kirsanov",
            "format": SourceFormat.VIDEO.value,
            "category": SourceCategory.DOCUMENTAIRE.value,
            "author_kind": AuthorKind.INDIVIDU.value,
            "annotation": (
                "Vidéo de vulgarisation scientifique qui synthétise les mécanismes "
                "moléculaires et cellulaires de la mémoire, en s'appuyant notamment "
                "sur les travaux de Kandel, Nader et Tonegawa. Approche visuelle "
                "complémentaire au contenu de la vidéo principale."
            ),
            "is_pivot": False,
            "parent_index": 1,
            "views_count": 1_800_000,
        },
        {
            "url": "https://lea-marchand.filum.app/notes/loftus-interview-2025",
            "title": "Compte-rendu : entretien avec Elizabeth Loftus sur les faux souvenirs",
            "authors": "Léa Marchand",
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.NOTES.value,
            "author_kind": AuthorKind.INDIVIDU.value,
            "annotation": (
                "Notes personnelles prises lors d'un entretien informel avec Loftus "
                "après une conférence à Paris en 2025. Échanges sur l'éthique "
                "et la controverse autour de ses expertises judiciaires."
            ),
            "is_pivot": False,
            "parent_index": None,
        },
        {
            "url": "https://wellcomecollection.org/works/pb7xkuyz",
            "title": "Dessin des neurones de l'hippocampe — Santiago Ramón y Cajal, 1909",
            "authors": "Santiago Ramón y Cajal",
            "format": SourceFormat.IMAGE.value,
            "category": SourceCategory.PAGE_WEB.value,
            "author_kind": AuthorKind.CHERCHEUR.value,
            "annotation": (
                "Dessin original du prix Nobel de médecine 1906, fondateur de la "
                "neuroscience moderne. Cette planche représente pour la première fois "
                "la structure détaillée des neurones hippocampiques — le siège "
                "anatomique de la mémoire décrit par Wiltgen et al."
            ),
            "is_pivot": False,
            "parent_index": None,
            "impact_factor": None,
        },
    ]


async def _get_or_create_demo_card(
    db: AsyncSession, user: User, key_manager: KeyManager
) -> tuple[BiblioCard, ContentAttestation | None]:
    result = await db.execute(
        select(BiblioCard)
        .options(selectinload(BiblioCard.sources))
        .options(selectinload(BiblioCard.user))
        .where(
            BiblioCard.user_id == user.id,
            BiblioCard.slug == DEMO_CARD_SLUG,
        )
    )
    card = result.scalar_one_or_none()

    sources_spec = _demo_sources()

    if card is None:
        card = BiblioCard(
            user_id=user.id,
            slug=DEMO_CARD_SLUG,
            title="Comment notre cerveau forme et oublie nos souvenirs",
            description=(
                "Vidéo de vulgarisation sur la neuroscience de la mémoire : "
                "consolidation, reconsolidation, oubli actif, sommeil. "
                "Bibliographie complète."
            ),
            content_url="https://www.youtube.com/watch?v=memoire-et-cerveau",
            platform=Platform.YOUTUBE.value,
            content_type=ContentType.VIDEO.value,
            status=CardStatus.DRAFT.value,
        )
        db.add(card)
        await db.flush()
    else:
        card.description = (
            "Vidéo de vulgarisation sur la neuroscience de la mémoire : "
            "consolidation, reconsolidation, oubli actif, sommeil. "
            "Bibliographie complète."
        )
        await db.execute(delete(Source).where(Source.biblio_card_id == card.id))
        await db.flush()

    created_sources: list[Source] = []
    for position, src in enumerate(sources_spec):
        manual_archive = src.get("archive_url")
        source = Source(
            biblio_card_id=card.id,
            position=position,
            url=src["url"],
            title=src["title"],
            authors=src["authors"],
            format=src["format"],
            category=src["category"],
            author_kind=src["author_kind"],
            annotation=src["annotation"],
            is_pivot=src["is_pivot"],
            archive_url=manual_archive,
            archive_status=(
                ArchiveStatus.ARCHIVED.value if manual_archive else ArchiveStatus.PENDING.value
            ),
            archive_timestamp=(datetime.now(UTC).replace(tzinfo=None) if manual_archive else None),
            conflict_of_interest=src.get("conflict_of_interest"),
            citations_count=src.get("citations_count"),
            subscribers_count=src.get("subscribers_count"),
            views_count=src.get("views_count"),
            impact_factor=src.get("impact_factor"),
        )
        db.add(source)
        created_sources.append(source)
    await db.flush()

    for source, src in zip(created_sources, sources_spec, strict=True):
        for excerpt_position, text in enumerate(src.get("excerpts", []) or []):
            db.add(
                SourceExcerpt(
                    source_id=source.id,
                    position=excerpt_position,
                    text=text,
                    suggested_by_ai=False,
                )
            )
    await db.flush()

    for index, src in enumerate(sources_spec):
        parent_index = src.get("parent_index")
        if parent_index is None:
            continue
        parent_pos = parent_index - 1
        if parent_pos < 0 or parent_pos >= len(created_sources) or parent_pos == index:
            continue
        created_sources[index].parent_source_id = created_sources[parent_pos].id

    card.published_at = _utcnow_naive()
    card.status = CardStatus.PUBLISHED.value

    await db.commit()

    # Create a ContentAttestation for the demo content URL
    attestation = None
    if card.content_url:
        now = _utcnow_naive()
        content_to_sign = {
            "user_id": str(user.id),
            "content_url": card.content_url,
            "attested_at": now.isoformat(),
        }
        canonical = Canonicalizer.canonicalize(content_to_sign)
        content_hash = HashService.sha256(canonical)
        private_pem = key_manager.decrypt_private_key(user.encrypted_private_key)
        signature = SigningService.from_pem(private_pem).sign(content_hash)

        attestation = ContentAttestation(
            user_id=user.id,
            content_url=card.content_url,
            attested_at=now,
            canonical_hash=content_hash,
            signature=signature,
        )
        db.add(attestation)
        await db.commit()

    refreshed = await db.execute(
        select(BiblioCard)
        .options(selectinload(BiblioCard.sources).selectinload(Source.excerpts))
        .options(selectinload(BiblioCard.user))
        .where(BiblioCard.id == card.id)
    )
    return refreshed.scalar_one(), attestation


async def seed() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    settings = get_settings()
    key_manager = KeyManager(settings.master_encryption_key)

    async with async_session_maker() as db:
        user = await _get_or_create_demo_user(db, key_manager)
        card, attestation = await _get_or_create_demo_card(db, user, key_manager)
        parent_count = sum(1 for s in card.sources if s.parent_source_id is not None)
        log_extra = ""
        if attestation:
            log_extra = f" attestation={attestation.id}"
        logger.info(
            "Seed demo OK: user=%s card=%s status=%s sources=%d edges=%d%s",
            user.username,
            card.slug,
            card.status,
            len(card.sources),
            parent_count,
            log_extra,
        )


if __name__ == "__main__":
    asyncio.run(seed())
