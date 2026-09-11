/**
 * Traduction des noms d'outils techniques en actions lisibles par un humain.
 *
 * Chaque entree donne une action (verbe) et optionnellement un selecteur d'objet
 * (fonction qui extrait le nom de la cible depuis les arguments de l'appel, ou
 * depuis le resultat si celui-ci contient un titre resolvant l'UUID).
 *
 * Aucun nom a tiret bas ne doit atteindre l'ecran. La garantie ne tient pas a
 * la vigilance de celui qui ajoute un outil : `test_libelles_outils_front.py`,
 * cote serveur, lit cette table et echoue des qu'un outil du registre n'y a pas
 * d'entree.
 */

type ArgMap = Record<string, unknown>;

interface Rendu {
  action: string;
  objet: string | null;
}

/** Priorité à un titre lisible extrait du résultat, sinon repli sur l'arg. */
function titreDepuisResultat(result: ArgMap | null, cle = 'title'): string | null {
  if (!result) return null;
  const v = result[cle];
  if (typeof v === 'string' && v.trim()) return v;
  const st = result.source_title;
  if (typeof st === 'string' && st.trim()) return st;
  const src = result.source;
  if (src && typeof src === 'object') {
    const t = (src as ArgMap).title;
    if (typeof t === 'string' && t.trim()) return t;
  }
  const card = result.card;
  if (card && typeof card === 'object') {
    const t = (card as ArgMap).title;
    if (typeof t === 'string' && t.trim()) return t;
  }
  return null;
}

/** Premier argument texte non vide parmi les clés données. */
function texteArg(a: ArgMap, ...cles: string[]): string | null {
  for (const cle of cles) {
    const v = a[cle];
    if (typeof v === 'string' && v.trim()) return v;
  }
  return null;
}

const ACTIONS: Record<
  string,
  {
    action: string;
    objet?: ((a: ArgMap, r: ArgMap | null) => string | null) | undefined;
  }
> = {
  create_card: {
    action: 'Crée la fiche',
    objet: (a, r) => titreDepuisResultat(r) ?? texteArg(a, 'title'),
  },
  update_card: {
    action: 'Modifie la fiche',
    objet: (a, r) => titreDepuisResultat(r) ?? texteArg(a, 'slug'),
  },
  delete_card: {
    action: 'Supprime la fiche',
    objet: (a, r) => titreDepuisResultat(r) ?? texteArg(a, 'slug'),
  },
  publish_card: {
    action: 'Publie la fiche',
    objet: (a, r) => titreDepuisResultat(r) ?? texteArg(a, 'slug'),
  },
  get_card: {
    action: 'Lit la fiche',
    objet: (a, r) => titreDepuisResultat(r) ?? texteArg(a, 'slug'),
  },
  get_my_card: {
    action: 'Lit votre fiche',
    objet: (a, r) => titreDepuisResultat(r) ?? texteArg(a, 'slug', 'card_slug'),
  },
  list_my_cards: { action: 'Liste vos fiches' },
  search_cards: { action: 'Cherche des fiches', objet: (a) => texteArg(a, 'query', 'q') },
  find_cards_citing: {
    action: 'Cherche les fiches qui citent',
    objet: (a) => texteArg(a, 'url'),
  },
  add_source: {
    action: 'Ajoute la source',
    objet: (a, r) => titreDepuisResultat(r) ?? texteArg(a, 'title', 'url'),
  },
  update_source: {
    action: 'Modifie la source',
    objet: (a, r) => titreDepuisResultat(r) ?? texteArg(a, 'source_id'),
  },
  delete_source: {
    action: 'Supprime la source',
    objet: (a, r) => titreDepuisResultat(r) ?? texteArg(a, 'source_id'),
  },
  get_source: {
    action: 'Lit la source',
    objet: (a, r) => titreDepuisResultat(r) ?? texteArg(a, 'source_id'),
  },
  list_sources: { action: 'Liste les sources de', objet: (a) => texteArg(a, 'card_slug', 'slug') },
  archive_sources: { action: 'Archive les sources' },
  add_sources_batch: {
    action: 'Ajoute un lot de sources à',
    objet: (a) => texteArg(a, 'card_slug'),
  },
  add_excerpt: {
    action: 'Ajoute un extrait',
    objet: (a, r) => {
      const src = titreDepuisResultat(r) ?? null;
      const txt = (r?.text as string) ?? texteArg(a, 'text', 'title') ?? '';
      const extrait = txt
        ? `« ${txt.slice(0, 48).replace(/\s+/g, ' ')}${txt.length > 48 ? '…' : ''} »`
        : null;
      if (src && extrait) return `${extrait} → ${src}`;
      if (extrait) return extrait;
      return src ?? 'cette source';
    },
  },
  update_excerpt: {
    action: 'Modifie l’extrait',
    objet: (a, r) => {
      const src = titreDepuisResultat(r) ?? null;
      const txt = (r?.text as string) ?? texteArg(a, 'text') ?? '';
      const extrait = txt
        ? `« ${txt.slice(0, 40)}… »`
        : `#${String(a.excerpt_id ?? '').slice(0, 8)}`;
      return src ? `${extrait} dans ${src}` : extrait;
    },
  },
  delete_excerpt: {
    action: 'Supprime un extrait',
    objet: (_a, r) => {
      const src = titreDepuisResultat(r) ?? null;
      return src ? `dans ${src}` : null;
    },
  },
  verify_excerpts: {
    action: 'Vérifie les extraits de',
    objet: (_a, r) => titreDepuisResultat(r) ?? 'cette source',
  },
  suggest_excerpts: {
    action: 'Suggère des extraits depuis',
    objet: (_a, r) => titreDepuisResultat(r) ?? 'cette source',
  },
  annotate_excerpt: {
    action: 'Annote un extrait',
    objet: (_a, r) => titreDepuisResultat(r),
  },
  search_my_excerpts: { action: 'Cherche dans vos extraits', objet: (a) => texteArg(a, 'query') },
  set_content_text: {
    action: 'Écrit le texte du contenu de la fiche',
    objet: (a, r) => titreDepuisResultat(r) ?? texteArg(a, 'card_slug'),
  },
  parse_biblio: { action: 'Analyse une bibliographie' },
  get_url_metadata: { action: 'Lit les métadonnées de', objet: (a) => texteArg(a, 'url') },
  import_from_content_url: {
    action: 'Importe les sources citées par',
    objet: (a) => texteArg(a, 'content_url'),
  },
  create_content_attestation: {
    action: 'Signe une attestation de contenu pour',
    objet: (a, r) => titreDepuisResultat(r) ?? texteArg(a, 'card_slug'),
  },
  fetch_url: { action: 'Lit la page', objet: (a) => texteArg(a, 'url') },
  web_search: { action: 'Cherche sur le web', objet: (a) => texteArg(a, 'query', 'q') },
  fs_read: {
    action: 'Lit le fichier de l’espace de travail',
    objet: (a) => texteArg(a, 'path'),
  },
  fs_write: {
    action: 'Écrit le fichier de l’espace de travail',
    objet: (a) => texteArg(a, 'path'),
  },
  fs_list: {
    action: 'Liste le dossier de l’espace de travail',
    objet: (a) => texteArg(a, 'path'),
  },
  fiche_state: {
    action: 'Consulte l’avancement de la fiche',
    objet: (a) => texteArg(a, 'slug', 'card_slug'),
  },
  fiche_etapes: {
    action: 'Consulte les étapes de construction de la fiche',
    objet: (a) => texteArg(a, 'slug', 'card_slug'),
  },
  definir_objectif: {
    action: 'Fixe l’objectif de la conversation',
    objet: (a) => texteArg(a, 'objectif', 'texte', 'text'),
  },
  avancer_phase: { action: 'Passe à la phase', objet: (a) => texteArg(a, 'phase', 'nom') },
};

