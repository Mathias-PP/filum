# 05 — Design system

> ⚠️ **Refonte taxonomie ADR-020 (2026-05-14)** : la palette « par `source_type` » documentée plus bas (peer-reviewed vert, institutional bleu, etc.) est **obsolète**. Le graphe et les badges principaux sont désormais colorés par `author_kind` (9 entrées) ; `format` et `category` ont des badges neutres slate. Source de vérité : `apps/frontend/src/lib/utils/author-colors.ts`. Voir `DECISIONS.md` ADR-020.

> Couleurs, typographie, composants, principes esthétiques, inspirations.

---

## Principes esthétiques

Le projet a un défi inhabituel : **rendre la bibliographie désirable**. Une chose perçue comme aride, fastidieuse, académique. Le design doit la rendre belle, aérée, intelligente, presque ludique à explorer.

Quatre principes de référence :

1. **Densité informationnelle, mais respiration.** Beaucoup d'information à présenter, mais jamais surchargée. Recherche d'équilibre entre densité et calme visuel.

2. **Éditorial, pas applicatif.** L'esthétique de référence est celle d'un magazine intellectuel (Le Monde Diplomatique, Stratechery, Aeon, The Atlantic) plutôt que celle d'un SaaS (Slack, Linear, Notion). Le titre en serif est un marqueur fort.

3. **Sobriété chromatique.** Le projet n'utilise pas la couleur pour décorer. La couleur a toujours un sens (type de source, statut). Le reste est noir, blanc, gris très clair.

4. **Le graphe est la star.** Pas un élément parmi d'autres, le centre de l'expérience. Doit donner envie d'explorer.

---

## Inspirations directes

| Source | Ce qu'on en prend |
|---|---|
| **Obsidian Graph View** | Vue graphique des sources, navigation, halo sur les nœuds principaux |
| **Pappers.fr** | Cartographie des relations entre entités, sobriété visuelle, densité informationnelle maîtrisée |
| **Are.na** | Esthétique éditoriale, sobriété, valorisation des références |
| **Stratechery / Aeon** | Typographie éditoriale, serif sur les titres, hiérarchie classique |
| **Linear** | Sobriété de l'UI, minimalisme assumé (pour les écrans applicatifs) |
| **Notion** | Densité agréable, dépliage in-place pour la liste de sources |
| **Perma.cc** | Référence académique pour la pérennité des liens, mais Filum est plus contemporain visuellement |
| **Reuters Institute / journalism.org** | Esthétique sérieuse et institutionnelle pour le badge "vérifié" |

---

## Couleurs

### Palette neutre

```
--bg-primary:   #FFFFFF    blanc pur (fond principal)
--bg-secondary: #FAFAF7    blanc cassé légèrement chaud (cartes)
--bg-tertiary:  #F1EFE8    fond panneau, hover
--text-primary: #1A1A1A    presque noir, pour le texte principal
--text-second:  #555555    gris moyen, pour le texte secondaire
--text-tertiary:#888888    gris clair, pour les hints
--border:       #E8E6DE    bordures discrètes (0.5px par défaut)
--border-strong:#CFCDC4    bordures actives ou hover
```

### Palette sémantique (par type de source)

Inspirée des couleurs Anthropic, choisies pour porter du sens informationnel et rester douces.

```
peer-reviewed (vert)    fill: #C0DD97  stroke: #639922  text: #173404
institutional (bleu)    fill: #B5D4F4  stroke: #378ADD  text: #042C53
press (ambre)           fill: #FAC775  stroke: #EF9F27  text: #412402
original (violet)       fill: #CECBF6  stroke: #7F77DD  text: #26215C
```

### Palette d'état

```
success (vérifié, archivé, signé)   #1D9E75   bg léger: #E1F5EE
warning (en cours, en attente)      #BA7517   bg léger: #FAEEDA
danger (erreur, non vérifié)        #A32D2D   bg léger: #FCEBEB
info (badge, lien)                  #185FA5   bg léger: #E6F1FB
```

### Mode sombre

Prévu pour la phase 2. Conception initiale orientée mode clair, mais en utilisant des variables CSS pour faciliter la bascule.

---

## Typographie

### Familles

- **Sans-serif (par défaut)** : `Inter` — gratuite, lisible, moderne. Fallback : `system-ui`.
- **Serif (titres éditoriaux)** : `Source Serif 4` ou `Crimson Pro` — gratuites, élégantes, lisibles à l'écran. Fallback : `Georgia`.
- **Mono (code, hashs, slugs)** : `JetBrains Mono` ou `IBM Plex Mono`. Fallback : `Consolas, monospace`.

### Échelle

```
Display (rare, hero homepage)  : 40-48px / 1.1 / serif / weight 500
H1 (titre fiche, page-identité): 26-32px / 1.2 / serif / weight 500
H2 (sections principales)      : 20-22px / 1.3 / sans / weight 500
H3 (sous-sections)             : 16-18px / 1.4 / sans / weight 500
Body                           : 15-16px / 1.6 / sans / weight 400
Body small                     : 13-14px / 1.5 / sans / weight 400
Caption (labels, hints)        : 11-12px / 1.4 / sans / weight 500 / letter-spacing: 0.04em / uppercase pour les labels de section
Mono (hash, code)              : 12-13px / 1.4 / mono
```

### Recommandations d'usage

