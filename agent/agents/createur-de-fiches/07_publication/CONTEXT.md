# Étape 7 : Publication

**Reads**
- `runs/<slug>/06_relecture/verdict.md` : DOIT contenir `go: yes` en frontmatter. Sinon, refuser.
- `runs/<slug>/01_brief/card.json` (`card_slug`).

**Does**
1. **Vérification finale** : `mcp__philum__get_card(creator=<username>, slug=<slug>)` pour confirmer que la fiche existe encore et porte les bons champs.
2. **Publication** : `mcp__philum__publish_card(slug)`. Le serveur bascule `status=published`, écrit `published_at`, envoie une entrée au feed public.
3. **Vérification post-publish** :
   - Ouvrir `https://filum-eight.vercel.app/@<creator>/<slug>` dans le navigateur : la fiche doit se charger.
   - Ouvrir un export : `https://philum-api.duckdns.org/api/v1/@<creator>/<slug>/export?format=markdown` : vérifier que titre, sources, extraits, connexions y sont.
   - Vérifier que le feed `/api/v1/feed` porte bien une entrée `card_published` récente pour cette fiche.

**Writes**
- `runs/<slug>/07_publication/publication.md` :

```markdown
---
published_at: 2026-08-18T...Z
public_url: https://filum-eight.vercel.app/@<creator>/<slug>
export_check: ok
feed_check: ok
---

# Publication

- Fiche publique : <URL>
- Vérifications post-publish OK : rendu, export markdown, feed.
```

**Human gate**
L'utilisateur ouvre la fiche publique et signe pour clore le run.

## Après publication

- Une fiche publiée peut être modifiée (nouvelle source, correction d'extrait), les changements sont visibles immédiatement.
- Republier n'ajoute PAS une deuxième entrée au feed : la première mise au public est unique par conception.
- Pour dépublier : `PATCH /api/v1/cards/{id}` avec `status=draft`.
