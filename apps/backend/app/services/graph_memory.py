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

# Ontologie fermée Philum (STARTER: 5 types → Philum 7)
ENTITY_TYPES = {"PERSON", "ROLE", "CARD", "SOURCE", "CONCEPT", "POLICY", "PROCESS"}
PREDICATES = {
    "authored_by",
    "created_by",
    "cites",
    "supports",
    "contradicts",
    "part_of",
    "held_by",
    "delegates_to",
    "references",
    "attests",
    "mentions",
}

WALK_SQL = """
WITH RECURSIVE walk(entity_id, depth) AS (
  SELECT id, 0 FROM graph_entities WHERE id IN ({seeds})
  UNION
  SELECT CASE WHEN r.source_id = w.entity_id THEN r.target_id ELSE r.source_id END, w.depth + 1
  FROM graph_relations r JOIN walk w ON w.entity_id IN (r.source_id, r.target_id)
  WHERE w.depth < :hops
)
SELECT e1.name, r.predicate, e2.name, r.source_card_id,
       LEAST((SELECT MIN(depth) FROM walk WHERE entity_id = r.source_id),
             (SELECT MIN(depth) FROM walk WHERE entity_id = r.target_id)) AS near
FROM graph_relations r
JOIN graph_entities e1 ON e1.id = r.source_id
JOIN graph_entities e2 ON e2.id = r.target_id
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
        header = f"memory: {len(self.triples)} facts recalled in {self.ms:.0f} ms"
        if not self.triples:
            return header + "\n(no memory matches for this prompt)"
        width = max(len(f"{s} --[{p}]--> {t}") for s, p, t, _ in self.triples)
        lines = [f"{f'{s} --[{p}]--> {t}':<{width}}   ({doc})" for s, p, t, doc in self.triples]
        text = header + "\n\n" + "\n".join(lines)
        if self.notes:
            text += "\n\nwhere:\n" + "\n".join(f"  {n}: {d}" for n, d in self.notes)
        return text


async def build_graph(db: AsyncSession) -> dict:
    """Construit le graphe depuis les fiches publiques (déterministe, sans LLM).

    2 passes comme STARTER:
    1) tous les noeuds content-addressed
    2) arêtes + aliases résolus par nom normalisé
    """
    # wipe
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
        add_node(card.slug, "CARD", card.description or card.title or "", card.id)
        add_node(card.title, "CARD", card.description or "", card.id)
        aliases.append((entity_id("CARD", card.slug), card.slug))
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


async def _seeds_lexical_sql(db: AsyncSession, question: str) -> list[str]:
    """Seeds via SQL LIKE — <50 ms même à 5k entités, vs 1.6s en Python."""
    words = [w for w in re.findall(r"\w{4,}", question.lower()) if len(w) >= 4]
    if not words:
        return []
    # un LIKE par mot, OR entre eux — pg_trgm accélère si index présent, sinon seq scan <30 ms à 5k
    conds = " OR ".join(f"lower(name) LIKE :w{i}" for i in range(len(words)))
    params = {f"w{i}": f"%{w}%" for i, w in enumerate(words)}
    ents = (
        await db.execute(text(f"SELECT id FROM graph_entities WHERE {conds}"  # nosec B608
        ), params)
    ).fetchall()
    conds_a = " OR ".join(f"lower(alias) LIKE :w{i}" for i in range(len(words)))
    aliases = (
        await db.execute(text(f"SELECT entity_id FROM graph_aliases WHERE {conds_a}"  # nosec B608
        ), params)
    ).fetchall()
    seeds = [str(r[0]) for r in ents] + [str(r[0]) for r in aliases]
    return list(dict.fromkeys(seeds))


async def recall(db: AsyncSession, question: str, hops: int = 3, top_k: int = 8) -> Facts:
    t0 = time.perf_counter()
    # 1) lexical SQL (<30 ms)
    seeds = await _seeds_lexical_sql(db, question)
    # 2) vector hybrid — si lexical vide, tente sémantique (refund≈remboursement)
    if not seeds:
        try:
            from app.services.embeddings import embed
            from app.services.excerpt_search import litteral_vecteur, schema_du_type_vector

            vecs = await embed([question])
            schema = await schema_du_type_vector(db)
            if vecs and schema:
                v = litteral_vecteur(vecs[0])
                # séquentiel sans HNSW à 5k — <20 ms, exact
                rows = (
                    await db.execute(
                        text(
                            f"SELECT id FROM graph_entities WHERE embedding IS NOT NULL ORDER BY embedding OPERATOR({schema}.<=>) CAST(:v AS {schema}.vector) LIMIT 8"  # nosec B608
                        ),
                        {"v": v},
                    )
                ).fetchall()
                # filtrer par similarité >0.35 (approx 1-distance), sinon bruit
                seeds = [str(r[0]) for r in rows]
        except Exception:
            pass
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
