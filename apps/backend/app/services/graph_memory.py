from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.biblio_card import BiblioCard
from app.models.graph_memory import GraphAlias, GraphEntity, GraphRelation
from app.models.source import Source

# Ontologie fermée, réduite à ce que `build_graph` écrit réellement. Le portage
# initial déclarait 7 types et 11 prédicats pour 4 types et 3 prédicats
# construits : un vocabulaire déclaré au-delà de l'écrit fait croire à une
# session future qu'elle dispose d'arêtes qui n'existent pas. Toute extension
# se fait ici *et* dans `build_graph`, jamais ici seulement.
ENTITY_TYPES = {"PERSON", "CARD", "SOURCE", "CONCEPT"}
PREDICATES = {"authored_by", "cites", "references"}

# La jointure sur `biblio_cards` sert le slug plutôt que l'UUID de la fiche : le
# modèle lisait `(7c9a1f2e-...)`, qui ne le mène nulle part et qu'il ne peut ni
# citer ni rappeler, là où le slug est l'identifiant que le reste des outils
# accepte.
WALK_SQL = """
WITH RECURSIVE walk(entity_id, depth) AS (
  SELECT id, 0 FROM graph_entities WHERE id IN ({seeds})
  UNION
  SELECT CASE WHEN r.source_id = w.entity_id THEN r.target_id ELSE r.source_id END, w.depth + 1
  FROM graph_relations r JOIN walk w ON w.entity_id IN (r.source_id, r.target_id)
  WHERE w.depth < :hops
)
SELECT e1.name, r.predicate, e2.name, c.slug,
       LEAST((SELECT MIN(depth) FROM walk WHERE entity_id = r.source_id),
             (SELECT MIN(depth) FROM walk WHERE entity_id = r.target_id)) AS near
FROM graph_relations r
JOIN graph_entities e1 ON e1.id = r.source_id
JOIN graph_entities e2 ON e2.id = r.target_id
LEFT JOIN biblio_cards c ON c.id = r.source_card_id
WHERE r.source_id IN (SELECT entity_id FROM walk)
  AND r.target_id IN (SELECT entity_id FROM walk)
ORDER BY near
"""


def _normalise(name: str) -> str:
    return name.lower().strip().replace(" ", "_")


def entity_id(type_: str, name: str) -> str:
    key = f"{type_}:{_normalise(name)}"
    return str(uuid.uuid5(uuid.NAMESPACE_OID, key))


@dataclass
class Facts:
    triples: list
    notes: list
    ms: float

    def as_text(self) -> str:
        entete = f"memoire : {len(self.triples)} faits rappeles en {self.ms:.0f} ms"
        if not self.triples:
            return entete + "\n(aucun fait du graphe ne correspond a cette question)"
        largeur = max(len(f"{s} --[{p}]--> {t}") for s, p, t, _ in self.triples)
        lignes = [f"{f'{s} --[{p}]--> {t}':<{largeur}}   ({doc})" for s, p, t, doc in self.triples]
        texte = entete + "\n\n" + "\n".join(lignes)
        if self.notes:
            texte += "\n\nou :\n" + "\n".join(f"  {n} : {d}" for n, d in self.notes)
        return texte


#: Écart minimal entre deux reconstructions. Le graphe est **global** : il porte
#: les fiches publiées et publiques de tout le monde, et le reconstruire les vide
#: puis les réécrit toutes. L'outil MCP étant ouvert à tout compte authentifié,
#: rien n'empêchait de le rappeler en boucle et de faire porter à la base le coût
#: d'un parcours complet à chaque appel.
#:
#: L'écart est tenu en mémoire de processus, pas en base : Philum tourne sur un
#: conteneur unique. Un passage en multi-instance devrait le déplacer, faute de
#: quoi la garde vaudra par instance.
_ECART_RECONSTRUCTION_S = 300.0

_derniere_reconstruction: float | None = None


class ReconstructionTropRecenteError(Exception):
    """Le graphe vient d'être reconstruit, et il l'est pour tout le monde."""


