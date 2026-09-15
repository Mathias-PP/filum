/**
 * Repli des appels d'outils en blocs d'activité.
 *
 * Une conversation réelle comptait 64 cartes d'outils, dont des suites de 10
 * et 11 suppressions affichées carte par carte : le fil devenait un mur que
 * personne ne relisait. Chaque suite d'appels consécutifs devient ici un bloc,
 * résumé en une ligne (« 12 actions : lit 6 sources, supprime 5 extraits »),
 * et dans le bloc les appels consécutifs d'un même outil forment un groupe.
 *
 * Fonction pure, testée sans navigateur.
 */

import type { ChatItem } from './conversation';
import { rendreGroupe, rendreOutil } from './toolLabels';

export type AppelOutil = Extract<ChatItem, { kind: 'tool' }>;

export interface GroupeOutils {
  name: string;
  entrees: AppelOutil[];
}

export interface BlocActivite {
  kind: 'activite';
  groupes: GroupeOutils[];
  total: number;
  echecs: number;
  enCours: number;
}

export type Affichable = Exclude<ChatItem, AppelOutil> | BlocActivite;

function estEchec(appel: AppelOutil): boolean {
  return appel.result !== null && 'error' in appel.result;
}

export function regrouper(items: ChatItem[]): Affichable[] {
  const rendu: Affichable[] = [];
  for (const item of items) {
    if (item.kind !== 'tool') {
      rendu.push(item);
      continue;
    }
    const precedent = rendu[rendu.length - 1];
    let bloc: BlocActivite;
    if (precedent?.kind === 'activite') {
      bloc = precedent;
    } else {
      bloc = { kind: 'activite', groupes: [], total: 0, echecs: 0, enCours: 0 };
      rendu.push(bloc);
    }
    const groupe = bloc.groupes[bloc.groupes.length - 1];
    if (groupe?.name === item.name) groupe.entrees.push(item);
    else bloc.groupes.push({ name: item.name, entrees: [item] });
    bloc.total += 1;
    if (item.result === null) bloc.enCours += 1;
    else if (estEchec(item)) bloc.echecs += 1;
  }
  return rendu;
}

function minuscule(phrase: string): string {
  return phrase.charAt(0).toLowerCase() + phrase.slice(1);
}

/** Nombre d'outils distincts nommés dans le résumé, le reste est compté. */
const OUTILS_NOMMES = 3;

/** « 12 actions : lit 6 sources, supprime 5 extraits et 1 autre » */
export function resumerActivite(bloc: BlocActivite): string {
  const parNom = new Map<string, number>();
  for (const groupe of bloc.groupes) {
    parNom.set(groupe.name, (parNom.get(groupe.name) ?? 0) + groupe.entrees.length);
  }
  const phrases = [...parNom].map(([name, n]) =>
    n === 1 ? rendreOutil(name, {}).action : rendreGroupe(name, n)
  );
  const tete = `${bloc.total} action${bloc.total > 1 ? 's' : ''}`;
  if (phrases.length === 1 && bloc.total === 1) return phrases[0];
  const nommees = phrases.slice(0, OUTILS_NOMMES).map(minuscule);
  const reste = phrases.length - nommees.length;
  const detail =
    reste > 0
      ? `${nommees.join(', ')} et ${reste} autre${reste > 1 ? 's' : ''}`
      : nommees.join(', ');
  return `${tete} : ${detail}`;
}

interface Compte {
  un: string;
  plusieurs: string;
}

const MODIFICATION: Compte = { un: 'modification', plusieurs: 'modifications' };
const SUPPRESSION: Compte = { un: 'suppression', plusieurs: 'suppressions' };
const SOURCE_AJOUTEE: Compte = { un: 'source ajoutée', plusieurs: 'sources ajoutées' };
const EXTRAIT_REFUSE: Compte = { un: 'extrait refusé', plusieurs: 'extraits refusés' };
const ECRITURE_ECHOUEE: Compte = { un: 'écriture en échec', plusieurs: 'écritures en échec' };
const EXTRAIT_POSE: Compte = { un: 'extrait posé', plusieurs: 'extraits posés' };

/** Les outils qui écrivent dans les fiches, et ce qu'une réussite compte. */
const ECRITURES: Record<string, Compte> = {
  create_card: { un: 'fiche créée', plusieurs: 'fiches créées' },
  publish_card: { un: 'fiche publiée', plusieurs: 'fiches publiées' },
  restore_card: { un: 'fiche restaurée', plusieurs: 'fiches restaurées' },
  add_source: SOURCE_AJOUTEE,
  add_sources_batch: SOURCE_AJOUTEE,
  add_excerpt: EXTRAIT_POSE,
  retenir: EXTRAIT_POSE,
  update_card: MODIFICATION,
  update_source: MODIFICATION,
  update_excerpt: MODIFICATION,
  annotate_excerpt: MODIFICATION,
  set_content_text: MODIFICATION,
  delete_card: SUPPRESSION,
  delete_source: SUPPRESSION,
  delete_excerpt: SUPPRESSION,
  delete_excerpts: SUPPRESSION,
};

