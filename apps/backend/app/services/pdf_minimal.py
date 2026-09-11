"""Un ecrivain PDF reduit a ce qu'une bibliographie demande.

Pourquoi a la main plutot qu'une bibliotheque : `export.py` produit deja le
DOCX et le XLSX avec `zipfile` et du XML minimal, sans dependance, parce que la
VM qui sert Philum est une e2-micro d'un gigaoctet. Les candidats PDF purs
Python n'auraient rien reduit du travail reel : ils savent tracer du texte,
mais l'ecriture d'un glyphe hors Latin-1 leur demande, a eux aussi, d'embarquer
une police TrueType dans le depot. Le cout etait donc le meme, moins la
maitrise.

Ce module ne sait faire que quatre choses, et c'est deliberement tout : poser
une ligne de texte dans une des trois Helvetica standard, couper un paragraphe
a la largeur utile, rendre une zone cliquable, numeroter les pages. Aucune
image, aucun tableau, aucune couleur de fond.

**La limite qu'il ne faut pas taire.** Les polices standard d'un PDF n'ont que
256 positions, ici WinAnsi (CP1252) : le francais et l'anglais passent en
entier, une lettre grecque ou un ideogramme non. Le module ne les remplace pas
en silence. `encoder()` rend un drapeau avec les octets, et l'appelant est tenu
d'en faire quelque chose de visible : une citation verbatim amputee sans le
dire serait une citation faussee, et c'est exactement ce que Philum existe pour
empecher.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: A4 en points typographiques, l'unite native du PDF.
LARGEUR_PAGE = 595.28
HAUTEUR_PAGE = 841.89
MARGE = 56.0
#: Plancher du texte courant. Le pied de page vit en dessous.
BAS_TEXTE = 72.0
BASE_PIED = 42.0

REGULIERE = "F1"
GRASSE = "F2"
ITALIQUE = "F3"

_POLICES = {
    REGULIERE: "Helvetica",
    GRASSE: "Helvetica-Bold",
    ITALIQUE: "Helvetica-Oblique",
}

#: Largeurs Helvetica en millièmes de cadratin, telles que les fixe le fichier
#: de metriques Adobe. Elles ne servent qu'a decider ou couper une ligne : une
#: erreur d'un millieme se verrait en fin de ligne, pas ailleurs.
_LARGEURS: dict[str, int] = {
    " ": 278, "!": 278, '"': 355, "#": 556, "$": 556, "%": 889, "&": 667,
    "'": 191, "(": 333, ")": 333, "*": 389, "+": 584, ",": 278, "-": 333,
    ".": 278, "/": 278, ":": 278, ";": 278, "<": 584, "=": 584, ">": 584,
    "?": 556, "@": 1015, "[": 278, "\\": 278, "]": 278, "^": 469, "_": 556,
    "`": 333, "{": 334, "|": 260, "}": 334, "~": 584,
    "A": 667, "B": 667, "C": 722, "D": 722, "E": 667, "F": 611, "G": 778,
    "H": 722, "I": 278, "J": 500, "K": 667, "L": 556, "M": 833, "N": 722,
    "O": 778, "P": 667, "Q": 778, "R": 722, "S": 667, "T": 611, "U": 722,
    "V": 667, "W": 944, "X": 667, "Y": 667, "Z": 611,
    "a": 556, "b": 556, "c": 500, "d": 556, "e": 556, "f": 278, "g": 556,
    "h": 556, "i": 222, "j": 222, "k": 500, "l": 222, "m": 833, "n": 556,
    "o": 556, "p": 556, "q": 556, "r": 333, "s": 500, "t": 278, "u": 556,
    "v": 500, "w": 722, "x": 500, "y": 500, "z": 500,
}  # fmt: skip

#: Les chiffres partagent tous la meme chasse, ce qui aligne les colonnes.
for _c in "0123456789":
    _LARGEURS[_c] = 556

#: Une lettre accentuee a la chasse de sa lettre nue, et le reste du repertoire
#: Latin-1 ne s'en ecarte guere. 556 est la valeur mediane : s'en servir comme
#: repli fait une coupe legerement imprecise, jamais une coupe absurde.
_LARGEUR_INCONNUE = 556

#: Helvetica-Bold est plus large que Helvetica dans des proportions qui varient
#: selon le glyphe. Un facteur unique suffit ici : le gras ne sert qu'a des
#: titres courts, ou l'erreur cumulee reste inferieure au mot.
_FACTEUR_GRAS = 1.07


def largeur(texte: str, taille: float, police: str = REGULIERE) -> float:
    """Largeur d'un texte rendu, en points."""
    total = sum(_LARGEURS.get(c, _LARGEUR_INCONNUE) for c in texte)
    points = total * taille / 1000.0
    return points * _FACTEUR_GRAS if police == GRASSE else points


