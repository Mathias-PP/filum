"""Banc d'essai de l'agent : dix demandes fixes, les memes chiffres a chaque fois.

Point 0 de `agent/plans/2026-09-13-agent-petits-modeles.md`. Sans lui, savoir si
un changement de prompt ou d'outil aide passait par une conversation reelle
relue a la main.

A lancer **depuis un poste de developpement, jamais depuis la VM**. Chaque
demande tourne sur une base SQLite neuve, avec un compte et un workspace neufs,
et appelle reellement le modele et le web.

    cd apps/backend
    BANC_BASE_URL=https://api.mistral.ai BANC_FOURNISSEUR=mistral \\
    BANC_MODELE=ministral-8b-latest BANC_CLE=... \\
    AGENT_WEB_SEARCH_PROVIDER=tavily AGENT_WEB_SEARCH_API_KEY=... \\
    uv run python -m app.scripts.banc_agent --questions 3

Chaque demande rend, entre autres : la part d'`add_excerpt` refuses, la part de
sources portant un extrait, les positions sans extrait, les jetons, la duree et
les annonces non tenues (`controle_relance`). Le resultat part dans
`banc-resultats/<modele>-<horodatage>.json`, et un tableau s'affiche.

Ne rien importer de l'application en tete de module : la base et les secrets
doivent etre poses dans l'environnement avant le premier import de `app`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

QUESTIONS: tuple[str, ...] = (
    "comment prévenir l'arthrose?",
    "Fait une fiche pour répondre à la question : le café est-il bon pour le cœur ?",
    "pourquoi le ciel est-il bleu ?",
    "est-ce que le jeûne intermittent fait maigrir plus qu'un régime classique ?",
    "quels sont les effets de la créatine sur la mémoire ?",
    "combien d'heures de sommeil faut-il à un adulte ?",
    "Crée une fiche sur l'effet Warburg dans les cellules cancéreuses",
    "est-ce que les écrans nuisent au sommeil des enfants ?",
    "comment les vaccins à ARN messager fonctionnent-ils ?",
    "pourquoi les abeilles disparaissent-elles ?",
)


def mesurer(evenements: list[dict[str, Any]]) -> dict[str, Any]:
    """Les chiffres d'un tour, tires de ses evenements. Fonction pure."""
    appels: dict[str, int] = {}
    refus: dict[str, int] = {}
    jetons = {"prompt_tokens": 0, "completion_tokens": 0}
    relances = 0
    erreurs: list[str] = []
    for evenement in evenements:
        genre = evenement.get("type")
        charge = evenement.get("payload") or {}
        if genre == "tool_result":
            nom = str(charge.get("name"))
            appels[nom] = appels.get(nom, 0) + 1
            resultat = charge.get("result")
            if isinstance(resultat, dict) and "error" in resultat:
                refus[nom] = refus.get(nom, 0) + 1
        elif genre in ("done", "continuation"):
            usage = charge.get("usage") or {}
            for cle in jetons:
                jetons[cle] += int(usage.get(cle) or 0)
        elif genre == "controle_relance":
            relances += 1
        elif genre == "error":
            erreurs.append(str(charge.get("message", ""))[:200])
    extraits_tentes = appels.get("add_excerpt", 0)
    return {
        "appels_outils": sum(appels.values()),
        "appels_par_outil": appels,
        "echecs_par_outil": refus,
        "add_excerpt_tentes": extraits_tentes,
        "add_excerpt_refuses": refus.get("add_excerpt", 0),
        "part_extraits_refuses": (
            round(refus.get("add_excerpt", 0) / extraits_tentes, 2) if extraits_tentes else None
        ),
        "controle_relances": relances,
        "erreurs": erreurs,
        **jetons,
    }


async def _mesurer_fiches(db: Any, creator_id: Any) -> dict[str, Any]:
    from sqlalchemy import func, select

    from app.models.biblio_card import BiblioCard
    from app.models.source import Source
    from app.models.source_excerpt import SourceExcerpt

    fiches = (
        (await db.execute(select(BiblioCard.id).where(BiblioCard.user_id == creator_id)))
        .scalars()
        .all()
    )
    sources = (
        await db.execute(
            select(Source.id, Source.stance).where(
                Source.biblio_card_id.in_(fiches), Source.deleted_at.is_(None)
            )
        )
    ).all()
    comptes = dict(
        (
            await db.execute(
                select(SourceExcerpt.source_id, func.count())
                .where(SourceExcerpt.source_id.in_([s.id for s in sources]))
                .group_by(SourceExcerpt.source_id)
            )
        ).all()
    )
    avec_extrait = sum(1 for s in sources if comptes.get(s.id))
    return {
        "fiches": len(fiches),
        "sources": len(sources),
        "sources_avec_extrait": avec_extrait,
        "part_sources_avec_extrait": round(avec_extrait / len(sources), 2) if sources else None,
        "extraits": sum(comptes.values()),
        "positions_sans_extrait": sum(1 for s in sources if s.stance and not comptes.get(s.id)),
    }


