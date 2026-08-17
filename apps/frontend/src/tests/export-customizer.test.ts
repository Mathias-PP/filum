/**
 * Le panneau d'export à la carte, monté pour de vrai.
 *
 * `export-query.test.ts` couvre la construction de l'adresse ; ce qu'il ne
 * peut pas voir, c'est si une case cochée arrive jusqu'à elle. Une liaison
 * rompue entre l'interface et le sérialiseur ne casse rien de visible : le
 * lien de téléchargement reste cliquable, le fichier arrive, il est
 * simplement amputé de ce qu'on croyait avoir demandé.
 *
 * L'autre invariant tenu ici : les deux sens du voisinage restent nommés
 * séparément. Les fondations d'un propos et sa postérité ne sont pas deux
 * valeurs d'un même réglage.
 */
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import ExportCustomizer from '$lib/components/ExportCustomizer.svelte';

const BASE = 'https://api.philum/api/v1/@mp/fiche/export';

function monter() {
  return render(ExportCustomizer, { open: true, exportBase: BASE });
}

function lienTelechargement(): HTMLAnchorElement {
  return screen.getByRole('link', { name: 'Télécharger' }) as HTMLAnchorElement;
}

describe('ExportCustomizer', () => {
  it('nomme les deux sens du voisinage separement', () => {
    monter();
    expect(screen.getByLabelText('Fiches citées par celle-ci')).toBeTruthy();
    expect(screen.getByLabelText('Fiches qui citent celle-ci')).toBeTruthy();
  });

  it('emporte tout par defaut', () => {
    monter();
    const url = new URL(lienTelechargement().href);
    expect(url.searchParams.get('format')).toBe('markdown');
    expect(url.searchParams.get('include')).toBe('annotations,excerpts,archives,reliability');
    expect(url.searchParams.has('cited')).toBe(false);
  });

  it('decocher une section la retire de ladresse', async () => {
    monter();
    await fireEvent.click(screen.getByLabelText('Extraits cités'));
    expect(new URL(lienTelechargement().href).searchParams.get('include')).toBe(
      'annotations,archives,reliability'
    );
  });

  it('choisir une profondeur ouvre un reglage par degre', async () => {
    monter();
    await fireEvent.change(screen.getByLabelText('Fiches citées par celle-ci'), {
      target: { value: '2' },
    });
    expect(screen.getByText('Degré 1')).toBeTruthy();
    expect(screen.getByText('Degré 2')).toBeTruthy();
    expect(new URL(lienTelechargement().href).searchParams.get('cited')).toBe(
      '1:annotations,excerpts,archives,reliability|2:annotations,excerpts,archives,reliability'
    );
  });

  it('un degre a son propre perimetre', async () => {
    monter();
    await fireEvent.change(screen.getByLabelText('Fiches citées par celle-ci'), {
      target: { value: '1' },
    });
    // Le degré 1 du voisinage, pas le périmètre de la fiche elle-même.
    await fireEvent.click(document.querySelector('#citees-1-excerpts') as HTMLElement);
    const params = new URL(lienTelechargement().href).searchParams;
    expect(params.get('cited')).toBe('1:annotations,archives,reliability');
    expect(params.get('include')).toBe('annotations,excerpts,archives,reliability');
  });

  it('un format bibliographique dit pourquoi les cases sont grisees', async () => {
    monter();
    await fireEvent.change(screen.getByLabelText('Format de fichier'), {
      target: { value: 'bibtex' },
    });
    const params = new URL(lienTelechargement().href).searchParams;
    expect(params.has('include')).toBe(false);
    expect(screen.getByText(/convention fermée/)).toBeTruthy();
  });
});