#: Ce qui s'affiche a la place d'un glyphe que WinAnsi ne sait pas ecrire. Le
#: point d'interrogation d'`errors="replace"` serait pire que rien : il ne se
#: distingue pas d'un point d'interrogation voulu par l'auteur.
SUBSTITUT = "¤"


def encoder(texte: str) -> tuple[bytes, bool]:
    """Vers WinAnsi, en signalant ce qui n'a pas pu s'ecrire.

    Le drapeau rendu vaut « des caracteres ont ete perdus ». Il n'est pas
    decoratif : l'appelant doit le remonter au lecteur, faute de quoi le
    document afficherait un texte que la source ne porte pas.
    """
    try:
        return texte.encode("cp1252"), False
    except UnicodeEncodeError:
        pass
    octets = bytearray()
    for caractere in texte:
        try:
            octets += caractere.encode("cp1252")
        except UnicodeEncodeError:
            octets += SUBSTITUT.encode("cp1252")
    return bytes(octets), True


def couper(texte: str, taille: float, police: str, largeur_max: float) -> list[str]:
    """Coupe un paragraphe en lignes qui tiennent dans `largeur_max`.

    Coupe aux espaces, et a l'interieur d'un mot quand le mot seul deborde :
    une URL de deux cents caracteres sortirait sinon de la page au lieu de
    passer a la ligne.
    """
    mots = texte.split()
    if not mots:
        return [""]
    lignes: list[str] = []
    courante = ""
    for mot in mots:
        essai = f"{courante} {mot}" if courante else mot
        if largeur(essai, taille, police) <= largeur_max:
            courante = essai
            continue
        if courante:
            lignes.append(courante)
            courante = ""
        while largeur(mot, taille, police) > largeur_max:
            pris = 1
            while pris < len(mot) and largeur(mot[: pris + 1], taille, police) <= largeur_max:
                pris += 1
            lignes.append(mot[:pris])
            mot = mot[pris:]
        courante = mot
    if courante:
        lignes.append(courante)
    return lignes


@dataclass
class _Ligne:
    texte: str
    x: float
    y: float
    police: str
    taille: float
    lien: str | None = None


@dataclass
class _Page:
    lignes: list[_Ligne] = field(default_factory=list)


def _echapper(octets: bytes) -> bytes:
    """Met des octets dans une chaine PDF litterale.

    Tout ce qui n'est pas ASCII imprimable part en octal : le fichier reste
    lisible dans un editeur de texte, ce qui rend une anomalie diagnosticable
    sans outil.
    """
    sortie = bytearray()
    for b in octets:
        if b in (0x28, 0x29, 0x5C):  # ( ) \
            sortie += b"\\" + bytes([b])
        elif 32 <= b <= 126:
            sortie.append(b)
        else:
            sortie += f"\\{b:03o}".encode("ascii")
    return bytes(sortie)