/** « Bilan : 2 sources ajoutées, 3 extraits posés, 5 extraits refusés. »
 *
 * Compté sur les résultats des outils, pas sur ce que dit le modèle : une
 * réponse annonçait trois extraits dans la fiche, dont un jamais posé sur une
 * page jamais lue. Le bilan est ce que la réponse ne peut pas contredire. Rien
 * quand le tour n'a rien tenté d'écrire.
 */
export function bilanDesAppels(appels: AppelOutil[]): string | null {
  const comptes = new Map<Compte, number>();
  const ajouter = (compte: Compte, n: number) =>
    comptes.set(compte, (comptes.get(compte) ?? 0) + n);
  for (const appel of appels) {
    const compte = ECRITURES[appel.name];
    if (!compte || appel.result === null) continue;
    if (appel.name === 'delete_excerpts' && typeof appel.result.deleted_count === 'number') {
      // Une validation, plusieurs extraits : le serveur compte ce qu'il a retiré.
      if (appel.result.deleted_count) ajouter(SUPPRESSION, appel.result.deleted_count);
      continue;
    }
    if (appel.name === 'retenir') {
      // Un appel pose plusieurs sources et extraits : le serveur les compte.
      const nombre = (valeur: unknown) => (typeof valeur === 'number' ? valeur : 0);
      const ajoutees = nombre(appel.result.sources_ajoutees);
      const poses = nombre(appel.result.extraits_poses);
      if (ajoutees) ajouter(SOURCE_AJOUTEE, ajoutees);
      if (poses) ajouter(EXTRAIT_POSE, poses);
      if (!poses) ajouter(ECRITURE_ECHOUEE, 1);
      continue;
    }
    if (estEchec(appel)) {
      ajouter(appel.name === 'add_excerpt' ? EXTRAIT_REFUSE : ECRITURE_ECHOUEE, 1);
      continue;
    }
    const lot = appel.args.sources;
    ajouter(compte, appel.name === 'add_sources_batch' && Array.isArray(lot) ? lot.length || 1 : 1);
  }
  if (comptes.size === 0) return null;
  const parties = [...comptes].map(([compte, n]) => `${n} ${n > 1 ? compte.plusieurs : compte.un}`);
  return `Bilan : ${parties.join(', ')}.`;
}

export interface NoteTour {
  bilan: string | null;
  /** La réponse affirme sans que le tour ait rien lu ni rien appelé. */
  sansSource: boolean;
}

/** En dessous, une réponse sans outil est une salutation ou une question en
 * retour, pas un contenu à vérifier. */
const LONGUEUR_AFFIRMATIVE = 280;

/** Annote la dernière réponse de chaque tour : son bilan, ou l'absence de source.
 *
 * Rend une table indexée comme `affichables`. La première réponse d'une
 * conversation réelle listait des conseils médicaux sans une source ni un
 * appel d'outil : la consigne « rien de mémoire » existe, elle ne garantit rien,
 * alors l'interface le montre.
 */
export function annoterTours(affichables: Affichable[]): Map<number, NoteTour> {
  const notes = new Map<number, NoteTour>();
  let appels: AppelOutil[] = [];
  let reponse = -1;
  const clore = () => {
    if (reponse >= 0) {
      const texte = (affichables[reponse] as { text: string }).text;
      const bilan = bilanDesAppels(appels);
      const sansSource = appels.length === 0 && texte.trim().length >= LONGUEUR_AFFIRMATIVE;
      if (bilan || sansSource) notes.set(reponse, { bilan, sansSource });
    }
    appels = [];
    reponse = -1;
  };
  affichables.forEach((item, i) => {
    if (item.kind === 'user') clore();
    else if (item.kind === 'activite')
      for (const groupe of item.groupes) appels.push(...groupe.entrees);
    else if (item.kind === 'assistant') reponse = i;
  });
  clore();
  return notes;
}

/** État d'un groupe, pour l'en-tête replié. */
export function etatGroupe(groupe: GroupeOutils): { echecs: number; enCours: number } {
  let echecs = 0;
  let enCours = 0;
  for (const appel of groupe.entrees) {
    if (appel.result === null) enCours += 1;
    else if (estEchec(appel)) echecs += 1;
  }
  return { echecs, enCours };
}
