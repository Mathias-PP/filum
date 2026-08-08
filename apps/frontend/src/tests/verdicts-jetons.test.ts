/**
 * Les verdicts de retractation et d'acces libre sont la seule chose que Philum
 * affirme sur une source qu'il n'a pas ecrite. Un verdict illisible ne dit pas
 * « je ne sais pas » : il ne dit rien du tout, et le lecteur conclut de son
 * absence.
 *
 * Deux familles de badges, deux regimes de couleur :
 *
 * - Les **avis** (retracte, mise en garde, corrige ; libre, gratuit) portent un
 *   fond colore clair et un texte fonce. La paire est close sur elle-meme et ne
 *   depend pas de la page : la figer est un choix, elle ne s'inverse pas.
 * - Les **non-avis** (aucun avis, non verifiable, acces payant, non verifie)
 *   sont du texte nu pose sur la surface de la page. Leur lisibilite depend
 *   donc du fond, qui s'inverse — ils doivent venir de jetons.
 *
 * `text-neutral-500` / `text-neutral-400` melangeaient les deux regimes : une
 * nuance figee en face d'un fond qui bascule.
 */
import { describe, expect, it } from 'vitest';
import { retractionBadge } from '$lib/utils/retraction';
import { openAccessBadge } from '$lib/utils/open-access';

/** Une classe de couleur de texte qui ne vient pas d'un jeton du theme. */
function nuanceFigee(className: string): string | null {
  return className.match(/\btext-(?:slate|neutral|gray|zinc|stone)-\d+\b/)?.[0] ?? null;
}

describe('verdicts sans avis', () => {
  it('tirent leur couleur de texte d’un jeton, faute de fond qui les porte', () => {
    const sansFond = [
      ['retraction', retractionBadge('none')],
      ['retraction', retractionBadge('unverifiable')],
      ['acces', openAccessBadge('closed')],
      ['acces', openAccessBadge('unverifiable')],
    ] as const;

    for (const [famille, badge] of sansFond) {
      expect(badge, `${famille} : badge attendu`).not.toBeNull();
      const classes = badge!.className;
      expect(classes, `${famille} : un non-avis n’a pas de fond propre`).not.toMatch(/\bbg-/);
      expect(
        nuanceFigee(classes),
        `${famille} : « ${classes} » fige la couleur du texte sur une surface qui, elle, s’inverse`
      ).toBeNull();
      expect(classes, `${famille} : la couleur doit venir du theme`).toMatch(/text-ink-/);
    }
  });
});
