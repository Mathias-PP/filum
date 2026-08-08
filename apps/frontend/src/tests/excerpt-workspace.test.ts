/**
 * Cet écran décide de ce qu'une fiche Philum affirmera d'une source. Le risque
 * propre n'est donc pas le plantage : c'est le verdict abusif. Dire
 * « introuvable » d'une citation que la page n'a simplement pas rendue
 * accuserait l'auteur·ice à la place du site — et une fiche qui accuse à tort
 * ne vaut rien.
 *
 * D'où les invariants tenus ici : les quatre verdicts restent distincts, un
 * passage collé à la main part avec un ancrage vide plutôt qu'inventé, et
 * l'absence de modèle sur le serveur se dit sans fermer les autres chemins.
 */
import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const create = vi.fn();
const verify = vi.fn();
const suggest = vi.fn();
const supprimer = vi.fn();

vi.mock('$lib/api/client', () => ({
  api: {
    excerpts: {
      create: (...a: unknown[]) => create(...a),
      verify: (...a: unknown[]) => verify(...a),
      suggest: (...a: unknown[]) => suggest(...a),
      delete: (...a: unknown[]) => supprimer(...a),
      chunk: vi.fn().mockResolvedValue({
        text: '',
        text_source: 'none',
        unit: 'caracteres',
        suggested_size: 200,
        llm_enabled: false,
        chunks: [],
      }),
    },
  },
}));

import ExcerptWorkspace from '$lib/components/ExcerptWorkspace.svelte';

function extrait(id: string, text: string) {
  return {
    id,
    text,
    title: null,
    position: 0,
    suggested_by_ai: false,
    verified_at: null,
    verified_status: null,
    verified_text_source: null,
    context: null,
    annotated_by_ai: false,
  };
}

function monter(excerpts: ReturnType<typeof extrait>[] = []) {
  const vus: unknown[] = [];
  const vue = render(ExcerptWorkspace, {
    props: {
      sourceId: 's1',
      excerpts,
      onchange: (list: unknown) => vus.push(list),
    },
  });
  return { vue, vus };
}

describe('ExcerptWorkspace', () => {
  beforeEach(() => {
    create.mockReset();
    verify.mockReset();
    suggest.mockReset();
    supprimer.mockReset();
  });

  it('envoie un ancrage vide plutôt qu’inventé pour un passage collé à la main', async () => {
    // Une saisie à la main ne connaît pas le texte de la page : lui fabriquer
    // un voisinage ferait désigner une position qui n'existe nulle part.
    create.mockResolvedValue(extrait('e1', 'Un passage.'));
    monter();
    await fireEvent.input(screen.getByRole('textbox'), { target: { value: 'Un passage.' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Ajouter' }));
    await vi.waitFor(() => expect(create).toHaveBeenCalled());
    expect(create.mock.calls[0][1]).toMatchObject({
      text: 'Un passage.',
      anchor_prefix: null,
      anchor_suffix: null,
      anchor_offset: null,
    });
  });

  it('ne dit pas « introuvable » d’une page qui n’a rendu aucun texte', async () => {
    verify.mockResolvedValue({
      checks: [{ excerpt_id: 'e1', status: 'unreadable', start: null, end: null }],
      page_text_length: 0,
    });
    monter([extrait('e1', 'Un passage.')]);
    await fireEvent.click(screen.getByRole('button', { name: /Relire la source/ }));
    await vi.waitFor(() => expect(screen.getByText('? illisible')).toBeTruthy());
    expect(screen.queryByText('✕ introuvable')).toBeNull();
    expect(screen.getByText(/ne dit rien sur ces citations/)).toBeTruthy();
  });

  it('distingue une citation retrouvée d’une citation dont les mots ont changé', async () => {
    verify.mockResolvedValue({
      checks: [
        { excerpt_id: 'e1', status: 'found', start: 0, end: 5 },
        { excerpt_id: 'e2', status: 'moved', start: 9, end: 14 },
        { excerpt_id: 'e3', status: 'missing', start: null, end: null },
      ],
      page_text_length: 400,
    });
    monter([extrait('e1', 'Un.'), extrait('e2', 'Deux.'), extrait('e3', 'Trois.')]);
    await fireEvent.click(screen.getByRole('button', { name: /Relire la source/ }));
    await vi.waitFor(() => expect(screen.getByText('✓ retrouvée')).toBeTruthy());
    expect(screen.getByText('≈ déplacée')).toBeTruthy();
    expect(screen.getByText('✕ introuvable')).toBeTruthy();
    // Le décompte ne compte pas l'introuvable comme retrouvée.
    expect(screen.getByText(/2 citations sur 3/)).toBeTruthy();
  });

  it('ne propose pas de relire quand il n’y a aucune citation', () => {
    monter();
    const bouton = screen.getByRole('button', { name: /Relire la source/ }) as HTMLButtonElement;
    expect(bouton.disabled).toBe(true);
  });

  it('dit l’absence de modèle sans fermer les autres chemins', async () => {
    suggest.mockResolvedValue({ suggestions: [], page_text_length: 0, llm_enabled: false });
    monter();
    await fireEvent.click(screen.getByRole('button', { name: /Suggérer des citations/ }));
    await vi.waitFor(() => expect(screen.getByText(/n'est pas configurée/)).toBeTruthy());
    // Coller reste possible : l'absence de modèle ne bloque pas la saisie.
    expect(screen.getByRole('textbox')).toBeTruthy();
  });

  it('bascule entre coller un passage et découper un texte long', async () => {
    monter();
    expect(screen.getByPlaceholderText(/Collez ici le passage exact/)).toBeTruthy();
    await fireEvent.click(screen.getByRole('button', { name: 'Découper un texte long' }));
    expect(screen.queryByPlaceholderText(/Collez ici le passage exact/)).toBeNull();
    expect(screen.getByRole('button', { name: /Proposer un découpage/ })).toBeTruthy();
  });

  it('ne laisse pas dépasser dix citations', () => {
    const dix = Array.from({ length: 10 }, (_, i) => extrait(`e${i}`, `Phrase ${i}.`));
    monter(dix);
    expect(screen.getByText(/Dix citations, c’est le maximum/)).toBeTruthy();
    expect(screen.queryByPlaceholderText(/Collez ici le passage exact/)).toBeNull();
  });

  it('remonte la liste amputée quand on supprime une citation', async () => {
    supprimer.mockResolvedValue(undefined);
    const { vus } = monter([extrait('e1', 'Un.'), extrait('e2', 'Deux.')]);
    await fireEvent.click(screen.getAllByRole('button', { name: 'Supprimer cette citation' })[0]);
    await vi.waitFor(() => expect(vus).toHaveLength(1));
    expect((vus[0] as { id: string }[]).map((x) => x.id)).toEqual(['e2']);
  });
});
