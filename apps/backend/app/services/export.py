"""Export d'une fiche bibliographique en formats standards.

Fonctions pures : elles prennent une BiblioCard (avec .sources et .user
charges) et retournent le contenu serialise. Aucune dependance externe :
le XLSX est genere via zipfile/XML minimal (format OOXML, inline strings).
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape  # nosec B406 - echappe la sortie, ne parse rien

from app.services import citation_styles
from app.services.csl import author_display, to_csl
from app.services.export_scope import FULL, ExportScope

if TYPE_CHECKING:
    from app.models.biblio_card import BiblioCard
    from app.models.source import Source

CSV_COLUMNS = [
    "position",
    "title",
    "authors",
    "url",
    "published_at",
    "format",
    "category",
    "author_kind",
    "is_pivot",
    "annotation",
    "journal",
    "volume",
    "pages",
    "publisher",
    "doi",
    "archive_url",
    "archive_timestamp",
]


def _source_row(source: Source) -> list[str]:
    return [
        str(source.position),
        source.title or "",
        source.authors or "",
        source.url,
        source.published_at.date().isoformat() if source.published_at else "",
        source.format,
        source.category,
        source.author_kind,
        "oui" if source.is_pivot else "non",
        source.annotation or "",
        source.journal or "",
        source.volume or "",
        source.pages or "",
        source.publisher or "",
        source.doi or "",
        source.archive_url or "",
        source.archive_timestamp.isoformat() if source.archive_timestamp else "",
    ]


def _excerpts(source: Source) -> list[dict]:
    """Les extraits d'une source, ancrage compris.

    L'ancrage (`prefix`/`suffix`/`offset`) part avec le texte : sans lui, un
    extrait exporte n'est plus qu'une citation invérifiable, et retrouver le
    passage dans une page qui a bouge redevient impossible.
    """
    return [
        {
            "position": e.position,
            "title": e.title,
            "text": e.text,
            "suggested_by_ai": e.suggested_by_ai,
            "anchor": {
                "prefix": e.anchor_prefix,
                "suffix": e.anchor_suffix,
                "offset": e.anchor_offset,
            }
            if e.anchor_prefix or e.anchor_suffix or e.anchor_offset is not None
            else None,
        }
        for e in sorted(source.excerpts, key=lambda e: e.position)
    ]


def export_json(card: BiblioCard, public_url: str, scope: ExportScope = FULL) -> str:
    payload = {
        "philum_export_version": 1,
        "card": {
            "title": card.title,
            "description": card.description,
            "content_url": card.content_url,
            "platform": card.platform,
            "public_url": public_url,
            "creator": {
                "username": card.user.username,
                "display_name": card.user.display_name,
            },
            "published_at": card.published_at.isoformat() if card.published_at else None,
        },
        "sources": [_json_source(s, scope) for s in card.sources],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _json_source(s: Source, scope: ExportScope) -> dict:
    entry: dict = {
        "position": s.position,
        "title": s.title,
        "authors": s.authors,
        "url": s.url,
        "published_at": s.published_at.isoformat() if s.published_at else None,
        "format": s.format,
        "category": s.category,
        "author_kind": s.author_kind,
        "is_pivot": s.is_pivot,
        "journal": s.journal,
        "volume": s.volume,
        "pages": s.pages,
        "publisher": s.publisher,
        "doi": s.doi,
    }
    if scope.annotations:
        entry["annotation"] = s.annotation
    if scope.excerpts:
        entry["excerpts"] = _excerpts(s)
    if scope.archives:
        entry["archive_url"] = s.archive_url
        entry["archive_timestamp"] = (
            s.archive_timestamp.isoformat() if s.archive_timestamp else None
        )
    if scope.reliability:
        entry["retraction_status"] = s.retraction_status
        entry["retraction_notice_doi"] = s.retraction_notice_doi
        entry["oa_status"] = s.oa_status
        entry["oa_url"] = s.oa_url
    return entry


def export_philum_json(card: BiblioCard, public_url: str, scope: ExportScope = FULL) -> str:
    """Format `application/vnd.philum+json` : cible primaire des agents IA.

    Superset de `export_json` avec :
    - un contexte JSON-LD (schema.org) : un agent qui connait schema.org peut
      cabler directement Article, Person, ScholarlyArticle sans mapping ;
    - le champ `stance` par source (declaration explicite de la relation
      entre l'affirmation du contenu et la source citee) ;
    - le statut de retraction (`retraction_status`, `retraction_notice_doi`)
      indispensable pour qu'un agent evite de propager une source retiree ;
    - la version du format en clair, pour permettre une evolution stricte.
    """
    return json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "philum_format_version": "1.0",
            "url": public_url,
            "headline": card.title,
            "description": card.description,
            "datePublished": card.published_at.isoformat() if card.published_at else None,
            "author": {
                "@type": "Person",
                "identifier": card.user.username,
                "name": card.user.display_name or card.user.username,
                "url": f"{public_url.rsplit('/@', 1)[0]}/@{card.user.username}",
            },
            "isBasedOn": card.content_url,
            "citation": [_philum_source(s, scope) for s in card.sources],
        },
        ensure_ascii=False,
        indent=2,
    )


def _philum_source(s: Source, scope: ExportScope) -> dict:
    entry: dict = {
        "@type": "CreativeWork",
        "position": s.position,
        "name": s.title,
        "author": s.authors,
        "url": s.url,
        "datePublished": s.published_at.isoformat() if s.published_at else None,
        "identifier": {"@type": "PropertyValue", "propertyID": "DOI", "value": s.doi}
        if s.doi
        else None,
        "isPartOf": s.journal,
        "volumeNumber": s.volume,
        "pagination": s.pages,
        "publisher": s.publisher,
        # Champs Philum specifiques : lisibles par un agent, meme si non
        # schema.org, grace au prefixe philum: (JSON-LD tolere).
        # `stance` reste hors perimetre : c'est la relation declaree entre le
        # propos et la source, donc une propriete de la citation elle-meme, pas
        # un supplement qu'on emporte ou non.
        "philum:stance": s.stance,
        "philum:isPivot": s.is_pivot,
    }
    if scope.annotations:
        entry["annotation"] = s.annotation
    if scope.excerpts:
        # `citation` schema.org ne prevoit pas d'extrait ; `philum:excerpts`
        # porte donc le verbatim que l'agent peut recouper avec la source.
        entry["philum:excerpts"] = _excerpts(s)
    if scope.archives:
        entry["philum:archiveUrl"] = s.archive_url
        entry["philum:archiveTimestamp"] = (
            s.archive_timestamp.isoformat() if s.archive_timestamp else None
        )
        entry["philum:accessibility"] = s.archive_status
    if scope.reliability:
        entry["philum:retractionStatus"] = s.retraction_status
        entry["philum:retractionNoticeDOI"] = s.retraction_notice_doi
        entry["philum:openAccessStatus"] = s.oa_status
        entry["philum:openAccessUrl"] = s.oa_url
    return entry


def export_csv(card: BiblioCard) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for source in card.sources:
        writer.writerow(_source_row(source))
    return buf.getvalue()


# --- BibTeX -----------------------------------------------------------------

_BIBTEX_TYPE_BY_CATEGORY = {
    "article-scientifique": "article",
    "preprint": "article",
    "article-presse": "article",
    "livre": "book",
}


def _bibtex_escape(value: str) -> str:
    return value.replace("\\", "\\textbackslash{}").replace("{", "\\{").replace("}", "\\}")


def export_bibtex(card: BiblioCard) -> str:
    entries: list[str] = []
    for i, source in enumerate(card.sources, start=1):
        item = to_csl(source, i)
        entry_type = _BIBTEX_TYPE_BY_CATEGORY.get(source.category, "misc")
        fields = {
            "title": item["title"],
            "url": item["URL"],
        }
        if item.get("author"):
            # BibTeX veut « Famille, Prenom and Famille, Prenom » : c'est ce
            # decoupage qui permet a LaTeX d'abreger et de trier les noms.
            fields["author"] = " and ".join(
                author_display([a]) for a in item["author"] if author_display([a])
            )
        if source.published_at:
            fields["year"] = str(source.published_at.year)
        for bib_key, csl_key_name in (
            ("journal", "container-title"),
            ("volume", "volume"),
            ("pages", "page"),
            ("publisher", "publisher"),
            ("doi", "DOI"),
            ("note", "note"),
        ):
            if item.get(csl_key_name):
                fields[bib_key] = item[csl_key_name]
        body = ",\n".join(f"  {k} = {{{_bibtex_escape(v)}}}" for k, v in fields.items())
        entries.append(f"@{entry_type}{{{item['id']},\n{body}\n}}")
    header = f"% Bibliographie Philum — {card.title}\n% {len(card.sources)} sources\n\n"
    return header + "\n\n".join(entries) + "\n"


# --- CSL-JSON (Zotero et al.) -----------------------------------------------


def export_csl_json(card: BiblioCard) -> str:
    items = [to_csl(s, i) for i, s in enumerate(card.sources, start=1)]
    return json.dumps(items, ensure_ascii=False, indent=2)


# --- RIS (EndNote, Mendeley, Zotero) ----------------------------------------

# Vocabulaire RIS, ferme lui aussi. Derive du type CSL pour que les deux
# formats ne puissent pas diverger. Defaut « ELEC » (ressource electronique),
# le plus honnete pour une URL dont on ne sait rien de plus.
_RIS_TYPE_BY_CSL = {
    "article-journal": "JOUR",
    "article-newspaper": "NEWS",
    "report": "RPRT",
    "motion_picture": "MPCT",
    "interview": "ICOMM",
    "broadcast": "SOUND",
    "book": "BOOK",
    "manuscript": "UNPB",
    "webpage": "ELEC",
}


def _ris_lines(item: dict, source: Source) -> list[str]:
    """Un item CSL en lignes RIS.

    Le format impose « XX  - valeur » (deux espaces avant le tiret) et une
    balise « ER  - » de fin d'enregistrement : sans elle, le lecteur fusionne
    silencieusement toutes les references en une seule.
    """
    lines = [f"TY  - {_RIS_TYPE_BY_CSL.get(item['type'], 'ELEC')}"]
    # RIS veut un auteur par ligne AU, en « Famille, Prenom ».
    for author in item.get("author", []):
        rendered = author_display([author])
        if rendered:
            lines.append(f"AU  - {rendered}")
    lines.append(f"TI  - {item['title']}")
    if source.published_at:
        # PY veut l'annee seule ; DA porte la date complete.
        lines.append(f"PY  - {source.published_at.year}")
        lines.append(f"DA  - {source.published_at.strftime('%Y/%m/%d')}")
    for tag, key in (
        ("JO", "container-title"),
        ("VL", "volume"),
        ("SP", "page"),
        ("PB", "publisher"),
        ("DO", "DOI"),
        ("UR", "URL"),
    ):
        if item.get(key):
            lines.append(f"{tag}  - {item[key]}")
    if item.get("note"):
        # Une note multi-ligne casserait le parsing : chaque ligne RIS doit
        # commencer par une balise.
        for chunk in str(item["note"]).splitlines():
            if chunk.strip():
                lines.append(f"N1  - {chunk.strip()}")
    lines.append("ER  - ")
    return lines


def export_ris(card: BiblioCard) -> str:
    out: list[str] = []
    for i, source in enumerate(card.sources, start=1):
        out.extend(_ris_lines(to_csl(source, i), source))
        out.append("")
    return "\n".join(out)


# --- Bibliographie formatee (texte) -----------------------------------------


def export_bibliography(card: BiblioCard, public_url: str, style: str) -> str:
    """La bibliographie de la fiche, rendue dans le style demande.

    L'en-tete rappelle la fiche d'origine : une bibliographie collee dans un
    document perd sinon toute trace de sa provenance, et c'est precisement ce
    lien que Philum sert a etablir.
    """
    lines = [
        f"Bibliographie ({citation_styles.STYLES[style]}) — {card.title}",
        f"Fiche Philum : {public_url}",
        "",
    ]
    lines += citation_styles.format_bibliography(list(card.sources), style)
    return "\n".join(lines) + "\n"


# --- Markdown (Obsidian, et lecture par une IA) -----------------------------

#: Rendu de `Source.stance`. Un `None` n'a volontairement pas d'entree : une
#: position non declaree est un silence, la rabattre sur « mentionne » ferait
#: dire au createur ce qu'il n'a pas dit.
_STANCE_LABELS = {
    "appuie": "appuie le propos",
    "nuance-contredit": "nuance ou contredit le propos",
    "mentionne": "est mentionnee",
    "contexte": "apporte du contexte",
}

#: Etats de verification comptes en tete de document plutot que repetes sous
#: chaque source. Mesure sur une fiche reelle de 185 references : les etats
#: « vérification impossible » y etaient universels et ajoutaient 370 lignes
#: qui n'affirmaient rien, noyant les quelques faits qui, eux, comptent.
#: Le detail par source est reserve aux *trouvailles* — une retractation, un
#: texte integral gratuit. Le bilan reste au complet ci-dessous, donc rien
#: n'est tu : c'est la place de l'information qui change, pas son existence.
_RETRACTION_TALLY = {
    "retracted": "rétractée(s)",
    "none": "vérifiée(s) sans rétractation",
    "unverifiable": "non vérifiable(s)",
    None: "jamais vérifiée(s)",
}

_OA_TALLY = {
    "closed": "sans version gratuite connue",
    "unverifiable": "accès non vérifiable",
    None: "accès jamais vérifié",
}


def _tally(values: list[str | None], labels: dict[str | None, str]) -> str:
    """« 3 rétractée(s), 180 vérifiée(s) sans rétractation, 2 jamais vérifiée(s) ».

    Un etat inconnu du dictionnaire est compte tel quel plutot que fondu dans
    un autre : mieux vaut un libelle brut qu'un total faux le jour ou une
    nouvelle valeur apparait en base.
    """
    counts: dict[str | None, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    ordered = list(labels) + [v for v in counts if v not in labels]
    return ", ".join(f"{counts[v]} {labels.get(v, v)}" for v in ordered if counts.get(v))


def _reliability_summary(sources: list[Source]) -> list[str]:
    if not sources:
        return []
    retraction = _tally([s.retraction_status for s in sources], _RETRACTION_TALLY)
    # Ce qui compte pour un lecteur est le texte gratuit *effectivement*
    # atteignable, pas le statut declare par OpenAlex : un « gold » sans URL ne
    # lui ouvre aucune porte.
    access = _tally(
        ["en accès ouvert" if s.oa_url else s.oa_status for s in sources],
        _OA_TALLY,
    )
    return [
        "## Fiabilité des sources",
        "",
        f"Sur {len(sources)} source(s) :",
        f"- Rétractation : {retraction}",
        f"- Accès : {access}",
        "",
        "Le détail sous chaque source ne signale que les faits établis : une "
        "rétractation, un texte intégral gratuit, une archive.",
        "",
    ]


def _source_details(source: Source, scope: ExportScope = FULL) -> list[str]:
    """Les lignes qui rendent une source *verifiable*, pas seulement citable.

    C'est le markdown qu'un agent conversationnel lira pour decider ce qu'il
    ose affirmer d'une reference : y taire une retractation serait le pire
    resultat possible pour Philum. Tout s'ecrit en texte plutot qu'en lien —
    `parse_markdown` recolte toute URL du document, et une metadonnee ne doit
    pas renaitre en source fantome au reimport. L'acces ouvert fait seul
    exception : c'est le texte integral gratuit, l'omettre couterait plus que
    la gene qu'il cause.
    """
    lines: list[str] = []

    if scope.reliability and source.retraction_status == "retracted":
        retraction = "⚠️ RÉTRACTÉE"
        if source.retraction_notice_doi:
            retraction += f" — avis de rétractation : {source.retraction_notice_doi}"
        lines.append(f"  - {retraction}")

    # Le DOI n'est repete que s'il n'est pas deja l'adresse de la source : la
    # plupart des references academiques pointent vers `doi.org/<doi>`, et le
    # redire n'apprendrait rien a un lecteur tout en faisant naitre une source
    # de plus au reimport (`parse_markdown` recolte aussi les DOI nus).
    if source.doi and source.doi.lower() not in (source.url or "").lower():
        lines.append(f"  - DOI : {source.doi}")

    if scope.reliability and source.oa_url:
        label = f"Accès ouvert ({source.oa_status})" if source.oa_status else "Accès ouvert"
        lines.append(f"  - {label} : {source.oa_url}")

    stance = _STANCE_LABELS.get(source.stance or "")
    if stance:
        lines.append(f"  - Position déclarée : {stance}")

    return lines


def _excerpt_lines(source: Source) -> list[str]:
    """Les extraits en citation Markdown, un bloc par extrait.

    Le titre de l'extrait precede le texte quand il existe. L'ancrage n'est pas
    rendu : il n'a de sens que pour une machine, et le Markdown est ici lu par
    un humain — le JSON le porte pour l'autre usage.
    """
    lines: list[str] = []
    for e in sorted(source.excerpts, key=lambda e: e.position):
        intitule = f"**{e.title}** — " if e.title else "**Extrait** — "
        marque = " *(proposé par IA)*" if e.suggested_by_ai else ""
        texte = " ".join(e.text.split())
        lines.append(f"  - > {intitule}« {texte} »{marque}")
    return lines


def export_markdown(card: BiblioCard, public_url: str, scope: ExportScope = FULL) -> str:
    lines = [
        "---",
        f'title: "{card.title}"',
        f"creator: {card.user.display_name or card.user.username}",
        f"philum_url: {public_url}",
    ]
    if card.published_at:
        lines.append(f"published: {card.published_at.date().isoformat()}")
    lines += ["tags:", "  - philum", "  - bibliographie", "---", ""]
    lines.append(f"# {card.title}")
    lines.append("")
    if card.description:
        lines.append(card.description)
        lines.append("")
    if card.content_url:
        lines.append(f"Contenu : {card.content_url}")
        lines.append("")
    if scope.reliability:
        lines += _reliability_summary(list(card.sources))
    lines.append("## Sources")
    lines.append("")
    for source in card.sources:
        label = source.title or source.url
        pivot = " ⭐" if source.is_pivot else ""
        lines.append(f"- [{label}]({source.url}){pivot}")
        meta = []
        if source.authors:
            meta.append(source.authors)
        if source.published_at:
            meta.append(source.published_at.date().isoformat())
        meta.append(source.category)
        if source.journal:
            meta.append(source.journal)
        lines.append(f"  - {' · '.join(meta)}")
        lines += _source_details(source, scope)
        if scope.annotations and source.annotation:
            # Nommee, parce que l'extrait juste en dessous porte la meme marque
            # de citation : l'un est ce que la source dit, l'autre ce que le
            # createur en dit. Les confondre attribuerait a un auteur des mots
            # qu'il n'a pas ecrits — le contraire exact de ce que Philum sert.
            lines.append(f"  - > **Note du créateur** — {source.annotation}")
        if scope.excerpts:
            lines += _excerpt_lines(source)
        if scope.archives and source.archive_url:
            lines.append(f"  - [Archive]({source.archive_url})")
    lines.append("")
    return "\n".join(lines)


# --- DOCX (WordprocessingML minimal, stdlib uniquement) ---------------------

_W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _docx_run(
    text: str, *, bold: bool = False, italic: bool = False, size: int | None = None
) -> str:
    props = ""
    if bold or italic or size:
        parts = []
        if bold:
            parts.append("<w:b/>")
        if italic:
            parts.append("<w:i/>")
        if size:
            parts.append(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
        props = f"<w:rPr>{''.join(parts)}</w:rPr>"
    return f'<w:r>{props}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def _docx_p(*runs: str) -> str:
    return f"<w:p>{''.join(runs)}</w:p>"


def export_docx(card: BiblioCard, public_url: str, scope: ExportScope = FULL) -> bytes:
    """Document Word minimal : titre, méta, sources numérotées.

    Généré sans dépendance (zipfile + XML), comme le XLSX. Word/LibreOffice
    ignorent proprement l'absence de styles.xml : la mise en forme passe par
    des propriétés directes (gras, italique, taille en demi-points).
    """
    paragraphs: list[str] = [_docx_p(_docx_run(card.title, bold=True, size=36))]

    creator = card.user.display_name or card.user.username
    meta = f"Fiche bibliographique de {creator}"
    if card.published_at:
        meta += f" — publiée le {card.published_at.date().isoformat()}"
    paragraphs.append(_docx_p(_docx_run(meta, italic=True)))
    if card.description:
        paragraphs.append(_docx_p(_docx_run(card.description)))
    if card.content_url:
        paragraphs.append(_docx_p(_docx_run(f"Contenu : {card.content_url}")))
    paragraphs.append(_docx_p())
    paragraphs.append(_docx_p(_docx_run(f"Sources ({len(card.sources)})", bold=True, size=28)))

    for i, s in enumerate(card.sources, start=1):
        title_runs = [_docx_run(f"{i}. "), _docx_run(s.title or s.url, bold=True)]
        if s.is_pivot:
            title_runs.append(_docx_run(" (source pivot)"))
        paragraphs.append(_docx_p(*title_runs))
        meta_parts = []
        if s.authors:
            meta_parts.append(s.authors)
        if s.published_at:
            meta_parts.append(s.published_at.date().isoformat())
        meta_parts.append(s.category)
        paragraphs.append(_docx_p(_docx_run(" · ".join(meta_parts))))
        paragraphs.append(_docx_p(_docx_run(s.url)))
        if scope.reliability and s.retraction_status == "retracted":
            paragraphs.append(_docx_p(_docx_run("RÉTRACTÉE", bold=True)))
        if scope.annotations and s.annotation:
            paragraphs.append(_docx_p(_docx_run(s.annotation, italic=True)))
        if scope.excerpts:
            for e in sorted(s.excerpts, key=lambda e: e.position):
                paragraphs.append(
                    _docx_p(_docx_run(f"« {' '.join(e.text.split())} »", italic=True))
                )
        if scope.archives and s.archive_url:
            paragraphs.append(_docx_p(_docx_run(f"Archive : {s.archive_url}")))
        paragraphs.append(_docx_p())

    paragraphs.append(_docx_p(_docx_run(f"Exporté depuis Philum — {public_url}", italic=True)))

    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {_W_NS}><w:body>{''.join(paragraphs)}</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
        '2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document)
    return buf.getvalue()


# --- XLSX (OOXML minimal, stdlib uniquement) --------------------------------


def _xlsx_sheet_xml(rows: list[list[str]]) -> str:
    xml_rows = []
    for r_idx, row in enumerate(rows, start=1):
        cells = []
        for c_idx, value in enumerate(row):
            col = ""
            n = c_idx
            while True:
                col = chr(ord("A") + n % 26) + col
                n = n // 26 - 1
                if n < 0:
                    break
            cells.append(
                f'<c r="{col}{r_idx}" t="inlineStr"><is><t xml:space="preserve">'
                f"{escape(value)}</t></is></c>"
            )
        xml_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(xml_rows)}</sheetData></worksheet>"
    )


def export_xlsx(card: BiblioCard) -> bytes:
    rows = [CSV_COLUMNS] + [_source_row(s) for s in card.sources]
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
        '2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sources" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
        '2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", _xlsx_sheet_xml(rows))
    return buf.getvalue()
