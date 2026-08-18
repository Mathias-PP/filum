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

#: Mots qui trahissent une organisation plutot qu'une personne. Rendus dans
#: n'importe quel style, une institution parsee comme un nom donne
#: « Society, A.N. » pour « American Nuclear Society » ou « Team, E.T.E. »
#: pour « EUROfusion Tokamak Exploitation Team » -- des references Harvard
#: fausses qui n'attribuent le texte a personne d'identifiable. Reperees ici,
#: elles restent une chaine `literal` : Zotero et les styles la rendent telle
#: quelle, ce qui reste juste.
_MARQUEURS_INSTITUTION = re.compile(
    r"\b(?:"
    r"society|societ[ée]|team|equipe|institute|institut|group|groupe|"
    r"commission|committee|comit[ée]|office|centre|center|foundation|fondation|"
    r"organization|organisation|agency|agence|council|conseil|department|"
    r"departement|d[ée]partement|bureau|ministry|ministere|minist[eè]re|"
    r"university|universit[ée]|college|coll[eè]ge|school|[ée]cole|"
    r"laboratory|laboratoire|corporation|company|compagnie|"
    r"inc\.?|ltd\.?|llc\.?|gmbh|s\.?a\.?s\.?|sarl|plc|"
    r"cea|cnrs|inserm|inria|ifremer|irfm|"
    r"who|oms|onu|un|nato|otan|eurofusion|iter|nasa|esa|fda|epa|"
    r"afp|reuters|ans|apa|aps|"
    r"association|federation|f[ée]d[ée]ration"
    r")\b",
    re.IGNORECASE,
)

#: Particules nobiliaires europeennes. Sans elles, « van den Broeck » se
#: parsait « Broeck, van den » puis abregeait en « V.D. » : la famille perdait
#: la moitie de son nom et les initiales inventaient un prenom faux. Les
#: particules restent collees a la famille dans le rendu CSL.
_PARTICULES = {
    "van",
    "von",
    "de",
    "del",
    "della",
    "der",
    "den",
    "des",
    "du",
    "da",
    "di",
    "le",
    "la",
    "el",
    "al",
    "bin",
    "ben",
    "ibn",
    "y",
    "ap",
    "af",
}

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


#: Valeur reservee au marqueur d'abreviation. Un `literal` porteur d'un vrai
#: nom d'institution (« American Nuclear Society ») ne doit pas se confondre
#: avec ce marqueur : sans cette distinction, `noms_propres` filtrait aussi
#: les institutions et les styles retombaient sur le titre de la source.
_ET_AL_LITERAL = "et al."

#: L'abreviation, rendue en entree CSL. `literal` est la facon prevue par CSL
#: de porter ce qui n'est pas un nom decoupable ; les consommateurs qui ne
#: savent pas l'interpreter affichent la chaine telle quelle, ce qui reste
#: juste. La supprimer ferait passer un article collectif pour un article a
#: auteur unique : une attribution fausse, plus couteuse qu'une entree laide.
ET_AL: dict[str, str] = {"literal": _ET_AL_LITERAL}


def est_abrege(names: list[dict[str, str]]) -> bool:
    """La liste d'auteurs annonce-t-elle qu'elle est incomplete ?"""
    return any(n.get("literal") == _ET_AL_LITERAL for n in names)


def noms_propres(names: list[dict[str, str]]) -> list[dict[str, str]]:
    """Les auteurs nommes, sans la marque d'abreviation « et al. ».

    Les institutions (portees en `literal` par `parse_name`) sont conservees :
    une source signee par « American Nuclear Society » doit citer ce nom, non
    tomber sur le titre en remplacement.
    """
    return [n for n in names if n.get("literal") != _ET_AL_LITERAL]


#: `&` et ` and ` sont des separateurs d'auteurs quasi universels dans les
#: bibliographies anglaises et francaises (« Redondo & Morris », « Fasano and
#: Catassi »). Sans cette normalisation, « Redondo & Morris » restait UN
#: auteur, dont la famille etait devenue « Morris » et le prenom « Redondo &
#: Roger L. » -- initiales rendues « R.L.R.&.R.G.M. » dans la reference
#: Harvard. Le remplacement se fait AVANT le split point-virgule/virgule pour
#: qu'un « A, B & C » se lise ensuite comme trois auteurs.
_SEP_AUTEURS = re.compile(r"\s+(?:&|and)\s+", re.IGNORECASE)


