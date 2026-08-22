/**
 * Traduction des noms d'outils techniques en actions lisibles par un humain.
 *
 * Chaque entree donne une action (verbe) et optionnellement un selecteur d'objet
 * (fonction qui extrait le nom de la cible depuis les arguments de l'appel, ou
 * depuis le resultat si celui-ci contient un titre resolvant l'UUID).
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

const ACTIONS: Record<
  string,
  {
    action: string;
    objet?: ((a: ArgMap, r: ArgMap | null) => string | null) | undefined;
  }
> = {
  create_card: {
    action: 'Crée la fiche',
    objet: (a, r) => titreDepuisResultat(r) ?? (a.title as string) ?? null,
  },
  update_card: {
    action: 'Modifie la fiche',
    objet: (a, r) => titreDepuisResultat(r) ?? (a.slug as string) ?? null,
  },
  delete_card: {
    action: 'Supprime la fiche',
    objet: (a, r) => titreDepuisResultat(r) ?? (a.slug as string) ?? null,
  },
  publish_card: {
    action: 'Publie la fiche',
    objet: (a, r) => titreDepuisResultat(r) ?? (a.slug as string) ?? null,
  },
  add_source: {
    action: 'Ajoute la source',
    objet: (a, r) => titreDepuisResultat(r) ?? (a.title as string) ?? (a.url as string) ?? null,
  },
  update_source: {
    action: 'Modifie la source',
    objet: (a, r) => titreDepuisResultat(r) ?? (a.source_id as string) ?? null,
  },
  delete_source: {
    action: 'Supprime la source',
    objet: (a, r) => titreDepuisResultat(r) ?? (a.source_id as string) ?? null,
  },
  archive_sources: { action: 'Archive les sources' },
  add_sources_batch: {
    action: 'Ajoute un lot de sources',
    objet: (a) => (a.card_slug as string) ?? null,
  },
  add_excerpt: {
    action: 'Ajoute un extrait à',
    objet: (a, r) => titreDepuisResultat(r) ?? (a.source_id as string) ?? null,
  },
  update_excerpt: {
    action: 'Modifie un extrait',
    objet: (a, r) => titreDepuisResultat(r) ?? (a.excerpt_id as string) ?? null,
  },
  delete_excerpt: {
    action: 'Supprime un extrait',
    objet: (a) => (a.excerpt_id as string) ?? null,
  },
  verify_excerpts: {
    action: 'Verifie les extraits de',
    objet: (a, r) => titreDepuisResultat(r) ?? (a.source_id as string) ?? null,
  },
  suggest_excerpts: {
    action: 'Suggere des extraits depuis',
    objet: (a, r) => titreDepuisResultat(r) ?? (a.source_id as string) ?? null,
  },
  annotate_excerpt: {
    action: 'Annote un extrait',
    objet: (a) => (a.excerpt_id as string) ?? null,
  },
  set_content_text: {
    action: 'Ecrit le contenu de la fiche',
    objet: (a, r) => titreDepuisResultat(r) ?? (a.card_slug as string) ?? null,
  },
  list_my_cards: { action: 'Liste les fiches' },
  list_sources: { action: 'Liste les sources de', objet: (a) => (a.card_slug as string) ?? null },
  search_my_excerpts: { action: 'Cherche dans les extraits' },
  search_cards: { action: 'Cherche des fiches', objet: (a) => (a.query as string) ?? null },
  get_card: {
    action: 'Lit la fiche',
    objet: (a, r) => titreDepuisResultat(r) ?? (a.slug as string) ?? null,
  },
  get_source: {
    action: 'Lit la source',
    objet: (a, r) => titreDepuisResultat(r) ?? (a.source_id as string) ?? null,
  },
  find_cards_citing: {
    action: 'Cherche les fiches citant',
    objet: (a) => (a.url as string) ?? null,
  },
  parse_biblio: { action: 'Analyse une bibliographie' },
  get_url_metadata: { action: 'Lit les metadonnees de', objet: (a) => (a.url as string) ?? null },
  import_from_content_url: {
    action: 'Importe depuis',
    objet: (a) => (a.content_url as string) ?? null,
  },
  create_content_attestation: {
    action: 'Cree une attestation de contenu',
    objet: (a, r) => titreDepuisResultat(r) ?? (a.card_slug as string) ?? null,
  },
  fetch_url: { action: 'Lit la page', objet: (a) => (a.url as string) ?? null },
  web_search: { action: 'Recherche web', objet: (a) => (a.query as string) ?? null },
  fs_read: { action: 'Lit le fichier workspace', objet: (a) => (a.path as string) ?? null },
  fs_write: { action: 'Ecrit le fichier workspace', objet: (a) => (a.path as string) ?? null },
  fs_list: { action: 'Liste le dossier workspace', objet: (a) => (a.path as string) ?? null },
};

export function rendreOutil(name: string, args: ArgMap, result: ArgMap | null = null): Rendu {
  const entree = ACTIONS[name];
  if (!entree) return { action: name, objet: null };
  const objet = typeof entree.objet === 'function' ? entree.objet(args, result) : null;
  // Tronquer les valeurs longues (UUIDs, URLs) pour rester lisible. Un UUID
  // n'apporte aucune information : on montre juste ses 8 premiers caractères
  // pour distinguer deux appels sans encombrer l'interface.
  const objetCourt = tronquer(objet);
  return { action: entree.action, objet: objetCourt };
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
      return objet.slice(0, 48) + '...';
    }
  }
  return objet.slice(0, 48) + '...';
}
