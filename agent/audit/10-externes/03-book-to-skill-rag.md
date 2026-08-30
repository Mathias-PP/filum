# Audit 03. book-to-skill → Philum : découpe et assainissement des sources

> [book-to-skill](https://github.com/virgiliojr94/book-to-skill) : Convertit des livres techniques en « skills » Markdown structurés pour agents IA. MIT, Python, 27 224 étoiles. Extraction déterministe sans LLM, parsers PDF, EPUB, DOCX, RTF, HTML, Calibre, sanitisation Unicode.

> **Vérifié le 2026-08-30, et c'est la fiche la plus corrigée des trois.** Le dépôt, la licence, le compte d'étoiles et `book_to_skill/sanitize.py` (150 lignes, bloc de tags et algorithme bidi) sont confirmés. En revanche le **chunking sémantique multilingue n'existe pas dans ce dépôt** : aucun fichier n'y contient « chunk » ni « segment », et `SKILL.md` (724 lignes) n'en parle pas. Les patrons 1, 2 et 4 ci-dessous décrivent donc du code que personne n'a lu. Ils sont conservés comme idées, plus comme relevé, et les phases A et B qu'ils justifiaient sont abandonnées : Philum a déjà `services/chunker.py`, déterministe, sans réseau ni clé, qui ne coupe qu'aux frontières de phrase et de paragraphe et rend les positions `start`/`end`.

---

## 1. Ce que book-to-skill fait

### Architecture centrale

```
Livre (PDF/EPUB/DOCX/HTML/RTF) → Détection format
  → Extraction texte (4 backends PDF)
  → Détection structure multilingue (numérotation, headers, TOC)
  → Validation de structure (seuils de cohérence)
  → Budget adaptatif (type × profondeur)
  → Chunking sémantique (sections naturelles, pas taille fixe)
  → Sortie : SKILL.md (index) + chapters/*.md (contenu)
```

### Fichiers clés

| Fichier | Rôle |
|---|---|
| `book_to_skill/utils.py` | `detect_structure()`, `_numbered_titles_are_structural()` |
| `book_to_skill/parsers/pdf.py` | Extraction PDF (4 backends) |
| `book_to_skill/parsers/html.py` | Extraction HTML |
| `book_to_skill/sanitize.py` | Sanitisation Unicode invisible |
| `tools/discovery_tax.py` | Estimation token hybride (Latin/CJK) |
| `SKILL.md` | Spec de structuration (étapes 3, 7, 9) |

---

## 2. Patterns pertinents pour Philum

### Pattern 1 : Détection de structure multilingue

**Concept** : Détecte la numérotation et les headers dans le texte brut, AVANT tout traitement LLM.

```python
def detect_structure(text: str, lang: str) -> StructureGuess:
    lines = text.splitlines()
    hits = 0
    numbered = 0
    for line in lines[:2000]:  # scan max 2000 lignes
        stripped = line.strip()
        if re.match(_numbered_re, stripped):  # 1., 1.1, 1.1.1, etc.
            numbered += 1
        if re.match(_header_re, stripped):    # CHAPTER, Chapter, Chaptere, etc.
            hits += 1
    # Seuil : hits >= 2 OU numbered >= 3
    is_structural = hits >= 2 or numbered >= 3
    return StructureGuess(is_structural=is_structural, ...)
```

**Regex multilingue** (Zh, Ja, Ko, Ar, Rom, Fr, De, Hi, Th, Fa) :
- `第X章` / `第X節` (Chinois/Japonais)
- `제X장` / `제X절` (Coréen)
- `الفصل` (Arabe)
- `Capitolo` / `Capítulo` (Italien/Espagnol)
- `Капитал` (Cyrillique)

**Application Philum** :
- Les articles académiques ont souvent des sections numérotées (1. Introduction, 2. Méthodologie, etc.)
- La détection de structure permet de chunker par sections naturelles
- Le regex pourrait être étendu pour détecter les titres d'articles scientifiques

### Pattern 2 : Validation de structure

**Concept** : Vérifie que les sections détectées ont assez de contenu pour être exploitables.

```python
def is_well_structured(pairs: list[tuple[str, str]]) -> bool:
    lengths = [len(text.strip()) for _, text in pairs]
    return (
        len(pairs) >= 3 and               # Au moins 3 sections
        median(lengths) >= 200 and          # Médiane ≥ 200 chars
        all(lengths[i] >= 0.3 * median(lengths) for i in range(1, len(lengths)))
        # Chaque section ≥ 30% de la médiane
    )
```

**Application Philum** :
- Évite de créer des sections vides ou trop courtes (artefacts de parsing)
- Seuil de 200 chars médian = bon compromis pour des articles académiques

### Pattern 3 : Budget adaptatif

**Concept** : Le budget tokens dépend du type de contenu et de la profondeur souhaitée.

| Type | Base tokens | Tokens/chapitre | Tokens/section |
|---|---|---|---|
| reference (bible) | 2000 | 8000 | aucun |
| reference (brefs) | 3000 | aucun | 3000 |
| study (deep) | 3000 | 5000 | aucun |
| study (surface) | 2000 | 3000 | aucun |
| text (deep) | 2500 | 4500 | aucun |
| text (surface) | 1500 | 2500 | aucun |

**Application Philum** :
- Le mode gratuit a un budget tokens limité (96k historique, 6k après refus)
- Le budget adaptatif permettrait de limiter les extraits selon le type de source
- Un article court = budget faible, un livre = budget élevé

### Pattern 4 : Chunking sémantique (pas taille fixe)

**Concept** : Ne coupe JAMAIS à une taille fixe (512, 1024 tokens). Détecte la structure naturelle (sections, chapitres) ET NE TOUCHE PAS aux headers.

```python
# RÈGLE CRITIQUE : NE PAS DÉPLACER LES HEADERS
# Le titre DOIT rester la première ligne de chaque chunk
chunks = []
for heading, body in sections:
    # Si la section est trop longue, on sous-sectionne par paragraphes
    if token_count(body) > max_tokens:
        subsections = split_by_paragraphs(body, max_tokens)
        chunks.append(heading + "\n\n" + subsections[0])
        chunks.extend(subsections[1:])  # sans le heading
    else:
        chunks.append(heading + "\n\n" + body)
```

**Application Philum : aucune, c'est déjà fait.** La première rédaction affirmait que l'extraction dépendait du LLM. `services/chunker.py` dit le contraire dès sa première ligne : « Decoupe un texte en extraits proposables, sans reseau ni cle. » Il ne coupe qu'aux frontières de phrase ou de paragraphe, la taille visée étant une cible et non un couperet, et il rend `start`/`end` pour que déplacer une borne réindexe dans le même texte au lieu de redécouper. C'est exactement la règle « ne jamais couper à taille fixe » de ce patron, écrite en 2026-08 et motivée par une mesure sur dix URLs.

### Pattern 5 : Estimation token hybride

**Concept** : Estimation adaptative selon la langue.

```python
def estimate_tokens(text: str) -> int:
    if is_cjk(text):
        return len(text) // 1.5  # CJK : ~1.5 chars par token
    else:
        words = len(text.split())
        return int(words / 0.75)  # Latin : ~0.75 mots par token
```

**Application Philum** : Les sources Philum sont principalement en français/anglais : la formule Latin suffit. Mais si Philum évolue vers le japonais/chinois, le pattern est prêt.

### Pattern 6 : Sanitisation Unicode invisible

**Concept** : Supprime les caractères invisibles qui peuvent cacher des instructions d'injection prompt.

```python
# Character categories to strip
INVISIBLE_RANGE = 0x200B, 0x200C, 0x200D, 0x2060  # Zero-width chars
TAG_RANGE = 0xE0000, 0xE007F  # Tags (Loubardes)
PRIVATE_RANGE = 0xE0020, 0xE007F  # Private use

def sanitize_for_llm(text: str) -> str:
    return ''.join(c for c in text if not is_invisible(c))
```

**Application Philum** :
- Les sources uploadées par les utilisateurs peuvent contenir du texte invisible
- Sanitiser avant injection dans le contexte LLM = sécurité de base
- Code réutilisable directement (0 dépendances)

---

## 3. Ce qui n'est PAS pertinent pour Philum

| Pattern book-to-skill | Pourquoi pas |
|---|---|
| Extraction PDF | Faux motif dans la première rédaction : Philum traite bien des PDF, via GROBID (`extractors/grobid.py`) et `pypdf`. Le vrai motif est que cette chaîne existe déjà et vise l'article scientifique, pas le livre. |
| EPUB/DOCX parsing | Philum n'accepte pas ces formats |
| TOC generation | Philum n'a pas besoin de table des matières |
| Token budget per section (study/reference) | Philum a déjà un budget LLM, pas besoin de limiter par section |
| Estimation de tokens | Philum estime déjà, mais pas via tiktoken comme l'affirmait la première rédaction : `services/token_meter.py:14-18` écarte tiktoken parce que c'est le tokeniseur d'OpenAI et que Philum route vers Gemini, Mistral, Anthropic et Z.ai. L'estimation se fait par caractères, ancrée sur le compte réel rendu par le fournisseur. |

---

## 4. Plan d'implémentation recommandé

### Phases A et B : détection de structure et chunking : abandonnées

`services/chunker.py` couvre déjà le besoin, y compris le seuil de 200 caractères que la phase B proposait d'ajouter (`_CIBLE_MIN = 200`, même valeur, atteinte indépendamment). Ce qu'il ne fait pas, c'est reconnaître les titres de sections d'un article scientifique pour couper là plutôt qu'à la phrase la plus proche de la cible. C'est un raffinement réel mais mineur, et il ne se justifie qu'après une mesure montrant que les extraits proposés tombent au mauvais endroit. À ne pas engager sur la foi de cet audit.

### Phase C : Sanitisation Unicode (0.5 jour) : la seule retenue

C'est le seul apport net des trois audits côté sécurité, et le seul de cette fiche. Du texte tiers entre dans le contexte du modèle par `fetch_url` et par le texte de page lu à l'insertion d'un extrait ; des caractères invisibles y font passer des instructions qu'aucune relecture humaine ne voit. Philum normalise déjà en NFKD pour la recherche (`db/text_search.py`) et en NFKC pour le dédoublonnage (`extractors/ref_dedup.py`), mais rien ne couvre le chemin du contexte.

| # | Tâche | Fichiers Philum |
|---|---|---|
| C1 | Copier `sanitize.py` de book-to-skill (30 lignes) | `sanitize.py` (nouveau) |
| C2 | Appliquer avant injection dans le contexte LLM | `agent.py` |
| C3 | Appliquer avant embedding | `embeddings.py` |

### Phase D : Budget adaptatif (optionnel, 1 jour)

| # | Tâche | Fichiers Philum |
|---|---|---|
| D1 | Ajouter un champ `content_type` aux sources (article, livre, page web) | `models.py` |
| D2 | Associer un budget tokens par type | `agent.py` |
| D3 | Limiter le nombre d'extraits injectés selon le budget | `tools_write.py` |

---

## 5. Patterns à copier directement

Un seul subsiste après vérification : **`sanitize.py`**, 150 lignes dans le dépôt d'origine, dont seule la partie « caractères invisibles » nous concerne. `detect_structure()` et `is_well_structured()` n'ont pas été trouvés dans le dépôt et font double emploi avec `chunker.py` ; `estimate_tokens()` fait double emploi avec `token_meter.py`, qui mesure mieux puisqu'il s'ancre sur le compte rendu par le fournisseur.

---

## 6. Risques

| Risque | Mitigation |
|---|---|
| La sanitisation supprime du contenu légitime | Ne retirer que les caractères sans rendu visible. Un texte cité doit rester citable mot pour mot : si la sanitisation change un caractère visible, l'ancrage d'extrait ne retrouve plus le passage dans la page, et la garde anti-fabrication se met à refuser du travail honnête. |
| La sanitisation casse l'ancrage des extraits déjà posés | Appliquer la même fonction des deux côtés de la comparaison, texte de page et texte cité, jamais d'un seul. |

---

_Audit réalisé le 2026-08-30. Source : https://github.com/virgiliojr94/book-to-skill_
