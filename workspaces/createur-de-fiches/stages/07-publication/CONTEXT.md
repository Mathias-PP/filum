# 07-publication

## Scope

Publier la fiche et vérifier post-publish que le rendu public, l'export markdown et le feed la portent correctement.

## Inputs

| Source | File | Section | Why |
|---|---|---|---|
| Verdict de relecture | `../06-relecture/output/<slug>-verdict.md` | Frontmatter `go` | DOIT être `yes`, sinon refuser |
| Preuve d'existence | `../01-brief/output/<slug>-card.json` | Champ `slug` | Cible de `publish_card` |
| Signature `publish_card` | `../../shared/philum-mcp.md` | Ligne `publish_card` | Appel strict |

## Process

1. Vérifier `<slug>-verdict.md` : si `go: no`, s'arrêter et pointer l'étape défaillante.
2. Appeler `mcp__philum__get_card(creator=<username>, slug=<slug>)` : confirmer que la fiche existe et porte les bons champs.
3. Appeler `mcp__philum__publish_card(slug)`.
4. **Vérification post-publish** :
   - Ouvrir `https://filum-eight.vercel.app/@<creator>/<slug>` : la fiche se charge.
   - Ouvrir `https://philum-api.duckdns.org/api/v1/@<creator>/<slug>/export?format=markdown` : titre, sources, extraits, connexions y sont.
   - Vérifier que `/api/v1/feed` porte une entrée `card_published` récente.

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Rapport de publication | `output/<slug>-publication.md` | Markdown avec frontmatter (`published_at`, `public_url`, `export_check`, `feed_check`) |

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 3 | Timestamp publication + URL publique | Ouvrir la fiche, valider le rendu |
| 4 | Résultat des trois vérifications post-publish | Signer le rapport ou signaler un incident |

## Audit

| Check | Pass Condition |
|---|---|
| Verdict autorise | `<slug>-verdict.md` a `go: yes` en frontmatter |
| Fiche publique accessible | `curl -sI` sur `https://filum-eight.vercel.app/@<creator>/<slug>` retourne 200 |
| Export markdown fonctionnel | L'export markdown contient le titre, au moins une source et au moins un extrait |
| Feed à jour | Une entrée `card_published` pour ce `slug` figure dans `/api/v1/feed` dans les 60 secondes qui suivent |
