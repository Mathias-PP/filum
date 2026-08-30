"""Retire d'un texte tiers les caracteres que le modele lit et que nul ne voit.

Un texte recupere sur le web ou depose par un tiers peut porter des points de
code qui ne rendent rien a l'ecran mais qui entrent tels quels dans le contexte
du modele. L'humain qui relit et l'agent qui execute ne lisent alors pas la meme
chose, ce qui est exactement la condition d'une injection par document. Chez
Philum le cas est direct : `fetch_url` verse le texte d'une page arbitraire dans
le contexte.

Le predicat est expose separement du nettoyage : tout appelant qui voudrait
signaler plutot que retirer doit partager la meme definition, sinon les deux
couches divergent et chacune laisse passer ce que l'autre signale.

Le cout du retrait est assume et il est faible. Perdre U+200D casse les sequences
emoji composees, perdre les selecteurs de variation retire l'indice de
presentation emoji contre texte. Sur de la prose citee, aucun des deux ne porte
de sens.

Inspire de `book_to_skill/sanitize.py` (audit `agent/audit/10-externes/`), sans
sa redondance : la source y declare deux fois les controles d'annotation et deux
fois la plage des formats obsoletes.
"""

from __future__ import annotations

# Espaceurs de largeur nulle et joncteurs. Ne rendent rien, donc le texte place
# entre eux est invisible a la lecture et lisible par le modele.
_LARGEUR_NULLE = frozenset(
    {
        0x00AD,  # SOFT HYPHEN, invisible sauf en fin de ligne
        0x034F,  # COMBINING GRAPHEME JOINER, aucun effet de rendu
        0x061C,  # ARABIC LETTER MARK
        0x180E,  # MONGOLIAN VOWEL SEPARATOR
        0x200B,  # ZERO WIDTH SPACE
        0x200C,  # ZERO WIDTH NON-JOINER
        0x200D,  # ZERO WIDTH JOINER
        0x2060,  # WORD JOINER
        0x2061,  # FUNCTION APPLICATION
        0x2062,  # INVISIBLE TIMES
        0x2063,  # INVISIBLE SEPARATOR
        0x2064,  # INVISIBLE PLUS
        0xFEFF,  # ZERO WIDTH NO-BREAK SPACE, BOM ailleurs qu'en tete
    }
)

# Controles bidirectionnels, la classe Trojan Source (CVE-2021-42574). Ils ne
# changent pas la suite de caracteres que le modele lit, ils changent l'ordre que
# l'humain voit : une ligne peut s'afficher comme une phrase anodine pendant que
# le modele en consomme une autre.
#
# Les ecritures droite a gauche ne sont pas touchees : l'algorithme bidi d'Unicode
# derive la direction des caracteres eux-memes, l'arabe et l'hebreu se rendent
# correctement sans aucun de ces controles. Seuls les enrobages, surcharges et
# isolats explicites tombent, et de la prose courante n'en a jamais besoin.
_BIDIRECTIONNELS = frozenset(
    {
        0x200E,  # LEFT-TO-RIGHT MARK
        0x200F,  # RIGHT-TO-LEFT MARK
        0x202A,  # LEFT-TO-RIGHT EMBEDDING
        0x202B,  # RIGHT-TO-LEFT EMBEDDING
        0x202C,  # POP DIRECTIONAL FORMATTING
        0x202D,  # LEFT-TO-RIGHT OVERRIDE
        0x202E,  # RIGHT-TO-LEFT OVERRIDE
        0x2066,  # LEFT-TO-RIGHT ISOLATE
        0x2067,  # RIGHT-TO-LEFT ISOLATE
        0x2068,  # FIRST STRONG ISOLATE
        0x2069,  # POP DIRECTIONAL ISOLATE
    }
)

# Lettres de largeur nulle. Ce ne sont pas des controles de format, donc un filtre
# par categorie Unicode les manque ; et ce ne sont pas des espaces, donc la
# normalisation des blancs les conserve.
_REMPLISSEURS_HANGUL = frozenset({0x115F, 0x1160, 0x3164, 0xFFA0})

# Controles d'annotation interlineaire. Un moteur de rendu conforme masque ce qui
# est place entre l'ancre et le terminateur : du texte que l'humain ne voit
# jamais, lu en entier par le modele.
_ANNOTATION = frozenset({0xFFF9, 0xFFFA, 0xFFFB})

_PONCTUELS = _LARGEUR_NULLE | _BIDIRECTIONNELS | _REMPLISSEURS_HANGUL | _ANNOTATION

# Plages entieres. Le bloc de balises et les selecteurs de variation portent
# chacun une charge arbitraire : une suite de selecteurs placee apres n'importe
# quel caractere encode 256 valeurs par position en ne rendant rien du tout, et
# ce sont des marques combinantes plutot que des controles de format, donc un
# filtre sur la categorie Cf les manque entierement.
_PLAGES = (
    (0x206A, 0x206F),  # formats obsoletes : symmetric swapping, digit shapes
    (0xFE00, 0xFE0F),  # selecteurs de variation 1 a 16
    (0x1D173, 0x1D17A),  # ligatures et phrases musicales
    (0xE0000, 0xE007F),  # bloc de balises, une charge ASCII entiere
    (0xE0100, 0xE01EF),  # selecteurs de variation 17 a 256
)


def est_invisible(point_de_code: int) -> bool:
    """Vrai si le point de code ne rend rien et doit etre retire."""
    if point_de_code in _PONCTUELS:
        return True
    return any(bas <= point_de_code <= haut for bas, haut in _PLAGES)


def assainir(texte: str) -> tuple[str, int]:
    """Rend le texte sans ses caracteres invisibles, et combien ont ete retires.

    Le texte intact ressort tel quel : le cas courant ne paie pas de recopie.
    """
    retires = sum(1 for caractere in texte if est_invisible(ord(caractere)))
    if not retires:
        return texte, 0
    return "".join(c for c in texte if not est_invisible(ord(c))), retires
