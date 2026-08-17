"""Garde-fous partages contre les extraits qui trahissent leur source.

Un extrait cite seul doit rester intelligible. Trois pieges le compromettent :

- **Trop court sans autonomie** : « Cela ameliore la memoire » cite seul ne dit
  pas ce que « cela » nomme, et le lecteur pousse au contresens y voit ce
  qu'il veut.
- **Trop court avec un pronom demonstratif en tete** : meme piege, un
  « Ces travaux montrent que… » sans nommer les travaux devient une
  affirmation orpheline.
- **Sans mise en situation** : un extrait qui *aurait* besoin d'un contexte,
  livre sans lui, se lit comme une citation officielle du document.

Ces regles sont partagees entre l'endpoint /excerpts/suggest (qui filtre les
suggestions LLM avant de les proposer) et le tool MCP add_excerpt (qui refuse
un extrait pose sans garde-fou). Une seule source de verite, meme critere
partout.
"""

from __future__ import annotations

import re

#: Sous ce seuil, un extrait ne se comprend jamais seul quand il commence
#: par un mot referentiel. Au-dessus, la charge lexicale suffit generalement
#: a poser son propre contexte.
LONGUEUR_MIN_AUTONOME_MOTS = 15

#: Mots par lesquels un passage commence quand il pointe hors de lui-meme.
#: Cas vecus : « Cela ameliore la memoire » (quoi ?), « Il reste a valider ce
#: resultat » (lequel ?), « Ces travaux montrent que… » (lesquels ?). En
#: francais et en anglais, les LLM travaillent dans les deux langues.
#: `le|la|les|leur|lui` ne sont PAS dans la liste : ce sont trop souvent des
#: articles definis qui posent leur sujet dans la meme phrase (« La memoire
#: consolide… »). Les inclure produisait des faux positifs qui refusaient des
#: extraits parfaitement autonomes. On garde uniquement les demonstratifs et
#: les pronoms qui, en tete de phrase courte, pointent presque toujours en
#: dehors du passage.
_MARQUEURS_REFERENTS_ABSENTS = re.compile(
    r"^\s*(cela|c'est|ce|cet|cette|ces|ceci|celui|celle|ceux|celles"
    r"|il|elle|ils|elles|on"
    r"|this|that|these|those|it|they|he|she|such|these results?|this study)"
    r"\b",
    re.IGNORECASE,
)


def passage_a_besoin_de_contexte(text: str) -> bool:
    """L'extrait commence-t-il par un mot qui pointe hors du passage ?

    Un extrait court dont la premiere charge semantique est un pronom sans
    referent visible devient un contresens cite seul. Le retour True dit
    « ce passage ne se suffit pas ; il faut soit l'elargir soit poser une
    mise en situation qui nomme le referent en clair ».
    """
    return bool(_MARQUEURS_REFERENTS_ABSENTS.match(text.strip()))
