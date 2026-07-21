"""Extraction structurée des références d'un PDF via GROBID.

GROBID (grobid.readthedocs.io) segmente la bibliographie d'un PDF en
références structurées (titre, auteurs, année, DOI) — bien plus fiable que
le scan regex des URLs/DOIs. On l'appelle via le Space Hugging Face public
``kermitt2/grobid`` (gratuit, sans clé). Ce Space dort après inactivité
(cold start ~2 min) : tout échec, timeout ou réponse non-TEI est traité
comme « GROBID indisponible » et le caller retombe sur le parseur local.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET

import httpx

from app.core.config import get_settings
from app.services.import_parsers import ImportedRef, _doi_to_url

logger = logging.getLogger(__name__)

_TEI = "{http://www.tei-c.org/ns/1.0}"
# Identifiant arXiv dans un idno : "arXiv:1705.04304v2" ou "CoRR, abs/1703.03906".
_ARXIV_ID_RE = re.compile(r"(?:arXiv:|abs/)(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
# Le traitement GROBID prend 3-6 s par PDF une fois le Space chaud ; le
# timeout couvre aussi un éventuel réveil partiel sans bloquer l'endpoint.
_TIMEOUT = 45.0


def _text(elem: ET.Element | None) -> str | None:
    if elem is None:
        return None
    value = "".join(elem.itertext()).strip()
    return value or None


def _parse_tei(xml_text: str) -> list[ImportedRef] | None:
    """TEI ``processReferences`` → refs. None si la réponse n'est pas du XML
    (page HTML « Preparing Space » tronquée, erreur proxy…)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    refs: list[ImportedRef] = []
    for bibl in root.iter(f"{_TEI}biblStruct"):
        doi = _text(bibl.find(f".//{_TEI}idno[@type='DOI']"))
        ptr = bibl.find(f".//{_TEI}ptr[@target]")
        target = ptr.get("target", "") if ptr is not None else ""
        arxiv_id = None
        for idno in bibl.iter(f"{_TEI}idno"):
            m = _ARXIV_ID_RE.search("".join(idno.itertext()))
            if m:
                arxiv_id = m.group(1)
                break
        if doi:
            url = _doi_to_url(doi)
            category = "article-scientifique"
        elif target.startswith(("http://", "https://")):
            url = target
            category = "page-web"
        elif arxiv_id:
            url = f"https://arxiv.org/abs/{arxiv_id}"
            category = "preprint"
        else:
            continue
        title = _text(bibl.find(f".//{_TEI}title[@level='a']")) or _text(
            bibl.find(f".//{_TEI}title[@level='m']")
        )
        names: list[str] = []
        for pers in bibl.iter(f"{_TEI}persName"):
            forename = _text(pers.find(f"{_TEI}forename"))
            surname = _text(pers.find(f"{_TEI}surname"))
            name = " ".join(part for part in (forename, surname) if part)
            if name:
                names.append(name)
        year: int | None = None
        date = bibl.find(f".//{_TEI}date[@when]")
        if date is not None and date.get("when", "")[:4].isdigit():
            year = int(date.get("when", "")[:4])
        refs.append(
            ImportedRef(
                url=url,
                title=title,
                authors=", ".join(names) or None,
                year=year,
                category=category,
            )
        )
    return refs


async def extract_pdf_references(data: bytes) -> list[ImportedRef] | None:
    """Références structurées d'un PDF via GROBID. None = indisponible."""
    base = get_settings().grobid_base_url.rstrip("/")
    if not base:
        return None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                f"{base}/api/processReferences",
                files={"input": ("upload.pdf", data, "application/pdf")},
                data={"consolidateCitations": "0"},
            )
    except httpx.HTTPError as e:
        logger.warning("GROBID unreachable: %s", e)
        return None
    if r.status_code != 200:
        logger.warning("GROBID returned HTTP %s", r.status_code)
        return None
    refs = _parse_tei(r.text)
    if refs is None:
        logger.warning("GROBID response was not TEI XML")
    return refs
