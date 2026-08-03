import { dev } from '$app/environment';
import { error } from '@sveltejs/kit';

// Les pages de /sandbox sont des ateliers de design : etats intermediaires,
// variantes abandonnees, controles bruts. Elles servent au travail iteratif en
// local et n'ont rien a dire a un visiteur -- ni a un moteur d'indexation.
// Elles restent dans le depot, mais ne repondent qu'en developpement.
export const load = () => {
  if (!dev) error(404, 'Not found');
};
