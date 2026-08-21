/**
 * Traduction des noms d'outils techniques en actions lisibles par un humain.
 *
 * Chaque entree donne une action (verbe) et optionnellement un selecteur d'objet
 * (fonction qui extrait le nom de la cible depuis les arguments de l'appel).
 */

type ArgMap = Record<string, unknown>;

interface Rendu {
  action: string;
  objet: string | null;
}

const ACTIONS: Record<
  string,
  { action: string; objet?: ((a: ArgMap) => string | null) | undefined }
> = {
  create_card: { action: 'Crée la fiche', objet: (a) => (a.title as string) ?? null },
  update_card: { action: 'Modifie la fiche', objet: (a) => (a.slug as string) ?? null },
  delete_card: { action: 'Supprime la fiche', objet: (a) => (a.slug as string) ?? null },
  publish_card: { action: 'Publie la fiche', objet: (a) => (a.slug as string) ?? null },
  add_source: {
    action: 'Ajoute la source',
    objet: (a) => (a.title as string) ?? (a.url as string) ?? null,
  },
  update_source: { action: 'Modifie la source', objet: (a) => (a.source_id as string) ?? null },
  delete_source: { action: 'Supprime la source', objet: (a) => (a.source_id as string) ?? null },
  archive_sources: { action: 'Archive les sources' },
  add_sources_batch: {
    action: 'Ajoute un lot de sources',
    objet: (a) => (a.card_slug as string) ?? null,
  },
  add_excerpt: {
    action: 'Ajoute un extrait',
    objet: (a) => (a.source_id as string) ?? null,
  },
  update_excerpt: { action: 'Modifie un extrait', objet: (a) => (a.excerpt_id as string) ?? null },
  delete_excerpt: { action: 'Supprime un extrait', objet: (a) => (a.excerpt_id as string) ?? null },
  verify_excerpts: {
    action: 'Verifie les extraits de',
    objet: (a) => (a.source_id as string) ?? null,
  },
  suggest_excerpts: {
    action: 'Suggere des extraits depuis',
    objet: (a) => (a.source_id as string) ?? null,
  },
  annotate_excerpt: {
    action: 'Annote un extrait',
    objet: (a) => (a.excerpt_id as string) ?? null,
  },
  set_content_text: {
    action: 'Ecrit le contenu de la fiche',
    objet: (a) => (a.card_slug as string) ?? null,
  },
  list_my_cards: { action: 'Liste les fiches' },
  list_sources: { action: 'Liste les sources de', objet: (a) => (a.card_slug as string) ?? null },
  search_my_excerpts: { action: 'Cherche dans les extraits' },
  search_cards: { action: 'Cherche des fiches', objet: (a) => (a.query as string) ?? null },
  get_card: { action: 'Lit la fiche', objet: (a) => (a.slug as string) ?? null },
  get_source: { action: 'Lit la source', objet: (a) => (a.source_id as string) ?? null },
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
    objet: (a) => (a.card_slug as string) ?? null,
  },
  fetch_url: { action: 'Lit la page', objet: (a) => (a.url as string) ?? null },
  web_search: { action: 'Recherche web', objet: (a) => (a.query as string) ?? null },
  fs_read: { action: 'Lit le fichier workspace', objet: (a) => (a.path as string) ?? null },
  fs_write: { action: 'Ecrit le fichier workspace', objet: (a) => (a.path as string) ?? null },
  fs_list: { action: 'Liste le dossier workspace', objet: (a) => (a.path as string) ?? null },
};

export function rendreOutil(name: string, args: ArgMap): Rendu {
  const entree = ACTIONS[name];
  if (!entree) return { action: name, objet: null };
  const objet = typeof entree.objet === 'function' ? entree.objet(args) : null;
  // Tronquer les valeurs longues (UUIDs, URLs) pour rester lisible
  const objetCourt =
    objet && objet.length > 50
      ? objet.startsWith('http')
        ? new URL(objet).hostname
        : objet.slice(0, 48) + '...'
      : objet;
  return { action: entree.action, objet: objetCourt };
}
