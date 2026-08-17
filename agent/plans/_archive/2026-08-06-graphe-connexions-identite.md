# Graphe, connexions et identité — plan d'implémentation

> **Pour l'agent exécutant :** SOUS-COMPÉTENCE REQUISE — utiliser `superpowers:subagent-driven-development` (recommandé) ou `superpowers:executing-plans` pour dérouler ce plan tâche par tâche. Les étapes utilisent la syntaxe case à cocher (`- [ ]`).
>
> **Destinataire : Claude Sonnet dans Claude Code.** Chaque tâche est autonome : elle donne les chemins exacts, le code complet, les commandes et le résultat attendu. Aucune étape ne suppose la lecture d'une autre.

**But :** rendre le graphe lisible (sens de citation, imbrication, épaisseur, légende), donner aux créateurs un espace de gestion des connexions entre fiches, aligner les fiches sur les options de référencement de leurs sources, et poser par écrit les chantiers d'identité, de profils publics et de garantie d'authenticité.

**Architecture :** le backend encode déjà le sens des citations (`GraphEdge.kind == "is_card"`, `source` = fiche citante, `target` = fiche citée, cf. `apps/backend/app/services/card_graph.py:340-349`) ; c'est le frontend qui perd cette information à l'affichage. Les lots A et B sont donc quasi exclusivement frontend. Le lot C ajoute trois colonnes à `biblio_cards`, le lot D deux colonnes à `sources`, le lot E branche l'interopérabilité issue de l'étude « outils de recherche », le lot F ne produit que de la documentation (ADR et specs), sans code.

**Stack :** SvelteKit (Svelte 5 runes) + Tailwind + TypeScript strict côté frontend ; FastAPI + SQLAlchemy 2.x async + Alembic + Pydantic v2 côté backend ; `pytest` et `vitest` pour les tests ; `uv` et `pnpm` comme gestionnaires.

---

## Règles valables pour toutes les tâches

