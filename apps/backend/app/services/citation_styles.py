"""Rendu d'une source en reference bibliographique, dans plusieurs styles.

Philum n'a pas vocation a reimplementer CSL : le style de citation est une
convention editoriale mouvante, et les processeurs qui la traitent vraiment
(citeproc, Zotero) demandent les fichiers `.csl` officiels. L'export CSL-JSON
existe deja pour ce chemin-la, et reste le bon quand l'utilisateur veut la
typographie exacte de sa revue.

Ce module couvre l'autre besoin, plus courant : coller une bibliographie deja
formatee dans un document, sans passer par un gestionnaire de references. Six
styles suffisent a couvrir la demande, et chacun est rendu **au plus pres de sa
regle sur les champs dont Philum dispose**, pas exhaustivement.

Une limite assumee, et signalee ici parce qu'elle serait autrement invisible :
un champ absent est omis, jamais devine. Une source sans annee ne recoit pas
une annee plausible, elle porte la marque d'absence propre au style (« s. d. »,
« n.d. »). Inventer une date pour satisfaire un gabarit produirait une
reference bien formee et fausse — exactement ce que Philum existe pour eviter.
"""

from __future__ import annotations

from app.models.source import Source
from app.services.csl import est_abrege, noms_propres, parse_authors

#: Styles proposes. La cle est ce que l'API accepte, la valeur ce qu'on montre.
STYLES: dict[str, str] = {
    "apa": "APA 7",
    "harvard": "Harvard",
    "mla": "MLA 9",
    "chicago": "Chicago (auteur-date)",
    "vancouver": "Vancouver",
    "ieee": "IEEE",
}


def _initials(given: str, *, point: bool = True, espace: bool = True) -> str:
    """« Jean-Marc » -> « J.-M. ». Une initiale par mot, traits d'union tenus."""
    if not given:
        return ""
    morceaux: list[str] = []
    for mot in given.split():
        bouts = [p for p in mot.replace("–", "-").split("-") if p]
        rendu = "-".join(f"{p[0].upper()}{'.' if point else ''}" for p in bouts)
        morceaux.append(rendu)
    return (" " if espace else "").join(morceaux)


def _noms(source: Source) -> list[dict[str, str]]:
    return parse_authors(source.authors)


