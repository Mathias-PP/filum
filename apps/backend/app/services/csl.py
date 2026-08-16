"""CSL-JSON comme format pivot des exports bibliographiques.

BibTeX et RIS sont des formats de *sortie*, pas des pivots : chacun a son
vocabulaire, ses echappements, ses champs manquants. Les derivat d'une meme
representation intermediaire evite qu'ils divergent -- un champ ajoute au
pivot apparait partout, un champ corrige l'est partout.

CSL-JSON est le seul candidat serieux : JSON natif, lu et ecrit par Zotero,
Pandoc, citeproc. C'est aussi le format que le doctorant attend pour recuperer
une bibliographie dans son gestionnaire.

Le point dur est le nom d'auteur. Philum stocke une chaine libre ; CSL attend
``[{family, given}]``. Un ``[{literal: ...}]`` est accepte partout mais degrade
le tri dans Zotero (« Adleman N. » se classe sous A, ce qui est correct par
chance, mais « Jean Dupont » se classerait sous J). D'ou un decoupage
best-effort, decrit dans ``parse_authors``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.source import Source

# Mapping category ADR-020 -> type CSL 1.0.2. Les categories sans equivalent
# net tombent sur "webpage" (le plus honnete pour une URL).
CSL_TYPE_BY_CATEGORY = {
    "article-scientifique": "article-journal",
    "preprint": "article-journal",
    "article-presse": "article-newspaper",
    "communique": "report",
    "documentaire": "motion_picture",
    "interview": "interview",
    "podcast": "broadcast",
    "livre": "book",
    "notes": "manuscript",
}

#: Une suite d'initiales (« N. », « J. A. », « JA »), qui ne peut pas tenir
#: seule comme nom d'auteur : c'est forcement le prenom du precedent.
_INITIALS = re.compile(r"^(?:[A-Z]\.?[\s-]*){1,4}$")

#: Un jeton d'initiales isole, pour reconnaitre « N. » dans « Adleman N. ».
_INITIAL_TOKEN = re.compile(r"^[A-Z]\.?(?:-[A-Z]\.?)*$")

#: La marque d'abreviation d'une liste d'auteurs. Ce n'est pas un nom : la
#: regle « dernier jeton = famille » en tirait « al. » comme nom de famille et
#: « Brian J. Wiltgen et » comme prenom, une entree fausse dans tout ce qui
#: s'exporte (cle BibTeX `al2010n2`, champ RIS `AU  - al., Brian J. Wiltgen et`).
_ET_AL = re.compile(
    r"(?:^|[\s,]+)(?:et|and|&)[\s]+(?:al|coll|col|autres)\.?$",
    re.IGNORECASE,
)


#: L'abreviation, rendue en entree CSL. `literal` est la facon prevue par CSL
#: de porter ce qui n'est pas un nom decoupable ; les consommateurs qui ne
#: savent pas l'interpreter affichent la chaine telle quelle, ce qui reste
#: juste. La supprimer ferait passer un article collectif pour un article a
#: auteur unique : une attribution fausse, plus couteuse qu'une entree laide.
ET_AL: dict[str, str] = {"literal": "et al."}


def est_abrege(names: list[dict[str, str]]) -> bool:
    """La liste d'auteurs annonce-t-elle qu'elle est incomplete ?"""
    return any("literal" in n for n in names)


def noms_propres(names: list[dict[str, str]]) -> list[dict[str, str]]:
    """Les auteurs reellement nommes, sans la marque d'abreviation."""
    return [n for n in names if "literal" not in n]


def _split_entries(authors: str) -> list[str]:
    """Decoupe la chaine en auteurs, sans casser un « Famille, Prenom ».

    Le point-virgule est sans ambiguite : il ne separe jamais qu'un auteur du
    suivant. La virgule, elle, joue deux roles a la fois (« Dupont, J. » est
    *un* auteur, « Dupont J., Martin A. » en fait deux). On la traite comme un
    separateur, puis on recolle les morceaux qui ne sont que des initiales --
    seul cas ou l'on peut affirmer, sans deviner, que la virgule etait interne.
    """
    if ";" in authors:
        return [p.strip() for p in authors.split(";") if p.strip()]

    parts = [p.strip() for p in authors.split(",") if p.strip()]
    merged: list[str] = []
    fused = False
    for part in parts:
        if merged and _INITIALS.match(part):
            merged[-1] = f"{merged[-1]}, {part}"
            fused = True
        else:
            merged.append(part)
    if fused:
        return merged

    # Aucune initiale n'a tranche. Reste le cas « Dupont, Marie » : des
    # morceaux tous mono-mot et en nombre pair se lisent par paires
    # famille/prenom, la convention de saisie manuelle la plus repandue.
    # C'est un pari, et il peut se tromper sur « Bell, Aron » (deux auteurs
    # sans prenom) -- une chaine que rien ne distingue d'un auteur unique.
    # Le point-virgule leve l'ambiguite et reste la forme a preferer.
    if len(merged) >= 2 and len(merged) % 2 == 0 and all(" " not in p for p in merged):
        return [f"{merged[i]}, {merged[i + 1]}" for i in range(0, len(merged), 2)]
    return merged


