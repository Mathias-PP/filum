"""Ce qu'on emporte d'une fiche quand on l'exporte.

Une fiche Philum porte plus qu'une bibliographie : des extraits verbatim, des
archives, des verdicts de retractation et d'acces ouvert, les annotations du
createur. Jusqu'ici l'export decidait seul de ce qu'il en gardait, et le meme
fichier servait deux besoins opposes — coller une liste de references en fin
d'article, ou emporter la fiche entiere pour la relire ailleurs.

Le perimetre rend ce choix explicite. `?include=` vide donne la bibliographie
nue ; absent, il donne tout. Entre les deux, chacun compose.

Deux limites assumees :

- **Les references ne sont pas optionnelles.** Une fiche sans ses sources
  n'exporte rien : le perimetre choisit ce qu'on ajoute autour d'elles.
- **Les formats bibliographiques l'ignorent.** BibTeX, RIS, CSL-JSON et les six
  styles de citation obeissent a des conventions fermees ; y glisser un extrait
  ou un verdict produirait un fichier que Zotero refuserait. Le perimetre ne
  mord que sur les formats qui decrivent la fiche : JSON, Philum-JSON, Markdown,
  DOCX.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Cle -> ce qu'elle emporte, tel qu'affiche a l'utilisateur.
SECTIONS: dict[str, str] = {
    "annotations": "Les notes du créateur sur chaque source",
    "excerpts": "Les extraits cités verbatim",
    "archives": "Les captures d'archive (Wayback Machine)",
    "reliability": "Rétractations et accès ouvert",
}


@dataclass(frozen=True)
class ExportScope:
    annotations: bool = True
    excerpts: bool = True
    archives: bool = True
    reliability: bool = True

    @property
    def references_only(self) -> bool:
        return not any((self.annotations, self.excerpts, self.archives, self.reliability))


#: Le perimetre par defaut : tout. Un export sans parametre reste un export
#: complet, sinon un lien deja en circulation se mettrait a rendre moins.
FULL = ExportScope()


def parse_scope(include: str | None) -> ExportScope:
    """`?include=excerpts,archives` -> un perimetre. `None` -> tout.

    `include=` vide n'est pas `None` : c'est le choix explicite de n'emporter
    que les references. Les cles inconnues sont refusees plutot qu'ignorees —
    une faute de frappe qui retire silencieusement une section donnerait un
    export incomplet dont personne ne verrait qu'il l'est.
    """
    if include is None:
        return FULL
    demandees = {p.strip() for p in include.split(",") if p.strip()}
    inconnues = demandees - set(SECTIONS)
    if inconnues:
        raise ValueError(
            f"Section(s) inconnue(s) : {', '.join(sorted(inconnues))}. "
            f"Disponibles : {', '.join(sorted(SECTIONS))}"
        )
    return ExportScope(**{cle: cle in demandees for cle in SECTIONS})