def _joindre(parts: list[str], dernier: str) -> str:
    """« A, B et C » — `dernier` etant le liant avant le dernier nom."""
    parts = [p for p in parts if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"{', '.join(parts[:-1])}{dernier}{parts[-1]}"


def _annee(source: Source) -> int | None:
    return source.published_at.year if source.published_at else None


def _lien(source: Source) -> str:
    return f"https://doi.org/{source.doi}" if source.doi else (source.url or "")


def _titre(source: Source) -> str:
    """Le titre, ou l'URL a defaut. Jamais vide : une entree muette n'aide personne."""
    return (source.title or "").strip() or (source.url or "").strip()


# --- Un rendu d'auteurs par convention ---------------------------------------


def _point(segment: str) -> str:
    """Termine par un point, sans en doubler un deja present (« et al.. »)."""
    segment = segment.rstrip()
    return segment if segment.endswith(".") else f"{segment}."


def _et_al(rendu: str, noms: list[dict[str, str]]) -> str:
    """Rend la marque d'abreviation portee par la liste d'auteurs.

    Sans elle, « Wiltgen, B. J. et al. » se citerait « Wiltgen, B. J. » : la
    reference attribuerait a une personne un article ecrit a plusieurs. Tous
    les styles rendus ici emploient la meme abreviation.
    """
    if not rendu or not est_abrege(noms):
        return rendu
    return f"{rendu}, et al."


def _auteurs_apa(noms: list[dict[str, str]]) -> str:
    rendus = [
        f"{n.get('family', '')}, {_initials(n.get('given', ''))}".strip(", ")
        for n in noms_propres(noms)
    ]
    # APA 7 garde la virgule avant l'esperluette (« A, B, & C »).
    return _et_al(_joindre(rendus, ", & "), noms)


def _auteurs_harvard(noms: list[dict[str, str]]) -> str:
    rendus = [
        f"{n.get('family', '')}, {_initials(n.get('given', ''), espace=False)}".strip(", ")
        for n in noms_propres(noms)
    ]
    return _et_al(_joindre(rendus, " and "), noms)


def _auteurs_mla(noms: list[dict[str, str]]) -> str:
    """MLA inverse le premier nom seulement, et abrege des trois auteurs."""
    propres = noms_propres(noms)
    if not propres:
        return ""
    premier = ", ".join(p for p in (propres[0].get("family"), propres[0].get("given")) if p)
    if est_abrege(noms) or len(propres) > 2:
        return f"{premier}, et al."
    if len(propres) == 1:
        return premier
    second = " ".join(p for p in (propres[1].get("given"), propres[1].get("family")) if p)
    return f"{premier}, and {second}"


def _auteurs_chicago(noms: list[dict[str, str]]) -> str:
    propres = noms_propres(noms)
    if not propres:
        return ""
    rendus = [", ".join(p for p in (propres[0].get("family"), propres[0].get("given")) if p)]
    rendus += [" ".join(p for p in (n.get("given"), n.get("family")) if p) for n in propres[1:]]
    return _et_al(_joindre(rendus, ", and "), noms)


def _auteurs_vancouver(noms: list[dict[str, str]]) -> str:
    """Vancouver n'abrege qu'au-dela de six auteurs, sans ponctuation d'initiales."""
    rendus = [
        f"{n.get('family', '')} {_initials(n.get('given', ''), point=False, espace=False)}".strip()
        for n in noms_propres(noms)
    ]
    if len(rendus) > 6:
        return ", ".join(rendus[:6]) + ", et al."
    return _et_al(", ".join(rendus), noms)


def _auteurs_ieee(noms: list[dict[str, str]]) -> str:
    rendus = [
        f"{_initials(n.get('given', ''))} {n.get('family', '')}".strip() for n in noms_propres(noms)
    ]
    return _et_al(_joindre(rendus, " and "), noms)


# --- Un rendu de reference par style -----------------------------------------


def _apa(source: Source) -> str:
    noms = _noms(source)
    an = _annee(source)
    tete = _auteurs_apa(noms) or _titre(source)
    parts = [f"{tete} ({an})." if an else f"{tete} (s. d.)."]
    if noms:
        parts.append(f"{_titre(source)}.")
    if source.journal:
        ref = source.journal
        if source.volume:
            ref += f", {source.volume}"
        if source.pages:
            ref += f", {source.pages}"
        parts.append(ref + ".")
    elif source.publisher:
        parts.append(f"{source.publisher}.")
    parts.append(_lien(source))
    return " ".join(p for p in parts if p).strip()


def _harvard(source: Source) -> str:
    noms = _noms(source)
    an = _annee(source)
    tete = _auteurs_harvard(noms) or _titre(source)
    date = f"({an})" if an else "(no date)"
    # Sans auteur, le titre a pris la tete : la date clot alors la phrase, au
    # lieu d'introduire le titre qui suivrait.
    parts = [f"{tete} {date}" if noms else f"{tete} {date}."]
    if noms:
        parts.append(f"'{_titre(source)}',")
    if source.journal:
        ref = source.journal
        if source.volume:
            ref += f", {source.volume}"
        if source.pages:
            ref += f", pp. {source.pages}"
        parts.append(ref + ".")
    elif source.publisher:
        parts.append(f"{source.publisher}.")
    lien = _lien(source)
    if lien:
        parts.append(f"Available at: {lien}")
    return " ".join(p for p in parts if p).strip()


def _mla(source: Source) -> str:
    noms = _noms(source)
    parts: list[str] = []
    tete = _auteurs_mla(noms)
    if tete:
        parts.append(_point(tete))
    parts.append(f'"{_titre(source)}."')
    if source.journal:
        ref = source.journal
        if source.volume:
            ref += f", vol. {source.volume}"
        an = _annee(source)
        if an:
            ref += f", {an}"
        if source.pages:
            ref += f", pp. {source.pages}"
        parts.append(ref + ".")
    else:
        if source.publisher:
            parts.append(f"{source.publisher},")
        an = _annee(source)
        parts.append(f"{an}." if an else "n.d.")
    parts.append(_lien(source))
    return " ".join(p for p in parts if p).strip()


def _chicago(source: Source) -> str:
    noms = _noms(source)
    an = _annee(source)
    parts: list[str] = []
    tete = _auteurs_chicago(noms)
    if tete:
        # « Loftus, Elizabeth F. » se terminait deja par un point : le style
        # servait « Loftus, Elizabeth F.. 2005. »
        parts.append(_point(tete))
    parts.append(f"{an}." if an else "n.d.")
    parts.append(f'"{_titre(source)}."')
    if source.journal:
        ref = source.journal
        if source.volume:
            ref += f" {source.volume}"
        if source.pages:
            ref += f": {source.pages}"
        parts.append(ref + ".")
    elif source.publisher:
        parts.append(f"{source.publisher}.")
    parts.append(_lien(source))
    return " ".join(p for p in parts if p).strip()


def _vancouver(source: Source) -> str:
    noms = _noms(source)
    parts: list[str] = []
    tete = _auteurs_vancouver(noms)
    if tete:
        parts.append(_point(tete))
    parts.append(f"{_titre(source)}.")
    if source.journal:
        parts.append(f"{source.journal}.")
    elif source.publisher:
        parts.append(f"{source.publisher};")
    an = _annee(source)
    queue = f"{an}" if an else "[date inconnue]"
    if source.volume:
        queue += f";{source.volume}"
    if source.pages:
        queue += f":{source.pages}"
    parts.append(queue + ".")
    parts.append(_lien(source))
    return " ".join(p for p in parts if p).strip()


def _ieee(source: Source) -> str:
    noms = _noms(source)
    parts: list[str] = []
    tete = _auteurs_ieee(noms)
    if tete:
        parts.append(f"{tete},")
    parts.append(f'"{_titre(source)},"')
    if source.journal:
        ref = source.journal
        if source.volume:
            ref += f", vol. {source.volume}"
        if source.pages:
            ref += f", pp. {source.pages}"
        parts.append(ref + ",")
    elif source.publisher:
        parts.append(f"{source.publisher},")
    an = _annee(source)
    parts.append(f"{an}." if an else "n.d.")
    parts.append(_lien(source))
    return " ".join(p for p in parts if p).strip()


_RENDUS = {
    "apa": _apa,
    "harvard": _harvard,
    "mla": _mla,
    "chicago": _chicago,
    "vancouver": _vancouver,
    "ieee": _ieee,
}


def format_reference(source: Source, style: str) -> str:
    """Une source rendue dans le style demande. `KeyError` si le style est inconnu."""
    return _RENDUS[style](source)


def format_bibliography(sources: list[Source], style: str) -> list[str]:
    """La bibliographie entiere, une entree par ligne.

    IEEE numerote les references : le numero fait partie de la convention, pas
    de la mise en page, donc il est rendu ici et non par l'appelant.
    """
    lignes = [format_reference(s, style) for s in sources]
    if style == "ieee":
        return [f"[{i}] {ligne}" for i, ligne in enumerate(lignes, start=1)]
    return lignes
