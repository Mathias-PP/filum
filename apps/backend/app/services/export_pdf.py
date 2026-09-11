"""La fiche en PDF : ce qu'on y met, et ce qu'on refuse d'y mettre.

`pdf_minimal` sait poser du texte sur une page ; ce module decide quel texte.
Il ne passe pas par le Markdown : rendre puis desbaliser ferait transiter le
document par une syntaxe dont il n'a pas besoin, et chaque `**` oublie
finirait a l'ecran. Il lit donc le modele directement, en partageant avec
`export.py` les seules fonctions qui portent du sens plutot que de la mise en
forme (le style de citation, les libelles de position, le verdict de
relecture, le bilan de fiabilite).

Deux regles de fond, heritees du reste des exports :

1. **Le verbatim et ce qu'on en dit ne se touchent pas.** La citation est en
   italique entre guillemets ; la mise en situation et la note du createur
   sont sur des lignes distinctes et nommees. Un lecteur ne doit jamais
   pouvoir attribuer a un auteur une phrase que le createur a ecrite.
2. **Le document dit ses propres limites.** S'il a fallu remplacer un glyphe
   faute de pouvoir l'ecrire, une mention finale le declare, et renvoie a la
   fiche en ligne qui, elle, porte le texte entier.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services import citation_styles, pdf_minimal
from app.services.export import (
    _OA_TALLY,
    _RETRACTION_TALLY,
    _STANCE_LABELS,
    _concerne_par_la_retractation,
    _excerpt_verdict,
    _tally,
)
from app.services.export_neighbourhood import NeighbourCard, Neighbourhood
from app.services.export_scope import FULL, ExportScope
from app.services.pdf_minimal import GRASSE, ITALIQUE, Document

if TYPE_CHECKING:
    from app.models.biblio_card import BiblioCard
    from app.models.source import Source

#: Retrait des blocs sous une source, en points. Une valeur pour ce qui depend
#: de la source, une autre pour ce qui depend de l'extrait : deux niveaux
#: suffisent a rendre la hierarchie, un troisieme la brouillerait.
_RETRAIT_SOURCE = 16.0
_RETRAIT_EXTRAIT = 30.0

_DIRECTION_TITRES = {
    "cited": "Fiches citées par celle-ci",
    "citing": "Fiches qui citent celle-ci",
}

#: Les marques de tete de `_VERIFIED_LABELS` sont hors WinAnsi : les laisser
#: ferait un substitut la ou la phrase se suffit, et declencherait pour rien
#: l'avertissement de fin de document.
_MARQUES_VERDICT = "✓↪✗? "


def _titre_section(doc: Document, texte: str) -> None:
    # `besoin` garde le titre avec au moins deux lignes de ce qu'il annonce :
    # un intitule seul en bas de page ne dit plus de quoi il est le titre.
    doc.espace(14)
    doc.besoin(46)
    doc.paragraphe(texte, taille=12.5, police=GRASSE)
    doc.espace(3)


def _bilan_fiabilite(doc: Document, sources: list[Source]) -> None:
    if not sources:
        return
    retractables = [s for s in sources if _concerne_par_la_retractation(s)]
    _titre_section(doc, "Fiabilité des sources")
    doc.paragraphe(f"Sur {len(sources)} source(s) :")
    if retractables:
        # Le denominateur est dit : sans lui, « 5 verifiee(s) sans
        # retractation » sur une fiche de 18 sources laisserait croire que les
        # 13 autres attendent un verdict qui ne viendra jamais.
        bilan = _tally([s.retraction_status for s in retractables], _RETRACTION_TALLY)
        doc.paragraphe(
            f"Rétractation ({len(retractables)} source(s) de littérature scientifique) : {bilan}",
            indent=_RETRAIT_SOURCE,
        )
    acces = _tally(
        ["en accès ouvert" if s.oa_url else s.oa_status for s in sources],
        _OA_TALLY,
    )
    doc.paragraphe(f"Accès : {acces}", indent=_RETRAIT_SOURCE)
    doc.espace(4)
    doc.paragraphe(
        "Le détail sous chaque source ne signale que les faits établis : une "
        "rétractation, un texte intégral gratuit, une archive.",
        taille=8.5,
        police=ITALIQUE,
    )


def _source(doc: Document, source: Source, rang: int, scope: ExportScope, style: str) -> None:
    doc.espace(10)
    doc.besoin(40)
    # « Source clé » plutot qu'une etoile : le symbole demanderait une legende,
    # et c'est le mot qu'emploie deja l'interface.
    cle = " (source clé)" if source.is_pivot else ""
    # Le titre porte le lien : un PDF de bibliographie dont les references ne
    # s'ouvrent pas oblige a recopier l'adresse a la main.
    doc.paragraphe(
        f"{rang}. {source.title or source.url}{cle}",
        taille=10.5,
        police=GRASSE,
        lien=source.url,
    )
    reference = citation_styles.format_reference(source, style)
    doc.paragraphe(reference, taille=9, police=ITALIQUE, indent=_RETRAIT_SOURCE)
    # L'adresse n'est ecrite en clair que si la reference stylee ne la porte
    # pas deja : la plupart des styles la rendent, et la redire ferait la meme
    # information deux fois a une ligne d'ecart.
    if source.url and source.url not in reference:
        doc.paragraphe(source.url, taille=8.5, indent=_RETRAIT_SOURCE, lien=source.url)
    doc.paragraphe(f"Catégorie : {source.category}", taille=8.5, indent=_RETRAIT_SOURCE)

    if scope.reliability and source.retraction_status == "retracted":
        avis = "RÉTRACTÉE"
        if source.retraction_notice_doi:
            avis += f" (avis de rétractation : {source.retraction_notice_doi})"
        doc.paragraphe(avis, taille=9, police=GRASSE, indent=_RETRAIT_SOURCE)
        # Le motif est cite verbatim et attribue : c'est le vocabulaire de
        # Retraction Watch, pas une qualification que Philum porterait.
        if source.retraction_reason:
            doc.paragraphe(
                f"Motif (Retraction Watch) : {source.retraction_reason}",
                taille=8.5,
                indent=_RETRAIT_SOURCE,
            )

    if source.doi and source.doi.lower() not in (source.url or "").lower():
        doc.paragraphe(f"DOI : {source.doi}", taille=8.5, indent=_RETRAIT_SOURCE)
    if scope.reliability and source.oa_url:
        libelle = f"Accès ouvert ({source.oa_status})" if source.oa_status else "Accès ouvert"
        doc.paragraphe(
            f"{libelle} : {source.oa_url}",
            taille=8.5,
            indent=_RETRAIT_SOURCE,
            lien=source.oa_url,
        )
    position = _STANCE_LABELS.get(source.stance or "")
    if position:
        doc.paragraphe(f"Position déclarée : {position}", taille=8.5, indent=_RETRAIT_SOURCE)

    if scope.annotations and source.annotation:
        # Nommee, parce que l'extrait juste en dessous porte la meme marque de
        # citation : l'un est ce que la source dit, l'autre ce que le createur
        # en dit. Les confondre attribuerait a un auteur des mots qu'il n'a
        # pas ecrits, le contraire exact de ce que Philum sert.
        doc.paragraphe(f"Note du créateur : {source.annotation}", taille=9, indent=_RETRAIT_SOURCE)

    if scope.excerpts:
        for extrait in sorted(source.excerpts, key=lambda e: e.position):
            _extrait(doc, extrait)

    if scope.archives and source.archive_url:
        doc.paragraphe(
            f"Archive : {source.archive_url}",
            taille=8.5,
            indent=_RETRAIT_SOURCE,
            lien=source.archive_url,
        )


def _extrait(doc: Document, extrait) -> None:  # noqa: ANN001 - SourceExcerpt (TYPE_CHECKING)
    doc.espace(4)
    doc.besoin(30)
    intitule = extrait.title or "Extrait"
    marque = " (proposé par IA)" if extrait.suggested_by_ai else ""
    doc.paragraphe(f"{intitule}{marque}", taille=9, police=GRASSE, indent=_RETRAIT_SOURCE)
    # Le verbatim en italique entre guillemets, et rien d'autre dans ce
    # paragraphe : tout ce qui s'y glisserait se lirait comme venant de la
    # source.
    doc.paragraphe(
        f"« {extrait.text} »",
        taille=9,
        police=ITALIQUE,
        indent=_RETRAIT_EXTRAIT,
    )
    if extrait.context:
        origine = " (mise en situation proposée par IA)" if extrait.annotated_by_ai else ""
        doc.paragraphe(
            f"Mise en situation : {extrait.context}{origine}",
            taille=8.5,
            indent=_RETRAIT_EXTRAIT,
        )
    verdict = _excerpt_verdict(extrait)
    if verdict:
        doc.paragraphe(verdict.lstrip(_MARQUES_VERDICT), taille=8.5, indent=_RETRAIT_EXTRAIT)


def _voisinage(doc: Document, voisinage: Neighbourhood, base_url: str, style: str) -> None:
    for sens, voisines in (("cited", voisinage.cited), ("citing", voisinage.citing)):
        if not voisines:
            continue
        _titre_section(doc, _DIRECTION_TITRES[sens])
        for degre in sorted({v.degree for v in voisines}):
            doc.espace(6)
            doc.paragraphe(f"Degré {degre}", taille=10, police=GRASSE)
            for voisine in (v for v in voisines if v.degree == degre):
                _voisine(doc, voisine, base_url, style)
    if voisinage.truncated:
        doc.espace(8)
        doc.paragraphe(
            "Le voisinage a été tronqué : la fiche en compte plus que ce qu'un export peut porter.",
            taille=8.5,
            police=ITALIQUE,
        )


def _voisine(doc: Document, voisine: NeighbourCard, base_url: str, style: str) -> None:
    adresse = f"{base_url}/@{voisine.card.user.username}/{voisine.card.slug}"
    doc.espace(8)
    doc.besoin(36)
    doc.paragraphe(voisine.card.title, taille=10, police=GRASSE)
    doc.paragraphe(adresse, taille=8.5, indent=_RETRAIT_SOURCE, lien=adresse)
    doc.paragraphe(f"Par @{voisine.card.user.username}", taille=8.5, indent=_RETRAIT_SOURCE)
    if voisine.scope.references_only:
        for source in voisine.card.sources:
            doc.paragraphe(
                source.title or source.url,
                taille=8.5,
                indent=_RETRAIT_EXTRAIT,
                lien=source.url,
            )
        return
    for rang, source in enumerate(voisine.card.sources, start=1):
        _source(doc, source, rang, voisine.scope, style)


def export_pdf(
    card: BiblioCard,
    public_url: str,
    scope: ExportScope = FULL,
    neighbourhood: Neighbourhood | None = None,
    style: str = "apa",
) -> bytes:
    """La fiche en PDF, prete a imprimer ou a joindre a un message."""
    doc = Document(card.title, f"Philum  |  {public_url}")

    doc.paragraphe(card.title, taille=19, police=GRASSE, interligne=1.22)
    doc.espace(4)
    createur = card.user.display_name or card.user.username
    meta = f"Fiche bibliographique de {createur}"
    if card.published_at:
        meta += f", publiée le {card.published_at.date().isoformat()}"
    doc.paragraphe(meta, taille=9, police=ITALIQUE)
    if card.description:
        doc.espace(8)
        doc.paragraphe(card.description, taille=10)
    if card.content_url:
        doc.espace(6)
        doc.paragraphe(f"Contenu : {card.content_url}", taille=8.5, lien=card.content_url)

    if scope.reliability:
        _bilan_fiabilite(doc, list(card.sources))

    _titre_section(doc, f"Sources ({len(card.sources)}), style {citation_styles.STYLES[style]}")
    for rang, source in enumerate(card.sources, start=1):
        _source(doc, source, rang, scope, style)

    if neighbourhood is not None:
        _voisinage(doc, neighbourhood, public_url.rsplit("/@", 1)[0], style)

    doc.espace(18)
    if doc.caracteres_perdus:
        # Un verbatim ampute sans le dire serait un verbatim faux. Le document
        # declare la substitution et renvoie la ou le texte est entier.
        doc.paragraphe(
            f"Certains caractères de ce document ne s'écrivent pas dans une police "
            f"PDF standard et apparaissent sous la forme « {pdf_minimal.SUBSTITUT} ». "
            f"Le texte intégral, lui, est sur la fiche en ligne.",
            taille=8.5,
            police=ITALIQUE,
        )
        doc.espace(6)
    doc.paragraphe(f"Exporté depuis Philum : {public_url}", taille=8.5, police=ITALIQUE)
    return doc.rendu()