def _split_par_virgule(chunk: str) -> list[str]:
    """Sous-decoupe : virgule joue deux roles ambigus.

    Cas 1 : « Dupont, J. » -- UN auteur (famille, initiales).
    Cas 2 : « Dupont J., Martin A. » -- DEUX auteurs.
    Cas 3 : « Dupont, Marie » -- famille/prenom occidental.

    On decoupe puis on recolle les initiales isolees au precedent (cas 1) ;
    a defaut d'initiales, une liste paire mono-mot se lit par paires (cas 3).
    """
    parts = [p.strip() for p in chunk.split(",") if p.strip()]
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
    if len(merged) >= 2 and len(merged) % 2 == 0 and all(" " not in p for p in merged):
        return [f"{merged[i]}, {merged[i + 1]}" for i in range(0, len(merged), 2)]
    return merged


def _split_entries(authors: str) -> list[str]:
    """Decoupe la chaine en auteurs, sans casser un « Famille, Prenom ».

    Le point-virgule est sans ambiguite : il ne separe jamais qu'un auteur du
    suivant. La virgule joue deux roles a la fois (`_split_par_virgule` s'en
    charge). `&` et « and » sont normalises en point-virgule d'abord, mais
    chaque morceau peut lui-meme contenir des virgules a decouper : « Rogerson,
    Cai, Frank & Silva » se lit d'abord « Rogerson, Cai, Frank ; Silva », et
    la premiere moitie porte encore trois auteurs.
    """
    authors = _SEP_AUTEURS.sub("; ", authors)
    chunks = [c.strip() for c in authors.split(";") if c.strip()]
    if not chunks:
        return []
    if len(chunks) > 1:
        result: list[str] = []
        for chunk in chunks:
            result.extend(_split_par_virgule(chunk))
        return result
    return _split_par_virgule(chunks[0])


def _semble_institution(entry: str) -> bool:
    """L'entree se lit-elle comme une organisation plutot qu'une personne ?

    Deux marqueurs : un mot institutionnel connu (Society, Team, Agency,
    CEA...), ou un sigle typographique. Sans virgule et avec plusieurs mots
    qui commencent tous par une majuscule *sauf* les articles courts, la
    chaine est probablement un nom d'institution : « CEA Cadarache »,
    « American Nuclear Society ». Une chaine avec virgule est presumee
    « Famille, Prenom » et suit le chemin normal.
    """
    if "," in entry:
        return False
    if _MARQUEURS_INSTITUTION.search(entry):
        return True
    # Sigle en majuscules (« AFP », « CEA », « CNRS », « EUROfusion ») ou
    # un mot majoritairement majuscules qui n'a pas la forme d'un nom propre.
    tokens = entry.split()
    if len(tokens) == 1 and tokens[0].isupper() and len(tokens[0]) >= 2:
        return True
    # Un tiret dans un sigle acronyme (« CEA-IRFM ») : deux morceaux tout en
    # majuscules. Un patronyme composé (« Lopez-Aranda ») n'entre pas ici :
    # ses moities sont capitalisees, pas tout en majuscules.
    if len(tokens) == 1 and "-" in tokens[0]:
        morceaux = tokens[0].split("-")
        if all(m.isupper() and len(m) >= 2 for m in morceaux):
            return True
    return False


def parse_name(entry: str) -> dict[str, str]:
    """Un nom d'auteur en ``{family, given}``, au mieux de ce qu'on peut lire.

    Aucune base de noms n'etant disponible, on s'appuie sur la seule marque
    typographique fiable : les initiales. « Adleman N. » et « N. Adleman »
    designent le meme auteur et se resolvent tous deux ; « Jean Dupont » suit
    la convention occidentale (dernier jeton = famille). Un nom d'un seul mot
    reste un nom de famille seul, plutot que d'inventer un prenom vide.

    Une entree qui se lit comme une organisation (`_semble_institution`) est
    portee telle quelle en `literal` : la decouper produirait des initiales
    fausses (« Society, A.N. » pour « American Nuclear Society »).
    """
    entry = _ET_AL.sub("", entry.strip()).strip()
    if not entry:
        return {}

    if _semble_institution(entry):
        return {"literal": entry}

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
        # « HC van den Broeck » : les particules qui suivent les initiales
        # doivent rester avec la famille. Les detecter puis avancer `leading`
        # jusqu'apres la derniere particule.
        while leading < len(tokens) - 1 and tokens[leading].lower() in _PARTICULES:
            leading += 1
        return {"family": " ".join(tokens[leading:]), "given": " ".join(tokens[:leading])}

    # « Jean Dupont » / « Jean van der Berg » : dernier jeton = famille, sauf
    # que les particules avant le dernier jeton en font partie.
    coupe = len(tokens) - 1
    while coupe > 0 and tokens[coupe - 1].lower() in _PARTICULES:
        coupe -= 1
    return {"family": " ".join(tokens[coupe:]), "given": " ".join(tokens[:coupe])}


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
