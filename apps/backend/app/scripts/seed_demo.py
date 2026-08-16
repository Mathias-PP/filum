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
from collections.abc import Sequence
from datetime import UTC, date, datetime

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
from app.models.source import (
    ArchiveStatus,
    AuthorKind,
    Source,
    SourceCategory,
    SourceFormat,
    SourceStance,
)
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
            "doi": "10.1126/science.1067020",
            "journal": "Science",
            "published_at": date(2001, 11, 2),
            "stance": SourceStance.APPUIE.value,
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
            # Pre-populated Wayback snapshots for a few demo sources so the
            # "Voir l'archive" CTA is exercised on the public card without
            # waiting for the background Save-Page-Now task to land. Wayback
            # URLs with a full timestamp resolve to the closest snapshot, so
            # these stay valid even if the exact moment isn't archived.
            "archive_url": (
                "https://web.archive.org/web/20240601000000/"
                "https://www.science.org/doi/10.1126/science.1067020"
            ),
            #: Sans extrait : science.org oppose un mur de lecture, et un extrait
            #: qu'aucune relecture ne peut confirmer ne vaut pas mieux qu'une
            #: absence sur la fiche qui sert de vitrine au produit.
        },
        {
            "url": "https://www.cell.com/current-biology/fulltext/S0960-9822(10)01007-0",
            "title": "The Hippocampus Plays a Selective Role in the Retrieval of Detailed Contextual Memories",
            "authors": "Brian J. Wiltgen et al.",
            "doi": "10.1016/j.cub.2010.06.068",
            "journal": "Current Biology",
            "published_at": date(2010, 8, 10),
            "stance": SourceStance.APPUIE.value,
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.ARTICLE_SCIENTIFIQUE.value,
            "author_kind": AuthorKind.CHERCHEUR.value,
            "annotation": "Démonstration du rôle sélectif de l'hippocampe pour les détails contextuels.",
            "is_pivot": True,
            "parent_index": None,
            "citations_count": 987,
            "archive_url": (
                "https://web.archive.org/web/20240601000000/"
                "https://www.cell.com/current-biology/fulltext/S0960-9822(10)01007-0"
            ),
        },
        {
            "url": "https://www.nature.com/articles/35021052",
            "title": "Fear Memories Require Protein Synthesis in the Amygdala for Reconsolidation After Retrieval",
            "authors": "Karim Nader, Glenn E. Schafe, Joseph E. LeDoux",
            "doi": "10.1038/35021052",
            "journal": "Nature",
            "published_at": date(2000, 8, 17),
            "stance": SourceStance.APPUIE.value,
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
            "archive_url": (
                "https://web.archive.org/web/20240601000000/"
                "https://www.nature.com/articles/35021052"
            ),
        },
        {
            "url": "https://www.nature.com/articles/nature11028",
            "title": "Optogenetic Stimulation of a Hippocampal Engram Activates Fear Memory Recall",
            "authors": "Xu Liu, Steve Ramirez, Susumu Tonegawa et al.",
            "doi": "10.1038/nature11028",
            "journal": "Nature",
            "published_at": date(2012, 3, 22),
            "stance": SourceStance.APPUIE.value,
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
            "archive_url": (
                "https://web.archive.org/web/20240601000000/"
                "https://www.nature.com/articles/nature11028"
            ),
            #: Verbatim du résumé publié, dans la langue de l'article : c'est ce
            #: que « Relire la source » retrouve mot à mot. Une traduction, même
            #: fidèle, ne s'y retrouve jamais.
            "excerpts": [
                (
                    "Here we show in mice that optogenetic reactivation of hippocampal "
                    "neurons activated during fear conditioning is sufficient to induce "
                    "freezing behaviour."
                ),
                (
                    "Together, our findings indicate that activating a sparse but specific "
                    "ensemble of hippocampal neurons that contribute to a memory engram is "
                    "sufficient for the recall of that memory."
                ),
            ],
        },
        {
            "url": "https://learnmem.cshlp.org/content/12/4/361.full",
            "title": "Planting Misinformation in the Human Mind: A 30-Year Investigation of the Misinformation Effect",
            "authors": "Elizabeth F. Loftus",
            "doi": "10.1101/lm.94705",
            "journal": "Learning & Memory",
            "published_at": date(2005, 7, 1),
            "stance": SourceStance.NUANCE_CONTREDIT.value,
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.ARTICLE_SCIENTIFIQUE.value,
            "author_kind": AuthorKind.CHERCHEUR.value,
            "annotation": "Synthèse des 30 ans de recherche sur les faux souvenirs.",
            "is_pivot": False,
            "parent_index": None,
            "citations_count": 3120,
            "archive_url": (
                "https://web.archive.org/web/20240601000000/"
                "https://learnmem.cshlp.org/content/12/4/361.full"
            ),
            "conflict_of_interest": (
                "L'auteure a témoigné comme experte rémunérée dans plusieurs procès "
                "(défense, identification oculaire). Cette activité est documentée "
                "publiquement et fait partie de son parcours académique."
            ),
            #: Sans extrait : learnmem.cshlp.org ne rend rien depuis un serveur.
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
            "archive_url": (
                "https://web.archive.org/web/20240601000000/"
                "https://www.ninds.nih.gov/health-information/public-education/"
                "brain-basics/brain-basics-understanding-sleep"
            ),
            #: Sans extrait : ninds.nih.gov refuse la lecture automatisée.
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
            "archive_url": (
                "https://web.archive.org/web/20240601000000/https://memorylab.stanford.edu/"
            ),
        },
        {
            "url": "https://www.inserm.fr/dossier/memoire/",
            "title": "Mémoire : Quand nos souvenirs façonnent notre cerveau",
            "authors": "Inserm",
            "published_at": date(2017, 6, 23),
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.PAGE_WEB.value,
            "author_kind": AuthorKind.LABORATOIRE.value,
            "annotation": "Dossier de synthèse Inserm sur la mémoire, en français, à destination grand public.",
            "is_pivot": False,
            "parent_index": None,
            "archive_url": (
                "https://web.archive.org/web/20240601000000/https://www.inserm.fr/dossier/memoire/"
            ),
            "excerpts": [
                (
                    "Cette mémoire est sollicitée en permanence : par exemple, c’est elle "
                    "qui permet de retenir un numéro de téléphone le temps de le noter, ou "
                    "le début d’une phrase le temps de la terminer."
                ),
                (
                    "Enfin, la mémoire autobiographique renvoie à nos souvenirs personnels "
                    "et à nos connaissances sur nous-même, en interaction avec le monde qui "
                    "nous entoure."
                ),
            ],
        },
        # --- Tier 3 — Press ---
        {
            "url": (
                "https://www.quantamagazine.org/"
                "light-triggered-genes-reveal-the-hidden-workings-of-memory-20171214/"
            ),
            "title": "Light-Triggered Genes Reveal the Hidden Workings of Memory",
            "authors": "Elizabeth Svoboda — Quanta Magazine",
            "published_at": date(2017, 12, 14),
            "stance": SourceStance.MENTIONNE.value,
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.ARTICLE_PRESSE.value,
            "author_kind": AuthorKind.MEDIA.value,
            "annotation": (
                "Vulgarisation des travaux du laboratoire Tonegawa sur les engrammes "
                "silencieux et le rôle du subiculum dans le rappel."
            ),
            "is_pivot": False,
            "parent_index": 1,
            "archive_url": (
                "https://web.archive.org/web/20240601000000/"
                "https://www.quantamagazine.org/"
                "light-triggered-genes-reveal-the-hidden-workings-of-memory-20171214/"
            ),
            #: Sans extrait : quantamagazine.org ne rend rien depuis un serveur.
        },
        {
            "url": (
                "https://lejournal.cnrs.fr/nos-blogs/aux-frontieres-du-cerveau/"
                "et-si-le-sommeil-nous-aidait-a-faire-le-tri-dans-nos-souvenirs"
            ),
            "title": "Et si le sommeil nous aidait à faire le tri dans nos souvenirs ?",
            "authors": "Alexandra Gros — CNRS Le Journal",
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.ARTICLE_PRESSE.value,
            "author_kind": AuthorKind.MEDIA.value,
            "annotation": (
                "Billet de chercheuse sur la consolidation mnésique pendant le sommeil : "
                "downscaling synaptique, gène Homer1a, rôle de la noradrénaline."
            ),
            "is_pivot": False,
            "parent_index": 6,
            "archive_url": (
                "https://web.archive.org/web/20240601000000/"
                "https://lejournal.cnrs.fr/nos-blogs/aux-frontieres-du-cerveau/"
                "et-si-le-sommeil-nous-aidait-a-faire-le-tri-dans-nos-souvenirs"
            ),
        },
        {
            "url": "https://time.com/6171190/new-science-of-forgetting/",
            "title": "The New Science of Forgetting",
            "authors": "Corinne Purtill — TIME",
            "published_at": date(2022, 4, 28),
            "stance": SourceStance.MENTIONNE.value,
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.ARTICLE_PRESSE.value,
            "author_kind": AuthorKind.MEDIA.value,
            "annotation": (
                "Synthèse 2022 sur l'oubli comme processus actif et adaptatif, "
                "de l'évolution du mécanisme jusqu'à ses dérèglements dans le TSPT."
            ),
            "is_pivot": False,
            "parent_index": 5,
            "archive_url": (
                "https://web.archive.org/web/20240601000000/"
                "https://time.com/6171190/new-science-of-forgetting/"
            ),
            "excerpts": [
                (
                    "It’s the first known look at how a living vertebrate’s brain "
                    "restructures itself as the animal forms a memory."
                )
            ],
        },
        # --- Tier 4 — Original ---
        {
            "url": "https://radiolab.org/podcast/memory-and-forgetting",
            "title": "Memory and Forgetting",
            "authors": "Jad Abumrad & Robert Krulwich — Radiolab (WNYC)",
            "format": SourceFormat.AUDIO.value,
            "category": SourceCategory.PODCAST.value,
            "author_kind": AuthorKind.MEDIA.value,
            "annotation": (
                "Épisode où Karim Nader raconte lui-même son expérience d'effacement "
                "d'un souvenir pendant son rappel. Source orale complémentaire "
                "de l'article de 2000."
            ),
            "is_pivot": False,
            "parent_index": 3,
            "archive_url": (
                "https://web.archive.org/web/20240601000000/"
                "https://radiolab.org/podcast/memory-and-forgetting"
            ),
            "conflict_of_interest": (
                "Radiolab est une production de radio publique éditorialisée : "
                "le montage sonore sélectionne et dramatise les propos des chercheurs."
            ),
        },
        {
            "url": "https://tonegawalab.mit.edu/susumu-tonegawa/",
            "title": "Susumu Tonegawa — Picower Institute, MIT",
            "authors": "Tonegawa Lab, MIT",
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.PAGE_WEB.value,
            "author_kind": AuthorKind.LABORATOIRE.value,
            "annotation": (
                "Page du laboratoire dont sont issus les travaux sur l'engramme. "
                "Sert de rattachement institutionnel à l'article de 2012."
            ),
            "is_pivot": False,
            "parent_index": None,
        },
        {
            "url": ("https://www.penguinrandomhouse.com/books/624480/remember-by-lisa-genova/"),
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
            "archive_url": (
                "https://web.archive.org/web/20240601000000/"
                "https://www.penguinrandomhouse.com/books/624480/remember-by-lisa-genova/"
            ),
            "conflict_of_interest": (
                "Auteure également romancière à succès ; le livre est commercialisé "
                "par un éditeur grand public, ce qui peut orienter le ton vulgarisateur."
            ),
            #: Verbatim de la présentation de l'ouvrage, seul texte que la page
            #: publie. Une page de libraire ne porte pas le livre.
            "excerpts": [
                (
                    "You’ll learn whether forgotten memories are temporarily inaccessible "
                    "or erased forever and why some memories are built to exist for only a "
                    "few seconds (like a passcode) while others can last a lifetime (your "
                    "wedding day)."
                ),
                (
                    "And you’ll see how memory is profoundly impacted by meaning, emotion, "
                    "sleep, stress, and context."
                ),
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
            "archive_url": (
                "https://web.archive.org/web/20240601000000/"
                "https://www.pbs.org/wgbh/nova/video/memory-hackers/"
            ),
            #: Sans extrait : la page du documentaire ne porte pas son contenu,
            #: seulement une notice. Un extrait de la vidéo ne s'y retrouve pas.
        },
        {
            "url": "https://www.youtube.com/watch?v=X5trRLX7PQY",
            "title": "Building Blocks of Memory in the Brain",
            "authors": "Artem Kirsanov",
            "format": SourceFormat.VIDEO.value,
            "category": SourceCategory.DOCUMENTAIRE.value,
            "author_kind": AuthorKind.INDIVIDU.value,
            "annotation": (
                "Vidéo de vulgarisation scientifique qui synthétise les mécanismes "
                "moléculaires de l'engramme : conditionnement de peur, gènes précoces "
                "immédiats, marquage des populations neuronales. Approche visuelle "
                "complémentaire au contenu de la vidéo principale."
            ),
            "is_pivot": False,
            "parent_index": 1,
            "archive_url": (
                "https://web.archive.org/web/20240601000000/"
                "https://www.youtube.com/watch?v=X5trRLX7PQY"
            ),
        },
        {
            "url": "https://www.faculty.uci.edu/profile/?facultyId=4901",
            "title": "Elizabeth F. Loftus — University of California, Irvine",
            "authors": "University of California, Irvine",
            "format": SourceFormat.TEXTE.value,
            "category": SourceCategory.PAGE_WEB.value,
            "author_kind": AuthorKind.ECOLE.value,
            "annotation": (
                "Page institutionnelle de l'auteure de la synthèse sur les faux "
                "souvenirs. Permet de rattacher la source à son affiliation, "
                "et de replacer ses expertises judiciaires dans son parcours."
            ),
            "is_pivot": False,
            "parent_index": None,
        },
        {
            "url": "https://commons.wikimedia.org/wiki/File:CajalHippocampus.jpeg",
            "title": "Dessin du circuit neuronal de l'hippocampe — Santiago Ramón y Cajal, 1911",
            "authors": "Santiago Ramón y Cajal",
            "stance": SourceStance.CONTEXTE.value,
            "published_at": date(1911, 1, 1),
            "format": SourceFormat.IMAGE.value,
            "category": SourceCategory.PAGE_WEB.value,
            "author_kind": AuthorKind.CHERCHEUR.value,
            "annotation": (
                "Planche du prix Nobel de médecine 1906, fondateur de la neuroscience "
                "moderne, tirée de l'« Histologie du Système Nerveux de l'Homme et des "
                "Vertébrés ». Elle représente la circuiterie hippocampique — le siège "
                "anatomique de la mémoire décrit par Wiltgen et al."
            ),
            "is_pivot": False,
            "parent_index": None,
            "archive_url": (
                "https://web.archive.org/web/20240601000000/"
                "https://commons.wikimedia.org/wiki/File:CajalHippocampus.jpeg"
            ),
        },
    ]


