"""Mesure : que rapporterait une surveillance du corpus publie ?

Repond a une seule question, avant d'ecrire la moindre ligne de produit :
sur les sources reellement publiees, combien de retractations, de liens
morts et de bascules en acces ouvert une veille periodique trouverait-elle ?

Si le chiffre est proche de zero, la surveillance n'a pas d'interet et il
vaut mieux le savoir maintenant. Script jetable, hors chemin applicatif.
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter

import httpx

from app.extractors.open_access import check_open_access
from app.extractors.retraction import check_retraction

API = "https://philum-api.duckdns.org/api/v1"
CONCURRENCY = 8


async def fetch_corpus() -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as c:
        cards = (await c.get(f"{API}/discover", params={"limit": 100})).json()["results"]
        sources: list[dict] = []
        for card in cards:
            r = await c.get(f"{API}/@{card['creator_slug']}/{card['slug']}")
            if r.status_code != 200:
                print(f"  ! {card['slug']}: HTTP {r.status_code}")
                continue
            for s in r.json().get("sources", []):
                s["_card"] = card["slug"]
                sources.append(s)
    return sources


async def probe_link(client: httpx.AsyncClient, url: str) -> str:
    """'ok' | 'mort' | 'bloque' | 'injoignable'."""
    try:
        r = await client.head(url, follow_redirects=True)
        if r.status_code >= 400:
            r = await client.get(url, follow_redirects=True)
        if r.status_code == 404 or r.status_code == 410:
            return "mort"
        if r.status_code >= 400:
            return "bloque"
        return "ok"
    except Exception:
        return "injoignable"


async def main() -> None:
    sources = await fetch_corpus()
    print(f"sources publiees : {len(sources)}")

    with_doi = [s for s in sources if s.get("doi") or "10." in (s.get("url") or "")]
    print(f"  dont avec DOI  : {len(with_doi)}")

    sem = asyncio.Semaphore(CONCURRENCY)

    def doi_of(s: dict) -> str | None:
        if s.get("doi"):
            return str(s["doi"])
        url = s.get("url") or ""
        if "doi.org/" in url:
            return url.split("doi.org/", 1)[1]
        return None

    # --- retractations -----------------------------------------------------
    async def one_retraction(s: dict):
        async with sem:
            return s, await check_retraction(doi_of(s))

    retr = await asyncio.gather(*(one_retraction(s) for s in with_doi))
    tally_r: Counter[str] = Counter()
    trouvees = []
    for s, res in retr:
        tally_r[res.status or "none"] += 1
        if res.status and res.status not in ("none", "unverifiable"):
            trouvees.append((s["_card"], doi_of(s), res.status, (s.get("title") or "")[:70]))
            # etat stocke en base vs etat reel
            if s.get("retraction_status") != res.status:
                trouvees[-1] = (*trouvees[-1], f"EN BASE: {s.get('retraction_status')}")

    # --- acces ouvert ------------------------------------------------------
    async def one_oa(s: dict):
        async with sem:
            return s, await check_open_access(doi_of(s))

    oa = await asyncio.gather(*(one_oa(s) for s in with_doi))
    bascules = []
    tally_oa: Counter[str] = Counter()
    for s, res in oa:
        tally_oa[res.status or "inconnu"] += 1
        stored = s.get("oa_status")
        libre_now = res.status not in (None, "closed", "unknown")
        libre_stored = stored not in (None, "closed", "unknown")
        if libre_now and not libre_stored:
            bascules.append((s["_card"], doi_of(s), f"{stored} -> {res.status}"))

    # --- liens morts -------------------------------------------------------
    avec_url = [s for s in sources if (s.get("url") or "").strip()]

    async def one_link(client, s):
        async with sem:
            return s, await probe_link(client, s["url"])

    async with httpx.AsyncClient(
        timeout=15,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; PhilumBot/1.0)"},
    ) as client:
        links = await asyncio.gather(*(one_link(client, s) for s in avec_url))
    tally_l: Counter[str] = Counter()
    morts = []
    for s, verdict in links:
        tally_l[verdict] += 1
        if verdict in ("mort", "injoignable"):
            morts.append((s["_card"], verdict, s["url"][:90], bool(s.get("archive_url"))))

    print("\n=== RETRACTATIONS ===")
    print(dict(tally_r))
    for t in trouvees:
        print("  !", t)
    print("\n=== ACCES OUVERT ===")
    print(dict(tally_oa))
    print(f"  bascules non enregistrees en base : {len(bascules)}")
    for b in bascules[:15]:
        print("  +", b)
    print("\n=== LIENS ===")
    print(dict(tally_l))
    print(f"  morts/injoignables : {len(morts)}")
    couverts = sum(1 for m in morts if m[3])
    print(f"  dont sauves par une archive Wayback : {couverts}/{len(morts)}")
    for m in morts[:20]:
        print("  x", m)

    with open("mesure_surveillance.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "sources": len(sources),
                "avec_doi": len(with_doi),
                "retractation": dict(tally_r),
                "retractees": [list(t) for t in trouvees],
                "oa": dict(tally_oa),
                "bascules_oa": bascules,
                "liens": dict(tally_l),
                "morts": morts,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )


if __name__ == "__main__":
    asyncio.run(main())
