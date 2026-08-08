"""Ce qu'un document depose peut rendre, et ce qu'il doit refuser de rendre.

Le risque propre a ce module n'est pas le plantage : c'est le texte vide ou
partiel rendu comme s'il etait complet. Un PDF scanne qui rendrait `""` ferait
proposer zero extrait sur un document qui en contient cent, sans que rien ne
dise pourquoi. Un document tronque ferait pire : il donnerait un decoupage qui
se lit comme entier.
"""

from __future__ import annotations

import io
import zipfile

import pytest

from app.services.document_text import (
    MAX_BYTES,
    MAX_CHARS,
    DocumentError,
    extract_text,
)


def _docx(paragraphes: list[str]) -> bytes:
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    corps = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphes)
    xml = f'<?xml version="1.0"?><w:document {ns}><w:body>{corps}</w:body></w:document>'
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return tampon.getvalue()


def _odt(paragraphes: list[str]) -> bytes:
    ns = 'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"'
    corps = "".join(f"<text:p>{p}</text:p>" for p in paragraphes)
    xml = f'<?xml version="1.0"?><doc {ns}>{corps}</doc>'
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as archive:
        archive.writestr("content.xml", xml)
    return tampon.getvalue()


class TestTexteBrut:
    def test_utf8(self):
        assert extract_text("notes.txt", "Étude sur l'inhibition".encode()) == (
            "Étude sur l'inhibition"
        )

    def test_markdown_est_rendu_tel_quel(self):
        # Pas de rendu : c'est sur ce texte que l'ancrage d'extrait sera
        # calcule, il doit correspondre a ce que l'auteur·ice voit.
        assert extract_text("n.md", b"# Titre\n\nCorps.") == "# Titre\n\nCorps."

    def test_octet_isole_ne_coute_pas_le_document(self):
        texte = extract_text("n.txt", b"debut \xff\xfe fin")
        assert "debut" in texte and "fin" in texte


class TestDocumentsStructures:
    def test_docx(self):
        assert extract_text("c.docx", _docx(["Premier.", "Second."])) == (
            "Premier.\nSecond.\n"
        )

    def test_odt(self):
        assert extract_text("c.odt", _odt(["Premier.", "Second."])) == (
            "Premier.\nSecond.\n"
        )

    def test_les_paragraphes_ne_se_collent_pas(self):
        """Sans saut, « fin.Debut » ferait un mot qui n'existe dans aucun texte,
        et un extrait ancre dessus serait introuvable dans la source."""
        assert "fin.\nDebut" in extract_text("c.docx", _docx(["fin.", "Debut"]))

    def test_archive_illisible_refusee_avec_une_consigne(self):
        with pytest.raises(DocumentError, match="structure attendue"):
            extract_text("c.docx", b"ceci n'est pas un zip")


def _pdf(texte: str) -> bytes:
    """Un PDF valide d'une page. `texte` vide donne un PDF sans texte
    selectionnable, c'est-a-dire ce que rend un scan."""
    flux = f"BT /F1 12 Tf 72 720 Td ({texte}) Tj ET".encode()
    objets = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
        b"/Resources<</Font<</F1 5 0 R>>>>/Contents 4 0 R>>",
        b"<</Length " + str(len(flux)).encode() + b">>stream\n" + flux + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    positions = []
    for i, objet in enumerate(objets, start=1):
        positions.append(len(out))
        out += f"{i} 0 obj".encode() + objet + b"endobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objets) + 1}\n0000000000 65535 f \n".encode()
    for position in positions:
        out += f"{position:010d} 00000 n \n".encode()
    out += f"trailer<</Root 1 0 R/Size {len(objets) + 1}>>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


class TestPdf:
    def test_texte_selectionnable(self):
        assert "inhibition" in extract_text("a.pdf", _pdf("Une inhibition mesurable."))

    def test_un_scan_le_dit_au_lieu_de_rendre_le_vide(self):
        """Rendre `""` ferait proposer zero extrait sur un document qui en
        contient cent, sans que rien ne dise pourquoi. Et deviner le texte
        d'une image ferait citer des mots produits par une reconnaissance
        de caracteres — le contraire de ce qu'un extrait garantit."""
        with pytest.raises(DocumentError, match="scannée"):
            extract_text("scan.pdf", _pdf(""))

    def test_fichier_illisible_oriente_vers_une_cause_plausible(self):
        with pytest.raises(DocumentError, match="mot de passe"):
            extract_text("casse.pdf", b"pas un pdf")


class TestRefus:
    def test_format_inconnu(self):
        with pytest.raises(DocumentError, match="Formats acceptés"):
            extract_text("image.png", b"...")

    def test_ancien_doc_oriente_vers_une_solution(self):
        with pytest.raises(DocumentError, match=r"\.docx"):
            extract_text("vieux.doc", b"...")

    def test_fichier_trop_gros_refuse_avant_tout_decodage(self):
        with pytest.raises(DocumentError, match="trop volumineux"):
            extract_text("gros.txt", b"a" * (MAX_BYTES + 1))

    def test_texte_trop_long_refuse_plutot_que_tronque(self):
        """Un document coupe en son milieu donnerait un decoupage qui se lit
        comme complet."""
        with pytest.raises(DocumentError, match="chapitre"):
            extract_text("long.txt", b"a" * (MAX_CHARS + 1))