- Tous les titres en **sentence case**, jamais Title Case ni ALL CAPS
- ALL CAPS réservé aux labels de section très courts (`fiche bibliographique · ...`)
- Pas de gras au milieu d'une phrase (réservé aux titres et labels)
- Justification : laisser le texte se mettre normalement, ne pas forcer la justification

---

## Composants

### Cartes (cards)

```
background: var(--bg-primary)
border: 0.5px solid var(--border)
border-radius: 12px
padding: 1.25rem-1.5rem
```

Pas d'ombres portées. La séparation se fait par la bordure fine.

### Boutons

Trois variants seulement :

**Primary** :
```
background: var(--text-primary)  (presque noir)
color: white
padding: 8px 16px
border-radius: 6px
font-weight: 500
font-size: 14px
```

**Secondary** :
```
background: transparent
border: 0.5px solid var(--border-strong)
color: var(--text-primary)
... (idem)
```

**Tertiary** (link-like) :
```
background: transparent
border: none
color: var(--info)
text-decoration: underline
```

### Tags / badges

```
font-size: 10-11px
padding: 2-3px 7-8px
border-radius: 8px
font-weight: 500
```

Variations selon le sens (couleur de bg + couleur de texte de la palette sémantique correspondante).

### Inputs

```
background: var(--bg-primary)
border: 0.5px solid var(--border)
border-radius: 6px
padding: 8-10px 12px
font-size: 14px
height: 36px (pour les inputs uniques)
focus: outline 2px var(--info)
```

### Sources dans la liste

Format inspiré des bibliographies académiques :

```
01    [point coloré]    Titre de la source en weight 500
                        Auteurs · Publication · Date
                        Annotation contextuelle (en italique, in-place quand déplié)
                        [tags]
```

Numérotation en serif, point coloré par type, titre en sans-serif weight 500.

---

## Le graphe interactif — choix techniques

**Lib** : D3.js pour le calcul du layout (force simulation), SVG natif pour le rendu, pas de canvas.

**Layout** : force-directed avec :
- Force de répulsion entre nœuds
- Force d'attraction sur les liens
- Force de centrage faible
- Nœud central (la vidéo) ancré au milieu, taille la plus grande

**Interactions** :
- Drag pour repositionner un nœud
- Click pour ouvrir la fiche compacte
- Hover pour highlight les liens connectés
- Boutons zoom + / - / recentrer

**Animations** :
- Au chargement : nœuds apparaissent en cascade (50ms entre chacun) pour effet "constellation qui s'illumine"
- À l'ouverture d'une fiche compacte : transition douce
- Pas d'animations gratuites

**Performance** : pour 100 nœuds ou moins (cas réaliste d'une fiche), pas d'optimisation nécessaire. Au-delà (vue agrégée d'un créateur, phase 2), considérer un layout pré-calculé en backend.

---

## Tailwind config

Le projet utilise Tailwind CSS avec une configuration minimaliste. La palette ci-dessus est exposée comme couleurs custom Tailwind. Pas de plugins UI (pas de `@tailwindcss/forms` etc.).

Configuration de base :

```js
// tailwind.config.js
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: '#FFFFFF',
          secondary: '#FAFAF7',
          tertiary: '#F1EFE8',
        },
        text: {
          primary: '#1A1A1A',
          secondary: '#555555',
          tertiary: '#888888',
        },
        border: {
          DEFAULT: '#E8E6DE',
          strong: '#CFCDC4',
        },
        peer: { fill: '#C0DD97', stroke: '#639922', text: '#173404' },
        inst: { fill: '#B5D4F4', stroke: '#378ADD', text: '#042C53' },
        press: { fill: '#FAC775', stroke: '#EF9F27', text: '#412402' },
        orig: { fill: '#CECBF6', stroke: '#7F77DD', text: '#26215C' },
        success: { DEFAULT: '#1D9E75', bg: '#E1F5EE' },
        warning: { DEFAULT: '#BA7517', bg: '#FAEEDA' },
        danger: { DEFAULT: '#A32D2D', bg: '#FCEBEB' },
        info: { DEFAULT: '#185FA5', bg: '#E6F1FB' },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        serif: ['"Source Serif 4"', 'Georgia', 'serif'],
        mono: ['"JetBrains Mono"', 'Consolas', 'monospace'],
      },
      borderRadius: {
        DEFAULT: '6px',
        md: '8px',
        lg: '12px',
        xl: '16px',
      },
    },
  },
};
```

---

## Mobile responsive

En MVP, l'objectif est que :
- La page d'accueil est totalement responsive
- La page publique de fiche est lisible sur mobile, avec le graphe simplifié (mode liste seulement, ou graphe scrollable horizontalement)
- Le dashboard créateur est responsive mais optimisé pour desktop (la création de fiche est un geste plutôt fait sur ordinateur)

Breakpoints standards Tailwind : `sm` 640px, `md` 768px, `lg` 1024px, `xl` 1280px.

---

## Accessibilité

Engagement minimum WCAG AA :
- Contrastes vérifiés (palette ci-dessus est conçue pour ça)
- Navigation clavier complète
- `aria-label` sur les boutons icône
- Focus visible
- Pas de carrousels auto-scrolling
- Texte alternatif sur les images significatives

---

*Pour le plan de développement détaillé, voir [`06-roadmap.md`](./06-roadmap.md).*
