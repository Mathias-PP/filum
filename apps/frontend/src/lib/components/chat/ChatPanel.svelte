<script lang="ts">
  import { onMount, tick } from 'svelte';
  import {
    agentApi,
    type AgentDefinition,
    type AgentMessage,
    type AgentProvider,
    type AgentSessionUsage,
  } from '$lib/api/agent';
  import { ApiError } from '$lib/api';
  import {
    appliquer,
    cloturerSansReponse,
    depuisMessages,
    tourTermine,
    type ChatItem,
  } from '$lib/agent/conversation';
  import { regrouper } from '$lib/agent/activite';
  import { ecrireBrouillon, effacerBrouillon, lireBrouillon } from '$lib/agent/brouillons';
  import Button from '../Button.svelte';
  import { toast } from '../Toast.svelte';
  import ApprovalCard from './ApprovalCard.svelte';
  import BlocActivite from './BlocActivite.svelte';
  import CopierBouton from './CopierBouton.svelte';
  import FicheVivante from './FicheVivante.svelte';
  import { appelsTermines, slugFicheCourante } from '$lib/agent/ficheCourante';
  import AgentMarkdown from './AgentMarkdown.svelte';
  import LogoLoader from '../LogoLoader.svelte';
  import ConsentementGratuit from './ConsentementGratuit.svelte';

  interface Props {
    sessionId?: string | null;
    onsession?: (id: string) => void;
    /** Titre propose avant le premier message (choisi par l'utilisateur). */
    titreInitial?: string;
  }

  let { sessionId = $bindable(null), onsession, titreInitial = '' }: Props = $props();

  let items = $state<ChatItem[]>([]);
  let saisie = $state('');
  let enCours = $state(false);
  let chargement = $state(Boolean(sessionId));
  let controleur: AbortController | null = null;
  // Le flux SSE a trois issues, pas deux : il vit, il est coupé et on retrouve la
  // réponse en base, ou il est perdu. Sans le deuxième état, une coupure réseau
  // vidait l'écran alors que le serveur avait terminé et persisté le tour.
  let reprise = $state<'idle' | 'encours'>('idle');
  // Objectif de session, pose par l'agent lui-meme. Affiche hors du fil pour
  // qu'il ne parte pas au defilement : c'est justement ce qui ne doit pas se
  // perdre sur un travail long.
  let objectif = $state<string | null>(null);
  let phase = $state<string | null>(null);
  let usage = $state<AgentSessionUsage | null>(null);
  let decouverte = $state<{
    provider_public_name: string;
    retention_notice: string;
  } | null>(null);
  let banniereMode = $state<'decouverte' | 'gratuit'>('decouverte');

  // Mode gratuit : lanes serveur sans clé, derrière consentement versionné.
  let gratuit = $state<{
    disponible: boolean;
    actif: boolean;
    version_warning: string;
    fournisseur_actuel: string | null;
    modele_actuel: string | null;
    peut_choisir_modele?: boolean;
  } | null>(null);
  let consentOuvert = $state(false);
  const gratuitActif = $derived(gratuit?.actif ?? false);
  // Test de la lane gratuite (même logique que le testeur des clés perso) :
  // 'idle' avant, 'testing' pendant, 'ok'/'ko' après avec le détail renvoyé.
  let etatTestGratuit = $state<'idle' | 'testing' | 'ok' | 'ko'>('idle');
  let messageTestGratuit = $state('');
  // Catalogue des modèles gratuits (primaire + secours) et choix en cours.
  let modelesGratuit = $state<Array<{ model: string; label: string; role: string }>>([]);
  let modelePrimaire = $state('');

  // Selectors provider + modele
  let cles = $state<AgentProvider[]>([]);
  let cleChoisie = $state('');
  let modeles = $state<string[]>([]);
  let modeleChoisi = $state('');
  // Etat de compatibilite du couple cle+modele : 'idle' avant test, 'testing'
  // pendant, 'ok'/'ko' apres, 'incompat' si le modele choisi n'appartient meme
  // pas a la liste des modeles du provider (evite de payer un appel API pour
  // rien).
  let etatTest = $state<'idle' | 'testing' | 'ok' | 'ko' | 'incompat'>('idle');
  let messageTest = $state('');
  let jetonTest = 0; // sert a annuler un test devenu obsolete

  // Agents nommes : chaque definition restreint les outils et le contexte. Le
  // choix vaut pour la session entiere, il est relu au rechargement.
  let agents = $state<AgentDefinition[]>([]);
  let agentChoisi = $state('');
  const agentActif = $derived(agents.find((a) => a.slug === agentChoisi) ?? null);

  // Autoscroll
  let fil = $state<HTMLDivElement | null>(null);
  let auBas = $state(true);
  // Selection en cours : l'utilisateur maintient le bouton et etire la
  // selection. On desactive l'autoscroll de fin de fil (sinon un nouveau
  // token pendant le streaming casse la selection) et on scrolle a la main
  // quand la souris approche les bords du fil (le navigateur ne le fait
  // pas nativement pour un conteneur overflow-y-auto).
  let selectionEnCours = $state(false);
  let intervalleScroll: ReturnType<typeof setInterval> | null = null;

  function arreterScrollSelection() {
    if (intervalleScroll !== null) {
      clearInterval(intervalleScroll);
      intervalleScroll = null;
    }
  }

  function onMouseDownFil() {
    selectionEnCours = true;
  }

  function onMouseUpGlobal() {
    // Le mouseup peut arriver hors du fil : ecoute globale obligatoire.
    if (selectionEnCours) {
      selectionEnCours = false;
      arreterScrollSelection();
    }
  }

  function onMouseMoveFil(e: MouseEvent) {
    if (!selectionEnCours || !fil) return;
    const rect = fil.getBoundingClientRect();
    const zone = 60; // pixels depuis le bord ou l'auto-scroll se declenche
    const vitesse = 18;
    const distanceBas = rect.bottom - e.clientY;
    const distanceHaut = e.clientY - rect.top;
    arreterScrollSelection();
    if (distanceBas < zone && distanceBas > -zone * 2) {
      intervalleScroll = setInterval(() => {
        if (fil) fil.scrollTop += vitesse;
      }, 30);
    } else if (distanceHaut < zone && distanceHaut > -zone * 2) {
      intervalleScroll = setInterval(() => {
        if (fil) fil.scrollTop -= vitesse;
      }, 30);
    }
  }

  $effect(() => {
    window.addEventListener('mouseup', onMouseUpGlobal);
    return () => {
      window.removeEventListener('mouseup', onMouseUpGlobal);
      arreterScrollSelection();
    };
  });

  // Derive un "fingerprint" du dernier contenu assistant pour declencher l'autoscroll
  // meme pendant le streaming token par token.
  const derniereAssistantLongueur = $derived(
    items.filter((i) => i.kind === 'assistant').at(-1)?.text.length ?? 0
  );
  const empreinte = $derived(`${items.length}-${derniereAssistantLongueur}`);

  // Amorces cliquables affichees dans l'EmptyState. Trois questions qui
  // couvrent les trois flux principaux (creation, verification, decouverte)
  // pour aider l'utilisateur qui ne sait pas quoi taper.
  const AMORCES = [
    'Crée une fiche pour cette vidéo YouTube :',
    'Vérifie les extraits de ma dernière source',
    "Trouve des sources sur l'effet Warburg",
  ];

  // Chaque suite d'appels d'outils devient un bloc d'activite resume en une
  // ligne : 64 cartes affichees une a une faisaient du fil un mur.
  const affichables = $derived(regrouper(items));

  // Annonce pour les lecteurs d'ecran. Le fil n'est plus une region vivante :
  // il faisait lire chaque jeton recu. On annonce le debut et la fin du tour.
  let annonce = $state('');

  // Fiche en direct : la fiche que l'agent modifie, a droite du fil, relue a
  // chaque action terminee. Claude a ses artefacts, ChatGPT son canevas ; ici
  // l'objet produit existe deja, c'est la fiche, avec ses verdicts.
  const slugFiche = $derived(slugFicheCourante(items));
  const appelsFinis = $derived(appelsTermines(items));
  const PREFERENCE_FICHE = 'philum:fiche-vivante';
  let ficheOuverte = $state(false);
  let ficheDejaNommee = false;

  function preferenceFiche(): string | null {
    try {
      return localStorage.getItem(PREFERENCE_FICHE);
    } catch {
      return null;
    }
  }

  function basculerFiche(ouvrir: boolean) {
    ficheOuverte = ouvrir;
    try {
      localStorage.setItem(PREFERENCE_FICHE, ouvrir ? 'ouverte' : 'fermee');
    } catch {
      // Préférence non retenue : le panneau se rouvrira à la prochaine fiche.
    }
  }

  // La premiere fiche nommee ouvre le panneau sur grand ecran, sauf si
  // l'utilisateur l'a ferme expres une fois. Sur petit ecran il recouvrirait
  // le fil : il attend qu'on le demande.
  $effect(() => {
    if (!slugFiche || ficheDejaNommee) return;
    ficheDejaNommee = true;
    if (preferenceFiche() !== 'fermee' && window.matchMedia('(min-width: 1280px)').matches) {
      ficheOuverte = true;
    }
  });

  // Zone de saisie : curseur place a l'ouverture et apres une amorce, et
  // brouillon garde par conversation.
  let champSaisie = $state<HTMLTextAreaElement | null>(null);
  const cleBrouillon = $derived(sessionId ?? 'nouvelle');

  async function focaliserSaisie() {
    await tick();
    if (!champSaisie) return;
    champSaisie.focus();
    const fin = champSaisie.value.length;
    champSaisie.setSelectionRange(fin, fin);
    ajusterHauteur(champSaisie);
  }

  /** Remet un message dans la zone de saisie, pour le corriger et le renvoyer.
   *
   * L'historique n'est pas réécrit : l'agent a peut-être déjà écrit en base
   * pendant ce tour, et un historique tronqué le lui cacherait. Le message
   * corrigé part comme un nouveau message.
   */
  function reprendreMessage(texte: string) {
    saisie = texte;
    ecrireBrouillon(cleBrouillon, texte);
    void focaliserSaisie();
  }

  // Echap arrete le tour en cours, sauf s'il sert d'abord a fermer un panneau.
  $effect(() => {
    if (!enCours) return;
    const surTouche = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !reglagesOuverts && !consentOuvert) interrompre();
    };
    window.addEventListener('keydown', surTouche);
    return () => window.removeEventListener('keydown', surTouche);
  });

  // Index du dernier message de l'utilisateur, seul a proposer « Reprendre ».
  const indexDernierUtilisateur = $derived(affichables.findLastIndex((a) => a.kind === 'user'));

  // Curseur clignotant : montre que le modele reflechit *avant* que le
  // premier token n'arrive. Sans ca, l'utilisateur ne sait pas si le message
  // a bien ete envoye pendant les 5-10 s de latence typiques d'un chat LLM.
  const attentePremierToken = $derived(
    enCours && (items.length === 0 || items[items.length - 1].kind === 'user')
  );

  // Modele effectif affiche a cote de l'usage : override de session > modele
  // du provider actif.
  const modeleEffectif = $derived(
    modeleChoisi || cles.find((c) => c.id === cleChoisie)?.model || ''
  );

  // Panneau des reglages, ouvert depuis la pastille de la zone de saisie.
  let reglagesOuverts = $state(false);
  let zoneSaisie = $state<HTMLDivElement | null>(null);

  // La pastille dit qui repondra : c'est le seul reglage utile en permanence,
  // le reste attend dans le panneau.
  const libellePastille = $derived.by(() => {
    const qui = agentActif && agentActif.slug !== 'assistant' ? `${agentActif.name} · ` : '';
    if (gratuitActif) {
      return `${qui}Mode gratuit${gratuit?.modele_actuel ? ` · ${gratuit.modele_actuel}` : ''}`;
    }
    return `${qui}${modeleEffectif || 'Choisir un modèle'}`;
  });
  const etatPastille = $derived(gratuitActif ? (etatTestGratuit === 'ko' ? 'ko' : 'ok') : etatTest);

  // Un clic hors de la zone de saisie ou Echap referme le panneau.
  $effect(() => {
    if (!reglagesOuverts) return;
    const surClic = (e: MouseEvent) => {
      if (zoneSaisie && !zoneSaisie.contains(e.target as Node)) reglagesOuverts = false;
    };
    const surTouche = (e: KeyboardEvent) => {
      if (e.key === 'Escape') reglagesOuverts = false;
    };
    window.addEventListener('click', surClic);
    window.addEventListener('keydown', surTouche);
    return () => {
      window.removeEventListener('click', surClic);
      window.removeEventListener('keydown', surTouche);
    };
  });

  $effect(() => {
    void empreinte; // lire la derivee pour que l'effet se rejoue
    // Ne pas forcer le scroll pendant une selection en cours : chaque
    // nouveau token pendant le streaming pousserait la page et casserait
    // la selection de l'utilisateur.
    if (auBas && fil && !selectionEnCours) {
      tick().then(() => {
        if (fil) fil.scrollTop = fil.scrollHeight;
      });
    }
  });

  function surDefilement() {
    if (!fil) return;
    auBas = fil.scrollHeight - fil.scrollTop - fil.clientHeight < 80;
  }

  function ajusterHauteur(el: HTMLTextAreaElement) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  }

  async function chargerModeles() {
    if (!cleChoisie) {
      modeles = [];
      return;
    }
    try {
      const res = await agentApi.providers.models(cleChoisie);
      // Dédoublonné : la liste vient du fournisseur et sert de clé au `{#each}`
      // du sélecteur, où un doublon leverait et emporterait tout le panneau.
      modeles = [
        ...new Set(res.models.map((m) => (typeof m === 'string' ? m : m.id)).filter(Boolean)),
      ] as string[];
    } catch {
      modeles = [];
    }
  }

  /** Teste le couple cle+modele en cours et met a jour l'indicateur.
   *
   * Le test appelle l'API du provider avec un « ping » (1 token). L'utilisateur
   * voit tout de suite si sa cle refuse le modele choisi, sans devoir envoyer
   * un vrai message et attendre l'erreur en pleine conversation.
   */
  async function testerCombo() {
    if (!cleChoisie) {
      etatTest = 'idle';
      messageTest = '';
      return;
    }
    // Modele sur override actif : il doit appartenir a la liste de la cle.
    // Sans ca l'API renverra une erreur systematiquement, autant l'eviter.
    if (modeleChoisi && modeles.length > 0 && !modeles.includes(modeleChoisi)) {
      etatTest = 'incompat';
      const cle = cles.find((c) => c.id === cleChoisie);
      messageTest = `Le modèle « ${modeleChoisi} » n'existe pas chez ${cle?.display_name ?? 'ce provider'}.`;
      return;
    }
    const jeton = ++jetonTest;
    etatTest = 'testing';
    messageTest = '';
    try {
      const res = await agentApi.providers.test(cleChoisie, modeleChoisi || null);
      if (jeton !== jetonTest) return; // resultat obsolete, l'utilisateur a change de nouveau
      etatTest = res.ok ? 'ok' : 'ko';
      messageTest = res.provider_message ?? res.message ?? '';
    } catch (e) {
      if (jeton !== jetonTest) return;
      etatTest = 'ko';
      messageTest = e instanceof ApiError ? e.message : 'Test impossible.';
    }
  }

  async function changerCle() {
    modeleChoisi = '';
    etatTest = 'idle';
    messageTest = '';
    await chargerModeles();
    if (sessionId && cleChoisie) {
      await agentApi.sessions.update(sessionId, { provider_id: cleChoisie }).catch(() => null);
    }
    void testerCombo();
  }

  async function changerModele() {
    if (sessionId) {
      // Ecrit l'override par session, ne mute jamais le provider global.
      await agentApi.sessions
        .update(sessionId, { model_override: modeleChoisi || null })
        .catch(() => null);
    }
    void testerCombo();
  }

  async function changerAgent() {
    if (sessionId) {
      await agentApi.sessions
        .update(sessionId, { agent_slug: agentChoisi || null })
        .catch(() => null);
    }
  }

  async function activerGratuit(version: string) {
    consentOuvert = false;
    try {
      await agentApi.gratuit.activer(version);
      gratuit = {
        ...(gratuit ?? {
          disponible: true,
          version_warning: version,
          fournisseur_actuel: null,
          modele_actuel: null,
        }),
        actif: true,
      };
      toast.info('Mode gratuit activé. Vous pouvez désactiver à tout moment.');
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Activation impossible.');
    }
  }

  async function testerGratuit() {
    etatTestGratuit = 'testing';
    messageTestGratuit = '';
    try {
      const r = await agentApi.gratuit.tester();
      if (r.ok) {
        etatTestGratuit = 'ok';
        messageTestGratuit = `${r.modele} répond en ${((r.latence_ms ?? 0) / 1000).toFixed(1)} s`;
      } else {
        etatTestGratuit = 'ko';
        messageTestGratuit = r.detail || 'Le fournisseur gratuit ne répond pas.';
      }
    } catch (e) {
      etatTestGratuit = 'ko';
      messageTestGratuit = e instanceof ApiError ? e.message : 'Test impossible.';
    }
  }

  async function desactiverGratuit() {
    try {
      await agentApi.gratuit.desactiver();
      if (gratuit) gratuit = { ...gratuit, actif: false };
      decouverte = null;
      toast.info('Mode gratuit désactivé.');
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Désactivation impossible.');
    }
  }

  async function changerModeleGratuit() {
    if (!modelePrimaire) return;
    try {
      const r = await agentApi.gratuit.definirModele(modelePrimaire);
      if (gratuit) gratuit = { ...gratuit, modele_actuel: r.model };
      modelesGratuit = modelesGratuit.map((m) => ({
        ...m,
        role: m.model === r.model ? 'primaire' : 'secours',
      }));
      toast.info(`Modèle gratuit : ${r.label}. L'ancien reste en secours (rotation auto).`);
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Changement impossible.');
    }
  }

  const libelleTest = $derived(
    etatTest === 'testing'
      ? 'Test…'
      : etatTest === 'ok'
        ? 'OK'
        : etatTest === 'ko'
          ? 'Échec'
          : etatTest === 'incompat'
            ? 'Incompatible'
            : ''
  );

  onMount(async () => {
    const taches: Promise<unknown>[] = [
      agentApi.providers.list().catch(() => []),
      agentApi.definitions.list().catch(() => ({ agents: [], rejected: [] })),
    ];
    if (sessionId) {
      taches.push(agentApi.sessions.messages(sessionId).catch(() => []));
      // Restaurer la clé et le modèle utilisés dans cette session : sans ça
      // on tomberait toujours sur la clé par défaut, ce qui casse la continuité
      // (une conversation démarrée sur Claude repart sur Gemini au reload).
      taches.push(agentApi.sessions.get(sessionId).catch(() => null));
    }

    const [clesRes, agentsRes, messagesRes, sessionRes] = await Promise.allSettled(taches);
    if (clesRes.status === 'fulfilled') {
      cles = clesRes.value as AgentProvider[];
    }
    if (agentsRes.status === 'fulfilled') {
      agents = (agentsRes.value as Awaited<ReturnType<typeof agentApi.definitions.list>>).agents;
    }
    // Etat du mode gratuit : hors du tableau positionnel (backend ancien =
    // endpoint absent, on ignore silencieusement).
    agentApi.gratuit
      .etat()
      .then((v) => {
        gratuit = v;
        modelePrimaire = v.modele_actuel ?? '';
      })
      .catch(() => null);
    agentApi.gratuit
      .modeles()
      .then((r) => (modelesGratuit = r.modeles))
      .catch(() => null);
    // Restauration : d'abord la clé enregistrée sur la session, sinon la clé
    // par défaut du créateur.
    const sessionSauvegardee =
      sessionRes && sessionRes.status === 'fulfilled'
        ? (sessionRes.value as Awaited<ReturnType<typeof agentApi.sessions.get>> | null)
        : null;
    objectif = sessionSauvegardee?.objectif ?? null;
    phase = sessionSauvegardee?.phase ?? null;
    if (
      sessionSauvegardee?.provider_id &&
      cles.some((c) => c.id === sessionSauvegardee.provider_id)
    ) {
      cleChoisie = sessionSauvegardee.provider_id;
    } else {
      // A defaut de cle marquee par defaut, prendre la premiere : envoyer un
      // `provider_id` vide alors que le createur a des cles le renvoyait vers
      // le mode gratuit ou une erreur, sans qu'il comprenne pourquoi.
      const defaut = cles.find((p) => p.is_default) ?? cles[0];
      if (defaut) cleChoisie = defaut.id;
    }
    if (sessionId && messagesRes && messagesRes.status === 'fulfilled') {
      const messages = messagesRes.value as AgentMessage[];
      const aReprendre = tourRecentInacheve(messages);
      items = depuisMessages(messages, { clore: !aReprendre });
      chargement = false;
      if (aReprendre) {
        void reprendreApresCoupure('rechargement').then((retrouve) => {
          if (!retrouve) items = cloturerSansReponse(items);
        });
      }
    } else if (sessionId) {
      chargement = false;
    }
    if (cleChoisie) await chargerModeles();
    // Restauration du modèle : la liste des modèles doit être chargée avant
    // pour que le <select> puisse le sélectionner.
    if (sessionSauvegardee?.model_override) {
      modeleChoisi = sessionSauvegardee.model_override;
    }
    // Un slug dont le fichier a disparu depuis retombe sur le generaliste,
    // comme le fait le serveur : le <select> ne montre pas un choix mort.
    if (
      sessionSauvegardee?.agent_slug &&
      agents.some((a) => a.slug === sessionSauvegardee.agent_slug)
    ) {
      agentChoisi = sessionSauvegardee.agent_slug;
    } else if (agents.length > 0) {
      agentChoisi = agents.some((a) => a.slug === 'assistant') ? 'assistant' : agents[0].slug;
    }
    // Test discret du couple cle+modele au chargement : si le modele
    // enregistre en session n'existe plus (compte migre, plan degrade),
    // l'utilisateur le voit avant d'envoyer un message.
    if (cleChoisie) void testerCombo();
    // Le brouillon laisse dans cette conversation revient, et le curseur est
    // pret : ouvrir l'agent, c'est pour lui ecrire.
    if (!saisie) saisie = lireBrouillon(cleBrouillon);
    void focaliserSaisie();
  });

  /** Relit l'objectif après un tour : c'est l'agent qui le pose, pas l'interface. */
  async function rafraichirObjectif() {
    if (!sessionId) return;
    const s = await agentApi.sessions.get(sessionId).catch(() => null);
    if (!s) return;
    objectif = s.objectif ?? null;
    phase = s.phase ?? null;
  }

  /** Délais entre deux relectures, en millisecondes. Total un peu moins d'une minute. */
  const DELAIS_REPRISE = [1000, 2000, 3000, 5000, 8000, 13000, 21000];

  /** Pourquoi on relit la session : une coupure du flux, ou une conversation
   * rouverte pendant que le serveur termine son tour. */
  let motifReprise = $state<'coupure' | 'rechargement'>('coupure');

  /** Au-delà, un tour inachevé ne reviendra plus : on le clôt au lieu d'attendre. */
  const FRAICHEUR_TOUR_MS = 10 * 60 * 1000;

  /** Le serveur termine-t-il peut-être encore le dernier tour ?
   *
   * Rouvrir une conversation pendant qu'il travaille affichait ses appels en
   * échec, avec « Aucun résultat reçu », alors que les résultats arrivaient.
   */
  function tourRecentInacheve(messages: AgentMessage[]): boolean {
    if (messages.length === 0 || tourTermine(messages)) return false;
    const brut = messages[messages.length - 1].created_at;
    // Les dates du serveur sont en UTC, sans fuseau écrit.
    const quand = Date.parse(/[zZ]$|[+-]\d\d:\d\d$/.test(brut) ? brut : `${brut}Z`);
    return Number.isFinite(quand) && Date.now() - quand < FRAICHEUR_TOUR_MS;
  }

  /** Rattrape un tour dont le flux a été coupé.
   *
   * Le serveur termine et persiste le tour même quand le client se déconnecte
   * (`_persister_tour`) : il n'y a donc rien à rejouer, il suffit de relire la
   * session. Pas de tampon en mémoire côté serveur, donc rien à perdre à un
   * redéploiement. Rend `true` si la réponse a été retrouvée.
   */
  async function reprendreApresCoupure(
    motif: 'coupure' | 'rechargement' = 'coupure'
  ): Promise<boolean> {
    if (!sessionId) return false;
    motifReprise = motif;
    reprise = 'encours';
    try {
      for (const delai of DELAIS_REPRISE) {
        await new Promise((r) => setTimeout(r, delai));
        const messages = await agentApi.sessions.messages(sessionId).catch(() => null);
        if (!messages) continue;
        if (tourTermine(messages)) {
          items = depuisMessages(messages);
          auBas = true;
          return true;
        }
      }
      return false;
    } finally {
      reprise = 'idle';
    }
  }

  /** Traite l'échec d'un flux : abandon volontaire, reprise, ou échec définitif.
   *
   * Une `ApiError` vient du contrôle de statut, avant que le corps ne s'ouvre :
   * la requête a été refusée, aucun tour n'a démarré, il n'y a rien à relire.
   * Seule une coupure en cours de flux vaut une reprise.
   */
  async function surCoupure(e: unknown) {
    if ((e as Error)?.name === 'AbortError') return;
    // Le flux est mort : plus rien n'arrive, l'indicateur de frappe mentirait.
    enCours = false;
    if (e instanceof ApiError) {
      items = [...items, { kind: 'error', text: e.message }];
      return;
    }
    if (await reprendreApresCoupure()) return;
    items = [
      ...items,
      {
        kind: 'error',
        text: "La connexion s'est coupée et la réponse n'est pas encore revenue. Le serveur termine le tour de son côté : rechargez la page dans un instant pour la relire.",
      },
    ];
  }

  async function envoyer(event: SubmitEvent) {
    event.preventDefault();
    if (event.target instanceof HTMLFormElement) {
      const textarea = event.target.querySelector('textarea');
      if (textarea) textarea.style.height = 'auto';
    }
    const message = saisie.trim();
    if (!message || enCours || reprise === 'encours') return;
    saisie = '';
    effacerBrouillon(cleBrouillon);
    await lancerTour(message);
  }

  /** Envoie un message et déroule le tour : commun à l'envoi, à « Continuer » et à « Réessayer ». */
  async function lancerTour(message: string) {
    // Envoyer pendant une reprise ferait écraser le fil par la relecture.
    if (enCours || reprise === 'encours') return;
    auBas = true;
    items = [...items, { kind: 'user', text: message }];
    enCours = true;
    annonce = 'Message envoyé. L’agent travaille.';
    controleur = new AbortController();
    try {
      for await (const evenement of agentApi.streamChat({
        message,
        session_id: sessionId ?? undefined,
        // Mode gratuit : la lane serveur décide du provider ET du modèle.
        // Envoyer un override écraserait le modèle de la lane côté serveur.
        ...(gratuitActif
          ? {}
          : {
              provider_id: cleChoisie || undefined,
              model_override: modeleChoisi || undefined,
            }),
        agent_slug: agentChoisi || undefined,
        signal: controleur.signal,
      })) {
        if (evenement.type === 'session' && !sessionId) {
          sessionId = evenement.payload.id;
          if (titreInitial && sessionId) {
            // L'echec etait avale : la conversation gardait le debut du message
            // pour titre, sans que rien ne le dise.
            await agentApi.sessions
              .update(sessionId, { title: titreInitial })
              .catch(() =>
                toast.danger(
                  "Le nom n'a pas pu être enregistré. Renommez la conversation depuis son en-tête."
                )
              );
          }
          onsession?.(sessionId);
        }
        if (evenement.type === 'discovery_active') {
          decouverte = evenement.payload;
          banniereMode = 'decouverte';
        }
        if (evenement.type === 'gratuit_actif') {
          decouverte = evenement.payload;
          banniereMode = 'gratuit';
        }
        items = appliquer(items, evenement);
      }
    } catch (e) {
      await surCoupure(e);
    } finally {
      enCours = false;
      controleur = null;
      annonce = 'Réponse de l’agent terminée.';
      if (sessionId) {
        agentApi.sessions
          .usage(sessionId)
          .then((u) => (usage = u))
          .catch(() => null);
      }
      void rafraichirObjectif();
    }
  }

  function interrompre() {
    controleur?.abort();
  }

  async function repondreApprobation(requestId: string, approuve: boolean) {
    try {
      await agentApi.approve(requestId, approuve);
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : "Cette demande n'attend plus de reponse.");
    }
  }

  function continuer() {
    void lancerTour('continue');
  }

  /** Renvoie le dernier message de l'utilisateur.
   *
   * « Réessayer » envoyait le mot « continue ». Quand l'erreur précédait la
   * création de la session, cela ouvrait une conversation intitulée ainsi.
   */
  function reessayer() {
    const dernier = items.findLast((i) => i.kind === 'user');
    if (!dernier || dernier.kind !== 'user') return;
    if (items.at(-1)?.kind === 'error') items = items.slice(0, -1);
    void lancerTour(dernier.text);
  }

  // Deux leviers distincts cote serveur : raccourcir de gros resultats d'outils,
  // et retirer des messages du debut. Les nommer separement, sinon un elagage
  // seul s'afficherait « 0 message retire ».
  function texteCompaction(retires: number, elagues: number): string {
    const parts: string[] = [];
    if (elagues > 0)
      parts.push(
        `${elagues} résultat${elagues > 1 ? 's' : ''} d'outil raccourci${elagues > 1 ? 's' : ''}`
      );
    if (retires > 0)
      parts.push(
        `${retires} message${retires > 1 ? 's' : ''} du début retiré${retires > 1 ? 's' : ''}`
      );
    if (parts.length === 0) return 'Contexte compacté pour tenir dans la fenêtre du modèle';
    return `${parts.join(', ')} pour tenir dans la fenêtre du modèle`;
  }
