/**
 * Le découpage manuel manipule des bornes dans un texte que la personne a
 * collé. Le risque propre à cet écran n'est pas le plantage : c'est qu'un
 * déplacement de borne fasse apparaître à l'écran un texte qui n'est pas
 * celui de la source — un mot avalé, une phrase dupliquée. Un extrait cité
 * sur une fiche Philum se lit comme du verbatim ; il doit en être.
 *
 * D'où l'invariant tenu ici : après n'importe quelle suite de « couper »,
 * « fusionner » et déplacements de borne, la concaténation des morceaux
 * affichés reste le texte reçu, aux espaces près.
 */
import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const TEXTE =
  'La mémoire de travail retient une information brièvement. ' +
  'Elle ne dure que quelques secondes. ' +
  'Baddeley en a proposé un modèle. ' +
  'Ce modèle distingue plusieurs sous-systèmes.';

const chunk = vi.fn();
const chunkFile = vi.fn();

vi.mock('$lib/api/client', () => ({
  api: {
    excerpts: {
      chunk: (...args: unknown[]) => chunk(...args),
      chunkFile: (...args: unknown[]) => chunkFile(...args),
    },
  },
}));

import ChunkArchitect from '$lib/components/ChunkArchitect.svelte';

/** Le texte des morceaux affichés, dans l'ordre, sans les intitulés. */
function morceauxAffiches(container: HTMLElement): string[] {
  return [...container.querySelectorAll('li p.text-sm')].map((p) => p.textContent?.trim() ?? '');
}

function normalise(s: string): string {
  return s.replace(/\s+/g, ' ').trim();
}

function reponseEnDeuxMorceaux() {
  const coupe = TEXTE.indexOf('Baddeley');
  return {
    text: TEXTE,
    text_source: 'pasted',
    unit: 'caracteres',
    suggested_size: 120,
    llm_enabled: true,
    chunks: [
      { text: TEXTE.slice(0, coupe).trim(), start: 0, end: coupe, size: coupe, title: null },
      {
        text: TEXTE.slice(coupe).trim(),
        start: coupe,
        end: TEXTE.length,
        size: TEXTE.length - coupe,
        title: null,
      },
    ],
  };
}

async function proposer() {
  const vue = render(ChunkArchitect, {
    props: { sourceId: 's1', remaining: 10, onadd: async () => {} },
  });
  await fireEvent.click(screen.getByRole('button', { name: /Proposer un découpage/ }));
  await vi.waitFor(() => expect(chunk).toHaveBeenCalled());
  return { vue };
}

