"""Ce qu'un petit modele peut tenir, et ce qu'on lui retire.

Mesure du 2026-09-13 (`agent/plans/2026-09-13-agent-petits-modeles.md`) :
l'assistant par defaut envoyait environ 70 000 caracteres d'instructions et de
schemas avant la question, 16 789 jetons au premier appel. Sur un modele de
8 milliards de parametres, 79 appels a `add_excerpt` sur 83 ont ete refuses,
et les consignes du debut pesaient peu face aux pages lues.

Un petit modele recoit donc un contexte a sa taille : les regles qui ont
echoue en vrai, dites en quelques lignes, des descriptions d'outils reduites a
leur premiere phrase, et rien d'injecte qu'il n'a pas demande. Le reste du
workspace reste lisible par `fs_read`.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from contextvars import ContextVar

#: Le tour en cours sert-il un petit modele ? Pose par la boucle, lu par les
#: outils dont la taille des resultats doit s'adapter, sans faire passer le
#: profil par chaque signature.
PETIT_MODELE: ContextVar[bool] = ContextVar("petit_modele", default=False)

#: Fenetre de lecture d'une page pour un petit modele. Mesure du 2026-09-13 :
#: 20 000 caracteres en moyenne par `fetch_url`, et les consignes du debut ne
#: pesaient plus rien au troisieme appel. Pour citer, `find_passage` cherche
#: dans la page entiere : le modele n'a pas besoin de tout avoir sous les yeux.
FENETRE_LECTURE_PETIT = 6_000

#: Resultats de recherche web rendus a un petit modele, et longueur de chacun.
#: Mesure : 7 400 a 10 000 caracteres par recherche, pour huit resultats.
RESULTATS_RECHERCHE_PETIT = 5
EXTRAIT_RECHERCHE_PETIT = 300

#: Au-dela, un modele est traite comme grand. Les modeles de 7 a 14 milliards
#: de parametres suivent mal un long contexte d'instructions ; les
#: architectures a experts se nomment en general par leur taille totale.
PARAMETRES_MAX_PETIT = 14.0

_TAILLE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)b(?![a-z0-9])", re.IGNORECASE)

#: Familles connues pour etre petites sans que leur nom porte une taille :
#: toutes les Ministral font 14 milliards de parametres ou moins, et les GLM
#: « flash » de Z.ai (lanes gratuites) n'en activent qu'environ 3 par jeton.
#: Liste fermee plutot que des mots comme « mini » ou « flash » seuls, qui
#: classeraient petits `o4-mini` ou `gemini-2.5-flash`.
_MOTS_PETIT = re.compile(r"ministral|glm-[\d.]+-flash", re.IGNORECASE)


def est_petit_modele(modele: str | None) -> bool:
    """Le nom du modele annonce-t-il un petit modele ?

    Deduit du nom plutot que declare : aucune cle ni aucune lane ne porte
    aujourd'hui la taille de son modele, et les noms la disent souvent
    (`ministral-8b-latest`, `llama-3.1-8b-instant`, `glm-4.7-flash`).
    """
    if not modele:
        return False
    nom = modele.lower()
    if _MOTS_PETIT.search(nom):
        return True
    return any(float(taille) <= PARAMETRES_MAX_PETIT for taille in _TAILLE.findall(nom))


#: Les regles qui ont echoue sur les conversations « arthrose », en quelques
#: lignes. Remplace les huit fichiers `shared/` (42 000 caracteres).
ESSENTIEL = (
    "\n\n---\n## Règles essentielles\n"
    "1. Une source, un fait, un chiffre, une date ou un auteur ne viennent que d'un "
    "outil appelé dans cette conversation, ou du créateur. Sinon, dis ce qui manque.\n"
    "2. Pour citer : `find_passage(source_id, query)`, puis recopie tel quel un des "
    "passages rendus dans `add_excerpt`. Ne reformule jamais un extrait.\n"
    "3. Une position (`stance`) se déclare seulement après un extrait qui la "
    "justifie. Dans le doute, aucune position.\n"
    "4. Une question à documenter avec des sources, en n'importe quelle langue et sous "
    "n'importe quelle forme, se confie au déroulé guidé : `demarrer_fiche_sujet(question)`.\n"
    "5. Cherche aussi ce qui nuance ou contredit, et dis ce que tu as trouvé, même "
    "si c'est rien.\n"
    "6. Pour un verbatim, `find_passage` suffit : ne lis une page entière avec "
    "`fetch_url` que si tu en as besoin.\n"
    "7. Termine par ce qui a été fait, ce qui n'a pas été trouvé, et les limites. "
    "Jamais un plan à la place d'un bilan.\n\n"
    "Les autres règles du workspace se lisent avec `fs_read` si tu en as besoin : "
    "`shared/principes-editoriaux.md`, `shared/garde-fous.md`, "
    "`shared/chercher-la-contradiction.md`.\n"
)

_FIN_DE_PHRASE = re.compile(r"(?<=[.!?])\s")


def description_courte(description: str) -> str:
    """La premiere phrase d'une description d'outil.

    Les valeurs acceptees restent dans le schema (`enum`), et le detail des cas
    limites revient dans le message d'erreur, au moment ou il sert.
    """
    texte = " ".join(description.split())
    return _FIN_DE_PHRASE.split(texte, maxsplit=1)[0]


def chemins_de_contexte(chemins: Sequence[str] | None, petit: bool) -> Sequence[str] | None:
    """Les fichiers du workspace a injecter.

    `None` veut dire tout `shared/` pour `_priming_workspace`. Un petit modele
    garde les fichiers propres a son etape, et perd `shared/`, que `ESSENTIEL`
    resume.
    """
    if not petit:
        return chemins
    return [chemin for chemin in (chemins or []) if not chemin.startswith("shared/")]