1. **Français partout** : prose, commentaires, messages de commit, textes d'interface.
2. **Commits conventionnels**, titre ≤ 50 caractères (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`).
3. **Svelte 5** : pas de `{@const}` hors d'un bloc `{#each}` / `{#if}` / `{#await}` / `{#snippet}` — utiliser `$derived`. Jamais de self-assignment (`foo = foo`) : ESLint `no-self-assign` casse la CI ; les proxies `$state` sont réactifs en profondeur.
4. **Pas d'em-dash** (`—`) dans un texte visible du frontend. Voir tâche A3 pour la règle et ses exceptions.
5. **Vérifications avant chaque commit** :
   - backend : `cd apps/backend && uv run ruff check app/ && uv run mypy app/`
   - frontend : `cd apps/frontend && pnpm check && pnpm lint`
6. **Migrations Alembic** : l'identifiant de révision doit tenir en 32 caractères (`alembic_version.version_num` est un `VARCHAR(32)`). Convention : `0XX_courte_description`. Ne jamais redoubler par un `op.create_index` un index déjà créé par `index=True` dans un `create_table`.
7. **Tests sous Windows** : `CI=true uv run pytest tests/unit -q` fonctionne en local depuis la PR #248.
8. **Une branche par lot**, nommée `feat/graphe-sens`, `feat/fiches-referencement`, etc. Ne jamais travailler directement sur `main`.

---

## Sommaire des lots

| Lot | Contenu | Nature | Demandes couvertes |
|-----|---------|--------|--------------------|
| A | Épaisseur des liens, légende repliable, purge des em-dashes | Frontend seul | 8, 4 |
| B | Sens de citation, imbrication des fiches, épinglage, lien Philum dans l'encadré | Frontend + 1 paramètre API | 2, 3, 5 |
| C | Options de référencement des fiches (format, catégorie, type d'auteur) | Migration + API + UI | 10 |
| D | Espace de gestion des connexions entre fiches | Migration + API + UI | 1 |
| E | Interopérabilité issue de l'étude (COinS, Highwire, alertes de citation) | Backend + frontend | conclusions de l'étude |
| F | Preuve d'autorat, profils publics et feed, garantie d'authenticité | Documentation seule | 6, 7, 9 |

Les lots A à D sont séquentiels : B touche les mêmes lignes que A, D suppose C mergé. Le lot E est indépendant. Le lot F peut être fait à tout moment, il ne touche aucun code.

---

# LOT A — Corrections graphiques rapides

Trois corrections indépendantes, sans dépendance backend. Objectif : alléger visuellement le graphe avant d'y ajouter le sens de citation au lot B.

### Tâche A1 : amincir les liens caractérisés

**Constat utilisateur :** « les liens entre les nœuds sont trop épais quand ils sont caractérisés (mention, nuance/contredit, etc.), ce qui alourdit le graphe. »

**Fichiers :**
- Modifier : `apps/frontend/src/lib/components/SourceGraph.svelte:1310-1316`

- [ ] **Étape 1 : lire le bloc actuel**

Ouvrir `apps/frontend/src/lib/components/SourceGraph.svelte` autour de la ligne 1310. Le bloc à modifier est :

```js
      .attr('stroke-width', (d) => {
        if ((d as any).forkHide) return 0;
        if (d.kind === 'sibling') return 0;
        if (d.kind === 'meta') return 2.5;
        if (d.stance) return 2.5;
        return d.kind === 'parent' ? 1 : 1.5;
      })
```

- [ ] **Étape 2 : remplacer par des épaisseurs resserrées**

```js
      .attr('stroke-width', (d) => {
        if ((d as any).forkHide) return 0;
        if (d.kind === 'sibling') return 0;
        // Un rapport déclaré se lit à la couleur du trait, pas à sa masse :
        // 2.5 px empâtait le maillage dès qu'une fiche déclarait ses rapports
        // sur la majorité de ses sources. L'écart avec un lien muet reste
        // perceptible à 1.6 px, sans que le trait devienne un objet.
        if (d.kind === 'meta') return 1.8;
        if (d.stance) return 1.6;
        return d.kind === 'parent' ? 1 : 1.2;
      })
```

- [ ] **Étape 3 : vérifier à l'œil**

```bash
cd apps/frontend && pnpm dev
```

Ouvrir `http://localhost:5173/@mathias-pinault/ca-sert-a-quoi-de-dormir`. Attendu : les traits colorés (vert « appuie », rouge « nuance/contredit », gris « mentionne », bleu « contexte ») restent distinguables d'un trait gris clair non déclaré, mais le maillage respire. Comparer avec la production sur `https://filum-eight.vercel.app` dans un autre onglet.

- [ ] **Étape 4 : lint**

```bash
cd apps/frontend && pnpm check && pnpm lint
```

Attendu : aucune erreur.

- [ ] **Étape 5 : commit**

```bash
git add apps/frontend/src/lib/components/SourceGraph.svelte
git commit -m "fix: amincir les liens caracterises du graphe"
```

---

### Tâche A2 : rendre la légende repliable

**Constat utilisateur :** le bandeau « N fiches Philum reliées… » doit pouvoir être fermé ou réduit.

**Fichiers :**
- Modifier : `apps/frontend/src/lib/components/SourceGraph.svelte:2421-2460` (bloc de légende) et la zone d'état `$state` autour de la ligne 233

**Test :**
- Créer : `apps/frontend/src/lib/components/__tests__/graph-legend.test.ts`

- [ ] **Étape 1 : écrire le test qui échoue**

Créer `apps/frontend/src/lib/components/__tests__/graph-legend.test.ts` :

```ts
import { describe, expect, it } from 'vitest';
import { legendLabel } from '../graph-legend';

describe('legendLabel', () => {
  it('accorde le pluriel au-dela d une fiche', () => {
    expect(legendLabel(2)).toContain('2 fiches Philum reliées');
  });

  it('reste au singulier pour une seule fiche', () => {
    expect(legendLabel(1)).toContain('1 fiche Philum reliée');
  });

  it("n'utilise aucun em-dash", () => {
    expect(legendLabel(3)).not.toContain('—');
  });
});
```

- [ ] **Étape 2 : lancer le test pour le voir échouer**

```bash
cd apps/frontend && pnpm vitest run src/lib/components/__tests__/graph-legend.test.ts
```

Attendu : ÉCHEC, `Failed to resolve import "../graph-legend"`.

- [ ] **Étape 3 : créer le module de libellé**

Créer `apps/frontend/src/lib/components/graph-legend.ts` :

```ts
/**
 * Libellé du bandeau de légende du graphe.
 *
 * Extrait du composant pour être testable seul : le texte a déjà changé
 * trois fois, et une régression de pluriel ou de ponctuation passe
 * inaperçue dans un composant de 2 400 lignes.
 */
export function legendLabel(count: number): string {
  const plural = count > 1;
  const fiches = plural ? 'fiches Philum reliées' : 'fiche Philum reliée';
  return `${count} ${fiches}. Cliquez la pastille « + » pour déplier ses sources, le nœud pour voir sa référence.`;
}
```

- [ ] **Étape 4 : relancer le test**

```bash
cd apps/frontend && pnpm vitest run src/lib/components/__tests__/graph-legend.test.ts
```

Attendu : 3 tests passent.

- [ ] **Étape 5 : ajouter l'état de repli dans le composant**

Dans `apps/frontend/src/lib/components/SourceGraph.svelte`, à côté de la déclaration `let neighborCards = $state(...)` (ligne 233 environ), ajouter :

```ts
  // La légende explique un geste qu'on n'apprend qu'une fois. Elle doit donc
  // pouvoir disparaître, et rester disparue le temps de la session : la
  // rouvrir à chaque remontage la transformerait en bandeau publicitaire.
  let legendOpen = $state(true);
```

Et dans le bloc `<script>` du même fichier, importer le libellé (à ajouter aux imports existants en haut de fichier) :

```ts
  import { legendLabel } from './graph-legend';
```

- [ ] **Étape 6 : remplacer le bandeau**

Remplacer le paragraphe des lignes 2450-2457 :

```svelte
        <p class="rounded-md border border-indigo-200 bg-indigo-50/95 px-2.5 py-1.5 text-indigo-900 backdrop-blur-sm">
          {neighborCards.size} fiche{neighborCards.size > 1 ? 's' : ''} Philum reliée{neighborCards.size > 1 ? 's' : ''} — cliquez la pastille « + » pour déplier ses sources, le nœud pour voir sa référence.
        </p>
```

par :

```svelte
        {#if legendOpen}
          <div
            class="flex items-start gap-2 rounded-md border border-indigo-200 bg-indigo-50/95 px-2.5 py-1.5 text-indigo-900 backdrop-blur-sm"
          >
            <p class="flex-1">{legendLabel(neighborCards.size)}</p>
            <button
              type="button"
              class="shrink-0 rounded px-1 text-indigo-700 hover:bg-indigo-100 hover:text-indigo-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-500"
              aria-label="Masquer l'aide du graphe"
              onclick={() => (legendOpen = false)}
            >
              ✕
            </button>
          </div>
        {:else}
          <button
            type="button"
            class="rounded-md border border-indigo-200 bg-indigo-50/95 px-2.5 py-1.5 text-indigo-900 backdrop-blur-sm hover:bg-indigo-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-500"
            onclick={() => (legendOpen = true)}
          >
            ? Aide du graphe
          </button>
        {/if}
```

- [ ] **Étape 7 : vérifier dans le navigateur**

```bash
cd apps/frontend && pnpm dev
```

Sur une fiche ayant au moins une fiche voisine : le bandeau s'affiche, le bouton `✕` le réduit à « ? Aide du graphe », un clic sur celui-ci le rouvre. Vérifier au clavier : `Tab` atteint les deux boutons, `Entrée` les active, l'anneau de focus est visible.

- [ ] **Étape 8 : lint et tests**

```bash
cd apps/frontend && pnpm check && pnpm lint && pnpm vitest run
```

- [ ] **Étape 9 : commit**

```bash
git add apps/frontend/src/lib/components/SourceGraph.svelte apps/frontend/src/lib/components/graph-legend.ts apps/frontend/src/lib/components/__tests__/graph-legend.test.ts
git commit -m "feat: legende du graphe repliable"
```

---

### Tâche A3 : bannir les em-dashes des textes visibles

**Constat utilisateur :** « ce genre de tirets crie "j'ai été écrit par une IA", ils sont donc à bannir sauf exceptions. Supprime et remplace tous les em-dashes visibles dans le texte du front. »

**Périmètre :** 27 fichiers `.svelte` contiennent au moins un `—` sous `apps/frontend/src/routes` et `apps/frontend/src/lib`.

**Règle de remplacement, dans cet ordre de préférence :**

| Usage de l'em-dash | Remplacement |
|---|---|
| Incise en milieu de phrase (« X — précision — Y ») | Virgules, ou parenthèses si l'incise est longue |
| Charnière explicative en fin de phrase (« X — c'est-à-dire Y ») | Point-virgule, ou deux-points, ou une phrase séparée |
| Juxtaposition d'un libellé et d'une valeur (« Titre — Auteur ») | Deux-points, ou un séparateur `·` |
| Liste d'apposition (« A — B — C ») | Virgules |

**Exceptions légitimes, à conserver :**
1. `<p>—</p>` ou `{value ?? '—'}` comme **marque de valeur absente** dans un tableau ou une fiche (par exemple `apps/frontend/src/routes/@[creator]/[card]/+page.svelte:463` et `:479`). Ce n'est pas de la prose, c'est un glyphe de vide.
2. Les commentaires de code (`//` et `<!-- -->`) : invisibles pour l'utilisateur, hors périmètre.
3. `apps/frontend/src/routes/sandbox/**` : pages de travail internes, non publiques.

**Fichiers :**
- Modifier : les 27 fichiers listés par la commande de l'étape 1

- [ ] **Étape 1 : établir la liste de travail**

```bash
cd apps/frontend/src && grep -rn "—" --include=*.svelte routes lib > /tmp/emdash.txt && wc -l /tmp/emdash.txt
```

Sous PowerShell :

```powershell
Select-String -Path (Get-ChildItem -Recurse -Include *.svelte apps/frontend/src/routes,apps/frontend/src/lib) -Pattern "—" | Out-File -Encoding utf8 emdash.txt
```

Attendu : une liste `chemin:ligne:contenu`. Écarter de la liste les lignes commençant par `//`, `/*`, `*`, `<!--`, celles sous `routes/sandbox/`, et celles où le `—` est seul entre balises ou après `??`.

- [ ] **Étape 2 : traiter fichier par fichier**

Pour chaque fichier restant, appliquer la table de remplacement ci-dessus. **Ne pas automatiser par un `sed` global** : le remplacement dépend du rôle grammatical, et un tiret demi-cadratin posé au hasard (`–`) ou un tiret court (`-`) reproduirait le problème. Relire chaque phrase modifiée à voix haute : si elle sonne bancale, refaire.

Exemples de transformations attendues :

```
« Sources horodatées — vérifiables par n'importe qui »
→ « Sources horodatées, vérifiables par n'importe qui »

« Philum — la couche de citation du web »
→ « Philum : la couche de citation du web »

« Chaque source est archivée — Wayback Machine, Perma.cc — au moment de la publication »
→ « Chaque source est archivée (Wayback Machine, Perma.cc) au moment de la publication »
```

Traiter dans cet ordre pour pouvoir committer par paquets cohérents :
1. `routes/+page.svelte`, `routes/about/`, `routes/features/`, `routes/roadmap/`, `routes/developers/`, `routes/security/`, `routes/privacy/` (pages vitrine)
2. `routes/dashboard/**` (parcours créateur)
3. `routes/@[creator]/[card]/+page.svelte`, `routes/discover/` (pages publiques de fiche)
4. `lib/components/**` (composants partagés)

- [ ] **Étape 3 : vérifier qu'il ne reste que les exceptions**

```bash
cd apps/frontend/src && grep -rn "—" --include=*.svelte routes lib | grep -v "sandbox/" | grep -v "^\s*//" | grep -v "<!--"
```

Attendu : uniquement des lignes de type `{... ?? '—'}` ou `<p>—</p>` (marques de valeur absente) et des commentaires.

- [ ] **Étape 4 : ajouter un garde-fou de lint**

Créer `apps/frontend/scripts/check-emdash.mjs` :

```js
/**
 * Refuse les em-dashes dans le texte visible du frontend.
 *
 * Le tiret cadratin est devenu un marqueur stylistique de texte généré. La
 * seule exception tolérée est le glyphe de valeur absente, isolé, qui n'est
 * pas de la prose.
 */
import { readFileSync } from 'node:fs';
import { globSync } from 'node:fs';

const files = globSync('src/{routes,lib}/**/*.svelte', { exclude: (p) => p.includes('sandbox') });
const offenders = [];

for (const file of files) {
  const lines = readFileSync(file, 'utf8').split('\n');
  lines.forEach((line, i) => {
    if (!line.includes('—')) return;
    const trimmed = line.trim();
    if (trimmed.startsWith('//') || trimmed.startsWith('*') || trimmed.startsWith('<!--')) return;
    // Glyphe de valeur absente : `—` isolé entre balises ou après `??`.
    if (/(\?\?\s*'—')|(>\s*—\s*<)/.test(line)) return;
    offenders.push(`${file}:${i + 1}: ${trimmed}`);
  });
}

if (offenders.length > 0) {
  console.error('Em-dashes interdits dans le texte visible :\n' + offenders.join('\n'));
  process.exit(1);
}
console.log('Aucun em-dash dans le texte visible.');
```

Ajouter le script à `apps/frontend/package.json`, dans `"scripts"` :

```json
    "check:emdash": "node scripts/check-emdash.mjs",
```

- [ ] **Étape 5 : lancer le garde-fou**

```bash
cd apps/frontend && node scripts/check-emdash.mjs
```

Attendu : `Aucun em-dash dans le texte visible.` Si le script signale des lignes, les corriger, ou élargir l'exception si le cas est légitime (et documenter pourquoi dans le commentaire du script).

- [ ] **Étape 6 : lint et build**

```bash
cd apps/frontend && pnpm check && pnpm lint && pnpm build
```

- [ ] **Étape 7 : commit**

```bash
git add apps/frontend/src apps/frontend/scripts/check-emdash.mjs apps/frontend/package.json
git commit -m "refactor: bannir les em-dashes du texte visible"
```

---

# LOT B — Sens de citation, imbrication, épinglage

C'est le lot le plus important. Il répond à trois demandes liées.

**Diagnostic préalable, à ne pas refaire :** le backend encode déjà le sens. Dans `apps/backend/app/services/card_graph.py:230-232`, `_record_card_edge(src_id, dst_id, stance)` est appelé avec `(citing_id, cited_id)` ligne 257 pour les citations entrantes et avec `(card_id, target_card)` ligne 289 pour les sortantes. L'arête `is_card` produite ligne 342-349 porte donc `source` = fiche **citante** et `target` = fiche **citée**. Le frontend conserve cet ordre dans `cardLinks` (`SourceGraph.svelte:605-611`) mais l'affiche comme un trait symétrique : c'est là, et là seulement, que le sens est perdu.

**Décision de conception (l'utilisateur a délégué le choix) :** implémenter les deux mécanismes, mais dans cet ordre de priorité.
1. **Toujours** dessiner une flèche sur les arêtes fiche → fiche. C'est peu coûteux, non ambigu, et ça ne surcharge pas : une pointe de 6 px sur un trait de 1.8 px reste discrète.
2. **En plus**, offrir un sélecteur de sens à trois positions (« Ce que cite cette fiche » / « Ce qui cite cette fiche » / « Les deux »), par défaut sur « Les deux ». Le défaut reste bidirectionnel parce que le sens entrant est la moitié de la valeur du méta-graphe ; il devient lisible grâce aux flèches, ce qui était le vrai problème.
3. **Le bug signalé** (une fiche qui cite la racine apparaissait comme si la racine la citait) est corrigé par le point 1 seul. Les points 2 et 3 le rendent en plus filtrable.

### Tâche B1 : marqueurs de flèche sur les arêtes fiche → fiche

**Fichiers :**
- Modifier : `apps/frontend/src/lib/components/SourceGraph.svelte` (définition des `<defs>` SVG, puis le rendu des liens autour de la ligne 1300)

- [ ] **Étape 1 : localiser le conteneur SVG**

```bash
cd apps/frontend && grep -n "defs\|append('svg')\|select(svgEl)" src/lib/components/SourceGraph.svelte | head -20
```

Repérer où le `<svg>` racine est créé et si un bloc `<defs>` existe déjà. S'il en existe un, y ajouter les marqueurs ; sinon, en créer un juste après la création du `<svg>`.

- [ ] **Étape 2 : déclarer les marqueurs de flèche**

Juste après la création du `<svg>` racine (avant l'ajout du groupe de zoom), insérer :

```js
    // Une pointe par couleur de rapport : un marqueur SVG n'hérite pas du
    // `stroke` de son trait, il faut le décliner. `context-stroke` existe mais
    // n'est pas supporté par Safari, et le graphe doit rester lisible partout.
    const arrowDefs = svg.append('defs');
    const ARROW_COLORS: Record<string, string> = {
      default: '#94a3b8',
      appuie: STANCE_STYLES['appuie'].stroke,
      'nuance-contredit': STANCE_STYLES['nuance-contredit'].stroke,
      contexte: STANCE_STYLES['contexte'].stroke,
      mentionne: STANCE_STYLES['mentionne'].stroke,
    };
    for (const [key, color] of Object.entries(ARROW_COLORS)) {
      arrowDefs
        .append('marker')
        .attr('id', `arrow-${key}`)
        .attr('viewBox', '0 -5 10 10')
        // Décalage : la pointe doit s'arrêter au bord du nœud cible, pas en son
        // centre. Le rayon d'un nœud fiche vaut 13 à 19 px selon la densité ;
        // `refX` est en unités de largeur de trait, d'où la conversion.
        .attr('refX', 10)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-4L9,0L0,4')
        .attr('fill', color);
    }
```

Vérifier que `STANCE_STYLES` est bien importé en haut du fichier depuis `$lib/utils/stance` ; si l'import n'existe pas, l'ajouter.

- [ ] **Étape 3 : appliquer le marqueur aux arêtes fiche → fiche**

Dans la chaîne d'attributs du rendu des liens (celle qui contient déjà `.attr('stroke-width', ...)` modifiée en tâche A1), ajouter :

```js
      .attr('marker-end', (d) => {
        // Seules les arêtes fiche → fiche portent un sens interprétable par le
        // lecteur. Une source appartient à sa fiche, ce n'est pas une citation
        // orientée : lui coller une flèche suggérerait une lecture fausse.
        if (d.kind !== 'meta') return null;
        if ((d as any).forkHide) return null;
        return `url(#arrow-${d.stance ?? 'default'})`;
      })
```

- [ ] **Étape 4 : décaler le trait pour que la pointe ne chevauche pas le nœud**

Dans la fonction de mise à jour des positions (le `tick` de la simulation), remplacer le calcul de la position de fin des liens `meta` pour qu'il s'arrête au bord du nœud cible. Repérer le `.attr('x2', ...)` / `.attr('y2', ...)` existant et l'envelopper :

```js
      .attr('x2', (d) => {
        const s = d.source as GraphNode;
        const t = d.target as GraphNode;
        if (d.kind !== 'meta') return t.x ?? 0;
        return edgeStop(s, t).x;
      })
      .attr('y2', (d) => {
        const s = d.source as GraphNode;
        const t = d.target as GraphNode;
        if (d.kind !== 'meta') return t.y ?? 0;
        return edgeStop(s, t).y;
      })
```

Et définir, à côté des autres fonctions utilitaires du composant :

```js
  /**
   * Point d'arrivée d'une arête orientée : le bord du nœud cible, pas son
   * centre. Sans ce recul, la pointe de flèche disparaît sous le disque et le
   * sens redevient invisible, ce qui était exactement le problème.
   */
  function edgeStop(s: GraphNode, t: GraphNode): { x: number; y: number } {
    const sx = s.x ?? 0;
    const sy = s.y ?? 0;
    const tx = t.x ?? 0;
    const ty = t.y ?? 0;
    const dx = tx - sx;
    const dy = ty - sy;
    const dist = Math.hypot(dx, dy);
    if (dist === 0) return { x: tx, y: ty };
    const back = (t.radius ?? 14) + 3;
    return { x: tx - (dx / dist) * back, y: ty - (dy / dist) * back };
  }
```

- [ ] **Étape 5 : vérifier sur le cas signalé**

```bash
cd apps/frontend && pnpm dev
```

Ouvrir `http://localhost:5173/@mathias-pinault/ca-sert-a-quoi-de-dormir`. Attendu : la flèche entre « Replay, the default mode network and the cascaded memory systems model » et « Synaptic tagging during memory allocation » **pointe vers** « Synaptic tagging », signifiant que Replay cite Synaptic tagging, et non l'inverse. C'est le sens que l'utilisateur a constaté dans les données. Si la flèche pointe dans l'autre sens, ne pas inverser le rendu : vérifier d'abord la donnée avec

```bash
curl -s "https://filum-api.up.railway.app/api/v1/cards/mathias-pinault/ca-sert-a-quoi-de-dormir/graph?depth=3" | python -m json.tool | grep -A3 is_card | head -40
```

et corriger la source du problème, pas son symptôme.

- [ ] **Étape 6 : lint**

```bash
cd apps/frontend && pnpm check && pnpm lint
```

- [ ] **Étape 7 : commit**

```bash
git add apps/frontend/src/lib/components/SourceGraph.svelte
git commit -m "feat: fleches de sens sur les liens fiche a fiche"
```

---

### Tâche B2 : sélecteur de sens à trois positions

**Fichiers :**
- Modifier : `apps/frontend/src/lib/components/SourceGraph.svelte`

- [ ] **Étape 1 : ajouter l'état**

À côté de `let legendOpen = $state(true);` (ajouté en tâche A2) :

```ts
  /**
   * Sens de lecture du méta-graphe.
   *
   * `sortant` : ce que cette fiche cite. `entrant` : ce qui cite cette fiche.
   * `deux` : les deux, distingués par la flèche. Le défaut est `deux` parce
   * que le sens entrant est la moitié de la valeur du graphe ; c'était son
   * illisibilité, pas sa présence, qui posait problème.
   */
  type GraphDirection = 'sortant' | 'entrant' | 'deux';
  let direction = $state<GraphDirection>('deux');
```

- [ ] **Étape 2 : filtrer les arêtes selon le sens**

Dans `buildGraph()`, remplacer la boucle des lignes 773-782 :

```js
    const seenCardLinks = new Set<string>();
    for (const [from, to, stance] of cardLinks) {
      const a = cardNodeIds.get(from);
      const b = cardNodeIds.get(to);
      if (!a || !b || a === b) continue;
      const key = `${a}|${b}`;
      if (seenCardLinks.has(key)) continue;
      seenCardLinks.add(key);
      links.push({ source: a, target: b, kind: 'meta', stance });
    }
```

par :

```js
    const seenCardLinks = new Set<string>();
    for (const [from, to, stance] of cardLinks) {
      const a = cardNodeIds.get(from);
      const b = cardNodeIds.get(to);
      if (!a || !b || a === b) continue;
      // `from` cite `to`. Le sens demandé se lit depuis la fiche consultée :
      // une arête qui part d'elle est sortante, une qui arrive est entrante.
      // Les arêtes entre deux voisines ne concernent aucun des deux sens
      // exclusifs : elles ne s'affichent qu'en vue complète.
      if (direction === 'sortant' && from !== card.id) continue;
      if (direction === 'entrant' && to !== card.id) continue;
      const key = `${a}|${b}`;
      if (seenCardLinks.has(key)) continue;
      seenCardLinks.add(key);
      links.push({ source: a, target: b, kind: 'meta', stance });
    }
```

- [ ] **Étape 3 : remonter le graphe quand le sens change**

Ajouter, à côté des autres `$effect` du composant :

```ts
  // Changer de sens change la topologie : la simulation doit repartir, sinon
  // les nœuds retirés laissent un trou et ceux ajoutés apparaissent au centre.
  $effect(() => {
    direction;
    if (!svgEl) return;
    remount();
  });
```

Vérifier le nom réel de la référence au nœud SVG dans le composant (`svgEl`, `container`, etc.) avec `grep -n "bind:this" src/lib/components/SourceGraph.svelte` et l'utiliser.

- [ ] **Étape 4 : ajouter le sélecteur dans la barre d'outils**

Repérer la barre d'outils existante du graphe (celle qui porte déjà le mode de couleur) :

```bash
cd apps/frontend && grep -n "colorMode" src/lib/components/SourceGraph.svelte | head -20
```

Ajouter à côté, dans le balisage :

```svelte
        <div
          class="flex items-center gap-1 rounded-md border border-slate-200 bg-white/95 p-0.5 text-xs backdrop-blur-sm"
          role="group"
          aria-label="Sens de citation affiché"
        >
          {#each [{ v: 'sortant', l: 'Ce que cite cette fiche' }, { v: 'entrant', l: 'Ce qui cite cette fiche' }, { v: 'deux', l: 'Les deux' }] as opt (opt.v)}
            <button
              type="button"
              class="rounded px-2 py-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-500 {direction ===
              opt.v
                ? 'bg-indigo-600 text-white'
                : 'text-slate-600 hover:bg-slate-100'}"
              aria-pressed={direction === opt.v}
              onclick={() => (direction = opt.v as GraphDirection)}
            >
              {opt.l}
            </button>
          {/each}
        </div>
```

Si la barre est déjà chargée sur mobile, n'afficher que « Cite » / « Cité par » / « Les deux » en dessous de `sm:` via deux jeux de libellés (`class="hidden sm:inline"` et `class="sm:hidden"`).

- [ ] **Étape 5 : vérifier dans le navigateur**

Sur une fiche ayant des voisines dans les deux sens : « Ce que cite cette fiche » ne montre que les fiches vers lesquelles part une flèche depuis la racine ; « Ce qui cite cette fiche » l'inverse ; « Les deux » montre tout. Aucun nœud fiche orphelin ne doit rester à l'écran après filtrage (une fiche sans arête visible ne doit pas être rendue). Si c'est le cas, ajouter en fin de `buildGraph()` un filtrage des nœuds `kind === 'card'` sans arête `meta` incidente, sauf le nœud racine et les fiches épinglées (tâche B4).

- [ ] **Étape 6 : lint**

```bash
cd apps/frontend && pnpm check && pnpm lint
```

- [ ] **Étape 7 : commit**

```bash
git add apps/frontend/src/lib/components/SourceGraph.svelte
git commit -m "feat: selecteur de sens du meta-graphe"
```

---

### Tâche B3 : n'afficher les fiches imbriquées qu'au dépliage

**Constat utilisateur :** « quand une fiche cite une fiche qui cite une fiche, tous les nœuds fiches s'affichent en même temps, ce qui n'est pas pertinent. Les fiches citées par d'autres fiches devraient apparaître uniquement lorsque l'utilisateur déplie les sources de la fiche amont. »

**Attention :** le commentaire actuel des lignes 744-747 justifie explicitement le comportement inverse (« Ne montrer que les fiches atteignables depuis les sources affichées masquait les chaînes A -> B -> C tant que B n'était pas dépliée, et tout le sens entrant »). Le nouveau comportement doit préserver **le sens entrant à un saut** : les fiches qui citent la racine restent visibles d'emblée. Seule la profondeur 2 et au-delà est différée.

**Fichiers :**
- Modifier : `apps/frontend/src/lib/components/SourceGraph.svelte:744-782`

- [ ] **Étape 1 : calculer l'ensemble des fiches visibles**

Dans `buildGraph()`, juste avant la boucle `for (const [cid, meta] of neighborCards)` (ligne 750), insérer :

```js
    // Une fiche n'entre dans le graphe que si elle touche une fiche déjà à
    // l'écran : la racine, une fiche dépliée, ou une fiche épinglée. Afficher
    // d'emblée toute la constellation à trois sauts produisait un nuage que
    // personne ne pouvait lire, où la fiche consultée se perdait.
    //
    // Le voisinage est calculé dans les deux sens : « qui me cite » à un saut
    // est aussi informatif que « qui je cite », et le masquer reviendrait à
    // amputer le graphe de sa moitié entrante.
    const anchorIds = new Set<string>([card.id, ...expandedCardIds, ...pinnedCardIds]);
    const visibleCardIds = new Set<string>(anchorIds);
    for (const [from, to] of cardLinks) {
      if (anchorIds.has(from)) visibleCardIds.add(to);
      if (anchorIds.has(to)) visibleCardIds.add(from);
    }
```

- [ ] **Étape 2 : restreindre la création des nœuds fiche**

Remplacer l'en-tête de boucle ligne 750 :

```js
    for (const [cid, meta] of neighborCards) {
```

par :

```js
    for (const [cid, meta] of neighborCards) {
      if (!visibleCardIds.has(cid)) continue;
```

Et remplacer le commentaire obsolète des lignes 744-747 par :

```js
    // Fiches du voisinage retenues à l'affichage : voir `visibleCardIds`
    // ci-dessus. Une fiche à deux sauts n'apparaît qu'une fois sa fiche amont
    // dépliée, ou si le lecteur l'a épinglée.
```

- [ ] **Étape 3 : signaler qu'une fiche en cache d'autres**

Dans la construction du nœud fiche (lignes 753-766), ajouter après `expandable` :

```js
        // Nombre de fiches que déplier celle-ci ferait apparaître. Sans ce
        // signal, le lecteur n'a aucun moyen de savoir que la constellation
        // continue derrière ce nœud.
        hiddenNeighbors: countHiddenNeighbors(cid, visibleCardIds),
```

Et définir, à côté de `buildGraph()` :

```js
  function countHiddenNeighbors(cid: string, visible: Set<string>): number {
    let n = 0;
    const seen = new Set<string>();
    for (const [from, to] of cardLinks) {
      const other = from === cid ? to : to === cid ? from : null;
      if (!other || visible.has(other) || seen.has(other)) continue;
      seen.add(other);
      n += 1;
    }
    return n;
  }
```

Ajouter `hiddenNeighbors?: number;` à l'interface `GraphNode` du composant.

- [ ] **Étape 4 : afficher le signal sur le nœud**

Dans le rendu des pastilles (autour de la fonction `expandBadgeLabel`, ligne 641), adapter le libellé de la pastille `+` pour cumuler sources et fiches masquées :

```js
  function expandBadgeLabel(d: GraphNode): string {
    const sources = neighborCards.get(d.expandable ?? '')?.sourcesCount ?? 0;
    const hidden = d.hiddenNeighbors ?? 0;
    // Deux natures d'objets masqués derrière un même geste : on additionne
    // plutôt que d'afficher « +12 / +2 », illisible à cette taille. Le titre
    // au survol détaille.
    return `+${sources + hidden}`;
  }
```

Et sur le `<title>` du nœud (ou son `aria-label`), préciser :

```js
      .text((d) => {
        const sources = neighborCards.get(d.expandable ?? '')?.sourcesCount ?? 0;
        const hidden = d.hiddenNeighbors ?? 0;
        if (hidden === 0) return `Déplier ${sources} source${sources > 1 ? 's' : ''}`;
        return `Déplier ${sources} source${sources > 1 ? 's' : ''} et ${hidden} fiche${hidden > 1 ? 's' : ''} reliée${hidden > 1 ? 's' : ''}`;
      })
```

- [ ] **Étape 5 : vérifier sur une chaîne à trois fiches**

Sur `http://localhost:5173/@mathias-pinault/ca-sert-a-quoi-de-dormir` : au chargement, seules les fiches à un saut de la racine sont visibles. Déplier une fiche voisine fait apparaître ses propres fiches reliées. Replier la fiche les fait disparaître, sauf si elles ont été épinglées (tâche B4).

- [ ] **Étape 6 : lint**

```bash
cd apps/frontend && pnpm check && pnpm lint
```

- [ ] **Étape 7 : commit**

```bash
git add apps/frontend/src/lib/components/SourceGraph.svelte
git commit -m "feat: differer l'affichage des fiches a deux sauts"
```

---

### Tâche B4 : épingler une fiche

**Constat utilisateur :** « un bouton supplémentaire pour "figer" les nœuds fiche malgré l'imbrication. »

**Fichiers :**
- Modifier : `apps/frontend/src/lib/components/SourceGraph.svelte`
- Modifier : `apps/frontend/src/lib/components/CardDetailPanel.svelte`

- [ ] **Étape 1 : ajouter l'état d'épinglage**

Dans `SourceGraph.svelte`, à côté de `expandedCardIds` (ligne 240) :

```ts
  /**
   * Fiches maintenues à l'écran quelle que soit la profondeur.
   *
   * Épingler est le contrepoids du repli automatique introduit avec
   * l'affichage différé : un lecteur qui a trouvé une fiche à trois sauts ne
   * doit pas la perdre parce qu'il replie le chemin qui l'y a mené.
   */
  let pinnedCardIds = $state<string[]>([]);

  function togglePin(cid: string) {
    pinnedCardIds = pinnedCardIds.includes(cid)
      ? pinnedCardIds.filter((id) => id !== cid)
      : [...pinnedCardIds, cid];
    remount();
  }
```

- [ ] **Étape 2 : marquer visuellement une fiche épinglée**

Dans la construction du nœud fiche, remplacer `stroke: '#6366f1',` par :

```js
        // Un contour ambre distingue une fiche épinglée d'une fiche de passage,
        // sans changer son remplissage : c'est le même objet, dans un état
        // différent, pas une autre catégorie.
        stroke: pinnedCardIds.includes(cid) ? '#f59e0b' : '#6366f1',
        pinned: pinnedCardIds.includes(cid),
```

Ajouter `pinned?: boolean;` à l'interface `GraphNode`, et dans la chaîne d'attributs du rendu des nœuds :

```js
      .attr('stroke-width', (d) => (d.pinned ? 3 : 2))
      .attr('stroke-dasharray', (d) => (d.pinned ? '4 2' : null))
```

- [ ] **Étape 3 : exposer l'action dans l'encadré de fiche**

Dans `apps/frontend/src/lib/components/CardDetailPanel.svelte`, ajouter aux `$props()` :

```ts
    pinned?: boolean;
    onTogglePin?: (cardId: string) => void;
```

et, à côté du bouton « Ouvrir la fiche » existant :

```svelte
    {#if onTogglePin}
      <button
        type="button"
        class="rounded-md border border-amber-300 px-3 py-1.5 text-sm text-amber-800 hover:bg-amber-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-amber-500"
        aria-pressed={pinned}
        onclick={() => onTogglePin?.(info.id)}
      >
        {pinned ? 'Détacher du graphe' : 'Garder sur le graphe'}
      </button>
    {/if}
```

Vérifier le nom réel du champ identifiant dans `CardPanelInfo` (`grep -n "interface CardPanelInfo" -A 12 src/lib/components/CardDetailPanel.svelte`) et utiliser celui-là plutôt que `info.id` s'il diffère.

- [ ] **Étape 4 : brancher le rappel dans le graphe**

À l'endroit où `SourceGraph.svelte` instancie `<CardDetailPanel …>`, ajouter :

```svelte
    pinned={pinnedCardIds.includes(selectedCardInfo.id)}
    onTogglePin={togglePin}
```

- [ ] **Étape 5 : vérifier**

Déplier une fiche, ouvrir l'encadré d'une de ses fiches reliées, cliquer « Garder sur le graphe », replier la fiche amont : la fiche épinglée reste à l'écran, avec un contour ambre pointillé. Cliquer « Détacher du graphe » la fait disparaître.

- [ ] **Étape 6 : lint**

```bash
cd apps/frontend && pnpm check && pnpm lint
```

- [ ] **Étape 7 : commit**

```bash
git add apps/frontend/src/lib/components/SourceGraph.svelte apps/frontend/src/lib/components/CardDetailPanel.svelte
git commit -m "feat: epingler une fiche sur le graphe"
```

---

### Tâche B5 : accès à la fiche Philum depuis l'encadré d'une source absorbée

**Constat utilisateur :** « "Synaptic tagging during memory allocation" est une fiche et on devrait donc pouvoir accéder au lien Philum de la fiche facilement via le graphe (dans l'encadré). »

**Diagnostic :** deux cas distincts.
- Un nœud fiche cliqué ouvre `CardDetailPanel`, qui possède déjà « Ouvrir la fiche » (`href="/@{info.creatorSlug}/{info.slug}"`). Rien à faire.
- Un nœud **source** dont `linked_card_id` est renseigné mais dont la fiche cible n'est pas dans le graphe (privée, ou hors profondeur) ouvre `SourceDetailPanel`, qui n'offre que `href={source.url}` (ligne 241) et `href={source.archive_url}` (ligne 261). **C'est ce cas qu'il faut couvrir.**

**Fichiers :**
- Modifier : `apps/frontend/src/lib/components/SourceDetailPanel.svelte`
- Modifier : `apps/backend/app/services/card_graph.py` (exposer le slug de la fiche liée)
- Modifier : `apps/backend/app/schemas/card_graph.py` (ou le schéma correspondant)
- Test : `apps/backend/tests/unit/test_card_graph.py`

- [ ] **Étape 1 : écrire le test backend qui échoue**

Dans `apps/backend/tests/unit/test_card_graph.py`, ajouter :

```python
@pytest.mark.asyncio
async def test_source_liee_expose_le_chemin_de_sa_fiche(db_session):
    """Une source qui designe une fiche doit porter de quoi y aller.

    Sans slug ni createur, le lecteur voit « cette source est une fiche
    Philum » sans pouvoir l'ouvrir : une promesse sans porte.
    """
    graph = await build_card_graph(db_session, root_card, depth=0)
    linked = [n for n in graph.nodes if n.kind == "source" and n.linked_card_id]
    assert linked, "le jeu de test doit contenir au moins une source liee"
    for node in linked:
        assert node.linked_card_slug
        assert node.linked_card_creator_slug
```

Adapter la fixture `root_card` au style déjà employé dans ce fichier (lire les tests voisins avant d'écrire).

- [ ] **Étape 2 : lancer le test pour le voir échouer**

```bash
cd apps/backend && CI=true uv run pytest tests/unit/test_card_graph.py -k liee -q
```

Attendu : ÉCHEC, `AttributeError: 'GraphNode' object has no attribute 'linked_card_slug'`.

- [ ] **Étape 3 : ajouter les champs au nœud**

Dans `apps/backend/app/services/card_graph.py`, à la suite de `linked_card_id: UUID | None = None` (ligne 73) :

```python
    # Chemin public de la fiche designee par cette source. `linked_card_id`
    # seul ne permet pas d'y aller : le frontend n'a pas de route par UUID.
    linked_card_slug: str | None = None
    linked_card_creator_slug: str | None = None
```

- [ ] **Étape 4 : renseigner ces champs**

Il faut charger les fiches désignées même quand elles ne sont pas dans le graphe. Ajouter après `_load_card_authors` :

```python
async def _load_linked_card_paths(
    db: AsyncSession, card_ids: set[UUID]
) -> dict[UUID, tuple[str, str]]:
    """Chemin public des fiches designees : ``card_id -> (slug, username)``.

    Distinct du BFS : une source peut designer une fiche hors profondeur ou
    absente du graphe pour cause de troncature, et le lecteur doit quand meme
    pouvoir l'ouvrir. Seules les fiches publiques et publiees remontent, la
    visibilite restant celle de `_load_cards`.
    """
    if not card_ids:
        return {}
    result = await db.execute(
        select(BiblioCard.id, BiblioCard.slug, User.username)
        .join(User, BiblioCard.user_id == User.id)
        .where(
            BiblioCard.id.in_(card_ids),
            BiblioCard.status == "published",
            BiblioCard.visibility == "public",
            BiblioCard.deleted_at.is_(None),
        )
    )
    return {row[0]: (row[1], row[2]) for row in result.all()}
```

Puis, juste avant le `return graph` final (ligne 362) :

```python
    linked_ids = {n.linked_card_id for n in graph.nodes if n.linked_card_id}
    if linked_ids:
        paths = await _load_linked_card_paths(db, linked_ids)
        for node in graph.nodes:
            if node.linked_card_id is None:
                continue
            found = paths.get(node.linked_card_id)
            if found is None:
                continue
            node.linked_card_slug, node.linked_card_creator_slug = found
```

- [ ] **Étape 5 : exposer les champs dans le schéma Pydantic**

```bash
cd apps/backend && grep -rn "linked_card_id" app/schemas/
```

Ajouter `linked_card_slug: str | None = None` et `linked_card_creator_slug: str | None = None` au schéma de nœud correspondant.

- [ ] **Étape 6 : relancer le test**

```bash
cd apps/backend && CI=true uv run pytest tests/unit/test_card_graph.py -q
```

Attendu : tous les tests passent.

- [ ] **Étape 7 : consommer les champs côté frontend**

Dans `apps/frontend/src/lib/components/SourceGraph.svelte`, fonction `loadNeighborhood()` (bloc lignes 581-599), ajouter au littéral de source :

```ts
          linked_card_slug: n.linked_card_slug ?? null,
          linked_card_creator_slug: n.linked_card_creator_slug ?? null,
```

Ajouter les deux champs au type `GraphSourceData` (le chercher avec `grep -rn "interface GraphSourceData\|type GraphSourceData" src/lib`).

- [ ] **Étape 8 : ajouter le bouton dans l'encadré de source**

Dans `apps/frontend/src/lib/components/SourceDetailPanel.svelte`, à côté du lien `href={source.url}` (ligne 241) :

```svelte
    {#if source.linked_card_slug && source.linked_card_creator_slug}
      <a
        class="inline-flex items-center gap-1.5 rounded-md border border-indigo-300 px-3 py-1.5 text-sm text-indigo-800 hover:bg-indigo-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-500"
        href="/@{source.linked_card_creator_slug}/{source.linked_card_slug}"
      >
        ★ Ouvrir la fiche Philum
      </a>
    {/if}
```

- [ ] **Étape 9 : vérifier de bout en bout**

Backend local :

```bash
cd apps/backend && CI=true uv run uvicorn app.main:app --reload
```

Frontend local, ouvrir une fiche dont une source pointe une fiche Philum : l'encadré de la source affiche « ★ Ouvrir la fiche Philum », le clic mène à la bonne page.

- [ ] **Étape 10 : lint**

```bash
cd apps/backend && uv run ruff check app/ && uv run mypy app/
cd ../frontend && pnpm check && pnpm lint
```

- [ ] **Étape 11 : commit**

```bash
git add apps/backend/app/services/card_graph.py apps/backend/app/schemas apps/backend/tests/unit/test_card_graph.py apps/frontend/src/lib/components/SourceDetailPanel.svelte apps/frontend/src/lib/components/SourceGraph.svelte
git commit -m "feat: ouvrir la fiche liee depuis l'encadre source"
```

---

# LOT C — Options de référencement des fiches

**Constat utilisateur :** « Les fiches devraient avoir les mêmes options de référencement que leurs sources/références : format, auteur, catégorie. »

**Diagnostic :** `Source` porte `format` (`SourceFormat`), `category` (`SourceCategory`) et `author_kind` (`AuthorKind`), tous `NOT NULL` (`apps/backend/app/models/source.py:102-104`). `BiblioCard` ne porte que `content_type` et `platform` (`apps/backend/app/models/biblio_card.py:74,82`), deux énumérations plus pauvres et orientées plateforme. Conséquence visible : dans le graphe, un nœud fiche est toujours ardoise/indigo, alors qu'un nœud source prend la couleur de son format, de sa catégorie ou du type de son auteur selon le mode choisi. Quand un lecteur bascule le mode de couleur, les fiches ne participent pas à la lecture.

**Décision :** les trois colonnes sont **nullables** sur `biblio_cards`, contrairement à `sources`. `NULL` veut dire « pas déclaré », jamais « inconnu » ni une valeur par défaut : c'est l'invariant d'honnêteté à trois états déjà appliqué à `stance`, à la rétractation et à l'accès ouvert. Les fiches existantes ne sont pas rétro-remplies.

**Ne pas supprimer `content_type` ni `platform`.** Ils servent ailleurs (parcours de création, affichage public) et une dépréciation est un chantier séparé.

### Tâche C1 : migration et modèle

**Fichiers :**
- Créer : `apps/backend/alembic/versions/026_card_referencing.py`
- Modifier : `apps/backend/app/models/biblio_card.py`

- [ ] **Étape 1 : vérifier la tête Alembic**

```bash
cd apps/backend && ls alembic/versions/ | tail -3
```

Attendu : `025_archive_attempted_at.py` en dernier, de révision `025_archive_try`. Si une révision plus récente existe, adapter `down_revision` en conséquence.

- [ ] **Étape 2 : créer la migration**

Créer `apps/backend/alembic/versions/026_card_referencing.py` :

```python
"""Aligner les fiches sur les options de referencement de leurs sources.

Une fiche est une reference comme une autre des qu'une autre fiche la cite :
elle a un format, une categorie et un type d'auteur. Sans ces colonnes, un
noeud fiche restait d'une seule couleur quel que soit le mode de lecture du
graphe, et sortait de la grille de lecture au moment ou le lecteur en avait le
plus besoin.

Les trois colonnes sont NULLABLE, contrairement a `sources` : NULL veut dire
« pas declare », pas « autre ». Retro-remplir depuis `content_type` aurait
invente une declaration que personne n'a faite.

Revision ID: 026_card_ref
Revises: 025_archive_try
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "026_card_ref"
down_revision: str | None = "025_archive_try"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("biblio_cards", sa.Column("format", sa.String(20), nullable=True))
    op.add_column("biblio_cards", sa.Column("category", sa.String(40), nullable=True))
    op.add_column("biblio_cards", sa.Column("author_kind", sa.String(40), nullable=True))


def downgrade() -> None:
    op.drop_column("biblio_cards", "author_kind")
    op.drop_column("biblio_cards", "category")
    op.drop_column("biblio_cards", "format")
```

- [ ] **Étape 3 : ajouter les colonnes au modèle**

Dans `apps/backend/app/models/biblio_card.py`, après `content_authors` (ligne 81) :

```python
    # Referencement du contenu documente, avec le meme vocabulaire que les
    # sources (`SourceFormat`, `SourceCategory`, `AuthorKind`) : une fiche
    # devient une reference des qu'une autre la cite, et doit se lire dans la
    # meme grille. NULL = non declare, jamais une valeur par defaut.
    format: Mapped[str | None] = mapped_column(String(20), nullable=True)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    author_kind: Mapped[str | None] = mapped_column(String(40), nullable=True)
```

- [ ] **Étape 4 : appliquer la migration en local**

```bash
cd apps/backend && uv run alembic upgrade head && uv run alembic current
```

Attendu : `026_card_ref (head)`.

- [ ] **Étape 5 : vérifier l'aller-retour**

```bash
cd apps/backend && uv run alembic downgrade -1 && uv run alembic upgrade head
```

Attendu : aucune erreur dans les deux sens.

- [ ] **Étape 6 : lint**

```bash
cd apps/backend && uv run ruff check app/ alembic/ && uv run mypy app/
```

- [ ] **Étape 7 : commit**

```bash
git add apps/backend/alembic/versions/026_card_referencing.py apps/backend/app/models/biblio_card.py
git commit -m "feat: referencement format/categorie/auteur sur les fiches"
```

---

### Tâche C2 : exposer et accepter les trois champs dans l'API

**Fichiers :**
- Modifier : `apps/backend/app/schemas/biblio_card.py`
- Modifier : `apps/backend/app/api/v1/endpoints/cards.py`
- Modifier : `apps/backend/app/services/card_graph.py`
- Test : `apps/backend/tests/integration/test_cards.py`

- [ ] **Étape 1 : écrire le test qui échoue**

Dans `apps/backend/tests/integration/test_cards.py`, ajouter :

```python
@pytest.mark.asyncio
async def test_mise_a_jour_du_referencement_d_une_fiche(client, auth_headers, card_id):
    """Les trois champs de referencement sont modifiables et relus tels quels."""
    payload = {"format": "video", "category": "documentaire", "author_kind": "individu"}
    resp = await client.patch(f"/api/v1/cards/{card_id}", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["format"] == "video"
    assert body["category"] == "documentaire"
    assert body["author_kind"] == "individu"


@pytest.mark.asyncio
async def test_referencement_non_declare_reste_null(client, auth_headers, card_id):
    """Ne rien declarer ne doit pas produire une valeur par defaut inventee."""
    resp = await client.get(f"/api/v1/cards/{card_id}", headers=auth_headers)
    body = resp.json()
    assert body["format"] is None
    assert body["category"] is None
    assert body["author_kind"] is None
```

Adapter les fixtures (`client`, `auth_headers`, `card_id`) aux noms réellement employés dans ce fichier : les lire d'abord.

- [ ] **Étape 2 : lancer le test pour le voir échouer**

```bash
cd apps/backend && CI=true uv run pytest tests/integration/test_cards.py -k referencement -q
```

Attendu : ÉCHEC (`KeyError: 'format'` ou 422).

- [ ] **Étape 3 : ajouter les champs aux schémas**

Dans `apps/backend/app/schemas/biblio_card.py`, importer les énumérations et les ajouter aux schémas de lecture, de création et de mise à jour :

```python
from app.models.source import AuthorKind, SourceCategory, SourceFormat
```

Puis, dans le schéma de réponse :

```python
    # Referencement du contenu documente, meme vocabulaire que les sources.
    # NULL = non declare : le frontend doit distinguer « pas renseigne » de
    # « autre », sans quoi une fiche muette passerait pour une fiche classee.
    format: SourceFormat | None = None
    category: SourceCategory | None = None
    author_kind: AuthorKind | None = None
```

Ajouter les trois mêmes champs, tous optionnels, au schéma de mise à jour (`BiblioCardUpdate` ou équivalent) et au schéma de création.

- [ ] **Étape 4 : propager dans l'endpoint de mise à jour**

Vérifier que l'endpoint `PATCH /api/v1/cards/{card_id}` applique les champs via `model_dump(exclude_unset=True)`. Si l'affectation est faite champ par champ, ajouter les trois. Chercher :

```bash
cd apps/backend && grep -n "exclude_unset\|setattr" app/api/v1/endpoints/cards.py | head
```

- [ ] **Étape 5 : exposer les champs sur le nœud de graphe**

Dans `apps/backend/app/services/card_graph.py`, le `GraphNode` porte déjà `category`, `format` et `author_kind` (lignes 304-306, remplis pour les sources). Renseigner ces mêmes champs pour les nœuds fiche, dans la construction du nœud (lignes 264-277) :

```python
                    authors=card.content_authors,
                    is_seed=bool(card.is_seed),
                    format=card.format,
                    category=card.category,
                    author_kind=card.author_kind,
```

- [ ] **Étape 6 : relancer les tests**

```bash
cd apps/backend && CI=true uv run pytest tests/integration/test_cards.py tests/unit/test_card_graph.py -q
```

Attendu : tout passe.

- [ ] **Étape 7 : lint**

```bash
cd apps/backend && uv run ruff check app/ && uv run mypy app/
```

- [ ] **Étape 8 : commit**

```bash
git add apps/backend/app/schemas apps/backend/app/api/v1/endpoints/cards.py apps/backend/app/services/card_graph.py apps/backend/tests
git commit -m "feat: exposer le referencement des fiches dans l'API"
```

---

### Tâche C3 : formulaire d'édition et coloration du graphe

**Fichiers :**
- Modifier : `apps/frontend/src/routes/dashboard/new/[card_id]/sources/+page.svelte` (ou l'écran d'édition des métadonnées de fiche, à confirmer)
- Modifier : `apps/frontend/src/lib/components/SourceGraph.svelte`
- Modifier : `apps/frontend/src/lib/api` (type de fiche)

- [ ] **Étape 1 : localiser l'écran d'édition des métadonnées de fiche**

```bash
cd apps/frontend && grep -rn "content_authors\|content_type" src/routes/dashboard | head -20
```

Le formulaire qui édite déjà `content_authors` est celui à étendre.

- [ ] **Étape 2 : ajouter les trois champs au type client**

Dans le type de fiche du client API (`grep -rn "content_authors" src/lib/api`), ajouter :

```ts
  format: SourceFormat | null;
  category: SourceCategory | null;
  author_kind: AuthorKind | null;
```

- [ ] **Étape 3 : ajouter les trois sélecteurs**

Réutiliser exactement les mêmes libellés et le même ordre que ceux des sources, pour que le créateur retrouve un vocabulaire connu. Chercher le composant existant :

```bash
cd apps/frontend && grep -rn "article-scientifique" src/lib src/routes | head
```

Si un composant de sélection de catégorie existe déjà, le réutiliser avec une option supplémentaire en tête :

```svelte
  <option value="">Non déclaré</option>
```

Cette option doit envoyer `null`, pas la chaîne vide : ajouter à la soumission

```ts
    format: form.format || null,
    category: form.category || null,
    author_kind: form.author_kind || null,
```

- [ ] **Étape 4 : colorer les nœuds fiche selon le mode de couleur**

Dans `apps/frontend/src/lib/components/SourceGraph.svelte`, la construction du nœud fiche fixe aujourd'hui `fill: '#1e293b'` et `stroke: '#6366f1'` (lignes 763-764). Remplacer par :

```js
        // Une fiche qui a déclaré son référencement se lit dans la même grille
        // que les sources : basculer le mode de couleur doit la faire bouger
        // aussi. Sans déclaration, elle garde l'ardoise neutre, qui dit « non
        // déclaré » et non « autre ».
        ...cardNodeColors(meta, colorMode, pinnedCardIds.includes(cid)),
```

Et définir :

```js
  function cardNodeColors(
    meta: NeighborCard,
    mode: ColorMode,
    pinned: boolean
  ): { fill: string; stroke: string } {
    const declared =
      mode === 'format' ? meta.format : mode === 'categorie' ? meta.category : meta.author_kind;
    if (!declared) {
      return { fill: '#1e293b', stroke: pinned ? '#f59e0b' : '#6366f1' };
    }
    const colors = sourceColor(
      { format: meta.format, category: meta.category, author_kind: meta.author_kind } as GraphSourceData,
      mode
    );
    // Le nœud fiche garde un fond plus sombre que ses sources : c'est un objet
    // d'une autre nature, la couleur dit sa catégorie, pas son rang.
    return { fill: colors.stroke, stroke: pinned ? '#f59e0b' : colors.stroke };
  }
```

Adapter les noms `ColorMode` et les valeurs de mode (`'format' | 'categorie' | 'auteur'`) à ceux réellement employés :

```bash
cd apps/frontend && grep -n "colorMode\s*=\|type ColorMode" src/lib/components/SourceGraph.svelte | head
```

- [ ] **Étape 5 : transporter les champs jusqu'au nœud**

Ajouter `format`, `category` et `author_kind` au type `NeighborCard`, et les renseigner dans `loadNeighborhood()` (bloc lignes 570-578) :

```ts
          format: (n.format ?? null) as SourceFormat | null,
          category: (n.category ?? null) as SourceCategory | null,
          author_kind: (n.author_kind ?? null) as AuthorKind | null,
```

- [ ] **Étape 6 : vérifier**

Éditer une fiche, déclarer `format = vidéo`, `catégorie = documentaire`, `auteur = individu`, publier. Ouvrir une fiche qui la cite : au mode de couleur « format », le nœud de la fiche citée prend la couleur des vidéos. Basculer sur « catégorie » : il change. Une fiche non déclarée reste ardoise dans tous les modes.

- [ ] **Étape 7 : lint**

```bash
cd apps/frontend && pnpm check && pnpm lint
```

- [ ] **Étape 8 : commit**

```bash
git add apps/frontend/src
git commit -m "feat: declarer et colorer le referencement des fiches"
```

---

# LOT D — Espace de gestion des connexions entre fiches

**Constat utilisateur :** « Dans l'espace de création/édition de fiche, un espace de gestion des connexions entre les fiches : visualiser les connexions (suggérées ou déjà validées), en supprimer ou en ajouter facilement. L'interface doit être élégante et *user friendly*, claire, intuitive, facilement compréhensible et utilisable facilement. »

**Diagnostic :** aujourd'hui, rien ne distingue une connexion **choisie** d'une connexion **devinée**. `effective_linked_card_id` (`apps/backend/app/services/card_link.py:206-228`) suit trois chemins : le sélecteur explicite, l'URL Philum collée, la résolution par contenu (même DOI ou même URL normalisée). Les trois écrivent la même colonne `Source.linked_card_id`, indiscernables ensuite. Pire, `link_sources_designating_card` (ligne 172-203) écrit ce lien **en masse sur les sources d'autres créateurs** quand une fiche est publiée, sans que personne ne l'ait validé. Un espace de gestion sans cette distinction n'aurait rien à montrer.

**Décision :** deux colonnes sur `sources`.
- `link_origin` : `'manuel'` (sélecteur), `'url'` (URL Philum collée), `'contenu'` (déduit d'un DOI ou d'une URL équivalente). `NULL` pour les liens antérieurs à la traçabilité, dont on ne peut rien affirmer.
- `link_confirmed_at` : horodatage de la validation humaine. `NULL` = jamais confirmé.

`'manuel'` et `'url'` sont confirmés d'office : le créateur a posé le geste. Seul `'contenu'` produit une **suggestion**, qui reste affichée dans le graphe (la retirer régresserait le méta-graphe) mais qui est signalée et révocable dans l'espace de gestion.

### Tâche D1 : migration et modèle

**Fichiers :**
- Créer : `apps/backend/alembic/versions/027_link_provenance.py`
- Modifier : `apps/backend/app/models/source.py`

- [ ] **Étape 1 : créer la migration**

```python
"""Tracer d'ou vient un lien fiche a fiche, et s'il a ete valide.

Trois chemins ecrivaient `linked_card_id` sans laisser de trace : le
selecteur, l'URL Philum collee, et la deduction par DOI ou URL equivalente.
Le troisieme est une hypothese, les deux premiers sont des gestes. Les
confondre rendait impossible tout espace de gestion : on ne peut pas proposer
de retirer une suggestion qu'on ne sait pas reconnaitre.

`link_confirmed_at` NULL = jamais confirme par un humain. Les liens existants
ne sont pas retro-confirmes : personne ne les a valides, l'affirmer serait
faux. Ils gardent `link_origin` NULL, qui dit « on ne sait pas ».

Revision ID: 027_link_prov
Revises: 026_card_ref
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "027_link_prov"
down_revision: str | None = "026_card_ref"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("link_origin", sa.String(20), nullable=True))
    op.add_column("sources", sa.Column("link_confirmed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "link_confirmed_at")
    op.drop_column("sources", "link_origin")
```

- [ ] **Étape 2 : ajouter l'énumération et les colonnes au modèle**

Dans `apps/backend/app/models/source.py`, après `class SourceStance` (ligne 70) :

```python
class LinkOrigin(str, Enum):
    """D'ou vient le lien d'une source vers une fiche Philum.

    MANUEL et URL sont des gestes du createur : ils valent confirmation.
    CONTENU est une hypothese de la machine (meme DOI, meme URL normalisee) :
    elle vaut proposition, pas declaration. Les confondre ferait porter au
    createur une affirmation qu'il n'a pas faite.
    """

    MANUEL = "manuel"
    URL = "url"
    CONTENU = "contenu"
```

Et dans la classe `Source`, à la suite de `linked_card_id` (ligne 126) :

```python
    link_origin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    link_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

- [ ] **Étape 3 : appliquer et vérifier l'aller-retour**

```bash
cd apps/backend && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
```

- [ ] **Étape 4 : lint et commit**

```bash
cd apps/backend && uv run ruff check app/ alembic/ && uv run mypy app/
git add apps/backend/alembic/versions/027_link_provenance.py apps/backend/app/models/source.py
git commit -m "feat: tracer l'origine des liens fiche a fiche"
```

---

### Tâche D2 : renseigner l'origine à chaque écriture de lien

**Fichiers :**
- Modifier : `apps/backend/app/services/card_link.py`
- Test : `apps/backend/tests/unit/test_card_link.py`

- [ ] **Étape 1 : écrire les tests qui échouent**

Dans `apps/backend/tests/unit/test_card_link.py` :

```python
@pytest.mark.asyncio
async def test_lien_choisi_est_confirme(db_session, user, card, other_card):
    """Choisir une fiche dans le selecteur vaut confirmation."""
    result = await resolve_link(
        db_session,
        chosen=other_card.id,
        url="https://exemple.test/article",
        user_id=user.id,
        current_card_id=card.id,
    )
    assert result.card_id == other_card.id
    assert result.origin == LinkOrigin.MANUEL
    assert result.confirmed is True


@pytest.mark.asyncio
async def test_lien_deduit_du_contenu_reste_une_suggestion(db_session, user, card, other_card):
    """Un meme DOI est une hypothese, pas une declaration du createur."""
    result = await resolve_link(
        db_session,
        chosen=None,
        url=other_card.content_url,
        user_id=user.id,
        current_card_id=card.id,
    )
    assert result.card_id == other_card.id
    assert result.origin == LinkOrigin.CONTENU
    assert result.confirmed is False
```

- [ ] **Étape 2 : lancer pour voir échouer**

```bash
cd apps/backend && CI=true uv run pytest tests/unit/test_card_link.py -k lien -q
```

Attendu : ÉCHEC, `ImportError: cannot import name 'resolve_link'`.

- [ ] **Étape 3 : introduire un résultat typé**

Dans `apps/backend/app/services/card_link.py`, ajouter en tête (après les imports) :

```python
@dataclass(frozen=True)
class LinkResolution:
    """Lien resolu, avec sa provenance.

    `effective_linked_card_id` ne rendait qu'un UUID : l'appelant ne pouvait
    donc pas savoir s'il ecrivait un geste ou une hypothese. Le tuple est
    nomme pour que le sens ne se perde pas au premier refactor.
    """

    card_id: UUID | None
    origin: LinkOrigin | None

    @property
    def confirmed(self) -> bool:
        # Le selecteur et l'URL Philum sont des gestes explicites du createur.
        # La deduction par contenu ne l'est pas : elle attend son accord.
        return self.origin in (LinkOrigin.MANUEL, LinkOrigin.URL)
```

Ajouter `from dataclasses import dataclass` et `from app.models.source import LinkOrigin, Source` aux imports.

- [ ] **Étape 4 : écrire la nouvelle résolution**

Ajouter, en gardant `effective_linked_card_id` comme mince adaptateur :

```python
async def resolve_link(
    db: AsyncSession,
    *,
    chosen: UUID | None,
    url: str,
    user_id: UUID,
    current_card_id: UUID,
    doi: str | None = None,
) -> LinkResolution:
    """Le lien fiche d'une source, avec la provenance qui le qualifie."""
    if chosen is not None:
        await assert_linked_card_allowed(
            db, chosen, user_id=user_id, current_card_id=current_card_id
        )
        return LinkResolution(chosen, LinkOrigin.MANUEL)
    by_path = await resolve_linked_card_id(db, url, exclude_card_id=current_card_id)
    if by_path is not None:
        return LinkResolution(by_path, LinkOrigin.URL)
    by_content = await resolve_card_by_content(db, url, doi=doi, exclude_card_id=current_card_id)
    if by_content is not None:
        return LinkResolution(by_content, LinkOrigin.CONTENU)
    return LinkResolution(None, None)


async def effective_linked_card_id(
    db: AsyncSession,
    *,
    chosen: UUID | None,
    url: str,
    user_id: UUID,
    current_card_id: UUID,
    doi: str | None = None,
) -> UUID | None:
    """Compatibilite : le seul identifiant, sans sa provenance."""
    resolution = await resolve_link(
        db,
        chosen=chosen,
        url=url,
        user_id=user_id,
        current_card_id=current_card_id,
        doi=doi,
    )
    return resolution.card_id
```

- [ ] **Étape 5 : marquer le rattrapage en masse comme suggestion**

Dans `link_sources_designating_card`, remplacer le `.values(linked_card_id=card.id)` (ligne 202) par :

```python
        .values(
            linked_card_id=card.id,
            # Rattrapage en masse sur les sources d'autres createurs : personne
            # n'a valide ce lien, il ne peut donc pas se presenter comme un
            # fait. `link_confirmed_at` reste NULL exprès.
            link_origin=LinkOrigin.CONTENU.value,
        )
```

- [ ] **Étape 6 : écrire l'origine aux points d'appel**

```bash
cd apps/backend && grep -rn "effective_linked_card_id" app/
```

À chaque appel, remplacer par `resolve_link` et écrire les deux colonnes :

```python
    resolution = await resolve_link(
        db,
        chosen=payload.linked_card_id,
        url=payload.url,
        user_id=current_user.id,
        current_card_id=card.id,
        doi=payload.doi,
    )
    source.linked_card_id = resolution.card_id
    source.link_origin = resolution.origin.value if resolution.origin else None
    source.link_confirmed_at = _utcnow_naive() if resolution.confirmed else None
```

- [ ] **Étape 7 : relancer les tests**

```bash
cd apps/backend && CI=true uv run pytest tests/unit -q
```

Attendu : tout passe, y compris les tests existants de `card_link`.

- [ ] **Étape 8 : lint et commit**

```bash
cd apps/backend && uv run ruff check app/ && uv run mypy app/
git add apps/backend/app apps/backend/tests
git commit -m "feat: distinguer lien valide et lien suggere"
```

---

### Tâche D3 : endpoints de gestion des connexions

**Fichiers :**
- Créer : `apps/backend/app/api/v1/endpoints/card_connections.py`
- Modifier : `apps/backend/app/api/v1/router.py` (ou l'agrégateur de routes)
- Test : `apps/backend/tests/integration/test_card_connections.py`

Trois opérations, toutes réservées au propriétaire de la fiche :
- `GET /api/v1/cards/{card_id}/connections` : les connexions sortantes (sources de cette fiche qui désignent une fiche) et entrantes (sources d'autres fiches qui désignent celle-ci), avec leur origine et leur état de confirmation.
- `POST /api/v1/cards/{card_id}/connections/{source_id}/confirm` : valider une suggestion.
- `DELETE /api/v1/cards/{card_id}/connections/{source_id}` : retirer le lien (met `linked_card_id` à `NULL`, la source reste).

**Attention aux droits :** une connexion entrante appartient à la source d'un autre créateur. Le propriétaire de la fiche citée **ne doit pas** pouvoir modifier la bibliographie d'autrui. Il peut la voir, pas la trancher. Seul le propriétaire de la source (donc de la fiche citante) confirme ou retire.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
@pytest.mark.asyncio
async def test_liste_les_connexions_sortantes_et_entrantes(client, auth_headers, card_id):
    resp = await client.get(f"/api/v1/cards/{card_id}/connections", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "outgoing" in body and "incoming" in body
    for item in body["outgoing"]:
        assert set(item) >= {"source_id", "card_title", "origin", "confirmed", "editable"}


@pytest.mark.asyncio
async def test_confirmer_une_suggestion(client, auth_headers, card_id, suggested_source_id):
    resp = await client.post(
        f"/api/v1/cards/{card_id}/connections/{suggested_source_id}/confirm",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["confirmed"] is True


@pytest.mark.asyncio
async def test_retirer_un_lien_conserve_la_source(client, auth_headers, card_id, source_id, db):
    resp = await client.delete(
        f"/api/v1/cards/{card_id}/connections/{source_id}", headers=auth_headers
    )
    assert resp.status_code == 204
    source = await db.get(Source, source_id)
    assert source is not None
    assert source.deleted_at is None
    assert source.linked_card_id is None


@pytest.mark.asyncio
async def test_on_ne_touche_pas_la_biblio_d_autrui(client, other_auth_headers, card_id, source_id):
    """Voir une citation entrante n'autorise pas a la modifier."""
    resp = await client.delete(
        f"/api/v1/cards/{card_id}/connections/{source_id}", headers=other_auth_headers
    )
    assert resp.status_code == 403
```

- [ ] **Étape 2 : lancer pour voir échouer**

```bash
cd apps/backend && CI=true uv run pytest tests/integration/test_card_connections.py -q
```

Attendu : 404 sur toutes les routes.

- [ ] **Étape 3 : écrire l'endpoint**

Créer `apps/backend/app/api/v1/endpoints/card_connections.py` :

```python
"""Gestion des connexions fiche a fiche par leur createur.

Une connexion est portee par une source (`Source.linked_card_id`). Elle peut
etre un geste du createur ou une hypothese de la machine, et le createur doit
pouvoir trancher. Voir les citations entrantes ne donne aucun droit dessus :
la bibliographie d'un autre createur lui appartient.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.models.user import User
from app.schemas.card_connection import CardConnection, CardConnections

router = APIRouter()


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _owned_card(db: AsyncSession, card_id: UUID, user: User) -> BiblioCard:
    card = await db.get(BiblioCard, card_id)
    if card is None or card.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fiche introuvable")
    if card.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cette fiche ne vous appartient pas")
    return card


@router.get("/{card_id}/connections", response_model=CardConnections)
async def list_connections(
    card_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CardConnections:
    card = await _owned_card(db, card_id, user)

    outgoing_rows = await db.execute(
        select(Source, BiblioCard)
        .join(BiblioCard, Source.linked_card_id == BiblioCard.id)
        .where(
            Source.biblio_card_id == card.id,
            Source.linked_card_id.is_not(None),
            Source.deleted_at.is_(None),
        )
        .order_by(Source.position)
    )
    incoming_rows = await db.execute(
        select(Source, BiblioCard)
        .join(BiblioCard, Source.biblio_card_id == BiblioCard.id)
        .where(
            Source.linked_card_id == card.id,
            Source.deleted_at.is_(None),
            BiblioCard.deleted_at.is_(None),
        )
        .order_by(Source.created_at)
    )

    def _row(src: Source, other: BiblioCard, editable: bool) -> CardConnection:
        return CardConnection(
            source_id=src.id,
            source_title=src.title,
            source_url=src.url,
            card_id=other.id,
            card_title=other.title,
            card_slug=other.slug,
            stance=src.stance,
            origin=src.link_origin,
            confirmed=src.link_confirmed_at is not None,
            # Une citation entrante appartient a la bibliographie d'un autre
            # createur : la voir n'autorise pas a la trancher.
            editable=editable,
        )

    return CardConnections(
        outgoing=[_row(s, c, True) for s, c in outgoing_rows.all()],
        incoming=[_row(s, c, False) for s, c in incoming_rows.all()],
    )


@router.post("/{card_id}/connections/{source_id}/confirm", response_model=CardConnection)
async def confirm_connection(
    card_id: UUID,
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CardConnection:
    card = await _owned_card(db, card_id, user)
    source = await db.get(Source, source_id)
    if source is None or source.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source introuvable")
    if source.biblio_card_id != card.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cette source ne vous appartient pas")
    if source.linked_card_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette source ne designe aucune fiche")
    source.link_confirmed_at = _utcnow_naive()
    await db.flush()
    linked = await db.get(BiblioCard, source.linked_card_id)
    assert linked is not None
    return CardConnection(
        source_id=source.id,
        source_title=source.title,
        source_url=source.url,
        card_id=linked.id,
        card_title=linked.title,
        card_slug=linked.slug,
        stance=source.stance,
        origin=source.link_origin,
        confirmed=True,
        editable=True,
    )


@router.delete("/{card_id}/connections/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_connection(
    card_id: UUID,
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    card = await _owned_card(db, card_id, user)
    source = await db.get(Source, source_id)
    if source is None or source.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source introuvable")
    if source.biblio_card_id != card.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cette source ne vous appartient pas")
    # Retirer le lien, pas la source : la reference reste dans la
    # bibliographie, elle cesse seulement de designer une fiche Philum.
    source.linked_card_id = None
    source.link_origin = None
    source.link_confirmed_at = None
    await db.flush()
```

- [ ] **Étape 4 : créer le schéma**

Créer `apps/backend/app/schemas/card_connection.py` :

```python
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.models.source import LinkOrigin, SourceStance


class CardConnection(BaseModel):
    source_id: UUID
    source_title: str | None
    source_url: str
    card_id: UUID
    card_title: str
    card_slug: str
    stance: SourceStance | None
    # NULL = lien anterieur a la tracabilite : on ne sait pas d'ou il vient.
    origin: LinkOrigin | None
    confirmed: bool
    editable: bool


class CardConnections(BaseModel):
    outgoing: list[CardConnection]
    incoming: list[CardConnection]
```

- [ ] **Étape 5 : enregistrer le routeur**

```bash
cd apps/backend && grep -rn "include_router" app/api/v1/ | head
```

Ajouter, en suivant exactement le style des lignes voisines :

```python
api_router.include_router(card_connections.router, prefix="/cards", tags=["connections"])
```

- [ ] **Étape 6 : relancer les tests**

```bash
cd apps/backend && CI=true uv run pytest tests/integration/test_card_connections.py -q
```

- [ ] **Étape 7 : lint et commit**

```bash
cd apps/backend && uv run ruff check app/ && uv run mypy app/
git add apps/backend/app apps/backend/tests
git commit -m "feat: endpoints de gestion des connexions"
```

---

### Tâche D4 : l'écran de gestion des connexions

**Exigence explicite de l'utilisateur :** interface élégante, claire, intuitive. Traduction concrète :
- **Deux sections nettes** : « Fiches que vous citez » et « Fiches qui vous citent ». Jamais un tableau unique avec une colonne « sens ».
- **Les suggestions d'abord**, dans un encart distinct en tête de la section sortante, avec un compteur. Elles sont l'action à faire ; le reste est de la consultation.
- **Deux boutons par ligne au maximum** : « Confirmer » et « Retirer ». Pas de menu contextuel.
- **Aucune modale de confirmation** pour « Retirer » : l'action est réversible (le lien peut être reposé), une modale coûterait plus qu'elle ne protège. Afficher à la place une bande d'annulation pendant 8 secondes.
- **Les citations entrantes sont en lecture seule**, avec une mention explicite de la raison, pas des boutons grisés sans explication.

**Fichiers :**
- Créer : `apps/frontend/src/routes/dashboard/new/[card_id]/connexions/+page.svelte`
- Modifier : `apps/frontend/src/lib/api/` (client)
- Modifier : `apps/frontend/src/lib/components/ProgressSteps.svelte` (ajouter l'étape)

- [ ] **Étape 1 : ajouter les appels au client API**

Dans le module client des fiches (`grep -rn "cards = {" src/lib/api`), ajouter :

```ts
    connections: (cardId: string) =>
      request<CardConnections>(`/api/v1/cards/${cardId}/connections`),
    confirmConnection: (cardId: string, sourceId: string) =>
      request<CardConnection>(`/api/v1/cards/${cardId}/connections/${sourceId}/confirm`, {
        method: 'POST',
      }),
    removeConnection: (cardId: string, sourceId: string) =>
      request<void>(`/api/v1/cards/${cardId}/connections/${sourceId}`, { method: 'DELETE' }),
```

Adapter au helper `request` réellement utilisé dans ce fichier. Déclarer les types `CardConnection` et `CardConnections` en miroir du schéma Pydantic.

- [ ] **Étape 2 : créer la page**

Créer `apps/frontend/src/routes/dashboard/new/[card_id]/connexions/+page.svelte` :

```svelte
<script lang="ts">
  import { page } from '$app/state';
  import { api } from '$lib/api';
  import type { CardConnection, CardConnections } from '$lib/api/types';

  const cardId = $derived(page.params.card_id ?? '');

  let data = $state<CardConnections | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let undo = $state<{ sourceId: string; title: string } | null>(null);

  const suggestions = $derived(data?.outgoing.filter((c) => !c.confirmed) ?? []);
  const confirmed = $derived(data?.outgoing.filter((c) => c.confirmed) ?? []);

  async function load() {
    loading = true;
    error = null;
    try {
      data = await api.cards.connections(cardId);
    } catch (e) {
      error = "Impossible de charger les connexions de cette fiche.";
    } finally {
      loading = false;
    }
  }

  async function confirm(c: CardConnection) {
    await api.cards.confirmConnection(cardId, c.source_id);
    await load();
  }

  async function remove(c: CardConnection) {
    await api.cards.removeConnection(cardId, c.source_id);
    undo = { sourceId: c.source_id, title: c.card_title };
    setTimeout(() => {
      if (undo?.sourceId === c.source_id) undo = null;
    }, 8000);
    await load();
  }

  $effect(() => {
    if (cardId) void load();
  });
</script>

<svelte:head><title>Connexions de la fiche · Philum</title></svelte:head>

<section class="mx-auto max-w-3xl space-y-8 px-4 py-8">
  <header class="space-y-2">
    <h1 class="text-2xl font-semibold text-slate-900">Connexions entre fiches</h1>
    <p class="text-slate-600">
      Une connexion relie cette fiche à une autre fiche Philum. Certaines ont été proposées
      automatiquement parce que la référence désigne le même contenu ; à vous de les confirmer.
    </p>
  </header>

  {#if loading}
    <p class="text-slate-500">Chargement…</p>
  {:else if error}
    <p class="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-800">{error}</p>
  {:else if data}
    {#if suggestions.length > 0}
      <div class="rounded-lg border border-amber-300 bg-amber-50 p-4">
        <h2 class="mb-3 font-medium text-amber-900">
          {suggestions.length} connexion{suggestions.length > 1 ? 's' : ''} à vérifier
        </h2>
        <ul class="space-y-3">
          {#each suggestions as c (c.source_id)}
            <li class="flex items-start gap-3 rounded-md bg-white p-3">
              <div class="flex-1">
                <p class="font-medium text-slate-900">{c.card_title}</p>
                <p class="text-sm text-slate-600">
                  Proposée depuis votre référence : {c.source_title ?? c.source_url}
                </p>
              </div>
              <button
                type="button"
                class="rounded-md bg-emerald-600 px-3 py-1.5 text-sm text-white hover:bg-emerald-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-500"
                onclick={() => confirm(c)}
              >
                Confirmer
              </button>
              <button
                type="button"
                class="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-400"
                onclick={() => remove(c)}
              >
                Retirer
              </button>
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    <div>
      <h2 class="mb-3 font-medium text-slate-900">Fiches que vous citez</h2>
      {#if confirmed.length === 0}
        <p class="text-slate-500">Aucune connexion confirmée pour le moment.</p>
      {:else}
        <ul class="divide-y divide-slate-200 rounded-lg border border-slate-200">
          {#each confirmed as c (c.source_id)}
            <li class="flex items-center gap-3 p-3">
              <a class="flex-1 font-medium text-indigo-700 hover:underline" href="/@{c.card_slug}">
                {c.card_title}
              </a>
              <button
                type="button"
                class="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-400"
                onclick={() => remove(c)}
              >
                Retirer
              </button>
            </li>
          {/each}
        </ul>
      {/if}
    </div>

    <div>
      <h2 class="mb-1 font-medium text-slate-900">Fiches qui vous citent</h2>
      <p class="mb-3 text-sm text-slate-600">
        Ces connexions appartiennent à la bibliographie d'autres créateurs. Vous les voyez, vous ne
        pouvez pas les modifier.
      </p>
      {#if data.incoming.length === 0}
        <p class="text-slate-500">Personne ne cite encore cette fiche.</p>
      {:else}
        <ul class="divide-y divide-slate-200 rounded-lg border border-slate-200">
          {#each data.incoming as c (c.source_id)}
            <li class="p-3">
              <p class="font-medium text-slate-900">{c.card_title}</p>
              <p class="text-sm text-slate-600">{c.source_title ?? c.source_url}</p>
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  {/if}

  {#if undo}
    <div
      class="fixed bottom-4 left-1/2 -translate-x-1/2 rounded-md bg-slate-900 px-4 py-2 text-sm text-white shadow-lg"
      role="status"
    >
      Connexion retirée vers « {undo.title} ».
    </div>
  {/if}
</section>
```

**Note :** le lien `href="/@{c.card_slug}"` est incomplet, il manque le créateur. Ajouter `card_creator_slug` au schéma `CardConnection` côté backend (via la jointure sur `User` déjà présente dans `_load_cards`) et utiliser `href="/@{c.card_creator_slug}/{c.card_slug}"`. Corriger avant de committer.

- [ ] **Étape 3 : ajouter l'étape au parcours**

Dans `apps/frontend/src/lib/components/ProgressSteps.svelte`, ajouter une étape « Connexions » entre « Sources » et la publication. Lire d'abord la structure existante pour respecter le format des étapes.

- [ ] **Étape 4 : vérifier de bout en bout**

Backend et frontend lancés, avec un compte de dev :
1. Créer une fiche B dont `content_url` est le DOI d'une source déjà citée par une fiche A. À la publication de B, `link_sources_designating_card` doit poser une suggestion sur la source de A.
2. Ouvrir `/dashboard/new/<id-de-A>/connexions` : l'encart ambre affiche « 1 connexion à vérifier ».
3. Cliquer « Confirmer » : la ligne passe dans « Fiches que vous citez ».
4. Cliquer « Retirer » : la ligne disparaît, la bande d'annulation s'affiche 8 secondes, la source reste présente dans `/dashboard/new/<id-de-A>/sources`.
5. Ouvrir `/dashboard/new/<id-de-B>/connexions` : la connexion apparaît en « Fiches qui vous citent », sans bouton.

- [ ] **Étape 5 : lint et commit**

```bash
cd apps/frontend && pnpm check && pnpm lint && node scripts/check-emdash.mjs
git add apps/frontend/src
git commit -m "feat: ecran de gestion des connexions"
```

---

# LOT E — Corrections issues de l'étude « outils de recherche »

Ce lot applique trois conclusions de l'étude du 2026-08-06. Il est indépendant des lots A à D et peut être fait en parallèle.

**Les trois conclusions opérationnelles retenues :**
1. **COinS + Highwire meta tags, pas JSON-LD.** Le guide CDH Princeton de novembre 2025 a testé cinq mécanismes et retenu COinS, parce que seul `rft.genre` distingue un billet de blog d'un article, et parce que Zotero ignore entièrement JSON-LD. Une fiche Philum exposée en COinS devient sauvegardable dans Zotero en un clic, sans extension, sans compte.
2. **Les alertes de citation entrante** sont le meilleur crochet de rétention par unité d'effort de tout l'écosystème. `apps/backend/app/services/citations.py` fournit déjà `list_incoming_citations` et `mark_citations_seen` : il ne manque que la surface.
3. **`llms.txt` est mort** (Ahrefs : 97 % des fichiers de 137 000 sites n'ont reçu aucune requête en mai 2026). Le serveur MCP est le canal sérieux, et il existe déjà. Rien à faire, sinon **ne pas** créer de `llms.txt`.

### Tâche E1 : exposer chaque fiche en COinS et Highwire

**Fichiers :**
- Créer : `apps/frontend/src/lib/utils/coins.ts`
- Modifier : `apps/frontend/src/routes/@[creator]/[card]/+page.svelte`
- Test : `apps/frontend/src/lib/utils/__tests__/coins.test.ts`

- [ ] **Étape 1 : écrire le test qui échoue**

```ts
import { describe, expect, it } from 'vitest';
import { coinsTitle } from '../coins';

const carte = {
  title: 'À quoi sert le sommeil',
  content_authors: 'Mathias Pinault',
  published_at: '2026-05-12T10:00:00Z',
  content_url: 'https://www.youtube.com/watch?v=abc',
  format: 'video',
};

describe('coinsTitle', () => {
  it('declare le contexte OpenURL attendu par Zotero', () => {
    const t = coinsTitle(carte as never);
    expect(t).toContain('ctx_ver=Z39.88-2004');
    expect(t).toContain('rft_val_fmt=info%3Aofi%2Ffmt%3Akev%3Amtx%3Adc');
  });

  it('porte le genre, seul champ qui distingue un billet d un article', () => {
    expect(coinsTitle(carte as never)).toContain('rft.genre=');
  });

  it('encode le titre sans casser la chaine', () => {
    expect(coinsTitle(carte as never)).toContain(encodeURIComponent('À quoi sert le sommeil'));
  });
});
```

- [ ] **Étape 2 : lancer pour voir échouer**

```bash
cd apps/frontend && pnpm vitest run src/lib/utils/__tests__/coins.test.ts
```

- [ ] **Étape 3 : écrire le module**

Créer `apps/frontend/src/lib/utils/coins.ts` :

```ts
/**
 * COinS : métadonnées OpenURL cachées dans l'attribut `title` d'un `<span>`.
 *
 * Mécanisme retenu plutôt que JSON-LD parce que Zotero, qui est l'outil que
 * nos lecteurs n'abandonneront pas, ignore entièrement JSON-LD. Seul le champ
 * `rft.genre` permet de distinguer un billet de blog d'un article, ce qui est
 * exactement la distinction que Philum doit porter.
 *
 * Le contexte `mtx:dc` (Dublin Core) est plus permissif que `mtx:journal` :
 * une fiche documente aussi bien une vidéo qu'un rapport, et forcer un modèle
 * d'article produirait des métadonnées fausses.
 */
import type { PublicCard } from '$lib/api/types';

const GENRE_PAR_FORMAT: Record<string, string> = {
  video: 'unknown',
  audio: 'unknown',
  texte: 'article',
  data: 'dataset',
  image: 'unknown',
};

export function coinsTitle(card: PublicCard): string {
  const parts: string[] = [
    'ctx_ver=Z39.88-2004',
    `rft_val_fmt=${encodeURIComponent('info:ofi/fmt:kev:mtx:dc')}`,
    `rft.type=${encodeURIComponent(card.format ?? 'webpage')}`,
    `rft.genre=${encodeURIComponent(GENRE_PAR_FORMAT[card.format ?? ''] ?? 'unknown')}`,
    `rft.title=${encodeURIComponent(card.title)}`,
  ];
  if (card.content_authors) {
    for (const author of card.content_authors.split(',')) {
      const trimmed = author.trim();
      if (trimmed) parts.push(`rft.au=${encodeURIComponent(trimmed)}`);
    }
  }
  if (card.published_at) {
    parts.push(`rft.date=${encodeURIComponent(card.published_at.slice(0, 10))}`);
  }
  if (card.content_url) {
    parts.push(`rft_id=${encodeURIComponent(card.content_url)}`);
  }
  return parts.join('&');
}
```

- [ ] **Étape 4 : relancer le test**

```bash
cd apps/frontend && pnpm vitest run src/lib/utils/__tests__/coins.test.ts
```

- [ ] **Étape 5 : poser le COinS et les Highwire tags sur la page publique**

Dans `apps/frontend/src/routes/@[creator]/[card]/+page.svelte`, ajouter dans `<svelte:head>` :

```svelte
<svelte:head>
  <!-- Highwire Press tags : reconnus par Zotero, Mendeley et Google Scholar
       sans extension ni convention propriétaire. -->
  <meta name="citation_title" content={card.title} />
  {#if card.content_authors}
    {#each card.content_authors.split(',') as author (author)}
      <meta name="citation_author" content={author.trim()} />
    {/each}
  {/if}
  {#if card.published_at}
    <meta name="citation_publication_date" content={card.published_at.slice(0, 10)} />
  {/if}
  {#if card.content_url}
    <meta name="citation_public_url" content={card.content_url} />
  {/if}
</svelte:head>
```

Et dans le corps de la page, juste après le titre :

```svelte
<!-- COinS : invisible, lu par le connecteur Zotero. Le `<span>` doit être vide
     et porter la classe exacte `Z3988`, la spécification l'impose. -->
<span class="Z3988" title={coinsTitle(card)}></span>
```

- [ ] **Étape 6 : vérifier avec un vrai Zotero**

Installer le connecteur Zotero dans le navigateur, ouvrir une fiche publique en local, cliquer l'icône de sauvegarde. Attendu : l'élément est enregistré avec le bon titre, les bons auteurs et la bonne date. Si Zotero enregistre « Page Web » sans métadonnées, les tags ne sont pas lus : vérifier que le `<span>` est bien vide et que la classe est exactement `Z3988`.

- [ ] **Étape 7 : lint et commit**

```bash
cd apps/frontend && pnpm check && pnpm lint && pnpm vitest run
git add apps/frontend/src
git commit -m "feat: exposer les fiches en COinS et Highwire"
```

---

### Tâche E2 : surface des alertes de citation entrante

**Fichiers :**
- Modifier : `apps/frontend/src/routes/dashboard/+page.svelte`
- Modifier : `apps/frontend/src/lib/api/`

`apps/backend/app/services/citations.py` expose déjà `list_incoming_citations` (borné à `MAX_CITATIONS = 200`) et `mark_citations_seen`, et `User.citations_seen_at` existe. Vérifier d'abord si un endpoint les expose :

```bash
cd apps/backend && grep -rn "list_incoming_citations\|citations_seen" app/api/
```

- [ ] **Étape 1 : si aucun endpoint n'existe, en créer un**

`GET /api/v1/me/citations` renvoyant la liste, et `POST /api/v1/me/citations/seen` marquant la lecture. Suivre le style des endpoints de `users.py`.

- [ ] **Étape 2 : afficher un bandeau sur le tableau de bord**

En tête de `/dashboard`, avant la liste des fiches :

```svelte
{#if newCitations.length > 0}
  <div class="mb-6 rounded-lg border border-indigo-200 bg-indigo-50 p-4">
    <h2 class="font-medium text-indigo-900">
      {newCitations.length} nouvelle{newCitations.length > 1 ? 's' : ''} citation{newCitations.length >
      1
        ? 's'
        : ''} de vos fiches
    </h2>
    <ul class="mt-2 space-y-1 text-sm">
      {#each newCitations.slice(0, 5) as c (c.source_id)}
        <li>
          <a class="text-indigo-700 hover:underline" href="/@{c.creator_slug}/{c.card_slug}">
            {c.card_title}
          </a>
          cite votre fiche « {c.cited_card_title} »
        </li>
      {/each}
    </ul>
    <button
      type="button"
      class="mt-3 text-sm text-indigo-700 hover:underline"
      onclick={markSeen}
    >
      Marquer comme lu
    </button>
  </div>
{/if}
```

- [ ] **Étape 3 : vérifier**

Avec deux comptes de dev : le compte A publie une fiche citant une fiche du compte B. Le tableau de bord de B affiche le bandeau. « Marquer comme lu » le fait disparaître et il ne revient pas au rechargement.

- [ ] **Étape 4 : lint et commit**

```bash
cd apps/frontend && pnpm check && pnpm lint && node scripts/check-emdash.mjs
git add apps/frontend/src apps/backend/app
git commit -m "feat: alerter des citations entrantes"
```

---

### Tâche E3 : ne pas créer de `llms.txt`

- [ ] **Étape unique : consigner la décision**

Ajouter à `agent/DECISIONS.md` :

```markdown
## `llms.txt` écarté au profit de MCP (2026-08-06)

Ahrefs a mesuré en mai 2026 que 97 % des fichiers `llms.txt` de 137 000 sites
n'avaient reçu aucune requête. John Mueller (Google) parle d'une « béquille
temporaire ». Le serveur MCP Philum existe déjà et sert le même besoin avec un
protocole réellement consommé.

Décision : ne pas produire de `llms.txt`. Si la question revient, relire cette
entrée avant d'ouvrir le sujet.
```

```bash
git add agent/DECISIONS.md
git commit -m "docs: ecarter llms.txt au profit de MCP"
```

---

# LOT F — Chantiers de conception (documentation seule)

**Ce lot ne produit aucun code.** Il répond à trois demandes que l'utilisateur a lui-même qualifiées de « solutions à implémenter plus tard mais il faut commencer à identifier les pistes dès maintenant » et « gros chantier, donc simplement à planifier ».

**Garde-fou explicite de l'utilisateur, à respecter mot pour mot :** « Cette idée ne doit pas être une fausse promesse basée sur du vent, il faut donc que la certification / garantie / revendication Philum + sa fonction d'outil de traçabilité d'information soit techniquement vraie. »

### Tâche F1 : ADR sur la preuve d'autorat et l'anti-usurpation

**Fichiers :**
- Créer : `.docs/ADR-019-bis-preuve-autorat.md`
- Modifier : `agent/DECISIONS.md`

- [ ] **Étape 1 : lire l'existant avant d'écrire**

```bash
cd C:/Users/mathi/Documents/filum_project/filum && cat .docs/18-linked-accounts.md
```

Le document spécifie déjà v0 / v1 / v2 des comptes liés, avec un tableau de difficulté par plateforme, et `LinkedAccount.verified_at` / `verification_method` (`backlink`, `bio-code`, `oauth`) existent déjà en base. **Étendre ce document, ne pas le dupliquer.**

- [ ] **Étape 2 : écrire l'ADR**

Créer `.docs/ADR-019-bis-preuve-autorat.md` avec la structure suivante, en développant chaque point.

**Section 1 : ce que Philum peut prouver, et ce qu'il ne peut pas.**

C'est la section la plus importante, celle qui tient la promesse au niveau de ce qui est techniquement vrai.

Philum peut établir, et signer, ceci et rien de plus :

> À la date T, le compte C, qui avait démontré son contrôle du canal K, a déclaré être l'auteur du contenu situé à l'URL U.

Les trois éléments sont vérifiables indépendamment : la date par l'horodatage signé, le contrôle du canal par la méthode de vérification (`backlink`, `bio-code`, `oauth`), la déclaration par la signature de l'attestation (ADR-019 : triplet `(creator_id, content_url, attested_at)`).

Philum **ne peut pas** établir :
- que le contenu est authentique, non modifié, ou non généré ;
- que le déclarant est réellement l'auteur intellectuel du contenu, seulement qu'il contrôle le canal qui le diffuse ;
- qu'un contenu **non** attesté est faux.

**Formulation autorisée dans l'interface :** « Le titulaire du canal officiel a déclaré ce contenu le 12 mai 2026. » **Formulations interdites :** « contenu certifié authentique », « garanti par Philum », « vérifié ».

**Section 2 : le risque de revendication première.**

Un usurpateur qui revendique un contenu avant son auteur légitime obtiendrait l'antériorité. Trois protections, par ordre de force :

1. **La revendication n'est jamais suffisante seule.** Elle ne prend valeur qu'adossée à une preuve de contrôle du canal de diffusion (`LinkedAccount` vérifié pour le domaine ou la chaîne du contenu). Une revendication sans compte lié reste affichée comme « déclarée, non adossée à un canal vérifié ».
2. **Le registre des revendications est public.** Il l'était déjà par décision antérieure, et il faut le maintenir : une usurpation visible est une usurpation contestable. Documenter ici que la gratuité et la publicité du registre sont une propriété de sécurité, pas une décision commerciale.
3. **Procédure de contestation** : décrire les états (`revendiquée`, `contestée`, `arbitrée`), qui peut contester, sur quelles preuves, et sous quel délai. Ne pas implémenter, mais nommer les états pour que le modèle de données futur les accueille.

**Section 3 : types de compte, individus et organisations.**

Ouvrir explicitement la question posée par l'utilisateur. Points à trancher dans l'ADR :
- une colonne `account_kind` sur `users` (`individu` | `organisation`), nullable, `NULL` = non déclaré ;
- une organisation peut avoir plusieurs personnes habilitées : cela suppose une table de liaison, hors périmètre immédiat, mais la nommer ;
- la vérification d'une organisation passe par le contrôle du domaine (`rel=me` sur le site officiel), pas par une pièce d'identité. Philum ne doit **jamais** stocker de document d'identité : c'est une charge réglementaire disproportionnée et un risque de fuite sans contrepartie.

**Section 4 : création de compte hors Google.**

L'utilisateur demande de rouvrir le sujet. Lister les options, avec leur coût réel, sans trancher : e-mail + mot de passe (coût : réinitialisation, hachage, rate limiting, vérification d'adresse), lien magique par e-mail (moins de surface, dépendance à la délivrabilité), OAuth supplémentaires (GitHub, ORCID). **Noter qu'ORCID est le seul qui apporte une information d'identité vérifiée exploitable pour la vérification d'un chercheur.**

- [ ] **Étape 3 : consigner dans DECISIONS.md**

Ajouter une entrée renvoyant à `.docs/ADR-019-bis-preuve-autorat.md` et rappelant la règle de formulation autorisée.

- [ ] **Étape 4 : commit**

```bash
git add .docs/ADR-019-bis-preuve-autorat.md agent/DECISIONS.md
git commit -m "docs: ADR preuve d'autorat et anti-usurpation"
```

---

### Tâche F2 : spécification des profils publics et du feed

**Fichiers :**
- Créer : `.docs/20-profils-et-feed.md`

**Constat utilisateur :** « des profils publics qui peuvent être cherchés avec l'accès à leurs fiches ; un feed d'actualité public qui annonce les liens et les fiches partagés, un peu comme un réseau social, mais l'objectif est de tracer les dates de publication des fiches sur un feed visible publiquement. »

- [ ] **Étape 1 : inventorier l'existant**

```bash
cd apps/frontend && ls src/routes/@\[username\] src/routes/discover 2>/dev/null; grep -rn "discover" src/lib/api | head
```

`/@[username]` et `/discover` existent déjà. La spécification doit dire ce qui manque, pas redécrire ce qui est là.

- [ ] **Étape 2 : écrire la spécification**

Points à couvrir :

**Recherche de profils.** Aujourd'hui `/discover` liste des fiches. Il manque une recherche par créateur. Définir : champs indexés (nom affiché, nom d'utilisateur, description), et surtout **ce qui n'est pas indexé** (les fiches privées, les brouillons).

**Le feed : sa raison d'être n'est pas sociale.** L'utilisateur l'a dit lui-même : « l'objectif est de tracer les dates de publication des fiches sur un feed visible publiquement ». Écrire cette phrase dans la spécification et en tirer les conséquences de conception :
- l'ordre est **chronologique strict**, jamais algorithmique. Un feed classé par engagement cesserait d'être une trace ;
- pas de compteurs de popularité, pas de « likes », pas de recommandations. Ils transformeraient l'horodatage en concours ;
- une entrée est **immuable** : elle enregistre qu'une fiche a été publiée à une date. Si la fiche est ensuite modifiée ou dépubliée, l'entrée reste, éventuellement marquée. C'est la même logique que l'attestation de contenu (ADR-019).

**Ce que le feed rend possible et qui n'existe nulle part ailleurs.** L'étude a établi (front 6, CHI 2024, Viblio) que publier une bibliographie pour une audience est un vide réel et documenté, et que les spectateurs traitent une description YouTube comme un signal d'effort, pas comme une source vérifiable. Le feed est la surface publique qui manque. Le noter explicitement, avec la référence, pour que la priorité soit défendable.

**Modèle de données esquissé** (à ne pas implémenter) : une table `feed_events` avec `(id, kind, actor_user_id, card_id, occurred_at)`, `kind` valant `card_published` en v1. Les autres types (`card_updated`, `claim_verified`) sont nommés mais pas ouverts.

**Vie privée.** Une fiche privée n'entre jamais dans le feed. Une fiche publiée puis passée en privé doit-elle disparaître du feed ? Poser la question dans `.docs/07-open-questions.md` plutôt que de trancher seul.

- [ ] **Étape 3 : ajouter la question ouverte**

Dans `.docs/07-open-questions.md`, ajouter la question de la rétroactivité du feed sur une fiche dépubliée.

- [ ] **Étape 4 : commit**

```bash
git add .docs/20-profils-et-feed.md .docs/07-open-questions.md
git commit -m "docs: spec des profils publics et du feed"
```

---

### Tâche F3 : la garantie d'authenticité face aux faux et à l'ingérence

**Fichiers :**
- Modifier : `.docs/ADR-019-bis-preuve-autorat.md` (section supplémentaire)

**Constat utilisateur :** un faux reportage attribué à un média (l'exemple donné est une fausse vidéo Blast) doit pouvoir être démenti ; un média doit pouvoir partager sa fiche certifiée, revendiquée avec vérification d'identité ; les générateurs de faux ne doivent pas pouvoir revendiquer un contenu dont ils ne sont pas les auteurs.

- [ ] **Étape 1 : écrire la chaîne de raisonnement honnête**

Ajouter une section à `.docs/ADR-019-bis-preuve-autorat.md` établissant, dans cet ordre :

1. **Philum ne détecte pas les faux.** Aucune analyse de contenu, aucune détection de génération. Toute promesse en ce sens serait fausse.
2. **Ce qui fonctionne réellement est l'argument par l'absence**, et il ne fonctionne que sous une condition stricte : si un média attesté **systématiquement** toutes ses publications, alors l'absence d'attestation devient un signal. Sans systématicité, l'absence ne prouve rien.
3. **Cette condition est le vrai produit.** Elle demande que l'attestation soit assez peu coûteuse pour être faite à chaque publication, ce qui renvoie à l'automatisation de l'attestation, pas à une fonctionnalité de détection.
4. **La vérification du canal est ce qui empêche le pirate de revendiquer.** Un générateur de faux ne contrôle pas le domaine du média ni sa chaîne : il ne peut donc pas produire de `LinkedAccount` vérifié, et sa revendication reste affichée comme non adossée.

- [ ] **Étape 2 : écrire les formulations d'interface autorisées**

Dresser la liste, à réutiliser telle quelle dans le frontend :

| Situation | Texte autorisé |
|---|---|
| Attestation signée + canal vérifié | « Déclaré par le titulaire du canal officiel le {date}. » |
| Attestation signée, canal non vérifié | « Déclaré par {compte} le {date}. Le canal de diffusion n'a pas été vérifié. » |
| Aucune attestation | « Aucune déclaration d'autorat sur Philum pour ce contenu. » (jamais « contenu suspect ») |

- [ ] **Étape 3 : croiser avec l'immuabilité du payload**

Rappeler l'invariant ADR-019 : le payload signé d'une attestation de contenu est immuable, aucun champ ne peut être ajouté ou retiré sans ADR et sans plan de ré-attestation. Toute idée de la section précédente qui supposerait d'enrichir le payload doit passer par là.

- [ ] **Étape 4 : commit**

```bash
git add .docs/ADR-019-bis-preuve-autorat.md
git commit -m "docs: perimetre honnete de la garantie Philum"
```

---

# Ordre d'exécution recommandé

1. **Lot A** (3 tâches, frontend seul, aucun risque) — livrable immédiat, améliore le graphe avant d'y toucher plus profondément.
2. **Lot B** (5 tâches) — le cœur de la demande. B5 touche le backend, prévoir un déploiement.
3. **Lot C** (3 tâches) — migration `026_card_ref`.
4. **Lot D** (4 tâches) — migration `027_link_prov`, dépend de C pour l'ordre des migrations.
5. **Lot E** (3 tâches) — indépendant, peut être intercalé n'importe quand.
6. **Lot F** (3 tâches) — documentation, aucun déploiement, peut être fait en attendant une revue.

**Une PR par lot.** Les lots C et D empilent des migrations : si la PR du lot C n'est pas encore mergée quand celle du lot D est ouverte, rebaser immédiatement après le merge de C, sans attendre, et vérifier que `down_revision` du `027` pointe bien sur `026_card_ref`.

# Vérification finale, avant de clore

- [ ] `cd apps/backend && CI=true uv run pytest tests/unit tests/integration -q` — tout passe
- [ ] `cd apps/backend && uv run ruff check app/ alembic/ && uv run mypy app/` — aucune erreur
- [ ] `cd apps/backend && uv run alembic upgrade head && uv run alembic current` — tête à `027_link_prov`
- [ ] `cd apps/frontend && pnpm check && pnpm lint && pnpm vitest run && pnpm build` — aucune erreur
- [ ] `cd apps/frontend && node scripts/check-emdash.mjs` — aucun em-dash visible
- [ ] Sur `/@mathias-pinault/ca-sert-a-quoi-de-dormir` : les flèches disent le sens, « Replay… » pointe vers « Synaptic tagging… », le sélecteur de sens filtre, seules les fiches à un saut s'affichent au chargement, la légende se referme, les liens caractérisés sont fins
- [ ] Une source liée à une fiche ouvre « ★ Ouvrir la fiche Philum » depuis son encadré
- [ ] `/dashboard/new/<id>/connexions` liste les suggestions, les confirme, les retire, et refuse de toucher aux citations entrantes
- [ ] Le connecteur Zotero enregistre une fiche publique avec son titre, ses auteurs et sa date
- [ ] **Mettre à jour `STATE.md`** : c'est le contrat de continuité du projet, aucune session ne se ferme sans

# Hors périmètre, volontairement

- **Implémentation** des chantiers du lot F : l'utilisateur a demandé d'identifier les pistes, pas de les construire.
- **Dépréciation de `content_type` et `platform`** sur `BiblioCard` au profit de `format` / `category` / `author_kind` : chantier séparé, avec migration de données.
- **Table de liaison organisation ↔ personnes habilitées** : nommée dans l'ADR F1, non ouverte.
- **Reprise du grain `Assertion`** (affirmation ↔ empan verbatim) : suspendue jusqu'à décision explicite de l'utilisateur.