/** Libellés des groupes d'appels consécutifs, là où le pluriel se dit mieux
 * qu'un compteur. `{n}` est remplacé par le nombre d'appels. */
const PLURIELS: Record<string, string> = {
  get_card: 'Lit {n} fiches',
  search_cards: 'Lance {n} recherches de fiches',
  get_source: 'Lit {n} sources',
  add_source: 'Ajoute {n} sources',
  update_source: 'Modifie {n} sources',
  delete_source: 'Supprime {n} sources',
  add_excerpt: 'Ajoute {n} extraits',
  update_excerpt: 'Modifie {n} extraits',
  delete_excerpt: 'Supprime {n} extraits',
  annotate_excerpt: 'Annote {n} extraits',
  verify_excerpts: 'Vérifie les extraits de {n} sources',
  get_url_metadata: 'Lit les métadonnées de {n} adresses',
  fetch_url: 'Lit {n} pages',
  web_search: 'Lance {n} recherches sur le web',
  fs_read: 'Lit {n} fichiers de l’espace de travail',
  fs_write: 'Écrit {n} fichiers de l’espace de travail',
};

/** Repli pour un outil absent de la table : jamais le nom brut à l'écran. */
function humaniser(name: string): string {
  return `Appelle l’outil « ${name.replace(/_/g, ' ')} »`;
}

export function rendreOutil(name: string, args: ArgMap, result: ArgMap | null = null): Rendu {
  const entree = ACTIONS[name];
  if (!entree) return { action: humaniser(name), objet: null };
  const objet = typeof entree.objet === 'function' ? entree.objet(args, result) : null;
  // Tronquer les valeurs longues (UUIDs, URLs) pour rester lisible. Un UUID
  // n'apporte aucune information : on montre juste ses 8 premiers caractères
  // pour distinguer deux appels sans encombrer l'interface.
  const objetCourt = tronquer(objet);
  return { action: entree.action, objet: objetCourt };
}

/** En-tête d'un groupe de `n` appels consécutifs du même outil. */
export function rendreGroupe(name: string, n: number): string {
  const pluriel = PLURIELS[name];
  if (pluriel) return pluriel.replace('{n}', String(n));
  return `${rendreOutil(name, {}).action} (${n} fois)`;
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function tronquer(objet: string | null): string | null {
  if (!objet) return objet;
  if (UUID_RE.test(objet)) return `#${objet.slice(0, 8)}`;
  if (objet.length <= 50) return objet;
  if (objet.startsWith('http')) {
    try {
      return new URL(objet).hostname;
    } catch {
      return objet.slice(0, 48) + '…';
    }
  }
  return objet.slice(0, 48) + '…';
}
