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
