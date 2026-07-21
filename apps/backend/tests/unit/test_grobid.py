from __future__ import annotations

import httpx
import pytest

import app.extractors.grobid as grobid_module
from app.extractors.grobid import _parse_tei, extract_pdf_references

TEI_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <text>
    <listBibl>
      <biblStruct>
        <analytic>
          <title level="a" type="main">Sleep and memory consolidation</title>
          <author><persName><forename type="first">Matthew</forename><surname>Walker</surname></persName></author>
          <author><persName><forename type="first">Robert</forename><surname>Stickgold</surname></persName></author>
          <idno type="DOI">10.1038/nrn.2017.55</idno>
        </analytic>
        <monogr>
          <title level="j">Nature Reviews Neuroscience</title>
          <imprint><date type="published" when="2017-09-01" /></imprint>
        </monogr>
      </biblStruct>
      <biblStruct>
        <monogr>
          <title level="m">Un livre sans DOI ni URL</title>
          <author><persName><surname>Anonyme</surname></persName></author>
          <imprint><date type="published" when="1999" /></imprint>
        </monogr>
      </biblStruct>
      <biblStruct>
        <monogr>
          <title level="m">Rapport en ligne</title>
          <ptr target="https://example.org/rapport-grobid" />
          <imprint />
        </monogr>
      </biblStruct>
      <biblStruct>
        <analytic>
          <title level="a">Attention avec identifiant arXiv</title>
          <idno type="arXiv">arXiv:1705.04304</idno>
        </analytic>
        <monogr><imprint /></monogr>
      </biblStruct>
      <biblStruct>
        <monogr>
          <title level="m">Papier CoRR sans type d'idno</title>
          <idno>CoRR, abs/1703.03906</idno>
          <imprint />
        </monogr>
      </biblStruct>
    </listBibl>
  </text>
</TEI>
"""


def test_parse_tei_extracts_structured_refs():
    refs = _parse_tei(TEI_SAMPLE)
    assert refs is not None
    # La ref sans DOI ni URL ni arXiv est ignorée (le modèle Source exige une URL).
    assert len(refs) == 4
    article = refs[0]
    assert article.url == "https://doi.org/10.1038/nrn.2017.55"
    assert article.title == "Sleep and memory consolidation"
    assert article.authors == "Matthew Walker, Robert Stickgold"
    assert article.year == 2017
    assert article.category == "article-scientifique"
    rapport = refs[1]
    assert rapport.url == "https://example.org/rapport-grobid"
    assert rapport.title == "Rapport en ligne"
    arxiv = refs[2]
    assert arxiv.url == "https://arxiv.org/abs/1705.04304"
    assert arxiv.title == "Attention avec identifiant arXiv"
    assert arxiv.category == "preprint"
    corr = refs[3]
    assert corr.url == "https://arxiv.org/abs/1703.03906"
    assert corr.category == "preprint"


def test_parse_tei_invalid_xml():
    assert _parse_tei("<html>Preparing Space</html>") == []
    assert _parse_tei("pas du xml <<<") is None


class _FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse | Exception, calls: list):
        self._response = response
        self._calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        self._calls.append(url)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


@pytest.mark.asyncio
async def test_extract_pdf_references_ok(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        grobid_module.httpx,
        "AsyncClient",
        lambda **kw: _FakeAsyncClient(_FakeResponse(200, TEI_SAMPLE), calls),
    )
    refs = await extract_pdf_references(b"%PDF-1.4 fake")
    assert refs is not None
    assert len(refs) == 4
    assert calls and calls[0].endswith("/api/processReferences")


@pytest.mark.asyncio
async def test_extract_pdf_references_network_failure(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        grobid_module.httpx,
        "AsyncClient",
        lambda **kw: _FakeAsyncClient(httpx.ConnectTimeout("boom"), calls),
    )
    assert await extract_pdf_references(b"%PDF-1.4 fake") is None


@pytest.mark.asyncio
async def test_extract_pdf_references_http_error(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        grobid_module.httpx,
        "AsyncClient",
        lambda **kw: _FakeAsyncClient(_FakeResponse(503, "sleeping"), calls),
    )
    assert await extract_pdf_references(b"%PDF-1.4 fake") is None


@pytest.mark.asyncio
async def test_extract_pdf_references_disabled(monkeypatch):
    class _Stub:
        grobid_base_url = ""

    monkeypatch.setattr(grobid_module, "get_settings", lambda: _Stub())
    assert await extract_pdf_references(b"%PDF-1.4 fake") is None
