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

vi.mock('$lib/api/client', () => ({
  api: { excerpts: { chunk: (...args: unknown[]) => chunk(...args) } },
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
      chunks: [],
    });
    await proposer();
    expect(screen.getByText(/ne laisse pas lire son texte/)).toBeTruthy();
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
});
