"""Idempotent seed: publishes the public demo card at /@example/memoire-et-cerveau.

Run via `uv run python -m app.scripts.seed_demo`. Re-running is safe (no
duplicates). Invoked from the Dockerfile CMD after `alembic upgrade head`.

The demo is a realistic bibliography that a science vulgariser (the
project's primary persona) might attach to a video about the
neuroscience of memory. It exercises every source type
(peer-reviewed / institutional / press / original / image / video) and the
`parent_source_id` citation graph (7 edges among 16 sources).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.crypto.hashing import Canonicalizer, HashService, SigningService
from app.crypto.keygen import KeyManager
from app.db.database import async_session_maker
from app.models.biblio_card import BiblioCard, CardStatus, ContentType, Platform
from app.models.source import ArchiveStatus, AuthorityLevel, Source, SourceType
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
    """16 realistic sources for a memory-and-brain vulgarization video.

    Includes academic (peer-reviewed, institutional, press) and non-academic
    (documentary, image) sources to demonstrate Filum beyond pure academia.

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
            "source_type": SourceType.PEER_REVIEWED.value,
            "authority_level": AuthorityLevel.HIGH.value,
            "annotation": (
                "Conférence Nobel 2000. Pose les fondations moléculaires de la "
                "consolidation mnésique (CREB, synapses, protéines)."
            ),
            "is_pivot": True,
            "parent_index": None,
            "citations_count": 12423,
            "impact_factor": 49.8,
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
            "source_type": SourceType.PEER_REVIEWED.value,
            "authority_level": AuthorityLevel.HIGH.value,
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
            "source_type": SourceType.PEER_REVIEWED.value,
            "authority_level": AuthorityLevel.HIGH.value,
            "annotation": (
                "Article 2000 qui relance le débat sur la reconsolidation : se souvenir "
                "rouvre la mémoire à modification. Cite Kandel comme socle."
            ),
            "is_pivot": False,
            "parent_index": 1,
            "citations_count": 4567,
            "impact_factor": 50.5,
        },
        {
            "url": "https://www.nature.com/articles/nature11028",
            "title": "Optogenetic Stimulation of a Hippocampal Engram Activates Fear Memory Recall",
            "authors": "Xu Liu, Steve Ramirez, Susumu Tonegawa et al.",
            "source_type": SourceType.PEER_REVIEWED.value,
            "authority_level": AuthorityLevel.HIGH.value,
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
            "source_type": SourceType.PEER_REVIEWED.value,
            "authority_level": AuthorityLevel.HIGH.value,
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
            "source_type": SourceType.INSTITUTIONAL.value,
            "authority_level": AuthorityLevel.HIGH.value,
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
            "source_type": SourceType.INSTITUTIONAL.value,
            "authority_level": AuthorityLevel.MEDIUM.value,
            "annotation": "Site du laboratoire de référence sur l'encodage et le rappel chez l'humain.",
            "is_pivot": False,
            "parent_index": None,
        },
        {
            "url": "https://www.inserm.fr/dossier/memoire/",
            "title": "Mémoire : Quand nos souvenirs façonnent notre cerveau",
            "authors": "Inserm",
            "source_type": SourceType.INSTITUTIONAL.value,
            "authority_level": AuthorityLevel.HIGH.value,
            "annotation": "Dossier de synthèse Inserm sur la mémoire, en français, à destination grand public.",
            "is_pivot": False,
            "parent_index": None,
        },
        # --- Tier 3 — Press ---
        {
            "url": "https://www.nytimes.com/2023/03/30/well/mind/memory-brain-science.html",
            "title": "How Your Brain Builds Memories",
            "authors": "Dana G. Smith — The New York Times",
            "source_type": SourceType.PRESS.value,
            "authority_level": AuthorityLevel.MEDIUM.value,
            "annotation": (
                "Vulgarisation grand public des travaux de Kandel et successeurs. "
                "Cite l'article fondateur de 2001 comme socle."
            ),
            "is_pivot": False,
            "parent_index": 1,
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
            "source_type": SourceType.PRESS.value,
            "authority_level": AuthorityLevel.MEDIUM.value,
            "annotation": "Article 2024 reprenant les ressources NIH sur sommeil et consolidation.",
            "is_pivot": False,
            "parent_index": 6,
        },
        {
            "url": "https://www.nature.com/articles/d41586-022-04123-3",
            "title": "The Neuroscience of Forgetting",
            "authors": "Lauren Gravitz — Nature News",
            "source_type": SourceType.PRESS.value,
            "authority_level": AuthorityLevel.MEDIUM.value,
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
            "source_type": SourceType.ORIGINAL.value,
            "authority_level": AuthorityLevel.MEDIUM.value,
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
            "source_type": SourceType.ORIGINAL.value,
            "authority_level": AuthorityLevel.LOW.value,
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
            "source_type": SourceType.ORIGINAL.value,
            "authority_level": AuthorityLevel.MEDIUM.value,
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
        # --- Tier 5 — Non-academic (documentary, image) ---
        {
            "url": "https://www.pbs.org/wgbh/nova/video/memory-hackers/",
            "title": "Memory Hackers",
            "authors": "NOVA PBS — Documentaire",
            "source_type": SourceType.ORIGINAL.value,
            "authority_level": AuthorityLevel.MEDIUM.value,
            "annotation": (
                "Documentaire vidéo sur la plasticité de la mémoire qui illustre "
                "par des cas cliniques et des expériences les concepts de reconsolidation "
                "et d'engramme vus dans les articles de Nader et Tonegawa."
            ),
            "is_pivot": False,
            "parent_index": 4,
            "views_count": 2_100_000,
            "excerpts": [
                (
                    "Chez certains individus, la mémoire n'est pas une histoire figée : "
                    "chaque rappel la réécrit, et cette malléabilité est la clé "
                    "de notre capacité à apprendre."
                )
            ],
        },
        {
            "url": "https://wellcomecollection.org/works/pb7xkuyz",
            "title": "Dessin des neurones de l'hippocampe — Santiago Ramón y Cajal, 1909",
            "authors": "Santiago Ramón y Cajal",
            "source_type": SourceType.ORIGINAL.value,
            "authority_level": AuthorityLevel.HIGH.value,
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
) -> BiblioCard:
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
                "Bibliographie complète signée cryptographiquement."
            ),
            content_url="https://www.youtube.com/watch?v=memoire-et-cerveau",
            platform=Platform.YOUTUBE.value,
            content_type=ContentType.VIDEO.value,
            status=CardStatus.DRAFT.value,
            canonical_hash="",
            signature="",
        )
        db.add(card)
        await db.flush()
    else:
        # No early return for PUBLISHED cards — always refresh sources and
        # excerpts so the demo card picks up schema additions (excerpts,
        # indicators, conflicts, new sources). Card-level metadata that does
        # NOT enter the canonical hash can be updated safely here.
        card.description = (
            "Vidéo de vulgarisation sur la neuroscience de la mémoire : "
            "consolidation, reconsolidation, oubli actif, sommeil. "
            "Bibliographie complète signée cryptographiquement."
        )
        # Drop old sources — DB cascade (ON DELETE CASCADE) handles
        # source_excerpts automatically.
        await db.execute(delete(Source).where(Source.biblio_card_id == card.id))
        await db.flush()

    created_sources: list[Source] = []
    # First pass: create every source without parent_source_id so we
    # know their freshly generated UUIDs.
    for position, src in enumerate(sources_spec):
        source = Source(
            biblio_card_id=card.id,
            position=position,
            url=src["url"],
            title=src["title"],
            authors=src["authors"],
            source_type=src["source_type"],
            authority_level=src["authority_level"],
            annotation=src["annotation"],
            is_pivot=src["is_pivot"],
            archive_status=ArchiveStatus.PENDING.value,
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

    # Second pass: wire parent_source_id (1-based parent_index → 0-based
    # list lookup). Skip self-references and out-of-range indices.
    for index, src in enumerate(sources_spec):
        parent_index = src.get("parent_index")
        if parent_index is None:
            continue
        parent_pos = parent_index - 1
        if parent_pos < 0 or parent_pos >= len(created_sources) or parent_pos == index:
            continue
        created_sources[index].parent_source_id = created_sources[parent_pos].id

    await db.commit()
    await db.refresh(card, attribute_names=["sources", "user"])

    # Canonical payload — explicitly EXCLUDES parent_source_id so adding
    # the citation graph never invalidates signatures on existing cards.
    sources_data = [
        {
            "url": s.url,
            "title": s.title,
            "source_type": s.source_type,
            "is_pivot": s.is_pivot,
            "archive_url": s.archive_url,
        }
        for s in sorted(card.sources, key=lambda x: x.position)
    ]
    content_to_sign = {
        "id": str(card.id),
        "title": card.title,
        "user_id": str(card.user_id),
        "slug": card.slug,
        "sources": sources_data,
        "created_at": card.created_at.isoformat(),
    }
    canonical = Canonicalizer.canonicalize(content_to_sign)
    content_hash = HashService.sha256(canonical)
    private_pem = key_manager.decrypt_private_key(card.user.encrypted_private_key)
    signature = SigningService.from_pem(private_pem).sign(content_hash)

    card.canonical_hash = content_hash
    card.signature = signature
    card.signed_at = _utcnow_naive()
    card.published_at = _utcnow_naive()
    card.status = CardStatus.PUBLISHED.value

    await db.commit()

    # Re-fetch with eager-loaded sources so callers can read
    # `card.sources` without triggering a lazy load (the async session
    # cannot do sync lazy loads outside a greenlet context).
    refreshed = await db.execute(
        select(BiblioCard)
        .options(selectinload(BiblioCard.sources).selectinload(Source.excerpts))
        .options(selectinload(BiblioCard.user))
        .where(BiblioCard.id == card.id)
    )
    return refreshed.scalar_one()


async def seed() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    settings = get_settings()
    key_manager = KeyManager(settings.master_encryption_key)

    async with async_session_maker() as db:
        user = await _get_or_create_demo_user(db, key_manager)
        card = await _get_or_create_demo_card(db, user, key_manager)
        parent_count = sum(1 for s in card.sources if s.parent_source_id is not None)
        logger.info(
            "Seed demo OK: user=%s card=%s status=%s sources=%d edges=%d",
            user.username,
            card.slug,
            card.status,
            len(card.sources),
            parent_count,
        )


if __name__ == "__main__":
    asyncio.run(seed())
