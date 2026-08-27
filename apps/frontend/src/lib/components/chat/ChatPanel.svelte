<script lang="ts">
  import { onMount, tick } from 'svelte';
  import {
    agentApi,
    type AgentDefinition,
    type AgentProvider,
    type AgentSessionUsage,
  } from '$lib/api/agent';
  import { ApiError } from '$lib/api';
  import { appliquer, depuisMessages, type ChatItem } from '$lib/agent/conversation';
  import Button from '../Button.svelte';
  import { toast } from '../Toast.svelte';
  import ApprovalCard from './ApprovalCard.svelte';
  import ToolCard from './ToolCard.svelte';
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
  let usage = $state<AgentSessionUsage | null>(null);
  let decouverte = $state<{
    provider_public_name: string;
    remaining_today: number | null;
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

  // Regroupe les appels d'outils consecutifs de meme nom pour eviter d'avoir
  // 10 cartes « Lit la source #a1b2c3d4 » qui empilent le meme verbe. Le nom
  // « Lit la source » figure une fois, les entrees s'empilent en dessous.
  type Affichable =
    | Extract<
        ChatItem,
        { kind: 'user' | 'assistant' | 'approval' | 'error' | 'compaction' | 'continuation' }
      >
    | {
        kind: 'group-outils';
        name: string;
        entrees: Extract<ChatItem, { kind: 'tool' }>[];
      };

  const affichables = $derived.by<Affichable[]>(() => {
    const rendu: Affichable[] = [];
    for (const item of items) {
      if (item.kind === 'tool') {
        const dernier = rendu[rendu.length - 1];
        if (dernier?.kind === 'group-outils' && dernier.name === item.name) {
          dernier.entrees.push(item);
          continue;
        }
        rendu.push({ kind: 'group-outils', name: item.name, entrees: [item] });
        continue;
      }
      rendu.push(item);
    }
    return rendu;
  });

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
      modeles = res.models
        .map((m) => (typeof m === 'string' ? m : m.id))
        .filter(Boolean) as string[];
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
        messageTestGratuit = `OK — ${r.modele} en ${((r.latence_ms ?? 0) / 1000).toFixed(1)} s`;
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
      items = depuisMessages(
        messagesRes.value as Awaited<ReturnType<typeof agentApi.sessions.messages>>
      );
      chargement = false;
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
  });

  async function envoyer(event: SubmitEvent) {
    event.preventDefault();
    if (event.target instanceof HTMLFormElement) {
      const textarea = event.target.querySelector('textarea');
      if (textarea) textarea.style.height = 'auto';
    }
    const message = saisie.trim();
    if (!message || enCours) return;
    saisie = '';
    auBas = true;
    items = [...items, { kind: 'user', text: message }];
    enCours = true;
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
            await agentApi.sessions.update(sessionId, { title: titreInitial }).catch(() => null);
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
      if ((e as Error)?.name !== 'AbortError') {
        items = [
          ...items,
          {
            kind: 'error',
            text: e instanceof ApiError ? e.message : "L'agent s'est interrompu.",
          },
        ];
      }
    } finally {
      enCours = false;
      controleur = null;
      if (sessionId) {
        agentApi.sessions
          .usage(sessionId)
          .then((u) => (usage = u))
          .catch(() => null);
      }
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

  async function continuer() {
    if (enCours) return;
    const message = 'continue';
    auBas = true;
    items = [...items, { kind: 'user', text: message }];
    enCours = true;
    controleur = new AbortController();
    try {
      for await (const evenement of agentApi.streamChat({
        message,
        session_id: sessionId ?? undefined,
        ...(gratuitActif
          ? {}
          : {
              provider_id: cleChoisie || undefined,
              model_override: modeleChoisi || undefined,
            }),
        agent_slug: agentChoisi || undefined,
        signal: controleur.signal,
      })) {
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
      if ((e as Error)?.name !== 'AbortError') {
        items = [
          ...items,
          { kind: 'error', text: e instanceof ApiError ? e.message : "L'agent s'est interrompu." },
        ];
      }
    } finally {
      enCours = false;
      controleur = null;
      if (sessionId)
        agentApi.sessions
          .usage(sessionId)
          .then((u) => (usage = u))
          .catch(() => null);
    }
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

<div class="flex h-[calc(100dvh-12rem)] flex-col">
  <!-- Selectors agent, provider et modele -->
  {#if cles.length > 0 || agents.length > 0 || (gratuit?.disponible ?? false)}
    <div class="mb-2 flex flex-wrap gap-3 border-b border-border pb-2 text-sm">
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
        {#if modelesGratuit.length > 0}
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
              <option value="">Défaut ({cles.find((c) => c.id === cleChoisie)?.model ?? ''})</option
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
          <button
            type="button"
            class="text-xs text-ink-tertiary underline hover:text-ink-primary disabled:opacity-50"
            onclick={testerGratuit}
            disabled={etatTestGratuit === 'testing'}
            title="Vérifier que le fournisseur gratuit répond (sans consommer de quota)"
          >
            {etatTestGratuit === 'testing'
              ? 'Test…'
              : etatTestGratuit === 'ok'
                ? 'OK'
                : etatTestGratuit === 'ko'
                  ? 'Échec'
                  : 'Tester'}
          </button>
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

  <!-- Fil de conversation : un seul fil vertical, pas de bulles. Les tours
       utilisateur sont marques par une barre laterale plutot qu'une bulle
       flottante (standard 2026 : ChatGPT, Claude, Cursor). -->
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div
    bind:this={fil}
    class="flex-1 space-y-4 overflow-y-auto px-1 py-2"
    onscroll={surDefilement}
    onmousedown={onMouseDownFil}
    onmousemove={onMouseMoveFil}
    role="log"
    aria-live="polite"
    aria-busy={enCours}
  >
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
                  saisie = amorce;
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
        <div class="break-words border-l-2 border-info pl-3 text-sm text-ink-primary">
          {item.text}
        </div>
      {:else if item.kind === 'assistant'}
        <div class="text-sm">
          <AgentMarkdown texte={item.text} />
        </div>
      {:else if item.kind === 'group-outils'}
        {#if item.entrees.length === 1}
          {@const seule = item.entrees[0]}
          <ToolCard name={seule.name} args={seule.args} result={seule.result} />
        {:else}
          <!-- N cartes consecutives de meme outil : un en-tete compte les
               appels, chaque carte reste consultable en dessous. -->
          <div class="space-y-1 rounded-lg border border-border bg-surface-secondary/40 p-1.5">
            <p class="px-1 text-xs text-ink-tertiary">
              {item.entrees.length}× {item.name}
            </p>
            {#each item.entrees as tc (tc.id)}
              <ToolCard name={tc.name} args={tc.args} result={tc.result} />
            {/each}
          </div>
        {/if}
      {:else if item.kind === 'compaction'}
        <!-- Le debut de la conversation est sorti de la fenetre du modele. Le
             dire ici, a sa place dans le fil : l'agent qui « oublie » sans
             prevenir passe pour defaillant alors qu'il subit une limite. -->
        <div class="flex items-center gap-3 py-1 text-xs text-ink-tertiary">
          <span class="h-px flex-1 bg-border"></span>
          <span>{texteCompaction(item.retires, item.elagues)}</span>
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
          <Button
            variant="ghost"
            onclick={() => {
              continuer();
              enCours = true;
            }}
            disabled={enCours}>Continuer</Button
          >
        </div>
      {:else}
        <div
          role="alert"
          class="rounded-lg border border-danger/30 bg-danger-bg px-3 py-2 text-sm text-danger"
        >
          <p>{item.text}</p>
          <button
            type="button"
            class="mt-1 text-xs font-medium text-danger underline hover:no-underline"
            onclick={() => {
              continuer();
              enCours = true;
            }}>Réessayer</button
          >
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

  {#if usage && (usage.total_prompt_tokens > 0 || usage.total_completion_tokens > 0)}
    <p class="py-1 text-right text-xs text-ink-tertiary">
      {#if modeleEffectif}
        <span class="font-mono">{modeleEffectif}</span> ·
      {/if}
      {(usage.total_prompt_tokens / 1000).toFixed(1)}k prompt · {(
        usage.total_completion_tokens / 1000
      ).toFixed(1)}k completion{usage.cost_eur != null
        ? ` · ~${usage.cost_eur.toFixed(2)} EUR`
        : ''}
    </p>
  {/if}

  {#if decouverte}
    <div
      class="mt-2 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200"
    >
      {#if banniereMode === 'gratuit'}
        <span class="font-medium">Mode gratuit</span> : vos échanges transitent par
      {:else}
        <span class="font-medium">Mode découverte</span> : vos échanges transitent par
      {/if}
      <span class="font-medium">{decouverte.provider_public_name}</span>.
      {decouverte.retention_notice}
      {#if decouverte.remaining_today !== null}
        <span class="ml-1 font-medium"
          >{decouverte.remaining_today} message{decouverte.remaining_today !== 1 ? 's' : ''} restant{decouverte.remaining_today !==
          1
            ? 's'
            : ''} aujourd'hui.</span
        >
      {/if}
      {#if banniereMode === 'gratuit'}
        <button type="button" class="ml-1 underline" onclick={desactiverGratuit} disabled={enCours}>
          Désactiver le mode gratuit</button
        >.
      {:else}
        <a href="/dashboard/agents" class="ml-1 underline">Connecter votre clé</a>
      {/if}
    </div>
  {/if}

  {#if consentOuvert && gratuit}
    <ConsentementGratuit
      version={gratuit.version_warning}
      onvalider={activerGratuit}
      onfermer={() => (consentOuvert = false)}
    />
  {/if}

  <form class="flex gap-2 border-t border-border pt-3" onsubmit={envoyer}>
    <textarea
      bind:value={saisie}
      rows="1"
      aria-label="Message à l'agent"
      placeholder="Que doit faire l'agent ?"
      class="flex-1 resize-none rounded border border-border bg-surface-primary px-3 py-2 text-sm touch-manipulation"
      style="overflow-y: hidden;"
      oninput={(e) => ajusterHauteur(e.currentTarget)}
      onkeydown={(e) => {
        if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
          e.preventDefault();
          if (!enCours && saisie.trim()) {
            e.currentTarget.form?.requestSubmit();
          }
        }
      }}></textarea>
    {#if enCours}
      <Button variant="ghost" onclick={interrompre}>Arrêter</Button>
    {:else}
      <Button type="submit">Envoyer</Button>
    {/if}
  </form>
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
