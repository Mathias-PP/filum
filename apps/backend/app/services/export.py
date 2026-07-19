"""Export d'une fiche bibliographique en formats standards.

Fonctions pures : elles prennent une BiblioCard (avec .sources et .user
charges) et retournent le contenu serialise. Aucune dependance externe :
le XLSX est genere via zipfile/XML minimal (format OOXML, inline strings).
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

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
        source.archive_url or "",
        source.archive_timestamp.isoformat() if source.archive_timestamp else "",
    ]


def export_json(card: BiblioCard, public_url: str) -> str:
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
        "sources": [
            {
                "position": s.position,
                "title": s.title,
                "authors": s.authors,
                "url": s.url,
                "published_at": s.published_at.isoformat() if s.published_at else None,
                "format": s.format,
                "category": s.category,
                "author_kind": s.author_kind,
                "annotation": s.annotation,
                "is_pivot": s.is_pivot,
                "archive_url": s.archive_url,
                "archive_timestamp": (
                    s.archive_timestamp.isoformat() if s.archive_timestamp else None
                ),
            }
            for s in card.sources
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


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


def _bibtex_key(source: Source, index: int) -> str:
    base = source.authors or source.title or "source"
    word = re.sub(r"[^A-Za-z0-9]", "", base.split(",")[0].split()[0]) or "source"
    year = source.published_at.year if source.published_at else "nd"
    return f"{word.lower()}{year}n{index}"


def export_bibtex(card: BiblioCard) -> str:
    entries: list[str] = []
    for i, source in enumerate(card.sources, start=1):
        entry_type = _BIBTEX_TYPE_BY_CATEGORY.get(source.category, "misc")
        fields = {
            "title": source.title or source.url,
            "url": source.url,
        }
        if source.authors:
            fields["author"] = source.authors
        if source.published_at:
            fields["year"] = str(source.published_at.year)
        if source.annotation:
            fields["note"] = source.annotation
        body = ",\n".join(f"  {k} = {{{_bibtex_escape(v)}}}" for k, v in fields.items())
        entries.append(f"@{entry_type}{{{_bibtex_key(source, i)},\n{body}\n}}")
    header = f"% Bibliographie Philum — {card.title}\n% {len(card.sources)} sources\n\n"
    return header + "\n\n".join(entries) + "\n"


# --- Markdown (Obsidian) ----------------------------------------------------


def export_markdown(card: BiblioCard, public_url: str) -> str:
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
        lines.append(f"  - {' · '.join(meta)}")
        if source.annotation:
            lines.append(f"  - > {source.annotation}")
        if source.archive_url:
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


def export_docx(card: BiblioCard, public_url: str) -> bytes:
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
        if s.annotation:
            paragraphs.append(_docx_p(_docx_run(s.annotation, italic=True)))
        if s.archive_url:
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
