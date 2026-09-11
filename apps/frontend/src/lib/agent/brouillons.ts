/**
 * Brouillon de message, gardé par conversation.
 *
 * Un texte en cours se perdait au premier changement de conversation. Il vit
 * désormais dans le navigateur, sous une clé par conversation : c'est une
 * commodité locale, rien ne part au serveur. Chaque accès est protégé, parce
 * que le stockage peut être refusé (navigation privée, données bloquées) et
 * qu'un brouillon perdu ne doit jamais empêcher d'écrire.
 */

const PREFIXE = 'philum:brouillon:';

export function lireBrouillon(cle: string): string {
  try {
    return localStorage.getItem(PREFIXE + cle) ?? '';
  } catch {
    return '';
  }
}

export function ecrireBrouillon(cle: string, texte: string): void {
  try {
    if (texte.trim()) localStorage.setItem(PREFIXE + cle, texte);
    else localStorage.removeItem(PREFIXE + cle);
  } catch {
    // Stockage refusé : le brouillon ne survivra pas à la navigation, rien de plus.
  }
}

export function effacerBrouillon(cle: string): void {
  ecrireBrouillon(cle, '');
}
