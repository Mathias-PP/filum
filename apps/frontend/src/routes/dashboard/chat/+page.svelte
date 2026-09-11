<script lang="ts">
  import { onMount } from 'svelte';
  import { replaceState } from '$app/navigation';
  import { agentApi, type AgentProvider } from '$lib/api/agent';
  import { ApiError } from '$lib/api';
  import { toast } from '$lib/components';
  import ChatPanel from '$lib/components/chat/ChatPanel.svelte';
  import { conversations, rafraichirConversations } from '$lib/agent/sessions.svelte';

  let providers = $state<AgentProvider[]>([]);
  let titreNouveau = $state('');
  // Session ouverte par le premier message. A partir de la, le champ de nom
  // renomme : avant, un nom saisi apres le premier message restait sans effet.
  let sessionCreee = $state<string | null>(null);

  // Le mode gratuit n'existe pas sur toutes les instances : sans lane
  // configuree, promettre « activez-le ci-dessous » designerait un bouton
  // absent.
  let gratuitDisponible = $state(false);
  let gratuitActifIci = $state(false);

  const defaut = $derived(providers.find((p) => p.is_default) ?? null);

  onMount(async () => {
    providers = await agentApi.providers.list().catch(() => []);
    agentApi.gratuit
      .etat()
      .then((v) => {
        gratuitDisponible = v.disponible;
        gratuitActifIci = v.actif;
      })
      .catch(() => null);
  });

  // Chaque « Nouvelle » repart d'une page vierge, y compris depuis cette page.
  $effect(() => {
    void conversations.generation;
    titreNouveau = '';
    sessionCreee = null;
    conversations.active = null;
  });

  async function renommer() {
    const titre = titreNouveau.trim();
    // Avant le premier message, le nom part avec lui : rien a enregistrer.
    if (!sessionCreee || !titre) return;
    try {
      await agentApi.sessions.update(sessionCreee, { title: titre });
      await rafraichirConversations();
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Renommage impossible.');
    }
  }

  function surSession(id: string) {
    sessionCreee = id;
    conversations.active = id;
    // `replaceState` de SvelteKit et non celui du navigateur : le routeur
    // ignorait l'adresse reecrite a la main, et « Nouvelle » ne rechargeait
    // plus rien. Pas de `goto` non plus : il demonterait le panneau et
    // couperait le flux du premier message.
    replaceState(`/dashboard/chat/${id}`, {});
    void rafraichirConversations();
  }
</script>

<svelte:head>
  <title>Agent · Philum</title>
</svelte:head>

<div class="flex h-full min-h-0 flex-col">
  <h1 class="font-serif text-3xl text-ink-primary mb-1">Agent</h1>
  {#if defaut && !gratuitActifIci}
    <p class="text-sm text-ink-secondary mb-4">
      Répondra avec <span class="font-mono">{defaut.model}</span> ({defaut.display_name}), votre
      clé, votre facture.
      <a href="/dashboard/agents" class="text-info hover:underline">Changer</a>
    </p>
  {:else if gratuitActifIci}
    <!-- Le panneau gere la lane : ne pas suggerer en parallele que la cle
         par defaut sert encore les messages. -->
    <p class="text-sm text-ink-secondary mb-4">
      Répondra via le mode gratuit (fournisseur serveur Philum). Voir la bannière dans le fil de
      discussion.
    </p>
  {:else}
    <!-- Sans clé, le chat reste utilisable : le serveur bascule sur le mode
         gratuit ou le mode découverte. Masquer le chat ici enfermait le
         nouvel arrivant, puisque le bouton d'activation du mode gratuit vit
         dans le chat lui-même. -->
    <p class="text-sm text-ink-secondary mb-4">
      {#if gratuitDisponible}
        Aucune clé par défaut. Essayez sans clé avec le bouton « Mode gratuit » ci-dessous, ou
        <a href="/dashboard/agents" class="text-info hover:underline">enregistrez la vôtre</a>
        pour choisir votre modèle et lever les quotas.
      {:else}
        Aucune clé par défaut.
        <a href="/dashboard/agents" class="text-info hover:underline">Enregistrez-en une</a>
        pour choisir votre modèle et votre fournisseur.
      {/if}
    </p>
  {/if}
  <div class="mb-3 shrink-0">
    <input
      bind:value={titreNouveau}
      class="w-full rounded border border-border bg-surface-primary px-3 py-2 text-sm"
      maxlength="200"
      aria-label="Nom de la conversation"
      placeholder={sessionCreee ? 'Renommer la conversation' : 'Nommer la conversation (optionnel)'}
      onchange={renommer}
      onkeydown={(e) => {
        if (e.key === 'Enter') e.currentTarget.blur();
      }}
    />
  </div>
  <div class="min-h-0 flex-1">
    {#key conversations.generation}
      <ChatPanel titreInitial={titreNouveau} onsession={surSession} />
    {/key}
  </div>
</div>