describe('ChunkArchitect', () => {
  beforeEach(() => {
    chunk.mockReset();
    chunk.mockResolvedValue(reponseEnDeuxMorceaux());
    chunkFile.mockReset();
    chunkFile.mockResolvedValue({ ...reponseEnDeuxMorceaux(), text_source: 'uploaded' });
  });

  it('affiche les morceaux proposés, tels qu’ils sont dans la source', async () => {
    const { vue } = await proposer();
    const morceaux = morceauxAffiches(vue.container);
    expect(morceaux).toHaveLength(2);
    expect(normalise(morceaux.join(' '))).toBe(normalise(TEXTE));
  });

  it('propose de coller son texte quand la page ne se laisse pas lire', async () => {
    chunk.mockResolvedValue({
      text: '',
      text_source: 'none',
      unit: 'caracteres',
      suggested_size: 200,
      llm_enabled: true,
      chunks: [],
    });
    await proposer();
    expect(screen.getByText(/ne laisse pas lire son texte/)).toBeTruthy();
  });

  it("ne propose pas de suggérer des intitulés quand aucun modèle n'est configuré", async () => {
    chunk.mockResolvedValue({ ...reponseEnDeuxMorceaux(), llm_enabled: false });
    await proposer();
    const case_ = screen.getByRole('checkbox') as HTMLInputElement;
    expect(case_.disabled).toBe(true);
    expect(screen.getByText(/les intitulés se saisissent à la main/)).toBeTruthy();
  });

  it('ne perd ni n’invente de texte quand on déplace une borne', async () => {
    const { vue } = await proposer();
    await fireEvent.click(screen.getAllByRole('button', { name: /borne ▶/ })[0]);
    expect(normalise(morceauxAffiches(vue.container).join(' '))).toBe(normalise(TEXTE));
    await fireEvent.click(screen.getAllByRole('button', { name: /◀ borne/ })[0]);
    expect(normalise(morceauxAffiches(vue.container).join(' '))).toBe(normalise(TEXTE));
  });

  it('ne perd ni n’invente de texte quand on coupe puis fusionne', async () => {
    const { vue } = await proposer();
    await fireEvent.click(screen.getAllByRole('button', { name: 'couper' })[0]);
    expect(morceauxAffiches(vue.container).length).toBe(3);
    expect(normalise(morceauxAffiches(vue.container).join(' '))).toBe(normalise(TEXTE));

    await fireEvent.click(screen.getAllByRole('button', { name: 'fusionner' })[0]);
    expect(morceauxAffiches(vue.container).length).toBe(2);
    expect(normalise(morceauxAffiches(vue.container).join(' '))).toBe(normalise(TEXTE));
  });

  it('une borne ne peut pas franchir sa voisine', async () => {
    const { vue } = await proposer();
    // Trois poussées vers la droite alors qu'il ne reste qu'une fin de phrase
    // avant la fin du texte : la borne doit s'arrêter, pas s'inverser.
    const pousser = () => screen.getAllByRole('button', { name: /borne ▶/ })[0];
    await fireEvent.click(pousser());
    await fireEvent.click(pousser());
    await fireEvent.click(pousser());
    const morceaux = morceauxAffiches(vue.container);
    expect(morceaux).toHaveLength(2);
    expect(morceaux.every((m) => m.length > 0)).toBe(true);
    expect(normalise(morceaux.join(' '))).toBe(normalise(TEXTE));
  });

  it('un morceau déjà ajouté ne peut pas l’être une seconde fois', async () => {
    // Vérifié au navigateur : le morceau ajouté était fusionné avec son
    // voisin, donc son texte restait affiché — et un second clic sur
    // « Ajouter » produisait un extrait qui chevauchait le premier. Deux
    // extraits qui se recouvrent se lisent sur la fiche comme deux passages
    // distincts de la source.
    const ajoutes: string[] = [];
    const vue = render(ChunkArchitect, {
      props: {
        sourceId: 's1',
        remaining: 10,
        onadd: async (t: string) => {
          ajoutes.push(t);
        },
      },
    });
    await fireEvent.click(screen.getByRole('button', { name: /Proposer un découpage/ }));
    await vi.waitFor(() => expect(chunk).toHaveBeenCalled());

    await fireEvent.click(screen.getAllByRole('button', { name: 'Ajouter' })[0]);
    await vi.waitFor(() => expect(ajoutes).toHaveLength(1));

    expect(screen.getByText('✓ ajouté')).toBeTruthy();
    expect(screen.getAllByRole('button', { name: 'Ajouter' })).toHaveLength(1);
    // Et le texte reste entier : marquer n'est pas retirer.
    expect(normalise(morceauxAffiches(vue.container).join(' '))).toBe(normalise(TEXTE));
  });

  it('remonte de quoi retrouver le passage dans une page qui aura bougé', async () => {
    // Un extrait qui ne porte que son texte cesse d'être retrouvable dès que
    // la source corrige une coquille — et se lit alors comme une citation
    // inventée. Le voisinage relevé ici est ce qui l'en préserve.
    let ancrage: { prefix: string; suffix: string; offset: number } | null = null;
    render(ChunkArchitect, {
      props: {
        sourceId: 's1',
        remaining: 10,
        onadd: async (_t: string, _ti: string | null, a: typeof ancrage) => {
          ancrage = a;
        },
      },
    });
    await fireEvent.click(screen.getByRole('button', { name: /Proposer un découpage/ }));
    await vi.waitFor(() => expect(chunk).toHaveBeenCalled());
    await fireEvent.click(screen.getAllByRole('button', { name: 'Ajouter' })[1]);
    await vi.waitFor(() => expect(ancrage).not.toBeNull());

    const a = ancrage as unknown as { prefix: string; suffix: string; offset: number };
    expect(a.offset).toBe(TEXTE.indexOf('Baddeley'));
    // Le voisinage doit être celui du texte réel, sinon il ne départage rien.
    expect(TEXTE.slice(a.offset - a.prefix.length, a.offset)).toBe(a.prefix);
    expect(a.prefix).toContain('secondes');
  });

  it('le texte collé part au serveur sans passer par la lecture de la page', async () => {
    render(ChunkArchitect, {
      props: { sourceId: 's1', remaining: 10, onadd: async () => {} },
    });
    await fireEvent.input(screen.getByRole('textbox'), {
      target: { value: 'Une phrase collée.' },
    });
    await fireEvent.click(screen.getByRole('button', { name: /Proposer un découpage/ }));
    expect(chunk).toHaveBeenCalledWith(
      's1',
      expect.objectContaining({ text: 'Une phrase collée.' })
    );
  });

  // --- Le document déposé --------------------------------------------------
  //
  // Un chapitre ne se colle pas. Le risque propre à ce chemin n'est pas
  // l'erreur visible : c'est le texte extrait qui n'atterrirait pas dans le
  // champ de collage. Tout l'aval — redécouper, changer d'unité, relire les
  // extraits — travaille dessus ; sans lui, le premier réglage modifié
  // redemanderait le fichier, sans que rien ne dise pourquoi.

  function deposer(vue: { container: HTMLElement }, nom: string) {
    const champ = vue.container.querySelector('#chunk-file') as HTMLInputElement;
    const fichier = new File(['peu importe'], nom);
    Object.defineProperty(champ, 'files', { value: [fichier], configurable: true });
    return fireEvent.change(champ);
  }

  it('un document déposé donne un découpage', async () => {
    const vue = render(ChunkArchitect, {
      props: { sourceId: 's1', remaining: 10, onadd: async () => {} },
    });
    await deposer(vue, 'chapitre.docx');
    await vi.waitFor(() => expect(chunkFile).toHaveBeenCalled());
    expect(morceauxAffiches(vue.container)).toHaveLength(2);
    expect(screen.getByText(/chapitre\.docx/)).toBeTruthy();
  });

  it('le texte extrait atterrit dans le champ de collage', async () => {
    const vue = render(ChunkArchitect, {
      props: { sourceId: 's1', remaining: 10, onadd: async () => {} },
    });
    await deposer(vue, 'chapitre.docx');
    await vi.waitFor(() => expect(chunkFile).toHaveBeenCalled());
    const zone = vue.container.querySelector('textarea') as HTMLTextAreaElement;
    await vi.waitFor(() => expect(zone.value).toBe(TEXTE));

    // Et le redécoupage part de ce texte, sans redemander le fichier.
    await fireEvent.click(screen.getByRole('button', { name: /Redécouper/ }));
    expect(chunk).toHaveBeenCalledWith('s1', expect.objectContaining({ text: TEXTE }));
  });

  it('un document illisible garde la consigne du serveur', async () => {
    // « Ce PDF est une image scannée » dit quoi faire ensuite ; le remplacer
    // par « une erreur est survenue » retirerait la seule action disponible.
    chunkFile.mockRejectedValue(
      new Error('Ce PDF ne contient pas de texte sélectionnable : c’est une image scannée.')
    );
    const vue = render(ChunkArchitect, {
      props: { sourceId: 's1', remaining: 10, onadd: async () => {} },
    });
    await deposer(vue, 'scan.pdf');
    await vi.waitFor(() => expect(screen.getByText(/image scannée/)).toBeTruthy());
  });
});