</script>

<!-- Le panneau prend la hauteur que son parent lui donne, il ne la calcule plus.
     Le `calc(100dvh-12rem)` d'avant supposait une seule entete au-dessus : sur
     la page d'accueil de l'agent, qui porte en plus un titre, une ligne d'etat
     et un champ de nommage, la zone de saisie tombait sous la ligne de flottaison
     et il fallait faire defiler la page pour ecrire. -->
<div class="flex h-full min-h-0 gap-4">
  <div class="flex h-full min-h-0 min-w-0 flex-1 flex-col">
    <!-- Reglages : agent, cle, modele, mode gratuit. Ils s'ouvrent depuis la
       pastille de la zone de saisie. En ligne permanente au-dessus du fil, ils
       prenaient jusqu'a cinq lignes, et le fil n'avait plus que la moitie de
       l'ecran (348 px sur 695, mesure du 2026-09-11). -->
    {#snippet reglages()}
      {#if cles.length > 0 || agents.length > 0 || (gratuit?.disponible ?? false)}
        <div class="flex flex-wrap items-center gap-3 text-sm">
          {#if agents.length > 0}
            <label class="flex items-center gap-1.5">
              <span class="text-xs text-ink-tertiary">Agent</span>
              <select
                bind:value={agentChoisi}
                onchange={changerAgent}
                disabled={enCours}
                class="rounded border border-border bg-surface-primary px-2 py-1 text-xs"
              >
                {#each agents as a (a.slug)}
                  <option value={a.slug}>{a.name}</option>
                {/each}
              </select>
            </label>
          {/if}
          {#if gratuitActif}
            <!-- Mode gratuit actif : la lane serveur porte la cle ; le modele
             primaire se choisit dans le catalogue gratuit, le secours prend
             le relais automatiquement quand le primaire sature. -->
            <span
              class="flex items-center gap-1.5 rounded border border-emerald-300 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700 dark:border-emerald-700 dark:bg-emerald-950 dark:text-emerald-200"
            >
              Mode gratuit{gratuit?.fournisseur_actuel ? ` · ${gratuit.fournisseur_actuel}` : ''}
            </span>
            {#if modelesGratuit.length > 0 && gratuit?.peut_choisir_modele}
              <label class="flex items-center gap-1.5">
                <span class="text-xs text-ink-tertiary">Modèle</span>
                <select
                  bind:value={modelePrimaire}
                  onchange={changerModeleGratuit}
                  disabled={enCours}
                  class="rounded border border-border bg-surface-primary px-2 py-1 text-xs"
                  title="Modèle principal du mode gratuit pour toute l'instance ; l'autre modèle du catalogue sert de secours en cas de surcharge"
                >
                  {#each modelesGratuit as m (m.model)}
                    <option value={m.model}>
                      {m.label}{m.role === 'secours' ? ' (secours)' : ''}
                    </option>
                  {/each}
                </select>
              </label>
            {:else if gratuit?.modele_actuel}
              <span class="text-xs text-ink-tertiary" title="Modèle qui sert les messages">
                {gratuit.modele_actuel}
              </span>
            {/if}
            <button
              type="button"
              class="rounded border border-border bg-surface-primary px-2 py-1 text-xs hover:border-primary-600 hover:text-primary-700 disabled:opacity-50 dark:hover:border-primary-400 dark:hover:text-primary-300"
              onclick={testerGratuit}
              disabled={etatTestGratuit === 'testing'}
              title="Envoyer un ping au fournisseur gratuit (hors quota) pour vérifier qu'il répond"
            >
              {etatTestGratuit === 'testing'
                ? 'Test…'
                : etatTestGratuit === 'ok'
                  ? 'OK'
                  : etatTestGratuit === 'ko'
                    ? 'Échec'
                    : 'Tester'}
            </button>
            <button
              type="button"
              class="rounded border border-border bg-surface-primary px-2 py-1 text-xs text-ink-secondary hover:border-danger hover:text-danger disabled:opacity-50"
              onclick={desactiverGratuit}
              disabled={enCours}
              title="Revenir à votre clé personnelle pour les nouveaux messages"
            >
              Quitter le mode gratuit
            </button>
          {:else}
            {#if cles.length > 0}
              <label class="flex items-center gap-1.5">
                <span class="text-xs text-ink-tertiary">Clé</span>
                <select
                  bind:value={cleChoisie}
                  onchange={changerCle}
                  disabled={enCours}
                  class="rounded border border-border bg-surface-primary px-2 py-1 text-xs"
                >
                  {#each cles as cle (cle.id)}
                    <option value={cle.id}>{cle.display_name} ({cle.api_key_masked})</option>
                  {/each}
                </select>
              </label>
            {/if}
            {#if modeles.length > 0}
              <label class="flex items-center gap-1.5">
                <span class="text-xs text-ink-tertiary">Modèle</span>
                <select
                  bind:value={modeleChoisi}
                  onchange={changerModele}
                  disabled={enCours}
                  class="rounded border border-border bg-surface-primary px-2 py-1 text-xs"
                >
                  <option value=""
                    >Défaut ({cles.find((c) => c.id === cleChoisie)?.model ?? ''})</option
                  >
                  {#each modeles as m (m)}
                    <option value={m}>{m}</option>
                  {/each}
                </select>
              </label>
            {/if}
            {#if gratuit?.disponible}
              <button
                type="button"
                class="rounded border border-border bg-surface-secondary px-2 py-1 text-xs text-ink-secondary hover:border-info hover:text-ink-primary disabled:opacity-50"
                onclick={() => (consentOuvert = true)}
                disabled={enCours}
                title="Utiliser l'agent sans clé, via les serveurs Philum"
              >
                Mode gratuit…
              </button>
              <!-- Pas de « Tester » ici : celui du couple cle+modele suit
               immediatement, et deux boutons du meme nom cote a cote ne
               disaient pas lequel testait quoi. Le fournisseur gratuit se
               teste depuis la barre du mode gratuit, une fois celui-ci actif,
               la ou le resultat porte a consequence. -->
            {/if}
          {/if}
          <!-- Indicateur du dernier test cle+modele. Le bouton relance le test a
           la demande ; le point coloré resume l'etat sans se disputer la
           largeur avec les selecteurs. -->
          {#if !gratuitActif}
            <span class="flex items-center gap-1.5">
              <span
                aria-hidden="true"
                class="inline-block h-2 w-2 rounded-full"
                class:bg-emerald-500={etatTest === 'ok'}
                class:bg-red-500={etatTest === 'ko' || etatTest === 'incompat'}
                class:bg-amber-400={etatTest === 'testing'}
                class:bg-ink-tertiary={etatTest === 'idle'}
                class:animate-pulse={etatTest === 'testing'}
              ></span>
              {#if libelleTest}
                <span
                  class="text-xs"
                  class:text-emerald-600={etatTest === 'ok'}
                  class:text-danger={etatTest === 'ko' || etatTest === 'incompat'}
                  class:text-ink-tertiary={etatTest === 'testing' || etatTest === 'idle'}
                  title={messageTest}
                >
                  {libelleTest}
                </span>
              {/if}
              <button
                type="button"
                class="text-xs text-ink-tertiary underline hover:text-ink-primary disabled:opacity-50"
                onclick={testerCombo}
                disabled={enCours || etatTest === 'testing' || !cleChoisie}
                title="Tester le couple clé + modèle"
              >
                Tester
              </button>
            </span>
          {/if}
        </div>
        {#if agentActif}
          <p class="mb-2 text-xs text-ink-tertiary">
            {agentActif.contract}
            <span class="text-ink-tertiary">({agentActif.tools.length} outils)</span>
          </p>
          {#if agentActif.tools_absents.length > 0}
            <p class="mb-2 text-xs text-warning">
              Outils demandés mais non disponibles sur ce serveur : {agentActif.tools_absents.join(
                ', '
              )}
            </p>
          {/if}
        {/if}
        {#if messageTest && (etatTest === 'ko' || etatTest === 'incompat')}
          <p class="mb-2 text-xs text-danger">{messageTest}</p>
        {/if}
        {#if messageTestGratuit && etatTestGratuit === 'ko'}
          <p class="mb-2 text-xs text-danger">Fournisseur gratuit : {messageTestGratuit}</p>
        {:else if messageTestGratuit && etatTestGratuit === 'ok'}
          <p class="mb-2 text-xs text-emerald-600 dark:text-emerald-400">
            Fournisseur gratuit : {messageTestGratuit}
          </p>
        {/if}
      {/if}
    {/snippet}

    <!-- Fil de conversation : un seul fil vertical, pas de bulles. Les tours
       utilisateur sont marques par une barre laterale plutot qu'une bulle
       flottante (standard 2026 : ChatGPT, Claude, Cursor). -->
    {#if objectif}
      <!-- Hors du fil, exprès : l'objectif sert justement sur les conversations
         longues, celles ou une ligne posee au debut aurait disparu du champ. -->
      <p
        class="mx-auto w-full max-w-4xl shrink-0 truncate border-l-2 border-info px-3 py-1 text-xs text-ink-secondary"
        title={objectif}
      >
        <span class="text-ink-tertiary">Objectif :</span>
        {objectif}{#if phase}<span class="text-ink-tertiary"> · {phase}</span>{/if}
      </p>
    {/if}

    <p class="sr-only" role="status">{annonce}</p>

    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div
      bind:this={fil}
      class="min-h-0 flex-1 overflow-y-auto px-1 py-2"
      onscroll={surDefilement}
      onmousedown={onMouseDownFil}
      onmousemove={onMouseMoveFil}
      role="log"
      aria-live="off"
      aria-busy={enCours}
    >
      <!-- Le fil defile sur toute la largeur, sa barre au bord de l'ecran ; le
         texte, lui, reste a une largeur de lecture. -->
      <div class="mx-auto max-w-4xl space-y-4">
        {#if chargement}
          <p class="text-sm text-ink-tertiary">Chargement de la conversation...</p>
        {:else if items.length === 0}
          <div class="mt-6 space-y-3">
            <p class="text-sm text-ink-secondary">
              Que doit faire l'agent ? Cliquez une amorce ou tapez la vôtre.
            </p>
            <ul class="space-y-1.5">
              {#each AMORCES as amorce (amorce)}
                <li>
                  <button
                    type="button"
                    class="w-full rounded border border-border bg-surface-secondary px-3 py-2 text-left text-sm text-ink-primary hover:border-info hover:bg-surface-tertiary"
                    onclick={() => {
                      // Une amorce qui attend une suite (une adresse) finit par
                      // une espace, et le curseur s'y place : il n'y a plus qu'a
                      // coller.
                      saisie = amorce.endsWith(':') ? `${amorce} ` : amorce;
                      void focaliserSaisie();
                    }}
                  >
                    {amorce}
                  </button>
                </li>
              {/each}
            </ul>
          </div>
        {/if}

        {#each affichables as item, i (i)}
          {#if item.kind === 'user'}
            <div class="group border-l-2 border-info pl-3 text-sm text-ink-primary">
              <p class="whitespace-pre-wrap [overflow-wrap:anywhere]">{item.text}</p>
              <div
                class="mt-1 flex gap-1 opacity-60 group-hover:opacity-100 focus-within:opacity-100"
              >
                <CopierBouton texte={item.text} />
                {#if !enCours && i === indexDernierUtilisateur}
                  <button
                    type="button"
                    class="rounded px-1.5 py-0.5 text-xs text-ink-tertiary hover:bg-surface-tertiary hover:text-ink-primary"
                    title="Remettre ce message dans la zone de saisie pour le corriger"
                    onclick={() => reprendreMessage(item.text)}
                  >
                    Reprendre
                  </button>
                {/if}
              </div>
            </div>
          {:else if item.kind === 'assistant'}
            <div class="group min-w-0 text-sm">
              <AgentMarkdown texte={item.text} />
              <!-- Pas de copie sur la reponse qui s'ecrit encore : on copierait
                 une moitie de phrase. -->
              {#if !(enCours && i === affichables.length - 1)}
                <div class="mt-1 flex opacity-60 group-hover:opacity-100 focus-within:opacity-100">
                  <CopierBouton texte={item.text} />
                </div>
              {/if}
            </div>
          {:else if item.kind === 'activite'}
            <BlocActivite bloc={item} enDirect={enCours && i === affichables.length - 1} />
          {:else if item.kind === 'compaction'}
            <!-- Le debut de la conversation est sorti de la fenetre du modele. Le
             dire ici, a sa place dans le fil : l'agent qui « oublie » sans
             prevenir passe pour defaillant alors qu'il subit une limite. -->
            <div class="flex items-center gap-3 py-1 text-xs text-ink-tertiary">
              <span class="h-px flex-1 bg-border"></span>
              <span>{texteCompaction(item.retires, item.elagues)}</span>
              <span class="h-px flex-1 bg-border"></span>
            </div>
          {:else if item.kind === 'controle'}
            <!-- La reponse au-dessus annoncait une action que rien n'avait executee.
             Sans cette marque, la reponse suivante contredit la precedente et
             l'utilisateur ne sait pas laquelle croire. -->
            <div class="flex items-center gap-3 py-1 text-xs text-amber-700 dark:text-amber-400">
              <span class="h-px flex-1 bg-border"></span>
              <span>Action annoncée mais non exécutée : réponse redemandée</span>
              <span class="h-px flex-1 bg-border"></span>
            </div>
          {:else if item.kind === 'repli'}
            <!-- Une cle a refuse, une autre a pris le relais. Discret et non rouge :
             la conversation a continue, seule la cle a change. Le taire ferait
             passer le temps perdu a essayer pour une lenteur du modele. -->
            <div class="flex items-center gap-3 py-1 text-xs text-ink-tertiary">
              <span class="h-px flex-1 bg-border"></span>
              <span>{item.quitte} n'a pas répondu, {item.pris} prend le relais. {item.raison}</span>
              <span class="h-px flex-1 bg-border"></span>
            </div>
          {:else if item.kind === 'approval'}
            <ApprovalCard
              tool={item.tool}
              args={item.args}
              resume={item.resume}
              expiresAt={item.expiresAt}
              approved={item.approved}
              onrespond={(approuve) => repondreApprobation(item.requestId, approuve)}
            />
          {:else if item.kind === 'continuation'}
            <div
              class="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 dark:border-amber-700 dark:bg-amber-950"
            >
              <p class="text-sm text-amber-800 dark:text-amber-200">{item.message}</p>
              <!-- `enCours` n'est plus force ici : quand le tour ne partait pas
               (reprise en cours), il restait vrai sans flux derriere, et la
               saisie affichait « Arreter » jusqu'au rechargement. -->
              <Button
                variant="ghost"
                onclick={continuer}
                disabled={enCours || reprise === 'encours'}>Continuer</Button
              >
            </div>
          {:else}
            <div
              role="alert"
              class="rounded-lg border border-danger/30 bg-danger-bg px-3 py-2 text-sm text-danger"
            >
              <p class="[overflow-wrap:anywhere]">{item.text}</p>
              <!-- Seule la derniere erreur se reessaie : une erreur ancienne n'a
               plus de message a renvoyer qui ait un sens a cet endroit du fil. -->
              {#if i === affichables.length - 1}
                <button
                  type="button"
                  class="mt-1 text-xs font-medium text-danger underline hover:no-underline disabled:opacity-50"
                  disabled={enCours || reprise === 'encours'}
                  onclick={reessayer}>Réessayer</button
                >
              {/if}
            </div>
          {/if}
        {/each}

        {#if attentePremierToken}
          <!-- Curseur clignotant : le message est parti, le modele n'a pas
           encore repondu. Sans ce signal, l'utilisateur ne sait pas si
           l'envoi a echoue ou si l'agent reflechit. -->
          <div class="flex items-center gap-2 text-sm text-ink-secondary">
            <span class="curseur-clignotant inline-block h-4 w-[2px] bg-ink-primary"></span>
          </div>
        {/if}

        {#if enCours && !attentePremierToken}
          <!-- Logo Philum anime : rassure sur le travail en cours apres le premier
           token (recherche web, appel d'outil, etc.). Avant le premier token,
           le curseur clignotant tient deja ce role : afficher les deux ferait
           deux signaux pour un seul etat. -->
          <div class="flex items-center gap-2 text-xs text-ink-tertiary">
            <LogoLoader size={20} />
            <span>Philum réfléchit…</span>
          </div>
        {/if}

        {#if reprise === 'encours'}
          <!-- Troisieme etat : le flux est coupe mais le serveur termine le tour de
           son cote. Le dire, sinon l'utilisateur lit une perte de donnees la ou
           il n'y a qu'une deconnexion. -->
          <div class="flex items-center gap-2 text-xs text-ink-tertiary" role="status">
            <LogoLoader size={20} />
            <span>
              {motifReprise === 'rechargement'
                ? 'L’agent termine un tour commencé plus tôt, on récupère sa réponse…'
                : 'Connexion perdue. La réponse continue côté serveur, on la récupère…'}
            </span>
          </div>
        {/if}
      </div>
    </div>

    <!-- Bouton "nouveaux messages" quand l'utilisateur a remonte -->
    {#if !auBas && enCours}
      <button
        type="button"
        class="mx-auto mb-1 rounded-full border border-border bg-surface-secondary px-3 py-1 text-xs text-ink-secondary shadow-sm hover:bg-surface-tertiary"
        onclick={() => {
          auBas = true;
          if (fil) fil.scrollTop = fil.scrollHeight;
        }}
      >
        Nouveaux messages
      </button>
    {/if}

    {#snippet usageLigne()}
      {#if usage && (usage.total_prompt_tokens > 0 || usage.total_completion_tokens > 0)}
        <p class="text-xs text-ink-tertiary">
          Cette conversation : {(usage.total_prompt_tokens / 1000).toFixed(1)} k jetons envoyés,
          {(usage.total_completion_tokens / 1000).toFixed(1)} k reçus{usage.cost_eur != null
            ? `, environ ${usage.cost_eur.toFixed(2)} €`
            : ''}.
        </p>
      {/if}
    {/snippet}

    {#snippet noticeMode()}
      {#if decouverte}
        <div
          class="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200"
        >
          {#if banniereMode === 'gratuit'}
            <span class="font-medium">Mode gratuit</span> : vos échanges transitent par
          {:else}
            <span class="font-medium">Mode découverte</span> : vos échanges transitent par
          {/if}
          <span class="font-medium">{decouverte.provider_public_name}</span>.
          {decouverte.retention_notice}
          <!-- Plus de « N messages restants » : le compteur ne comptait qu'un tour
           termine page ouverte, et affichait 30 restants apres 9 envois. -->
          {#if banniereMode === 'gratuit'}
            <button
              type="button"
              class="ml-1 underline"
              onclick={desactiverGratuit}
              disabled={enCours}
            >
              Désactiver le mode gratuit</button
            >.
          {:else}
            <a href="/dashboard/agents" class="ml-1 underline">Connecter votre clé</a>
          {/if}
        </div>
      {/if}
    {/snippet}

    {#if consentOuvert && gratuit}
      <ConsentementGratuit
        version={gratuit.version_warning}
        onvalider={activerGratuit}
        onfermer={() => (consentOuvert = false)}
      />
    {/if}

    <!-- Zone de saisie : un seul cadre, la pastille des reglages a gauche et
       l'envoi a droite, comme chez Claude et ChatGPT. Le panneau des reglages
       s'ouvre au-dessus, par-dessus le fil, et ne lui prend plus de hauteur. -->
    <div class="relative mx-auto w-full max-w-4xl shrink-0 pt-2" bind:this={zoneSaisie}>
      {#if reglagesOuverts}
        <div
          id="reglages-agent"
          class="absolute bottom-full left-0 z-20 mb-2 max-h-[60vh] w-full space-y-3 overflow-y-auto rounded-lg border border-border bg-surface-primary p-3 shadow-lg"
        >
          {@render reglages()}
          {@render noticeMode()}
          {@render usageLigne()}
          <a href="/dashboard/agents" class="inline-block text-xs text-info hover:underline">
            Gérer vos clés
          </a>
        </div>
      {/if}
      {#if messageTest && (etatTest === 'ko' || etatTest === 'incompat') && !reglagesOuverts}
        <!-- Un couple cle et modele refuse doit se voir sans ouvrir le panneau :
           c'est lui qui fera echouer le prochain message. -->
        <p class="mb-1 text-xs text-danger">{messageTest}</p>
      {/if}
      <form
        class="rounded-xl border border-border bg-surface-primary px-3 py-2 shadow-sm focus-within:border-info"
        onsubmit={envoyer}
      >
        <textarea
          bind:this={champSaisie}
          bind:value={saisie}
          rows="1"
          aria-label="Message à l'agent"
          placeholder="Que doit faire l'agent ?"
          class="block w-full resize-none bg-transparent py-1 text-sm text-ink-primary outline-none touch-manipulation placeholder:text-ink-tertiary"
          style="overflow-y: hidden;"
          oninput={(e) => {
            ajusterHauteur(e.currentTarget);
            ecrireBrouillon(cleBrouillon, e.currentTarget.value);
          }}
          onkeydown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
              e.preventDefault();
              if (!enCours && saisie.trim()) {
                e.currentTarget.form?.requestSubmit();
              }
            }
          }}></textarea>
        <div class="mt-1 flex items-center gap-2">
          <button
            type="button"
            class="flex min-w-0 items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs text-ink-secondary hover:border-info hover:text-ink-primary"
            aria-expanded={reglagesOuverts}
            aria-controls="reglages-agent"
            title="Agent, clé, modèle et mode gratuit"
            onclick={() => (reglagesOuverts = !reglagesOuverts)}
          >
            <span
              aria-hidden="true"
              class="inline-block h-2 w-2 shrink-0 rounded-full"
              class:bg-emerald-500={etatPastille === 'ok'}
              class:bg-red-500={etatPastille === 'ko' || etatPastille === 'incompat'}
              class:bg-amber-400={etatPastille === 'testing'}
              class:bg-ink-tertiary={etatPastille === 'idle'}
            ></span>
            <span class="truncate">{libellePastille}</span>
            <span aria-hidden="true" class="text-ink-tertiary">▾</span>
          </button>
          <button
            type="button"
            class="shrink-0 rounded-full border border-border px-2.5 py-1 text-xs text-ink-secondary hover:border-info hover:text-ink-primary"
            aria-pressed={ficheOuverte}
            title="La fiche que l’agent modifie, mise à jour à chacune de ses actions"
            onclick={() => basculerFiche(!ficheOuverte)}
          >
            {ficheOuverte ? 'Masquer la fiche' : 'Voir la fiche'}
          </button>
          <span class="flex-1"></span>
          {#if enCours}
            <Button size="sm" variant="ghost" onclick={interrompre}>Arrêter</Button>
          {:else}
            <Button size="sm" type="submit" disabled={!saisie.trim() || reprise === 'encours'}
              >Envoyer</Button
            >
          {/if}
        </div>
      </form>
    </div>
  </div>
  {#if ficheOuverte}
    <!-- A cote du fil a partir de `lg` ; en dessous, la fiche le recouvre et se
       referme par sa croix. -->
    <div class="fixed inset-0 z-40 bg-surface-primary lg:static lg:z-auto lg:shrink-0">
      <FicheVivante
        slug={slugFiche}
        empreinte={appelsFinis}
        onfermer={() => basculerFiche(false)}
      />
    </div>
  {/if}
</div>

<style>
  .curseur-clignotant {
    animation: clignoter 1s steps(2, start) infinite;
  }
  @keyframes clignoter {
    to {
      visibility: hidden;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .curseur-clignotant {
      animation: none;
      opacity: 0.6;
    }
  }
</style>
