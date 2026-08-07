"""Mesure du taux de detection de section sur des CMS varies.

Le pipeline d'extraction borne les references a une section du DOM avant de
valider un candidat. Toute la lutte anti-bruit repose donc sur
`detect_references_section` : la ou elle echoue, on retombe sur une recherche
dans le corps entier, et la confiance passe a « medium ».

Ce script mesure ou elle echoue, sur des URLs reelles plutot que sur des
fixtures choisies pour passer. Lecture seule, aucune ecriture en base.

Usage : uv run python scripts/audit_section_detection.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.extractors.section_detector import detect_references_section  # noqa: E402

# Choisies pour couvrir des moteurs de rendu differents, pas pour reussir :
# editeurs academiques, encyclopedie, presse, blogs, institutionnel.
URLS = [
    ("Frontiers", "https://www.frontiersin.org/articles/10.3389/fpsyg.2022.651547/full"),
    ("PMC", "https://pmc.ncbi.nlm.nih.gov/articles/PMC3181818/"),
    ("Nature", "https://www.nature.com/articles/s41586-020-2649-2"),
    ("PLOS", "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0000217"),
    ("eLife", "https://elifesciences.org/articles/00013"),
    ("MDPI", "https://www.mdpi.com/2072-6643/13/1/1"),
    ("arXiv abs", "https://arxiv.org/abs/1706.03762"),
    ("Wikipedia EN", "https://en.wikipedia.org/wiki/Working_memory"),
    ("Wikipedia FR", "https://fr.wikipedia.org/wiki/M%C3%A9moire_de_travail"),
    ("BMJ", "https://www.bmj.com/content/372/bmj.n71"),
    ("PeerJ", "https://peerj.com/articles/4375/"),
    ("Wiley", "https://onlinelibrary.wiley.com/doi/10.1111/jcpp.13606"),
    ("Cell", "https://www.cell.com/current-biology/fulltext/S0960-9822(10)00799-2"),
    ("bioRxiv", "https://www.biorxiv.org/content/10.1101/2020.01.01.891234v1"),
    ("Our World in Data", "https://ourworldindata.org/grapher/life-expectancy"),
    ("Stack Overflow blog", "https://stackoverflow.blog/2023/06/14/hype-or-not/"),
    ("Gwern", "https://gwern.net/scaling-hypothesis"),
    ("LessWrong", "https://www.lesswrong.com/posts/vJ7ggyjuP4u2yHNcP/thoughts-on-human-models"),
    ("WHO", "https://www.who.int/news-room/fact-sheets/detail/depression"),
    ("YouTube", "https://www.youtube.com/watch?v=aircAruvnKk"),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


async def probe(client: httpx.AsyncClient, label: str, url: str) -> tuple[str, str, int]:
    try:
        r = await client.get(url, headers=HEADERS, follow_redirects=True, timeout=25)
    except Exception as exc:  # noqa: BLE001 - on veut classer l'echec, pas le relancer
        return label, f"FETCH_ERR {type(exc).__name__}", 0
    if r.status_code != 200:
        return label, f"HTTP {r.status_code}", 0
    section = detect_references_section(r.text)
    if section is None:
        return label, "AUCUNE SECTION", len(r.text)
    return label, f"OK {len(section.text)} car.", len(r.text)


async def main() -> None:
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*(probe(client, lb, u) for lb, u in URLS))

    ok = sum(1 for _, verdict, _ in results if verdict.startswith("OK"))
    miss = sum(1 for _, verdict, _ in results if verdict == "AUCUNE SECTION")
    err = len(results) - ok - miss

    for label, verdict, size in results:
        print(f"{label:22} {verdict:24} (html {size} car.)")
    print(f"\nsection detectee : {ok}/{len(results)}   sans section : {miss}   injoignable : {err}")


if __name__ == "__main__":
    asyncio.run(main())