def _verdicts_par_extrait(sources: Sequence[Source]) -> dict[tuple[str, str], str]:
    """Verdicts de relecture deja rendus, indexes par (url de la source, texte).

    Le seed efface et recree les sources a chaque demarrage du conteneur : sans
    ce report, la fiche vitrine repart a « jamais verifie » a chaque
    deploiement, et la page qui vend la relecture des sources n'en montre plus
    aucune preuve.

    La cle porte le texte de l'extrait, pas sa position : une phrase reecrite
    doit etre relue, sinon on affirmerait « retrouve dans la source » d'un
    texte qu'on n'y a jamais cherche.
    """
    verdicts: dict[tuple[str, str], str] = {}
    for source in sources:
        for extrait in source.excerpts:
            if extrait.verified_status:
                verdicts[(source.url, extrait.text)] = extrait.verified_status
    return verdicts


async def _get_or_create_demo_card(
    db: AsyncSession, user: User, key_manager: KeyManager
) -> tuple[BiblioCard, ContentAttestation | None]:
    result = await db.execute(
        select(BiblioCard)
        .options(selectinload(BiblioCard.sources).selectinload(Source.excerpts))
        .options(selectinload(BiblioCard.user))
        .where(
            BiblioCard.user_id == user.id,
            BiblioCard.slug == DEMO_CARD_SLUG,
        )
    )
    card = result.scalar_one_or_none()

    sources_spec = _demo_sources()
    verdicts = _verdicts_par_extrait(card.sources) if card else {}

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
            # Metadonnees verifiees (Crossref pour les DOI, extraction pour le
            # reste). Sans elles, la fiche vitrine n'affichait que des absences :
            # aucune date, donc tous les noeuds « s. d. » et une frise vide ;
            # aucun DOI, donc « non verifiable » partout sur l'acces libre et la
            # retractation. Les huit sources sans date le restent : une date
            # inventee vaudrait moins qu'un « s. d. » assume.
            doi=src.get("doi"),
            journal=src.get("journal"),
            published_at=src.get("published_at"),
            stance=src.get("stance"),
            archive_url=manual_archive,
            archive_status=(
                ArchiveStatus.ARCHIVED.value if manual_archive else ArchiveStatus.PENDING.value
            ),
            archive_timestamp=(datetime.now(UTC).replace(tzinfo=None) if manual_archive else None),
            conflict_of_interest=src.get("conflict_of_interest"),
            citations_count=src.get("citations_count"),
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
                    verified_status=verdicts.get((source.url, text)),
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

    # Create a ContentAttestation for the demo content URL (idempotent:
    # without this check, every backend restart re-running the seed would
    # accumulate a duplicate attestation row).
    attestation = None
    if card.content_url:
        existing = await db.execute(
            select(ContentAttestation).where(
                ContentAttestation.user_id == user.id,
                ContentAttestation.content_url == card.content_url,
            )
        )
        attestation = existing.scalars().first()
    if card.content_url and attestation is None:
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