def parse_name(entry: str) -> dict[str, str]:
    """Un nom d'auteur en ``{family, given}``, au mieux de ce qu'on peut lire.

    Aucune base de noms n'etant disponible, on s'appuie sur la seule marque
    typographique fiable : les initiales. « Adleman N. » et « N. Adleman »
    designent le meme auteur et se resolvent tous deux ; « Jean Dupont » suit
    la convention occidentale (dernier jeton = famille). Un nom d'un seul mot
    reste un nom de famille seul, plutot que d'inventer un prenom vide.
    """
    entry = _ET_AL.sub("", entry.strip()).strip()
    if not entry:
        return {}

    if "," in entry:
        family, _, given = entry.partition(",")
        family, given = family.strip(), given.strip()
        if not family:
            return {"family": given} if given else {}
        return {"family": family, "given": given} if given else {"family": family}

    tokens = entry.split()
    if len(tokens) == 1:
        return {"family": tokens[0]}

    # « Adleman N. » / « Adleman N. J. » : les initiales sont en queue.
    trailing = len(tokens)
    while trailing > 1 and _INITIAL_TOKEN.match(tokens[trailing - 1]):
        trailing -= 1
    if trailing < len(tokens):
        return {"family": " ".join(tokens[:trailing]), "given": " ".join(tokens[trailing:])}

    # « N. Adleman » / « J. A. Smith » : les initiales sont en tete.
    leading = 0
    while leading < len(tokens) - 1 and _INITIAL_TOKEN.match(tokens[leading]):
        leading += 1
    if leading > 0:
        return {"family": " ".join(tokens[leading:]), "given": " ".join(tokens[:leading])}

    # « Jean Dupont » : convention occidentale, dernier jeton = famille.
    return {"family": tokens[-1], "given": " ".join(tokens[:-1])}


def parse_authors(authors: str | None) -> list[dict[str, str]]:
    """La chaine libre d'auteurs en liste CSL. Liste vide si rien a lire.

    Quand la chaine s'acheve sur « et al. », la liste se termine par `ET_AL` :
    l'abreviation n'est pas un nom, mais elle dit que d'autres auteurs
    existent, et cette information doit survivre a l'export.
    """
    cleaned = (authors or "").strip()
    if not cleaned:
        return []
    names = [name for name in (parse_name(e) for e in _split_entries(cleaned)) if name]
    if names and _ET_AL.search(cleaned):
        names.append(dict(ET_AL))
    return names


def csl_key(source: Source, index: int) -> str:
    """Cle de citation stable (« adleman2012n3 »), partagee par CSL et BibTeX."""
    names = noms_propres(parse_authors(source.authors))
    if names:
        base = names[0].get("family") or names[0].get("given") or ""
    else:
        # Sans auteur, le premier mot du titre. Y appliquer la regle des noms
        # donnerait « cerveau » pour « Memoire et cerveau » : un titre n'a pas
        # de nom de famille.
        base = ((source.title or "").strip().split() or ["source"])[0]
    word = re.sub(r"[^A-Za-z0-9]", "", base) or "source"
    year = source.published_at.year if source.published_at else "nd"
    return f"{word.lower()}{year}n{index}"


def to_csl(source: Source, index: int) -> dict:
    """Une source Philum en item CSL-JSON.

    Les champs propres a Philum (``philum-*``) vont dans ``note``. Zotero ne
    les interprete pas -- ce sont des variables inconnues -- mais il les
    conserve tels quels : ils survivent a un aller-retour Philum -> Zotero ->
    Philum, ce qui est exactement ce qu'on veut.
    """
    item: dict = {
        "id": csl_key(source, index),
        "type": CSL_TYPE_BY_CATEGORY.get(source.category, "webpage"),
        "title": source.title or source.url,
        "URL": source.url,
    }
    authors = parse_authors(source.authors)
    if authors:
        item["author"] = authors
    if source.published_at:
        d = source.published_at
        item["issued"] = {"date-parts": [[d.year, d.month, d.day]]}
    if source.journal:
        item["container-title"] = source.journal
    if source.volume:
        item["volume"] = source.volume
    if source.pages:
        item["page"] = source.pages
    if source.publisher:
        item["publisher"] = source.publisher
    if source.doi:
        item["DOI"] = source.doi
    if source.archive_url:
        item["archive_location"] = source.archive_url

    notes = []
    if source.annotation:
        notes.append(source.annotation)
    if getattr(source, "stance", None):
        notes.append(f"philum-stance: {source.stance}")
    if notes:
        item["note"] = "\n".join(notes)
    return item


def author_display(names: list[dict[str, str]]) -> str:
    """Rend une liste CSL en « Famille, Prenom; Famille, Prenom »."""
    out = []
    for n in names:
        if "literal" in n:
            out.append(n["literal"])
            continue
        family, given = n.get("family", ""), n.get("given", "")
        out.append(f"{family}, {given}" if family and given else family or given)
    return "; ".join(p for p in out if p)