class Document:
    """Un PDF en construction, page courante et curseur vertical compris."""

    def __init__(self, titre: str, pied: str) -> None:
        self._titre = titre
        self._pied = pied
        self._pages: list[_Page] = []
        self._y = 0.0
        self.caracteres_perdus = False
        self._nouvelle_page()

    @property
    def largeur_utile(self) -> float:
        return LARGEUR_PAGE - 2 * MARGE

    def _nouvelle_page(self) -> None:
        self._pages.append(_Page())
        self._y = HAUTEUR_PAGE - MARGE

    def espace(self, points: float) -> None:
        """Avance le curseur sans rien ecrire, sauf en tete de page.

        Une page qui commencerait par un blanc trahirait la coupure : le saut
        appartient a la fin du bloc precedent, pas au debut du suivant.
        """
        if self._y < HAUTEUR_PAGE - MARGE:
            self._y -= points

    def besoin(self, points: float) -> None:
        """Passe a la page suivante si le bloc a venir n'y tient pas.

        Sert a garder un titre avec au moins une ligne de ce qu'il annonce :
        un intitule seul en bas de page ne dit plus de quoi il est le titre.
        """
        if self._y - points < BAS_TEXTE:
            self._nouvelle_page()

    def paragraphe(
        self,
        texte: str,
        *,
        taille: float = 9.5,
        police: str = REGULIERE,
        indent: float = 0.0,
        interligne: float = 1.32,
        lien: str | None = None,
    ) -> None:
        if not texte:
            return
        hauteur = taille * interligne
        disponible = self.largeur_utile - indent
        # Releve a la pose, pas au rendu : l'appelant doit pouvoir mentionner
        # les caracteres perdus avant que le document soit ferme. `split()`
        # sans argument absorbe au passage les espaces insecables, dont
        # l'etroit que WinAnsi ne porte pas.
        aplati = " ".join(texte.split())
        _, perdu = encoder(aplati)
        self.caracteres_perdus = self.caracteres_perdus or perdu
        for ligne in couper(aplati, taille, police, disponible):
            if self._y - hauteur < BAS_TEXTE:
                self._nouvelle_page()
            self._y -= hauteur
            self._pages[-1].lignes.append(
                _Ligne(ligne, MARGE + indent, self._y, police, taille, lien)
            )

    def rendu(self) -> bytes:
        objets: list[bytes] = []

        def ajouter(corps: bytes) -> int:
            objets.append(corps)
            return len(objets)

        catalogue = ajouter(b"")  # 1, rempli plus bas
        pages = ajouter(b"")  # 2
        polices = {
            cle: ajouter(
                f"<< /Type /Font /Subtype /Type1 /BaseFont /{nom} "
                f"/Encoding /WinAnsiEncoding >>".encode("ascii")
            )
            for cle, nom in _POLICES.items()
        }
        ressources = (
            "<< /Font << " + " ".join(f"/{c} {n} 0 R" for c, n in polices.items()) + " >> >>"
        )

        refs_pages: list[int] = []
        total = len(self._pages)
        for numero, page in enumerate(self._pages, start=1):
            flux, annotations = self._flux(page, numero, total)
            objet_flux = ajouter(
                b"<< /Length "
                + str(len(flux)).encode("ascii")
                + b" >>\nstream\n"
                + flux
                + b"\nendstream"
            )
            corps = (
                f"<< /Type /Page /Parent {pages} 0 R "
                f"/MediaBox [0 0 {LARGEUR_PAGE:.2f} {HAUTEUR_PAGE:.2f}] "
                f"/Resources {ressources} /Contents {objet_flux} 0 R"
            )
            if annotations:
                corps += " /Annots [" + " ".join(annotations) + "]"
            corps += " >>"
            refs_pages.append(ajouter(corps.encode("latin-1")))

        objets[pages - 1] = (
            f"<< /Type /Pages /Count {len(refs_pages)} "
            f"/Kids [{' '.join(f'{r} 0 R' for r in refs_pages)}] >>"
        ).encode("ascii")
        titre, _ = encoder(self._titre)
        info = ajouter(b"<< /Title (" + _echapper(titre) + b") /Producer (Philum) >>")
        objets[catalogue - 1] = f"<< /Type /Catalog /Pages {pages} 0 R >>".encode("ascii")

        return self._assembler(objets, catalogue, info)

    def _flux(self, page: _Page, numero: int, total: int) -> tuple[bytes, list[str]]:
        morceaux: list[bytes] = []
        annotations: list[str] = []
        for ligne in page.lignes:
            octets, _ = encoder(ligne.texte)
            morceaux.append(
                f"BT /{ligne.police} {ligne.taille:.2f} Tf "
                f"1 0 0 1 {ligne.x:.2f} {ligne.y:.2f} Tm ".encode("ascii")
                + b"("
                + _echapper(octets)
                + b") Tj ET"
            )
            if ligne.lien:
                large = largeur(ligne.texte, ligne.taille, ligne.police)
                cible, _ = encoder(ligne.lien)
                annotations.append(
                    "<< /Type /Annot /Subtype /Link /Border [0 0 0] "
                    f"/Rect [{ligne.x:.2f} {ligne.y - 2:.2f} "
                    f"{ligne.x + large:.2f} {ligne.y + ligne.taille:.2f}] "
                    "/A << /S /URI /URI (" + _echapper(cible).decode("latin-1") + ") >> >>"
                )
        pied = f"{self._pied}    {numero} / {total}"
        octets, _ = encoder(pied)
        morceaux.append(
            f"BT /{ITALIQUE} 7.50 Tf 0.45 0.45 0.45 rg "
            f"1 0 0 1 {MARGE:.2f} {BASE_PIED:.2f} Tm ".encode("ascii")
            + b"("
            + _echapper(octets)
            + b") Tj ET"
        )
        return b"\n".join(morceaux), annotations

    @staticmethod
    def _assembler(objets: list[bytes], catalogue: int, info: int) -> bytes:
        sortie = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        decalages: list[int] = []
        for numero, corps in enumerate(objets, start=1):
            decalages.append(len(sortie))
            sortie += f"{numero} 0 obj\n".encode("ascii") + corps + b"\nendobj\n"
        debut_xref = len(sortie)
        sortie += f"xref\n0 {len(objets) + 1}\n".encode("ascii")
        sortie += b"0000000000 65535 f \n"
        for decalage in decalages:
            sortie += f"{decalage:010d} 00000 n \n".encode("ascii")
        sortie += (
            f"trailer\n<< /Size {len(objets) + 1} /Root {catalogue} 0 R /Info {info} 0 R >>\n"
            f"startxref\n{debut_xref}\n%%EOF\n"
        ).encode("ascii")
        return bytes(sortie)
