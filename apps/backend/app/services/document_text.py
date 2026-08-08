"""Le texte d'un document depose, quand la page ne se laisse pas lire.

Mesure du 2026-08-08 sur dix URLs : cinq ne rendent aucun texte exploitable
(NYT, ScienceDirect, treasury.gov et Cell a zero caractere, YouTube 313). Le
decoupage en extraits, lui, est purement algorithmique — il ne lui manque que
le texte. Coller le passage marche deja ; deposer le PDF ou le .docx qu'on a
sous la main marche mieux, parce qu'un chapitre entier ne se colle pas.

Ce que ce module refuse de faire, et pourquoi :

- **Aucune OCR.** Un PDF scanne ne rend rien ici, et le dit. Deviner le texte
  d'une image ferait citer a un auteur des mots produits par un modele de
  reconnaissance — exactement ce qu'un extrait est cense empecher.
- **Aucune troncature silencieuse.** Au-dela du plafond on refuse. Un document
  coupe en son milieu donnerait un decoupage qui se lit comme complet.
- **Aucun rendu de mise en forme.** On veut le texte tel qu'il se lit, parce
  que c'est sur lui que l'ancrage d'extrait sera calcule.

Le `.docx` et l'`.odt` sont lus sans dependance : ce sont des archives ZIP
contenant du XML, et l'export Word du projet est deja construit ainsi. Le XML
vient d'un fichier fourni par l'utilisateur, donc `defusedxml` — `xml.etree`
de la stdlib reste vulnerable a l'expansion d'entites.
"""

from __future__ import annotations

import io
import zipfile

from defusedxml import ElementTree as DefusedET

#: Meme plafond que le collage : au-dela, on refuse plutot que de tronquer.
MAX_CHARS = 200_000

#: Plafond a l'octet, applique avant tout decodage. Un fichier de 30 Mo
#: n'atteindra jamais `MAX_CHARS` en texte utile, mais le lire entier sur une
#: e2-micro d'un gigaoctet coute une memoire qu'on n'a pas.
MAX_BYTES = 25 * 1024 * 1024

EXTENSIONS = (".txt", ".md", ".markdown", ".docx", ".odt", ".pdf")


class DocumentError(Exception):
    """Le document ne peut pas rendre de texte, et on sait dire pourquoi."""


def _texte_brut(data: bytes) -> str:
    """UTF-8 d'abord, latin-1 en dernier recours.

    `errors="replace"` plutot qu'une exception : un octet mal encode au milieu
    d'un chapitre ne doit pas coûter tout le document.
    """
    for encodage in ("utf-8", "cp1252"):
        try:
            return data.decode(encodage)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def _parcourir(noeud, paragraphes: frozenset[str], morceaux: list[str]) -> None:
    """Descente en profondeur, texte dans l'ordre du document.

    `iter()` ne suffit pas : il est pre-ordre, si bien qu'un saut de ligne pose
    en voyant un paragraphe atterrit *avant* son contenu. Le saut se pose donc
    a la remontee.

    Les `tail` comptent : dans un ODT, la phrase qui suit un passage en gras
    est le `tail` du `<text:span>`, et la perdre trouerait le texte au milieu
    d'une phrase. Ni Word ni LibreOffice n'indentent leur XML, ces `tail` sont
    donc du contenu et non de la mise en page.
    """
    if noeud.text:
        morceaux.append(noeud.text)
    for enfant in noeud:
        _parcourir(enfant, paragraphes, morceaux)
        if enfant.tail:
            morceaux.append(enfant.tail)
    if noeud.tag.rsplit("}", 1)[-1] in paragraphes:
        morceaux.append("\n")


def _texte_ooxml(data: bytes, chemin: str, paragraphes: frozenset[str]) -> str:
    """Le texte d'une archive ZIP + XML (`.docx`, `.odt`).

    Un saut de ligne clot chaque paragraphe : sans lui, deux phrases voisines
    se colleraient en un mot qui n'existe dans aucun texte, et un extrait
    ancre dessus serait introuvable dans la source.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml = archive.read(chemin)
    except (zipfile.BadZipFile, KeyError) as err:
        raise DocumentError(
            "Ce fichier n'a pas la structure attendue. "
            "Enregistrez-le à nouveau depuis votre traitement de texte."
        ) from err

    morceaux: list[str] = []
    _parcourir(DefusedET.fromstring(xml), paragraphes, morceaux)
    return "".join(morceaux)


def _texte_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as err:  # pragma: no cover - dependance declaree
        raise DocumentError("La lecture des PDF n'est pas disponible sur ce serveur.") from err

    try:
        lecteur = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in lecteur.pages]
    except Exception as err:
        raise DocumentError(
            "Ce PDF n'a pas pu être lu. S'il est protégé par un mot de passe, "
            "retirez la protection et réessayez."
        ) from err

    texte = "\n\n".join(pages)
    if not texte.strip():
        # Un PDF scanne est une suite d'images. Le dire, plutot que de rendre
        # une chaine vide qui se lirait comme un document sans contenu.
        raise DocumentError(
            "Ce PDF ne contient pas de texte sélectionnable : c'est une image "
            "scannée. Copiez-collez le passage à la main."
        )
    return texte


def extract_text(filename: str, data: bytes) -> str:
    """Le texte lisible d'un document, ou une `DocumentError` qui dit pourquoi."""
    if len(data) > MAX_BYTES:
        raise DocumentError(
            f"Fichier trop volumineux ({len(data) // (1024 * 1024)} Mo, "
            f"maximum {MAX_BYTES // (1024 * 1024)} Mo)."
        )

    nom = filename.lower()
    if nom.endswith(".pdf"):
        texte = _texte_pdf(data)
    elif nom.endswith(".docx"):
        texte = _texte_ooxml(data, "word/document.xml", frozenset({"p"}))
    elif nom.endswith(".odt"):
        # `h` : un titre ODT est un paragraphe d'un autre nom, et le coller au
        # texte qui suit ferait un mot inexistant.
        texte = _texte_ooxml(data, "content.xml", frozenset({"p", "h"}))
    elif nom.endswith((".txt", ".md", ".markdown")):
        texte = _texte_brut(data)
    elif nom.endswith(".doc"):
        # Le .doc binaire d'avant 2007 n'est pas une archive : le lire
        # demanderait une dependance lourde pour un format que tout
        # traitement de texte sait reenregistrer.
        raise DocumentError(
            "L'ancien format .doc n'est pas lu. Enregistrez le document en "
            ".docx ou en PDF, puis redéposez-le."
        )
    else:
        raise DocumentError(f"Format non reconnu. Formats acceptés : {', '.join(EXTENSIONS)}.")

    if len(texte) > MAX_CHARS:
        raise DocumentError(
            f"Le texte extrait fait {len(texte)} caractères, au-delà de la "
            f"limite de {MAX_CHARS}. Déposez le chapitre concerné plutôt que "
            "l'ouvrage entier."
        )
    return texte