async def build_graph(db: AsyncSession, *, forcer: bool = False) -> dict:
    """Construit le graphe depuis les fiches publiques (déterministe, sans LLM).

    Deux passes : d'abord tous les nœuds, adressés par leur contenu, puis les
    arêtes et les alias résolus par nom normalisé.

    Vide et réécrit **tout** le graphe, qui est global. La reconstruction se fait
    en une transaction, donc personne ne lit un graphe à moitié construit, mais
    elle coûte un parcours complet : d'où l'écart minimal entre deux appels.
    """
    global _derniere_reconstruction
    maintenant = time.monotonic()
    if (
        not forcer
        and _derniere_reconstruction is not None
        and maintenant - _derniere_reconstruction < _ECART_RECONSTRUCTION_S
    ):
        attente = _ECART_RECONSTRUCTION_S - (maintenant - _derniere_reconstruction)
        raise ReconstructionTropRecenteError(
            f"Le graphe a été reconstruit il y a moins de "
            f"{int(_ECART_RECONSTRUCTION_S // 60)} minutes. Il est global et "
            f"déterministe : le reconstruire à nouveau rendrait le même résultat. "
            f"Réessayez dans {int(attente)} s si des fiches ont été publiées entre-temps."
        )
    _derniere_reconstruction = maintenant

    await db.execute(text("DELETE FROM graph_aliases"))
    await db.execute(text("DELETE FROM graph_relations"))
    await db.execute(text("DELETE FROM graph_entities"))
    await db.flush()

    cards = (
        (
            await db.execute(
                select(BiblioCard).where(
                    BiblioCard.status == "published",
                    BiblioCard.visibility == "public",
                    BiblioCard.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    # preload sources
    card_ids = [c.id for c in cards]
    sources: list[Source] = []
    if card_ids:
        sources = list(
            (
                await db.execute(
                    select(Source).where(
                        Source.biblio_card_id.in_(card_ids), Source.deleted_at.is_(None)
                    )
                )
            )
            .scalars()
            .all()
        )
    by_card: dict = {}
    for s in sources:
        by_card.setdefault(s.biblio_card_id, []).append(s)

    # Pass 1 : noeuds
    nodes: dict[str, tuple[str, str, str, str | None]] = {}  # id -> (name,type,desc,card_id)
    aliases: list[tuple[str, str]] = []

    def add_node(name: str, type_: str, desc: str = "", card_id=None):
        if not name or type_ not in ENTITY_TYPES:
            return None
        eid = entity_id(type_, name)
        if eid not in nodes:
            nodes[eid] = (name, type_, desc, card_id)
        return eid

    for card in cards:
        # Une fiche, un seul nœud, identifié par son slug. Le portage en créait
        # un second nommé par le titre : les arêtes se rattachaient au premier,
        # si bien que nommer une fiche par son titre, ce que fait toute question
        # en langue naturelle, amorçait sur un nœud sans arête et rendait
        # « aucun fait ne correspond » alors que le graphe portait la réponse.
        #
        # Le titre devient donc un alias, ce qu'il aurait toujours dû être. Le
        # seul alias écrit jusqu'ici valait le nom du nœud, c'est-à-dire rien.
        add_node(card.slug, "CARD", card.description or card.title or "", card.id)
        if card.title and card.title != card.slug:
            aliases.append((entity_id("CARD", card.slug), card.title))
        if card.content_authors:
            for a in [x.strip() for x in card.content_authors.split(",") if x.strip()]:
                add_node(a, "PERSON", "", card.id)

    for src in sources:
        sname = (src.title or src.url or str(src.id))[:300]
        add_node(sname, "SOURCE", src.annotation or "", src.biblio_card_id)
        if src.authors:
            for a in [x.strip() for x in src.authors.split(",") if x.strip()][:4]:
                add_node(a, "PERSON", "", src.biblio_card_id)
        if src.category:
            add_node(src.category, "CONCEPT", "", src.biblio_card_id)

    # flush nodes
    for eid, (name, type_, desc, cid) in nodes.items():
        db.add(
            GraphEntity(id=eid, name=name, type=type_, description=desc or "", source_card_id=cid)
        )
    await db.flush()

    # Pass 2 : arêtes résolues par nom normalisé
    rel_count = 0

    for card in cards:
        card_eid = entity_id("CARD", card.slug)
        # CARD created_by PERSON (owner is not stored as name, mais content_authors PERSON déjà)
        for src in by_card.get(card.id, []):
            sname = (src.title or src.url or str(src.id))[:300]
            src_eid = entity_id("SOURCE", sname)
            if card_eid in nodes and src_eid in nodes:
                db.add(
                    GraphRelation(
                        source_id=card_eid,
                        target_id=src_eid,
                        predicate="cites",
                        source_card_id=card.id,
                    )
                )
                rel_count += 1
            # SOURCE authored_by PERSON
            if src.authors:
                for a in [x.strip() for x in src.authors.split(",") if x.strip()][:4]:
                    pid = entity_id("PERSON", a)
                    if pid in nodes and src_eid in nodes:
                        db.add(
                            GraphRelation(
                                source_id=src_eid,
                                target_id=pid,
                                predicate="authored_by",
                                source_card_id=card.id,
                            )
                        )
                        rel_count += 1
            # SOURCE references CARD via linked_card_id
            if src.linked_card_id:
                # linked card slug lookup
                linked = next((c for c in cards if c.id == src.linked_card_id), None)
                if linked:
                    linked_eid = entity_id("CARD", linked.slug)
                    if linked_eid in nodes and src_eid in nodes:
                        db.add(
                            GraphRelation(
                                source_id=src_eid,
                                target_id=linked_eid,
                                predicate="references",
                                source_card_id=card.id,
                            )
                        )
                        rel_count += 1

    for eid_str, alias in aliases:
        if eid_str in nodes:
            db.add(GraphAlias(entity_id=eid_str, alias=alias))

    await db.commit()
    return {
        "entities": len(nodes),
        "relations": rel_count,
        "aliases": len(aliases),
        "cards": len(cards),
    }


#: Mots trop courants pour désigner quoi que ce soit. Sans ce filtre, une
#: question comme « quelles sont les sources de la fiche » amorçait sur tout nœud
#: contenant « des », c'est-à-dire à peu près tous, et le parcours partait de
#: partout : le rappel rendait alors les huit premières arêtes de la base plutôt
#: que celles de la question.
_MOTS_VIDES = frozenset(
    {
        "avec",
        "cette",
        "comme",
        "dans",
        "donc",
        "elle",
        "fiche",
        "leur",
        "mais",
        "meme",
        "même",
        "pour",
        "quel",
        "quelle",
        "quelles",
        "quels",
        "sans",
        "sont",
        "source",
        "sources",
        "sous",
        "tout",
        "tous",
        "toute",
        "toutes",
        "about",
        "from",
        "that",
        "this",
        "what",
        "which",
        "with",
    }
)


def mots_utiles(question: str) -> list[str]:
    """Les mots d'une question qui peuvent designer une entite."""
    mots = re.findall(r"\w{4,}", question.lower())
    return list(dict.fromkeys(m for m in mots if m not in _MOTS_VIDES))


def _mot_entier(mot: str, nom: str) -> bool:
    return re.search(rf"\b{re.escape(mot)}\b", nom.lower()) is not None


async def _seeds_lexical_sql(db: AsyncSession, question: str) -> list[str]:
    """Les entites dont le nom ou un alias porte un mot de la question.

    Deux temps. Le `LIKE` en base ramene les candidats, parce qu'il se pose sur
    l'index trigramme de la migration 054 et reste sous les 30 ms a 5k entites.
    Le mot entier est ensuite verifie en Python, sur ces seuls candidats.

    La verification separee n'est pas un detour : une sous-chaine seule fait
    correspondre « art » a « particule » et « one » a « money », et le portage
    initial s'en tenait la, la ou le depot d'origine cherchait le mot entier.
    L'ecart se paie en amorces qui n'ont rien a voir avec la question.
    """
    mots = mots_utiles(question)
    if not mots:
        return []
    conds = " OR ".join(f"lower(name) LIKE :w{i}" for i in range(len(mots)))
    params = {f"w{i}": f"%{m}%" for i, m in enumerate(mots)}
    ents = (
        await db.execute(
            text(
                f"SELECT id, name FROM graph_entities WHERE {conds}"  # nosec B608
            ),
            params,
        )
    ).fetchall()
    conds_a = " OR ".join(f"lower(alias) LIKE :w{i}" for i in range(len(mots)))
    aliases = (
        await db.execute(
            text(
                f"SELECT entity_id, alias FROM graph_aliases WHERE {conds_a}"  # nosec B608
            ),
            params,
        )
    ).fetchall()
    seeds = [
        str(ligne[0])
        for ligne in list(ents) + list(aliases)
        if any(_mot_entier(mot, ligne[1]) for mot in mots)
    ]
    return list(dict.fromkeys(seeds))


async def recall(db: AsyncSession, question: str, hops: int = 3, top_k: int = 8) -> Facts:
    # Le repli sémantique qui vivait ici a été retiré : il lisait une colonne
    # `embedding` que `build_graph` n'écrit jamais, si bien que son
    # `WHERE embedding IS NOT NULL` filtrait toute la table. Il coûtait un appel
    # réseau par rappel sans amorce, pour zéro graine, sous un `except` muet.
    #
    # Le remplir plutôt que le retirer supposerait d'embarquer chaque nom
    # d'entité, pour un graphe dont les trois arêtes sont aujourd'hui des clés
    # étrangères qu'une jointure donne déjà. Le remettre suppose de trancher
    # d'abord cette question-là.
    t0 = time.perf_counter()
    seeds = await _seeds_lexical_sql(db, question)
    if not seeds:
        return Facts([], [], (time.perf_counter() - t0) * 1000)

    # build IN clause safely
    marks = ",".join(f":s{i}" for i in range(len(seeds)))
    sql = WALK_SQL.format(seeds=marks)  # nosec B608
    params: dict = {f"s{i}": sid for i, sid in enumerate(seeds)}
    params["hops"] = hops
    rows = (await db.execute(text(sql), params)).fetchall()
    triples = [(r[0], r[1], r[2], str(r[3]) if r[3] else "") for r in rows[:top_k]]
    names = {n for s, _, t, _ in triples for n in (s, t)}
    notes = []
    if names:
        # fetch descriptions
        placeholders = ",".join(f":n{i}" for i in range(len(names)))
        nparams = {f"n{i}": n for i, n in enumerate(names)}
        note_rows = (
            await db.execute(
                text(
                    f"SELECT name, description FROM graph_entities WHERE name IN ({placeholders}) AND description != ''"  # nosec B608
                ),
                nparams,
            )
        ).fetchall()
        notes = [(r[0], r[1]) for r in note_rows]

    return Facts(triples, notes, (time.perf_counter() - t0) * 1000)
