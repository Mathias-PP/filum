#!/usr/bin/env python3
"""Audit une fiche Philum publiee : titre exact, dates (contenu + sources), verifications editoriales.

ALERTES UNIQUEMENT, AUCUN BLOCAGE : le script rend toujours le code 0.
La decision de publier appartient a l'humain (verdict 06-relecture).

Usage:
    python audit_fiche.py <slug> [--creator mathias-pinault]
                           [--brief runs/<slug>/stages/01-brief/output/<slug>-brief.md]
                           [--content-title "Titre exact du contenu"]
                           [--content-date YYYY-MM-DD]
                           [--doi 10.xxxx]

Le brief est auto-detecte dans runs/<slug>/ ; --content-title/--content-date/--doi
permettent de fournir les valeurs attendues sans brief.

Verifications emises (prefixe ALERTE) :
  - titre de la fiche != titre exact du contenu (brief / Crossref via --doi)
  - date du contenu non renseignee sur la fiche (noeud carte du graphe)
  - source sans date de publication (s. d.)
  - tiret cadratin dans titre / annotation
  - pivot sans >= 2 extraits
"""

import argparse
import json
import re
import sys
import urllib.request
import urllib.parse
import os

API_BASE = "https://philum-api.duckdns.org/api/v1"
WS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")

ALERTS = []


def out(s):
    print(s)


def alert(msg):
    ALERTS.append(msg)
    out("ALERTE : " + msg)


def fetch_json(url):
    if not url.startswith(("http://", "https://")):
        raise ValueError("Schema d'URL refuse : " + url)
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:  # nosec B310
        return json.loads(r.read().decode("utf-8"))


def crossref_title(doi):
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi)
    m = fetch_json(url)["message"]
    return (m.get("title") or [""])[0]


def parse_brief_frontmatter(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    m = re.match(r"^---\n(.*?)\n---", txt, flags=re.S)
    fields = {}
    if not m:
        return fields
    for line in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z_]+):\s*(.*?)\s*$", line)
        if mm:
            fields[mm.group(1)] = mm.group(2).strip().strip("\"'")
    return fields


def main():
    # Sous un terminal sans stdout reconfigurable, l'audit reste utilisable en
    # ASCII degrade : l'encodage n'est pas une condition de son resultat.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        out("(stdout non reconfigurable, sortie dans l'encodage par defaut)")

    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--creator", default="mathias-pinault")
    ap.add_argument("--brief")
    ap.add_argument("--content-title")
    ap.add_argument("--content-date")
    ap.add_argument("--doi")
    args = ap.parse_args()

    slug = args.slug

    # --- recuperation des valeurs attendues -------------------------------
    expected_title = args.content_title
    expected_date = args.content_date

    brief_path = args.brief
    if not brief_path:
        cand = os.path.join(
            WS_ROOT, "runs", slug, "stages", "01-brief", "output", f"{slug}-brief.md"
        )
        if os.path.exists(cand):
            brief_path = cand
    if brief_path and os.path.exists(brief_path):
        fm = parse_brief_frontmatter(brief_path)
        if not expected_title:
            expected_title = fm.get("titre_contenu") or fm.get("title")
        if not expected_date:
            expected_date = fm.get("date_contenu")
        out(f"brief  : {brief_path}")

    if not expected_title and args.doi:
        try:
            expected_title = crossref_title(args.doi)
            out(f"crossref: titre = {expected_title[:80]}")
        except Exception as e:
            out(f"(crossref indisponible : {e})")

    # --- donnees live ------------------------------------------------------
    try:
        card = fetch_json(f"{API_BASE}/@{args.creator}/{slug}")
    except Exception as e:
        alert(f"fiche introuvable ou API indisponible : {e}")
        finish()
        return

    try:
        graph = fetch_json(f"{API_BASE}/@{args.creator}/{slug}/graph")
    except Exception as e:
        graph = None

    out(
        f"fiche : {card.get('title', '')[:80]} (publiee {card.get('published_at') or 'non publiee'})"
    )
    out("")

    # --- titre ------------------------------------------------------------
    if expected_title:
        actual = card.get("title") or ""
        if actual.strip() == expected_title.strip():
            out("OK     : titre = titre exact du contenu")
        else:
            alert(
                f"titre != titre exact du contenu\n        fiche   : {actual!r}\n        contenu : {expected_title!r}"
            )
    else:
        out(
            "INFO   : pas de titre de reference fourni (--content-title / --doi / brief) ; check titre saute"
        )

    # --- date du contenu sur la fiche -------------------------------------
    node_date = None
    if graph:
        for n in graph.get("nodes", []):
            if n.get("kind") == "card":
                node_date = n.get("published_at")
                break
    if expected_date:
        if not node_date:
            alert(
                f"date du contenu ({expected_date}) non renseignee sur la fiche : le graphe affiche la date de publication Philum (published_at de la carte)"
            )
        else:
            if str(node_date)[:10] == str(expected_date)[:10]:
                out(f"OK     : date du contenu renseignee sur la fiche ({str(node_date)[:10]})")
            else:
                alert(f"date du contenu attendue {expected_date}, renseignee {str(node_date)[:10]}")
    else:
        out(
            "INFO   : pas de date de contenu de reference (--content-date / brief) ; check date du contenu saute"
        )

    # --- dates des sources ------------------------------------------------
    sources = card.get("sources", [])
    if not sources:
        alert("aucune source sur la fiche")
    for s in sources:
        label = (s.get("title") or s.get("url") or s.get("id") or "")[:60]
        if not s.get("published_at"):
            alert(f"source sans date de publication (s. d.) : {label}")
        else:
            out(f"OK     : source datee {str(s.get('published_at'))[:10]} : {label}")

    # --- cadratin dans titre / annotations --------------------------------
    if "—" in (card.get("title") or ""):
        alert("tiret cadratin dans le titre de la fiche")
    for s in sources:
        if s.get("annotation") and "—" in s["annotation"]:
            alert(f"tiret cadratin dans l'annotation : {(s.get('title') or '')[:50]}")

    # --- pivots -----------------------------------------------------------
    for s in sources:
        if s.get("is_pivot"):
            n = len(s.get("excerpts", []) or [])
            if n < 2:
                alert(f"source pivot avec seulement {n} extrait(s) : {(s.get('title') or '')[:50]}")

    finish()


def finish():
    out("")
    out(f"VERDICT : {len(ALERTS)} ALERTE(S) : aucune ne bloque la publication (decision humaine)")
    for a in ALERTS:
        first = a.splitlines()[0]
        out(f"  - {first}")
    sys.exit(0)


if __name__ == "__main__":
    main()
