# Audit 01. OmniRoute → Philum : repli automatique de fournisseur

> [OmniRoute](https://github.com/diegosouzapw/OmniRoute) : Gateway API open-source (MIT, TypeScript, 58 430 étoiles) annonçant 350 fournisseurs et 1 200 modèles. Routing avec combos, circuit breaker, scoring multi-facteurs.

> **Vérifié le 2026-08-30.** Le dépôt, la licence et les chemins `open-sse/services/autoCombo/*.ts` existent bien. Deux chiffres de la première rédaction étaient faux : le scoring compte **12** facteurs (`ScoringFactors` dans `scoring.ts`), pas 15, et `freeModelCatalog.ts` fait **275** lignes, pas 455, les données étant déportées dans `freeModelCatalog.data.ts`.

---

## 1. Ce qu'OmniRoute fait

### Architecture centrale

```
Request → Parse model prefix ("auto/coding") → CreateVirtualAutoCombo
  → Build candidate pool from active connections
  → Filter: resilience blocked? paid-only? ToS avoid? strict-zero-cost?
  → Score all candidates with 12-factor function
  → Select top candidate (or explore 5% randomly)
  → Try request → if fail:
    Layer 3: Lock this model
    Layer 2: Cool down this connection
    Layer 1: Trip provider breaker
    → Combo routes to next candidate
  → If all fail → return error
```

### Fichiers clés

| Fichier | Rôle |
|---|---|
| `open-sse/services/autoCombo/virtualFactory.ts` | Construction dynamique du pool de candidats |
| `open-sse/services/autoCombo/scoring.ts` | Fonction de scoring 12 facteurs |
| `open-sse/services/autoCombo/engine.ts` | Logique de sélection, exploration bandit |
| `open-sse/services/accountFallback.ts` | Décision de fallback |
| `open-sse/services/combo.ts` | Moteur de routing central |
| `open-sse/services/autoCombo/strictZeroCostFilter.ts` | Filtrage strict zero-cost |
| `docs/architecture/RESILIENCE_GUIDE.md` | Modèle de résilience 3 couches |
| `docs/routing/AUTO-COMBO.md` | Documentation du système de combos |
| `open-sse/config/freeModelCatalog.ts` | Catalogue de free tiers (275 lignes, données dans `freeModelCatalog.data.ts`) |

---

## 2. Patterns pertinents pour Philum

### Pattern 1 : Virtual Combo Factory (zero-config)

**Concept** : Construit dynamiquement les combos de providers sans création manuelle. Les providers ajoutés élargissent automatiquement le pool.

```typescript
// Extrait virtualFactory.ts
export async function createVirtualAutoCombo(
  variant: AutoVariant | undefined,
  spec?: AutoComboSpec,
  apiKeyId?: string,
): Promise<VirtualAutoCombo> {
  // 1. Pull all active provider connections from DB
  // 2. Filter to those with valid credentials
  // 3. Cross-reference with provider registry
  // 4. Build VirtualAutoComboCandidate for each
  // 5. Score using 12-factor function
  // 6. Return in-memory AutoComboConfig (never persisted)
}
```

**Application Philum** : Le mode gratuit `choisir_lane()` ne sélectionne qu'une lane. Le fallback auto construirait un pool dynamique : default BYOK → free lanes (Z.ai) → discovery (DeepSeek) → error.

### Pattern 2 : Circuit breaker 3 couches

**Concept** : Trois niveaux indépendants gèrent différentes portées d'échec.

| Couche | Portée | Seuils | Reset |
|---|---|---|---|
| Circuit Breaker | Provider entier | OAuth 10x / API-key 15x / Local 2x | 60s/30s/15s → HALF_OPEN |
| Connection Cooldown | Une clé/compte | Base 5s OAuth / 3s API-key | Exponentiel ×2 |
| Model Lockout | Un modèle | 429, 404, mode denied | Success-decay |

**Application Philum** : Le cooldown actuel (10 min, provider-level) est trop grossier. Un rate-limit sur un modèle ne devrait pas tuer tout le provider.

### Pattern 3 : Headers de transparence

**Concept** : Chaque réponse porte les décisions de routing.

```
X-OmniRoute-Decision: strategy=auto; provider=openai; model=gpt-4o; latency=245ms
X-OmniRoute-Selected-Connection-Id: conn_abc123
```

**Application Philum** : Les SSE events portent déjà le modèle, mais pas le provider ni la stratégie. Ajouter un event `provider_changed` ou enrichir `done` avec `provider`, `model`, `strategy`.

### Pattern 4 : Strict zero-cost filtering

**Concept** : Ne router que vers les providers où l'utilisateur a confirmé l'accès gratuit, avec 1% de marge.

```typescript
const strictFilteredPool = filterStrictZeroCostCandidates(pool, {
  enabled: settings.freeAccessPolicy === "strict",
  resolveFreeAccessState,
  minRemainingAllowance: 1, // 1% headroom
  maxStateAgeMs: 180 * 1000,
});
```

**Application Philum** : Le mode gratuit devrait vérifier que la lane a encore du quota avant de la proposer, pas juste vérifier qu'elle n'est pas en cooldown.

### Pattern 5 : Success-decay recovery

**Concept** : Le lockout d'un modèle n'expire pas seulement sur timer : une réponse saine divise le compteur d'échec par 2.

```typescript
export function decayModelFailureCount(...): DecayResult {
  const newFailureCount = Math.floor(failure.failureCount / 2);
  if (newFailureCount === 0) {
    modelFailureState.delete(key);
    return { cleared: true, newFailureCount: 0 };
  }
}
```

**Application Philum** : Le cooldown actuel (10 min fixe) pourrait être remplacé par un decay : un provider qui reçoit un 429 récupère plus vite s'il redevient sain.

---

## 3. Ce qui n'est PAS pertinent pour Philum

| Pattern OmniRoute | Pourquoi pas |
|---|---|
| Scoring 12 facteurs | Philum a trois à cinq providers, pas trois cent cinquante : l'ordre suffit, le score est du poids mort |
| Strategies (19 au total) | Philum n'a pas besoin de weighted round-robin ou fusion |
| SQLite pour tout | Philum utilise PostgreSQL : pas de changement |
| Single-tenant | Philum est multi-tenant : nécessite adaptation |
| Electron desktop | Philum est web-only |

---

## 4. Plan d'implémentation recommandé

### Phase A : Fallback auto (3 jours)

C'est la seule phase des trois audits qui répare une panne en cours plutôt que d'ajouter une capacité : le mode gratuit est à l'arrêt sur le solde Z.ai, et comme rien ne bascule vers un autre provider, l'arrêt est total. À traiter en premier pour cette raison seule.

| # | Tâche | Fichiers Philum |
|---|---|---|
| A1 | Modéliser la chaîne de fallback : `default BYOK → free lanes → discovery → error` | `agent_chat.py` |
| A2 | Implémenter `choisir_pool()` : construit un pool ordonné de providers candidats | `agent_gratuit.py` (nouveau) |
| A3 | Modifier `_appel_provider()` pour accepter un pool et essayer le suivant en cas d'échec | `agent.py` |
| A4 | Ajouter le circuit breaker model-level (lockout par modèle, pas par provider) | `agent_gratuit.py` |

### Phase B : Transparence (1 jour)

| # | Tâche | Fichiers Philum |
|---|---|---|
| B1 | Ajouter event SSE `provider_changed` quand le fallback switch de provider | `agent.py` |
| B2 | Enrichir l'event `done` avec `provider`, `model`, `strategy` | `agent.py` |
| B3 | Afficher le provider actuel dans ChatPanel (badge ou tooltip) | `ChatPanel.svelte` |

### Phase C : Strict zero-cost (1 jour)

| # | Tâche | Fichiers Philum |
|---|---|---|
| C1 | Vérifier le quota restant de la lane avant de la proposer (pas juste cooldown) | `agent_gratuit.py` |
| C2 | Ajouter un seuil de headroom (1% minimum) pour éviter les 429 de justesse | `agent_gratuit.py` |

---

## 5. Patterns à copier directement

1. **Success-decay** : le code est petit (<20 lignes), applicable tel quel
2. **Headers de transparence** : pattern SSE existant chez Philum, enrichir le payload
3. **Virtual combo factory** : adapter le concept au modèle lane-based existant

---

## 6. Risques

| Risque | Mitigation |
|---|---|
| Le fallback multi-provider augmente la latence (essais successifs) | Ne basculer que sur un refus caractérisé (429, 5xx, solde épuisé, clé refusée), jamais sur une lenteur. Un timeout court par essai, tel que les 5 s de la première rédaction, couperait des réponses saines : un tour d'agent qui appelle des outils dépasse largement cette durée. Le budget se borne au nombre de providers essayés, pas au temps de chacun. |
| Le scoring ajoute de la complexité | Commencer sans scoring (fifo), ajouter le scoring plus tard |
| Les providers gratuits ont des quotas différents | Le quota par lane est déjà modélisé (`AgentLaneUsage`) |

---

_Audit réalisé le 2026-08-30. Source : https://github.com/diegosouzapw/OmniRoute_