def _preparer_environnement(base: Path) -> None:
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{base.as_posix()}"
    os.environ.setdefault("SESSION_SECRET", "banc-d-essai-secret-de-session-32c")
    os.environ.setdefault("MASTER_ENCRYPTION_KEY", "banc-d-essai-cle-de-chiffrement-32")
    os.environ.setdefault("GOOGLE_CLIENT_ID", "banc.apps.googleusercontent.com")
    os.environ.setdefault("GOOGLE_CLIENT_SECRET", "banc")
    os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://banc/callback")
    os.environ["CI"] = "true"
    from app.core.config import Settings, get_settings

    # Meme raison que dans `tests/conftest.py` : Windows met les variables en
    # majuscules, et `case_sensitive=True` ne les verrait pas.
    Settings.model_config["case_sensitive"] = False
    get_settings.cache_clear()


async def jouer(question: str, *, fournisseur: str, base_url: str, modele: str, cle: str) -> dict:
    """Une demande sur une base neuve, et ses chiffres."""
    from uuid import uuid4

    import app.models  # noqa: F401  # enregistre toutes les tables
    from app.core.config import get_settings
    from app.crypto.keygen import KeyManager
    from app.db.database import Base, async_session_maker, engine
    from app.models.agent_provider import AgentProvider
    from app.models.user import User
    from app.services import agent_workspace
    from app.services.deroule_guide import converser_ou_derouler

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    evenements: list[dict[str, Any]] = []

    async def emit(evenement: dict[str, Any]) -> None:
        evenements.append(evenement)

    async def refuser(request_id: str, tool: str, args: dict[str, Any]) -> bool:
        # Personne pour approuver : une action sensible est refusee, comme en
        # l'absence de reponse dans l'interface.
        return False

    async with async_session_maker() as db:
        utilisateur = User(
            id=uuid4(),
            email="banc@example.test",
            username="banc",
            display_name="Banc",
            public_key="b" * 64,
            encrypted_private_key="banc",
            google_id="banc",
            is_verified=True,
        )
        db.add(utilisateur)
        await db.commit()
        await agent_workspace.assurer_workspace(db, utilisateur.id)
        await db.commit()
        provider = AgentProvider(
            id=uuid4(),
            creator_id=utilisateur.id,
            provider=fournisseur,
            display_name=fournisseur,
            base_url=base_url,
            model=modele,
            api_key_enc=KeyManager(get_settings().master_encryption_key).encrypt_private_key(cle),
            is_default=True,
        )
        debut = time.monotonic()
        # Le modele decide lui-meme de confier la question au deroule guide.
        guide = await converser_ou_derouler(
            db,
            utilisateur,
            provider,
            [{"role": "user", "content": question}],
            emit,
            refuser,
            [],
            [],
        )
        duree = round(time.monotonic() - debut, 1)
        fiches = await _mesurer_fiches(db, utilisateur.id)
    return {"question": question, "guide": guide, "duree_s": duree, **mesurer(evenements), **fiches}


def _tableau(resultats: list[dict[str, Any]]) -> str:
    colonnes = (
        ("question", "Question"),
        ("duree_s", "Durée (s)"),
        ("appels_outils", "Appels"),
        ("part_extraits_refuses", "Extraits refusés"),
        ("sources", "Sources"),
        ("part_sources_avec_extrait", "Sources avec extrait"),
        ("positions_sans_extrait", "Positions sans extrait"),
        ("prompt_tokens", "Jetons prompt"),
        ("controle_relances", "Relances"),
    )
    lignes = [
        "| " + " | ".join(titre for _, titre in colonnes) + " |",
        "|" + "---|" * len(colonnes),
    ]
    for r in resultats:
        valeurs = [str(r.get(cle) if r.get(cle) is not None else "") for cle, _ in colonnes]
        valeurs[0] = valeurs[0][:40]
        lignes.append("| " + " | ".join(valeurs) + " |")
    return "\n".join(lignes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--questions", type=int, default=len(QUESTIONS))
    parser.add_argument("--sortie", type=Path, default=Path("banc-resultats"))
    arguments = parser.parse_args()

    manquantes = [v for v in ("BANC_BASE_URL", "BANC_MODELE", "BANC_CLE") if not os.environ.get(v)]
    if manquantes:
        raise SystemExit(f"Variables manquantes : {', '.join(manquantes)}.")
    arguments.sortie.mkdir(parents=True, exist_ok=True)
    _preparer_environnement(arguments.sortie / "banc.db")

    modele = os.environ["BANC_MODELE"]
    resultats: list[dict[str, Any]] = []
    for question in QUESTIONS[: arguments.questions]:
        print(f"... {question}", flush=True)
        resultats.append(
            asyncio.run(
                jouer(
                    question,
                    fournisseur=os.environ.get("BANC_FOURNISSEUR", "custom"),
                    base_url=os.environ["BANC_BASE_URL"],
                    modele=modele,
                    cle=os.environ["BANC_CLE"],
                )
            )
        )

    horodatage = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    fichier = arguments.sortie / f"{modele.replace('/', '_')}-{horodatage}.json"
    fichier.write_text(json.dumps(resultats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(_tableau(resultats))
    print(f"\nRésultats complets : {fichier}")


if __name__ == "__main__":
    main()
