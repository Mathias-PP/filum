<script lang="ts">
  /**
   * Page d'accueil.
   *
   * Le pari de cette page : le hero ne décore plus, il explique. Les sept
   * nœuds en orbite portent chacun une fonctionnalité, et un clic ouvre ce
   * qu'elle fait. La topologie du pulsar disait déjà quelque chose de vrai
   * (un satellite tourne autour de la source qui le cite, deux jumeaux se
   * répondent de part et d'autre d'une fourche) : on lui donne enfin ses mots.
   *
   * Contraintes tenues :
   * - les repères sont de vrais `<button>`, donc atteignables au clavier ;
   * - rien ne se déclenche au survol seul : ouvrir demande un clic ;
   * - sans WebGL (ou en `prefers-reduced-motion`), les repères retombent en
   *   liste posée sous la scène plutôt que de disparaître ;
   * - les positions sont écrites en impératif sur le DOM, jamais via `$state`,
   *   pour ne pas rendre soixante fois par seconde.
   */
  import HeroPulsar from '$lib/components/HeroPulsar.svelte';
  import { reveal } from '$lib/actions/reveal';
  import type { User } from '$lib/api';

  let { data }: { data: { user: User | null } } = $props();
  const isAuthenticated = $derived(!!data.user);

  type PulsarNodeFrame = {
    colorIdx: number;
    x: number;
    y: number;
    r: number;
    depth: number;
  };

  type PulsarCoreFrame = {
    x: number;
    y: number;
    r: number;
  };

  const googleLoginUrl = '/api/v1/auth/google/login';

  type Feature = {
    idx: number;
    label: string;
    title: string;
    body: string;
    color: string;
  };

  // Les couleurs reprennent `NODE_COLORS` de HeroPulsar, converties en hex :
  // le pastille du panneau doit être exactement celle du nœud allumé, sinon
  // le lien entre les deux se devine au lieu de se voir.
  const FEATURES: Feature[] = [
    {
      idx: 0,
      label: 'Extraction',
      title: 'Vous collez un lien, la référence se complète',
      body: "Philum récupère le titre, les auteur·ices, la date, le DOI et la revue chez l'éditeur. Vous pouvez aussi déposer un fichier BibTeX, un PDF, ou coller votre bibliographie telle quelle.",
      color: '#528FFF',
    },
    {
      idx: 1,
      label: 'Citations vérifiées',
      title: 'La citation est comparée à l’article d’origine',
      body: 'Vous citez une phrase tirée d’un article. Philum va la lire sur le site d’origine et vous dit si elle y figure, caractère pour caractère.',
      color: '#73DB8C',
    },
    {
      idx: 2,
      label: 'Archivage',
      title: 'Une copie de chaque page, datée du jour',
      body: 'Un site peut être modifié ou fermer. La copie archivée le jour où vous l’avez lu reste accessible depuis votre page.',
      color: '#4DD1FF',
    },
    {
      idx: 3,
      label: 'Positions',
      title: 'Dites si l’étude vous appuie ou vous contredit',
      body: 'Pour chaque citation, vous indiquez son rôle : elle confirme ce que vous avancez, elle le nuance, elle le contredit. Philum n’en décide rien à votre place.',
      color: '#FA7380',
    },
    {
      idx: 4,
      label: 'Découpage',
      title: 'Un long document se découpe en extraits',
      body: 'Déposez un PDF ou collez un texte entier. Philum le coupe en paragraphes, vous gardez ceux qui vous servent.',
      color: '#FFB85C',
    },
    {
      idx: 5,
      label: 'Sources liées',
      title: 'Les sources citées par vos sources',
      body: 'Un article s’appuie lui-même sur d’autres travaux. Philum les récupère, et votre lecteur peut continuer à remonter le fil sans quitter la page.',
      color: '#C780FF',
    },
    {
      idx: 6,
      label: 'Export',
      title: 'La bibliographie sort dans le format de votre outil',
      body: 'BibTeX, RIS, CSL, Markdown, JSON, tableur, traitement de texte. Votre bibliographie seule, ou avec celle des sources qu’elle cite.',
      color: '#FFDB6B',
    },
  ];

  let selected = $state<number | null>(null);
  // Passe à vrai à la première image reçue du canvas. Tant qu'il est faux, les
  // repères n'ont aucune position à occuper : on les pose en liste.
  let positioned = $state(false);
  // En dessous de 1024px les repères redeviennent une liste posée sous la
  // scène. Il faut le savoir en JS : un `transform` écrit sur un élément
  // redevenu statique le déplacerait hors de sa ligne.
  let floating = $state(false);

  $effect(() => {
    const mq = window.matchMedia('(min-width: 1024px)');
    const sync = () => {
      floating = mq.matches;
      if (!mq.matches) {
        for (const el of markerEls) if (el) el.style.cssText = '';
        // Sans cette remise à zéro, un retour au grand écran ferait glisser
        // chaque repère depuis la place qu'il occupait avant le repli.
        posesLissees.length = 0;
      }
    };
    sync();
    mq.addEventListener('change', sync);
    return () => mq.removeEventListener('change', sync);
  });

  let stageEl = $state<HTMLDivElement>();
  let canvasBoxEl = $state<HTMLDivElement>();
  let ringEl = $state<HTMLDivElement>();
  const markerEls: (HTMLButtonElement | undefined)[] = [];
  const markerWidths: number[] = [];
  let frameCount = 0;

  const openFeature = $derived(FEATURES.find((f) => f.idx === selected) ?? null);

  // Le pointeur entre dans la scène ⇒ les orbites se figent presque. Sans ça,
  // le repère qu'on vise a dérivé de vingt pixels au moment du clic, et on
  // ouvre le panneau d'une autre fonctionnalité, constaté à l'écran. Le
  // ralenti tient aussi tant qu'un panneau est ouvert : la bague qui entoure
  // la planète décrite reste alors lisible.
  let survole = $state(false);
  // Les orbites tournent un peu sous le rythme nominal : une étiquette collée à
  // sa planète traverse l'écran à la vitesse de celle-ci, et à 1 elle défilait
  // plus vite qu'on ne la lit. Approcher le pointeur ralentit sans figer : une
  // scène arrêtée passe pour cassée, et depuis qu'un nœud se dépose là où on le
  // lâche, viser n'est plus le seul recours contre la dérive.
  const VITESSE_ORBITE = 0.8;
  const VITESSE_VISEE = 0.22;
  const timeScale = $derived(selected !== null ? 0.12 : survole ? VITESSE_VISEE : VITESSE_ORBITE);

  // Repère sous le pointeur. Il reprend sa pleine opacité même s'il était
  // atténué par la profondeur ou par ce qui passe devant : viser une étiquette
  // suffit à la rendre lisible, sans avoir à attendre que son orbite la ramène
  // au premier plan.
  let survoleRepere = $state<number | null>(null);

  // Hauteur d'un repère, en pixels. Sert de boîte de collision pour calculer
  // ce qui en recouvre quelle part.
  const MARKER_H = 26;
  // Position affichée de chaque repère, distincte de sa cible. Le lissage reste
  // court : l'étiquette doit sembler tenue par sa planète, pas la suivre de
  // loin. Celui de l'opacité est plus long, c'est lui qui fait le fondu.
  const posesLissees: { x: number; y: number; o: number }[] = [];
  const LISSAGE_POS = 0.35;
  const LISSAGE_OPACITE = 0.1;
  // Le fondu de retour est lent, à dessein. Celui qui répond au pointeur ne
  // peut pas l'être : une étiquette qui met une seconde à s'allumer sous la
  // souris passe pour cassée.
  const LISSAGE_OPACITE_VISEE = 0.3;
  // Un repère entièrement masqué ne descend pas à zéro : on doit comprendre
  // qu'il est passé derrière quelque chose, pas qu'il a disparu.
  const OPACITE_MASQUEE = 0.08;

  /** Part d'un repère recouverte par un autre repère, de 0 à 1. */
  function recouvrementRepere(
    x: number,
    y: number,
    w: number,
    ox: number,
    oy: number,
    ow: number
  ): number {
    const dx = Math.min(x + w / 2, ox + ow / 2) - Math.max(x - w / 2, ox - ow / 2);
    if (dx <= 0) return 0;
    const dy = MARKER_H - Math.abs(y - oy);
    if (dy <= 0) return 0;
    return Math.min(1, (dx / w) * (dy / MARKER_H));
  }

  /** Part d'un repère mordue par un disque : une planète ou le pulsar. */
  function recouvrementDisque(
    x: number,
    y: number,
    w: number,
    cx: number,
    cy: number,
    r: number
  ): number {
    const px = Math.max(x - w / 2, Math.min(cx, x + w / 2));
    const py = Math.max(y, Math.min(cy, y + MARKER_H));
    const dist = Math.hypot(cx - px, cy - py);
    if (dist >= r) return 0;
    // Le masque monte à mesure que le disque mord : c'est ce dégradé qui
    // remplace la disparition sèche.
    return Math.min(1, (r - dist) / Math.max(r * 0.7, 1));
  }

  function handleFrame(nodes: PulsarNodeFrame[], core: PulsarCoreFrame) {
    if (!positioned) positioned = true;
    if (!floating) return;
    frameCount++;
    const stageW = stageEl?.clientWidth ?? 0;
    // Le canvas déborde volontairement de la scène (marges négatives) : ses
    // coordonnées ne sont donc pas celles du calque des repères. Sans ce
    // décalage, chaque étiquette flotte à quelques dizaines de pixels de la
    // planète qu'elle nomme.
    const offX = canvasBoxEl?.offsetLeft ?? 0;
    const offY = canvasBoxEl?.offsetTop ?? 0;
    const coreX = core.x + offX;
    const coreY = core.y + offY;

    // De l'avant vers l'arrière : un repère n'est masqué que par ce qui passe
    // devant lui, donc par ce qui a déjà été posé dans cette boucle.
    const ordre = [...nodes].sort((a, b) => b.depth - a.depth);
    const devant: { x: number; y: number; w: number }[] = [];

    for (const n of ordre) {
      const el = markerEls[n.colorIdx];
      if (!el) continue;

      // Mesurer la largeur provoque un calcul de mise en page : on ne le
      // refait que de loin en loin, une pastille ne change pas de taille en
      // tournant.
      if (frameCount % 30 === 1 || markerWidths[n.colorIdx] === undefined) {
        markerWidths[n.colorIdx] = el.offsetWidth;
      }
      const w = markerWidths[n.colorIdx] ?? 80;
      const half = w / 2;
      const cx = n.x + offX;
      const cy = n.y + offY;

      // Le repère tient à sa planète : le seul ajustement est de le garder
      // dans la scène. Plus aucune poussée verticale pour esquiver les
      // voisins, c'est elle qui faisait balader les étiquettes. Le
      // chevauchement qui en résulte est assumé, le fondu le rend lisible.
      const cibleX = Math.max(half + 4, Math.min(stageW - half - 4, cx));
      const cibleY = cy + n.r + 10;

      let masque = 0;
      for (const d of devant) {
        masque = Math.max(masque, recouvrementRepere(cibleX, cibleY, w, d.x, d.y, d.w));
      }
      for (const autre of nodes) {
        if (autre.colorIdx === n.colorIdx || autre.depth <= n.depth) continue;
        masque = Math.max(
          masque,
          recouvrementDisque(cibleX, cibleY, w, autre.x + offX, autre.y + offY, autre.r)
        );
      }
      // La moitié arrière du tri passe derrière le disque du pulsar.
      if (n.depth < 0.5) {
        masque = Math.max(masque, recouvrementDisque(cibleX, cibleY, w, coreX, coreY, core.r));
      }

      // Deux façons pour un repère de reprendre sa pleine visibilité : le
      // pointeur le vise, ou le panneau ouvert le décrit. Sinon il suit sa
      // planète, d'autant plus pâle qu'elle est loin derrière.
      const vise = n.colorIdx === selected || n.colorIdx === survoleRepere;
      const cibleO = vise ? 1 : (0.34 + 0.66 * n.depth) * (1 - (1 - OPACITE_MASQUEE) * masque);
      const p = (posesLissees[n.colorIdx] ??= { x: cibleX, y: cibleY, o: cibleO });
      p.x += (cibleX - p.x) * LISSAGE_POS;
      p.y += (cibleY - p.y) * LISSAGE_POS;
      p.o += (cibleO - p.o) * (vise ? LISSAGE_OPACITE_VISEE : LISSAGE_OPACITE);
      devant.push({ x: p.x, y: p.y, w });

      el.style.transform = `translate3d(${p.x.toFixed(1)}px, ${p.y.toFixed(1)}px, 0) translateX(-50%)`;
      el.style.opacity = p.o.toFixed(3);
      // Un repère presque effacé ne doit pas intercepter le clic : on viserait
      // la planète du dessus et on ouvrirait la mauvaise fonctionnalité.
      el.style.pointerEvents = p.o < 0.25 ? 'none' : 'auto';
      // Un repère visé passe devant tout le reste, sinon l'étiquette qu'on
      // vient d'allumer resterait lue à travers celle qui la recouvre.
      el.style.zIndex = vise ? '30' : String(10 + Math.round(n.depth * 10));

      if (ringEl && n.colorIdx === selected) {
        ringEl.style.transform = `translate3d(${cx}px, ${cy}px, 0) translate(-50%, -50%)`;
        ringEl.style.width = `${n.r * 2.9}px`;
        ringEl.style.height = `${n.r * 2.9}px`;
      }
    }
  }

  function toggle(idx: number | null) {
    if (idx === null) {
      selected = null;
      return;
    }
    selected = selected === idx ? null : idx;
  }

  function onWindowKeydown(event: KeyboardEvent) {
    if (event.key !== 'Escape' || selected === null) return;
    // Le focus revient sur le repère qu'on vient de fermer : sans ça, une
    // navigation au clavier repart du haut de la page à chaque fermeture.
    const revenir = markerEls[selected];
    selected = null;
    revenir?.focus();
  }

  // Démo « extraction » : les champs se remplissent l'un après l'autre.
  const CHAMPS = [
    { cle: 'Titre', valeur: 'Sleep drives metabolite clearance from the adult brain' },
    { cle: 'Auteur·ices', valeur: 'Xie, L. · Kang, H. · Xu, Q. · Nedergaard, M.' },
    { cle: 'Publié le', valeur: '18 octobre 2013' },
    { cle: 'DOI', valeur: '10.1126/science.1241224' },
    { cle: 'Archive', valeur: 'capture du 9 août 2026' },
  ];

  const VERDICTS = [
    { texte: '« Le sommeil accroît l’espace interstitiel de 60 %. »', etat: 'retrouvee' },
    { texte: '« La clairance du β-amyloïde double pendant le sommeil. »', etat: 'deplacee' },
    { texte: '« Les canaux gliaux se dilatent à l’endormissement. »', etat: 'illisible' },
  ];

  // Les questions qu'on se pose devant une information, et ce que la fiche
  // répond à chacune. Elles sont formulées telles qu'on se les pose, et les
  // réponses nomment le mécanisme réel : Crossref pour la rétractation, la
  // capture Wayback pour la disparition.
  const QUESTIONS = [
    {
      question: 'La source dit-elle vraiment ce qu’on lui fait dire ?',
      reponse:
        'Vous lisez les extraits cités mot pour mot, à côté de la référence d’où ils viennent.',
    },
    {
      question: 'Cette information est-elle toujours valable ?',
      reponse:
        'Une étude peut être rétractée des années après. Philum le vérifie auprès de Crossref et l’affiche.',
    },
    {
      question: 'Et si le site n’est plus accessible ?',
      reponse:
        'Chaque page est archivée le jour où elle est citée. Si elle change ou disparaît, l’archive reste lisible.',
    },
  ];

  // L'usage qui ne se voit pas depuis l'extérieur : la bibliographie sert
  // d'abord à celui qui la tient. Trois choses qu'aucune liste de références
  // plate ne permet.
  const USAGE_PRIVE = [
    {
      glyphe: 'passages',
      titre: 'Réduire un article aux passages qui comptent',
      texte:
        'Collez le texte ou déposez le document : Philum le découpe en passages et propose un intitulé pour chacun. Vous gardez ceux qui servent votre propos, vous laissez le reste.',
    },
    {
      glyphe: 'liens',
      titre: 'Voir ce qui relie vos lectures',
      texte:
        'Deux de vos bibliographies citent la même étude, ou une étude en cite une autre : le lien apparaît. Vous voyez aussi qui d’autre, sur Philum, s’appuie sur le même travail.',
    },
    {
      glyphe: 'volet',
      titre: 'Restez en mode privé si vous le souhaitez',
      texte:
        'Une bibliographie peut rester privée aussi longtemps que vous le voulez. Vous la rendez publique le jour où votre contenu paraît, ou jamais.',
    },
  ];

  // Ce que la fiche apporte quand le lecteur est un programme. Aucune promesse
  // sur l'exactitude du modèle : ce qui se garantit, c'est le périmètre.
  const LECTURE_IA = [
    {
      titre: 'Vous composez le corpus',
      texte:
        'Choisissez les pages sur lesquelles l’IA doit travailler : les vôtres, celles que d’autres ont publiées, ou un mélange des deux. Elle ne cherchera nulle part ailleurs.',
    },
    {
      titre: 'Elle cite, elle ne résume pas',
      texte:
        'Les réponses renvoient aux extraits que vous avez sélectionnés dans les articles. Chaque extrait cité peut être ouvert et relu dans le texte d’où il vient.',
    },
    {
      titre: 'Accessible depuis vos outils',
      texte:
        'Un serveur MCP permet d’interroger vos pages depuis un assistant IA compatible. Le reste s’exporte en JSON, JSON-LD, Markdown, CSV, BibTeX, RIS et CSL.',
    },
  ];

  const PUBLICS = [
    {
      titre: 'Vulgarisateur·ices',
      texte:
        'Un lien en description de la vidéo, et ceux qui doutent peuvent vérifier par eux-mêmes. Vos heures de recherche cessent d’être invisibles.',
    },
    {
      titre: 'Journalistes',
      texte:
        'La page que vous citez aujourd’hui peut être modifiée ou retirée demain. Vous en gardez une copie datée, et vous pouvez la montrer.',
    },
    {
      titre: 'Chercheur·ses',
      texte:
        'Votre veille arrête de se perdre dans des PDF : chaque lecture garde ses passages utiles et sa référence. La bibliographie ressort en BibTeX, RIS ou CSL-JSON, prête à réimporter dans votre gestionnaire de références.',
    },
    {
      titre: 'Enseignants et étudiants',
      texte:
        'Distribuez un dossier de lecture où chaque texte est réduit aux paragraphes qui comptent, références complètes incluses.',
    },
  ];
</script>

<svelte:head>
  <title>Philum | Un espace de travail pour vos sources</title>
  <meta
    name="description"
    content="Rassemblez les articles, études, vidéos et podcasts sur lesquels vous travaillez. Chaque référence est accompagnée des citations exactes qui vous intéressent. Publiez-les pour votre audience, ou interrogez une IA sur les sources que vous avez choisies."
  />
</svelte:head>

<svelte:window onkeydown={onWindowKeydown} />

<div class="page">
  <!-- Le hero et la section qui suit sont deux moments d'une même nuit. Le
       dégradé est porté par ce bloc, pas par chaque section : deux fonds
       voisins, même proches, laissent toujours voir la ligne qui les
       sépare. -->
  <div class="nuit-haut">
    <!-- Halos et grain couvrent les deux sections d'un seul tenant. Portés par
         chacune, ils s'arrêtaient net à la frontière et dessinaient la couture
         que le fond continu venait justement d'effacer. -->
    <div class="veil" aria-hidden="true"></div>
    <div class="grain" aria-hidden="true"></div>
    <!-- ===================== HERO ===================== -->
    <section class="hero">
      <div class="hero-stars" aria-hidden="true"></div>
      <div class="hero-aurora" aria-hidden="true"></div>

      <div class="hero-inner">
        <div class="hero-copy">
          <p class="eyebrow">Un espace de travail pour vos sources</p>
          <h1>
            Vous allez adorer<br />
            <span class="accent">partager vos références</span>
          </h1>
          <p class="lede">
            Rassemblez les articles, études, vidéos et podcasts sur lesquels vous travaillez. Chaque
            référence est accompagnée des citations exactes qui vous intéressent. Publiez-les pour
            votre audience, ou interrogez une IA sur les sources que vous avez choisies.
          </p>
          <div class="ctas">
            {#if isAuthenticated}
              <a class="cta-primary" href="/dashboard">Tableau de bord</a>
            {:else}
              <a class="cta-primary" href={googleLoginUrl}>
                <svg class="g" viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    fill="currentColor"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                  />
                  <path
                    fill="currentColor"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="currentColor"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  />
                  <path
                    fill="currentColor"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  />
                </svg>
                Continuer avec Google
              </a>
            {/if}
            <a class="cta-ghost" href="/@example/memoire-et-cerveau">Voir une fiche →</a>
          </div>
          <!-- Au doigt, on ne traîne pas une planète : le geste sert à faire
             défiler la page. La seconde phrase ne s'affiche donc qu'au
             pointeur fin. -->
          <p class="hint">
            <span class="hint-dot" aria-hidden="true"></span>
            <span>
              <span class="hint-clic">Cliquez</span><span class="hint-touche">Touchez</span> une
              planète, elle dit ce que Philum sait faire.<span class="hint-plus"
                >&nbsp;Attrapez-la, elle reste où vous la posez.</span
              >
            </span>
          </p>
        </div>

        <!-- La scène : canvas + repères DOM par-dessus. -->
        <div
          class="stage"
          class:is-open={selected !== null}
          bind:this={stageEl}
          role="group"
          aria-label="Fonctionnalités de Philum, en orbite"
          onpointerenter={() => (survole = true)}
          onpointerleave={() => (survole = false)}
        >
          <div class="stage-canvas" bind:this={canvasBoxEl}>
            <HeroPulsar {selected} {timeScale} onselect={toggle} onframe={handleFrame} />
          </div>

          <div
            class="ring"
            class:on={selected !== null && floating}
            bind:this={ringEl}
            aria-hidden="true"
          ></div>

          <div class="markers" class:floating={positioned && floating}>
            {#each FEATURES as f (f.idx)}
              <button
                type="button"
                class="marker"
                class:active={selected === f.idx}
                style:--dot={f.color}
                bind:this={markerEls[f.idx]}
                aria-pressed={selected === f.idx}
                onclick={() => toggle(f.idx)}
                onpointerenter={() => (survoleRepere = f.idx)}
                onpointerleave={() => {
                  if (survoleRepere === f.idx) survoleRepere = null;
                }}
                onfocus={() => (survoleRepere = f.idx)}
                onblur={() => {
                  if (survoleRepere === f.idx) survoleRepere = null;
                }}
              >
                <span class="dot" aria-hidden="true"></span>
                {f.label}
              </button>
            {/each}
          </div>
        </div>
      </div>

      <!-- Le panneau vit sous la grille : il ne recouvre jamais la scène, et sa
         place est réservée pour que l'ouverture ne pousse pas la page. -->
      <div class="panel-slot" aria-live="polite">
        {#if openFeature}
          {#key openFeature.idx}
            <div class="panel" style:--dot={openFeature.color}>
              <span class="panel-dot" aria-hidden="true"></span>
              <div>
                <h2>{openFeature.title}</h2>
                <p>{openFeature.body}</p>
              </div>
              <button type="button" class="panel-close" onclick={() => (selected = null)}>
                Fermer
              </button>
            </div>
          {/key}
        {/if}
      </div>
    </section>

    <!-- ===================== POURQUOI ===================== -->
    <!-- Prolonge la nuit du hero : le doute appartient encore au monde d'avant
       Philum. La page ne s'éclaire qu'à la section suivante, quand l'outil
       agit. Les questions sont un fil, pas trois cartes côte à côte. -->
    <section class="fil night">
      <div class="wrap">
        <h2 class="section-title" use:reveal>D’où vient l’information&nbsp;?</h2>
        <p class="section-lede" use:reveal>
          Une émission cite un chiffre. Une vidéo recommande une pratique. La source existe quelque
          part, mais presque personne n’ira la chercher.
        </p>

        <ol class="fil-list">
          {#each QUESTIONS as q (q.question)}
            <li class="fil-item" use:reveal>
              <span class="fil-node" aria-hidden="true"></span>
              <h3>{q.question}</h3>
              <p>{q.reponse}</p>
            </li>
          {/each}
        </ol>
      </div>
    </section>
  </div>

  <!-- ===================== COMMENT SE FAIT UNE FICHE ===================== -->
  <section class="gestes">
    <div class="wrap">
      <h2 class="section-title" use:reveal>
        Comment se construit une fiche bibliographique&nbsp;?
      </h2>
      <p class="section-lede" use:reveal>
        En trois étapes. Philum lit les pages, complète les références et vérifie les citations ;
        vous décidez de ce qui est retenu.
      </p>

      <div class="geste" use:reveal>
        <div class="geste-copy">
          <span class="geste-n">01</span>
          <h3>Rassembler les sources</h3>
          <p>
            Collez l’adresse de votre vidéo, de votre podcast ou de votre article. Philum en lit la
            page ou la transcription, y repère les références et récupère pour chacune le titre, les
            auteur·ices, la date, le DOI et la revue. Un fichier BibTeX, un PDF ou une bibliographie
            collée marchent aussi. Pour les études, Philum signale celles qui sont en accès libre,
            en archive ouverte comme HAL ou arXiv ou dans une revue ouverte, et mène droit au texte.
          </p>
        </div>
        <div class="demo demo-fields" aria-hidden="true">
          <div class="demo-bar"><span></span><span></span><span></span></div>
          <div class="demo-url">https://youtu.be/…</div>
          <p class="demo-alt">ou BibTeX · RIS · CSL-JSON · PDF · biblio collée</p>
          {#each CHAMPS as champ, i (champ.cle)}
            <div class="field" style="--d: {i * 220}ms">
              <span class="field-key">{champ.cle}</span>
              <span class="field-val">{champ.valeur}</span>
            </div>
          {/each}
        </div>
      </div>

      <div class="geste reverse" use:reveal>
        <div class="geste-copy">
          <span class="geste-n">02</span>
          <h3>Citer les passages utilisés</h3>
          <p>
            Recopiez les passages qui vous intéressent. Philum vérifie qu’ils figurent bien dans
            l’article, caractère pour caractère. Vous indiquez ensuite le rôle de chaque passage
            dans votre démonstration : il l’appuie, il la nuance, il la contredit. Un intitulé et
            une phrase de contexte peuvent s’y ajouter, écrits par vous ou repris des suggestions
            que Philum propose.
          </p>
        </div>
        <div class="demo demo-quote" aria-hidden="true">
          <p class="q-title">Coût énergétique du cerveau</p>
          <p class="q-text">
            «&nbsp;Le cerveau représente environ 2 % de la masse corporelle, mais consomme près de
            20 % de l’oxygène et du glucose de l’organisme. Cette dépense varie peu selon l’activité
            mentale : l’essentiel part dans le maintien de l’activité de base des neurones.&nbsp;»
          </p>
          <p class="q-ctx">
            Chiffre de départ de l’article : la dépense ne bougeant pas avec l’activité mentale, le
            sommeil ne peut pas être une simple mise en veille énergétique.
          </p>
        </div>
      </div>

      <div class="geste" use:reveal>
        <div class="geste-copy">
          <span class="geste-n">03</span>
          <h3>Publier</h3>
          <p>
            Votre bibliographie est en ligne, à mettre en description de votre vidéo ou en fin
            d’article. Chaque référence mène à l’article d’origine et montre les citations que vous
            avez sélectionnées, avec le résultat de leur vérification. Export en BibTeX, RIS, CSL,
            Markdown, JSON, tableur ou traitement de texte.
          </p>
        </div>
        <div class="demo demo-verdicts" aria-hidden="true">
          {#each VERDICTS as v, i (v.texte)}
            <div class="verdict {v.etat}" style="--d: {i * 260}ms">
              <span class="v-mark"
                >{v.etat === 'retrouvee' ? '✓' : v.etat === 'deplacee' ? '≈' : '?'}</span
              >
              <span class="v-text">{v.texte}</span>
              <span class="v-state"
                >{v.etat === 'retrouvee'
                  ? 'retrouvée'
                  : v.etat === 'deplacee'
                    ? 'déplacée'
                    : 'illisible'}</span
              >
            </div>
          {/each}
        </div>
      </div>
    </div>
  </section>

  <!-- ===================== L'USAGE PRIVE ===================== -->
  <!-- Un seul panneau tenu par des filets verticaux, pas trois cartes : ces
       trois usages sont les faces d'un même établi. Le glyphe porte à lui
       seul de quoi il s'agit, ce qui allège la lecture du titre. -->
  <section class="usages">
    <div class="wrap">
      <h2 class="section-title" use:reveal>Et pour votre propre travail</h2>
      <p class="section-lede" use:reveal>
        Une bibliographie sert d’abord à celle ou celui qui la tient, bien avant d’être lue par
        quelqu’un d’autre.
      </p>

      <div class="etabli" use:reveal>
        {#each USAGE_PRIVE as u (u.titre)}
          <article class="usage">
            <span class="glyphe" aria-hidden="true">
              {#if u.glyphe === 'passages'}
                <!-- Deux passages retenus dans un texte qui reste en arriere-plan. -->
                <svg viewBox="0 0 40 40" fill="none">
                  <path
                    d="M7 8h26M7 13h26M7 30h26M7 35h16"
                    stroke="currentColor"
                    stroke-width="1.2"
                    opacity="0.4"
                  />
                  <rect x="6" y="17" width="28" height="4.5" rx="2.2" fill="currentColor" />
                  <rect x="6" y="23.5" width="20" height="4.5" rx="2.2" fill="currentColor" />
                </svg>
              {:else if u.glyphe === 'liens'}
                <svg viewBox="0 0 40 40" fill="none">
                  <path
                    d="M20 20 9 10M20 20l12-7M20 20l-8 13M20 20l11 10"
                    stroke="currentColor"
                    stroke-width="1.2"
                  />
                  <circle cx="20" cy="20" r="4" fill="currentColor" />
                  <circle cx="9" cy="10" r="2.6" fill="currentColor" />
                  <circle cx="32" cy="13" r="2.2" fill="currentColor" />
                  <circle cx="12" cy="33" r="2.2" fill="currentColor" />
                  <circle cx="31" cy="30" r="2.6" fill="currentColor" />
                </svg>
              {:else}
                <svg viewBox="0 0 40 40" fill="none">
                  <rect
                    x="7"
                    y="18"
                    width="26"
                    height="16"
                    rx="3"
                    stroke="currentColor"
                    stroke-width="1.6"
                  />
                  <path d="M14 18v-4a6 6 0 0 1 12 0v4" stroke="currentColor" stroke-width="1.6" />
                  <path d="M20 24v4" stroke="currentColor" stroke-width="1.8" />
                </svg>
              {/if}
            </span>
            <h3>{u.titre}</h3>
            <p>{u.texte}</p>
          </article>
        {/each}
      </div>
    </div>
  </section>

  <!-- ===================== QUAND C'EST UNE IA QUI LIT ===================== -->
  <!-- Sombre à son tour, mais d'un noir qui vire au bleu : ce n'est plus le
       doute du début, c'est une machine qui travaille. Les trois moments
       s'enchaînent au lieu de se juxtaposer, d'où les raccords. -->
  <section class="ia night">
    <div class="veil ia-veil" aria-hidden="true"></div>
    <div class="grain" aria-hidden="true"></div>
    <div class="wrap">
      <h2 class="section-title" use:reveal>
        Interroger une IA sur des sources que vous avez choisies
      </h2>
      <p class="section-lede" use:reveal>
        Les questions sont de plus en plus posées à un assistant IA plutôt qu’à un moteur de
        recherche. Les sources qu’ils citent sont ramassées au fil de la réponse : rien ne dit
        qu’elles font autorité, ni qu’elles disent ce qu’on leur fait dire.
      </p>

      <div class="chaine">
        {#each LECTURE_IA as l, i (l.titre)}
          <div class="maillon" use:reveal style="transition-delay: {i * 110}ms">
            <span class="maillon-noeud" aria-hidden="true"></span>
            <h3>{l.titre}</h3>
            <p>{l.texte}</p>
          </div>
        {/each}
      </div>

      <p class="ia-limite" use:reveal>
        Une IA peut toujours se tromper. Au moins, vous savez sur quels documents elle a travaillé.
      </p>
    </div>
  </section>

  <!-- ===================== POUR QUI ===================== -->
  <section class="publics">
    <div class="wrap">
      <h2 class="section-title" use:reveal>Pour qui</h2>
      <div class="publics-grid">
        {#each PUBLICS as p, i (p.titre)}
          <div class="public-card" use:reveal style="transition-delay: {i * 70}ms">
            <h3>{p.titre}</h3>
            <p>{p.texte}</p>
          </div>
        {/each}
      </div>
    </div>
  </section>

  <!-- ===================== CTA ===================== -->
  <section class="final">
    <div class="wrap narrow" use:reveal>
      <h2>Publier votre bibliographie</h2>
      <p>C’est gratuit. Connexion avec un compte Google.</p>
      {#if isAuthenticated}
        <a class="cta-light" href="/dashboard">Accéder au tableau de bord</a>
      {:else}
        <a class="cta-light" href={googleLoginUrl}>Commencer</a>
      {/if}
    </div>
  </section>
</div>

<style>
  .page {
    --hero-void: #02020a;
  }
  .wrap {
    max-width: 68rem;
    margin: 0 auto;
    padding: 0 1.5rem;
  }
  .wrap.narrow {
    max-width: 40rem;
    text-align: center;
  }

  /* ===================== HERO ===================== */
  /* Un seul dégradé pour le hero et le fil de questions : la couleur descend
     sans marche, donc sans ligne de séparation. */
  .nuit-haut {
    position: relative;
    overflow: hidden;
    isolation: isolate;
    background: linear-gradient(180deg, #02020a 0%, #07091a 38%, #050614 72%, #02020a 100%);
  }
  .hero {
    position: relative;
    color: white;
    background: radial-gradient(ellipse at 50% 45%, rgba(70, 90, 180, 0.1) 0%, transparent 60%);
    padding-bottom: 3rem;
  }
  .hero-stars {
    position: absolute;
    inset: 0;
    pointer-events: none;
    background-image:
      radial-gradient(1.5px 1.5px at 12% 18%, rgba(255, 255, 255, 0.6), transparent 50%),
      radial-gradient(1px 1px at 24% 62%, rgba(255, 255, 255, 0.4), transparent 50%),
      radial-gradient(1.5px 1.5px at 38% 12%, rgba(255, 255, 255, 0.5), transparent 50%),
      radial-gradient(1px 1px at 55% 38%, rgba(255, 255, 255, 0.35), transparent 50%),
      radial-gradient(1.5px 1.5px at 72% 18%, rgba(255, 255, 255, 0.55), transparent 50%),
      radial-gradient(1px 1px at 88% 48%, rgba(255, 255, 255, 0.4), transparent 50%),
      radial-gradient(1.5px 1.5px at 18% 82%, rgba(255, 255, 255, 0.45), transparent 50%),
      radial-gradient(1px 1px at 46% 78%, rgba(255, 255, 255, 0.35), transparent 50%),
      radial-gradient(1.5px 1.5px at 78% 88%, rgba(255, 255, 255, 0.5), transparent 50%);
  }
  /* Voile lent : donne au fond une respiration sans rien demander au GPU. */
  .hero-aurora {
    position: absolute;
    inset: -20%;
    pointer-events: none;
    background:
      radial-gradient(40% 30% at 22% 28%, rgba(90, 80, 200, 0.14), transparent 70%),
      radial-gradient(45% 32% at 76% 66%, rgba(40, 110, 190, 0.12), transparent 70%);
    animation: aurora 26s ease-in-out infinite alternate;
  }
  @keyframes aurora {
    from {
      transform: translate3d(-2%, -1%, 0) scale(1);
    }
    to {
      transform: translate3d(3%, 2%, 0) scale(1.08);
    }
  }

  .hero-inner {
    position: relative;
    max-width: 72rem;
    margin: 0 auto;
    padding: 4rem 1.5rem 0;
    display: grid;
    gap: 2rem;
    align-items: center;
  }
  @media (min-width: 1024px) {
    .hero-inner {
      grid-template-columns: 1fr 1fr;
      gap: 3rem;
      padding-top: 3.5rem;
    }
  }

  .eyebrow {
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 0.72rem;
    color: rgba(181, 212, 244, 0.75);
    margin-bottom: 1rem;
  }
  .hero-copy h1 {
    font-family: var(--font-serif);
    font-weight: 500;
    font-size: clamp(2.2rem, 4.4vw, 3.4rem);
    line-height: 1.06;
    letter-spacing: -0.02em;
    margin-bottom: 1.25rem;
    max-width: 23ch;
    text-wrap: balance;
  }
  .accent {
    background: linear-gradient(115deg, #b5d4f4 0%, #cecbf6 55%, #9fe3d0 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    color: transparent;
  }
  .lede {
    font-size: 1.06rem;
    line-height: 1.62;
    color: rgba(226, 232, 240, 0.82);
    max-width: 34rem;
    margin-bottom: 1.75rem;
    text-wrap: pretty;
  }
  .ctas {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin-bottom: 1.25rem;
  }
  .cta-primary,
  .cta-ghost,
  .cta-light {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.7rem 1.35rem;
    border-radius: 8px;
    font-size: 0.95rem;
    font-weight: 500;
    text-decoration: none;
    transition:
      transform 180ms cubic-bezier(0.2, 0.7, 0.3, 1),
      background-color 180ms ease,
      border-color 180ms ease;
  }
  .cta-primary {
    background: white;
    color: #14161f;
  }
  .cta-primary:hover {
    transform: translateY(-2px);
    background: #eef2f8;
  }
  .g {
    width: 1.15rem;
    height: 1.15rem;
  }
  .cta-ghost {
    color: rgba(255, 255, 255, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.22);
  }
  .cta-ghost:hover {
    transform: translateY(-2px);
    border-color: rgba(255, 255, 255, 0.45);
    background: rgba(255, 255, 255, 0.06);
  }
  .hint {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    color: rgba(203, 213, 225, 0.7);
  }
  .hint-touche {
    display: none;
  }
  .hint-dot {
    width: 7px;
    flex: none;
    height: 7px;
    border-radius: 50%;
    background: #9fe3d0;
    box-shadow: 0 0 0 0 rgba(159, 227, 208, 0.6);
    animation: ping 2.4s ease-out infinite;
  }
  @keyframes ping {
    0% {
      box-shadow: 0 0 0 0 rgba(159, 227, 208, 0.5);
    }
    70%,
    100% {
      box-shadow: 0 0 0 12px rgba(159, 227, 208, 0);
    }
  }

  /* ---- scène ---- */
  .stage {
    position: relative;
    width: 100%;
  }
  .stage-canvas {
    position: relative;
    width: 100%;
    aspect-ratio: 1 / 1;
    margin: -2rem 0;
    transition: filter 320ms ease;
  }
  /* Panneau ouvert : la scène recule d'un cran pour que la lecture prime. */
  .stage.is-open .stage-canvas {
    filter: saturate(0.85) brightness(0.9);
  }
  @media (min-width: 1024px) {
    .stage-canvas {
      width: calc(100% + 8rem);
      /* Le débord vertical est plus franc que l'horizontal : c'est ce qui
         ramène le panneau dans l'écran, sans quoi il s'ouvre sous la ligne
         de flottaison et personne ne voit sa réponse. */
      margin: -7rem -4rem;
    }
  }

  .ring {
    position: absolute;
    top: 0;
    left: 0;
    border-radius: 50%;
    border: 1.5px solid rgba(255, 255, 255, 0.55);
    opacity: 0;
    pointer-events: none;
    transition: opacity 220ms ease;
    z-index: 25;
  }
  .ring.on {
    opacity: 1;
    animation: ringPulse 2.2s ease-out infinite;
  }
  @keyframes ringPulse {
    0% {
      box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.28);
    }
    70%,
    100% {
      box-shadow: 0 0 0 16px rgba(255, 255, 255, 0);
    }
  }

  /* Sans canvas (WebGL absent, mouvement réduit) les repères restent une
     liste lisible : ils ne dépendent pas du rendu pour exister. */
  .markers {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }
  .marker {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.32rem 0.7rem;
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.16);
    background: rgba(8, 11, 26, 0.68);
    backdrop-filter: blur(8px);
    color: rgba(226, 232, 240, 0.9);
    font-size: 0.76rem;
    font-weight: 500;
    white-space: nowrap;
    /* Un repère se clique souvent deux fois de suite ; sans ça le second clic
       surligne le texte de l'étiquette au lieu de refermer le panneau. */
    user-select: none;
    cursor: pointer;
    transition:
      border-color 160ms ease,
      background-color 160ms ease,
      color 160ms ease;
  }
  .marker:hover,
  .marker:focus-visible {
    border-color: var(--dot);
    color: white;
  }
  .marker.active {
    border-color: var(--dot);
    background: rgba(255, 255, 255, 0.1);
    color: white;
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--dot);
    box-shadow: 0 0 8px var(--dot);
    flex: none;
  }

  @media (min-width: 1024px) {
    .markers.floating {
      position: absolute;
      inset: 0;
      display: block;
      margin: 0;
      pointer-events: none;
    }
    .markers.floating .marker {
      position: absolute;
      top: 0;
      left: 0;
      pointer-events: auto;
      will-change: transform, opacity;
    }
  }

  /* ---- panneau ---- */
  .panel-slot {
    position: relative;
    max-width: 72rem;
    margin: 0 auto;
    padding: 0 1.5rem;
    min-height: 8.5rem;
  }
  .panel {
    display: flex;
    align-items: flex-start;
    gap: 0.9rem;
    max-width: 44rem;
    padding: 1.15rem 1.25rem;
    border-radius: 14px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    background: rgba(9, 12, 28, 0.72);
    backdrop-filter: blur(14px);
    box-shadow: 0 18px 50px rgba(0, 0, 0, 0.45);
    animation: panelIn 320ms cubic-bezier(0.2, 0.8, 0.25, 1) both;
  }
  @keyframes panelIn {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }
  .panel-dot {
    width: 10px;
    height: 10px;
    margin-top: 0.4rem;
    border-radius: 50%;
    background: var(--dot);
    box-shadow: 0 0 12px var(--dot);
    flex: none;
  }
  .panel h2 {
    font-family: var(--font-serif);
    font-size: 1.12rem;
    font-weight: 500;
    margin-bottom: 0.35rem;
  }
  .panel p {
    font-size: 0.92rem;
    line-height: 1.6;
    color: rgba(226, 232, 240, 0.78);
  }
  .panel-close {
    margin-left: auto;
    flex: none;
    font-size: 0.75rem;
    color: rgba(203, 213, 225, 0.65);
    cursor: pointer;
    padding: 0.2rem 0.4rem;
    border-radius: 6px;
  }
  .panel-close:hover {
    color: white;
    background: rgba(255, 255, 255, 0.08);
  }

  /* ===================== SECTIONS ===================== */
  .section-title {
    font-family: var(--font-serif);
    font-size: clamp(1.8rem, 3.4vw, 2.6rem);
    font-weight: 500;
    color: rgb(var(--text-primary));
    letter-spacing: -0.015em;
    text-align: center;
    text-wrap: balance;
  }
  .section-lede {
    text-align: center;
    color: rgb(var(--text-secondary));
    margin: 0.75rem auto 3.5rem;
    max-width: 34rem;
    line-height: 1.6;
    text-wrap: pretty;
  }

  /* ---- fonds de nuit, partagés ---- */
  .night {
    position: relative;
    overflow: hidden;
    background: var(--hero-void);
    isolation: isolate;
  }
  .night .section-title {
    color: rgba(255, 255, 255, 0.94);
  }
  .night .section-lede {
    color: rgba(226, 232, 240, 0.72);
  }
  .night .wrap {
    position: relative;
    z-index: 2;
  }
  .veil {
    position: absolute;
    inset: -25%;
    pointer-events: none;
    background:
      radial-gradient(38% 30% at 18% 22%, rgba(90, 80, 200, 0.16), transparent 70%),
      radial-gradient(42% 34% at 82% 74%, rgba(40, 110, 190, 0.14), transparent 70%);
    animation: aurora 34s ease-in-out infinite alternate;
  }
  /* Le grain casse le dégradé : sans lui, les grands aplats sombres montrent
     leurs bandes de quantification sur un écran 8 bits. */
  .grain {
    position: absolute;
    inset: 0;
    pointer-events: none;
    opacity: 0.5;
    mix-blend-mode: overlay;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='140' height='140' filter='url(%23n)' opacity='0.22'/%3E%3C/svg%3E");
  }

  /* ---- le fil des questions ---- */
  /* Le fond vient du bloc parent : la section ne pose rien par-dessus, sinon
     la couture réapparaît. */
  .fil {
    padding: 5.5rem 0 6rem;
    background: transparent;
  }
  .fil-list {
    position: relative;
    max-width: 58rem;
    margin: 0 auto;
    padding-left: 1.75rem;
    list-style: none;
  }
  .fil-item {
    position: relative;
    padding: 1.6rem 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  }
  .fil-item:last-child {
    border-bottom: 0;
  }
  /* Le rail n'est pas un trait unique posé derrière la liste : chaque question
     porte le segment qui la relie à la suivante. Il part donc du centre de son
     point et s'arrête au centre du point d'après, sans amorce en l'air ni
     fondu dans le vide. La dernière question n'en porte aucun : le fil finit
     sur elle. */
  .fil-item::before {
    content: '';
    position: absolute;
    left: -1.75rem;
    top: calc(2.1rem + 4.5px);
    bottom: calc(-2.1rem - 4.5px);
    width: 1px;
    background: linear-gradient(to bottom, rgba(159, 227, 208, 0.42), rgba(120, 160, 240, 0.32));
    transform-origin: top;
  }
  .fil-item:last-child::before {
    content: none;
  }
  /* Le segment se trace quand sa question arrive à l'écran. L'état de repos
     est porté par l'attribut que pose l'action reveal : sans JavaScript le
     rail reste entier plutôt qu'invisible. */
  .fil-item:global([data-reveal])::before {
    transform: scaleY(0);
    transition: transform 900ms cubic-bezier(0.2, 0.7, 0.3, 1);
  }
  .fil-item:global([data-reveal].is-revealed)::before {
    transform: scaleY(1);
  }
  .fil-node {
    position: absolute;
    left: calc(-1.75rem - 4px);
    top: 2.1rem;
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: #9fe3d0;
    box-shadow: 0 0 14px rgba(159, 227, 208, 0.85);
  }
  .fil-item h3 {
    font-family: var(--font-serif);
    font-size: clamp(1.3rem, 2.6vw, 1.75rem);
    font-weight: 500;
    line-height: 1.25;
    color: rgba(255, 255, 255, 0.94);
    text-wrap: balance;
  }
  .fil-item p {
    margin-top: 0.6rem;
    color: rgba(226, 232, 240, 0.7);
    line-height: 1.7;
    max-width: 34rem;
  }
  /* Au large, la réponse se pose en regard de la question plutôt qu'en
     dessous : l'œil lit une paire, pas un empilement. */
  @media (min-width: 900px) {
    .fil-item {
      display: grid;
      grid-template-columns: 1.05fr 1fr;
      gap: 2.5rem;
      align-items: baseline;
      padding: 2rem 0;
    }
    .fil-item p {
      margin-top: 0;
      font-size: 0.98rem;
    }
  }

  /* ---- l'établi : un seul panneau, trois faces ---- */
  /* La section précédente est d'un blanc à peine plus chaud. Passer de l'un à
     l'autre d'un coup dessine une ligne horizontale nette en travers de la
     page, alors que rien ne s'y termine : le fond monte donc en dégradé. */
  .usages {
    background: linear-gradient(180deg, rgb(var(--bg-secondary)) 0%, rgb(var(--bg-primary)) 14rem);
    padding: 5.5rem 0;
    position: relative;
    overflow: hidden;
  }
  .usages::before {
    content: '';
    position: absolute;
    inset: -30% -10% auto;
    height: 70%;
    background: radial-gradient(50% 60% at 50% 0%, rgb(var(--info) / 0.07), transparent 70%);
    pointer-events: none;
  }
  .usages .wrap {
    position: relative;
  }
  .etabli {
    display: grid;
    gap: 0;
    border: 1px solid rgb(var(--border));
    border-radius: 18px;
    background: rgb(var(--bg-secondary));
    overflow: hidden;
    box-shadow: 0 20px 50px rgb(15 23 42 / 0.05);
  }
  @media (min-width: 900px) {
    .etabli {
      grid-template-columns: repeat(3, 1fr);
    }
  }
  .usage {
    padding: 2rem 1.75rem;
    border-bottom: 1px solid rgb(var(--border));
    transition: background-color 220ms ease;
  }
  .usage:last-child {
    border-bottom: 0;
  }
  @media (min-width: 900px) {
    .usage {
      border-bottom: 0;
      border-right: 1px solid rgb(var(--border));
    }
    .usage:last-child {
      border-right: 0;
    }
  }
  .usage:hover {
    background: rgb(var(--bg-primary));
  }
  .glyphe {
    display: block;
    width: 2.6rem;
    height: 2.6rem;
    margin-bottom: 1.1rem;
    color: rgb(var(--info));
    opacity: 0.9;
    transition:
      transform 320ms cubic-bezier(0.2, 0.7, 0.3, 1),
      opacity 320ms ease;
  }
  .glyphe svg {
    width: 100%;
    height: 100%;
  }
  .usage:hover .glyphe {
    transform: translateY(-3px) scale(1.04);
    opacity: 1;
  }
  .usage h3 {
    font-family: var(--font-serif);
    font-size: 1.2rem;
    font-weight: 500;
    line-height: 1.35;
    color: rgb(var(--text-primary));
    margin-bottom: 0.55rem;
    text-wrap: balance;
  }
  .usage p {
    color: rgb(var(--text-secondary));
    line-height: 1.68;
    font-size: 0.92rem;
  }

  .gestes {
    background: rgb(var(--bg-secondary));
    padding: 5.5rem 0;
  }
  .geste {
    display: grid;
    gap: 2rem;
    align-items: center;
    padding: 2.5rem 0;
  }
  @media (min-width: 900px) {
    .geste {
      grid-template-columns: 1fr 1.1fr;
      gap: 3.5rem;
    }
    .geste.reverse .geste-copy {
      order: 2;
    }
  }
  .geste-n {
    font-family: var(--font-mono);
    font-size: 0.8rem;
    color: rgb(var(--info));
    letter-spacing: 0.1em;
  }
  .geste-copy h3 {
    font-family: var(--font-serif);
    font-size: 1.6rem;
    font-weight: 500;
    color: rgb(var(--text-primary));
    margin: 0.5rem 0 0.75rem;
  }
  .geste-copy p {
    color: rgb(var(--text-secondary));
    line-height: 1.68;
    max-width: 32rem;
  }

  .demo {
    border: 1px solid rgb(var(--border));
    border-radius: 14px;
    background: rgb(var(--bg-primary));
    padding: 1.25rem;
    box-shadow: 0 12px 34px rgba(15, 23, 42, 0.06);
  }
  .demo-bar {
    display: flex;
    gap: 0.35rem;
    margin-bottom: 0.85rem;
  }
  .demo-bar span {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: rgb(var(--border-strong));
  }
  .demo-url {
    font-family: var(--font-mono);
    font-size: 0.78rem;
    color: rgb(var(--text-tertiary));
    padding: 0.45rem 0.6rem;
    border: 1px dashed rgb(var(--border));
    border-radius: 8px;
    margin-bottom: 0.5rem;
  }
  .demo-alt {
    font-size: 0.72rem;
    color: rgb(var(--text-tertiary));
    margin-bottom: 0.9rem;
  }
  .field {
    display: flex;
    gap: 0.75rem;
    padding: 0.42rem 0;
    border-bottom: 1px solid rgb(var(--border));
    font-size: 0.83rem;
    opacity: 0;
  }
  .field:last-child {
    border-bottom: 0;
  }
  .field-key {
    flex: none;
    width: 6.2rem;
    color: rgb(var(--text-tertiary));
  }
  .field-val {
    color: rgb(var(--text-primary));
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  /* Les champs n'apparaissent qu'une fois la démo à l'écran : jouée en boucle
     hors du regard, l'animation ne raconte rien et coûte des images. */
  :global([data-reveal].is-revealed) .field {
    animation: fieldIn 520ms cubic-bezier(0.2, 0.8, 0.25, 1) both;
    animation-delay: var(--d);
  }
  @keyframes fieldIn {
    from {
      opacity: 0;
      transform: translateY(7px);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }

  .demo-quote {
    border-left: 3px solid rgb(var(--info));
  }
  .q-title {
    font-size: 0.78rem;
    font-weight: 600;
    color: rgb(var(--text-secondary));
    margin-bottom: 0.4rem;
  }
  .q-text {
    font-style: italic;
    font-size: 1.02rem;
    line-height: 1.6;
    color: rgb(var(--text-primary));
  }
  .q-ctx {
    margin-top: 0.55rem;
    font-size: 0.79rem;
    color: rgb(var(--text-tertiary));
  }

  .verdict {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    padding: 0.62rem 0.7rem;
    border-radius: 10px;
    background: rgb(var(--bg-secondary));
    font-size: 0.84rem;
    margin-bottom: 0.5rem;
    opacity: 0;
  }
  :global([data-reveal].is-revealed) .verdict {
    animation: fieldIn 520ms cubic-bezier(0.2, 0.8, 0.25, 1) both;
    animation-delay: var(--d);
  }
  .v-mark {
    flex: none;
    width: 1.15rem;
    text-align: center;
    font-weight: 700;
  }
  .v-text {
    color: rgb(var(--text-secondary));
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .v-state {
    margin-left: auto;
    flex: none;
    font-size: 0.74rem;
    font-style: italic;
  }
  .verdict.retrouvee .v-mark,
  .verdict.retrouvee .v-state {
    color: rgb(var(--success));
  }
  .verdict.deplacee .v-mark,
  .verdict.deplacee .v-state {
    color: rgb(var(--warning));
  }
  /* « Illisible » n'est pas « introuvable » : la nuance est grise, pas rouge :
     la page n'a rien dit sur la citation, elle ne la dément pas. */
  .verdict.illisible .v-mark,
  .verdict.illisible .v-state {
    color: rgb(var(--text-tertiary));
  }

  /* ---- la chaîne : trois moments raccordés ---- */
  .ia {
    padding: 5.5rem 0;
  }
  .ia-veil {
    background:
      radial-gradient(40% 34% at 26% 24%, rgba(82, 143, 255, 0.2), transparent 70%),
      radial-gradient(38% 30% at 74% 78%, rgba(199, 128, 255, 0.14), transparent 70%);
  }
  .chaine {
    display: grid;
    gap: 1rem;
  }
  .maillon {
    position: relative;
    padding: 1.6rem 1.5rem 1.5rem;
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(255, 255, 255, 0.035);
    backdrop-filter: blur(10px);
    transition:
      border-color 240ms ease,
      background-color 240ms ease,
      transform 240ms cubic-bezier(0.2, 0.7, 0.3, 1);
  }
  .maillon:hover {
    transform: translateY(-3px);
    border-color: rgba(159, 227, 208, 0.4);
    background: rgba(255, 255, 255, 0.06);
  }
  .maillon-noeud {
    position: absolute;
    top: -5px;
    left: 1.5rem;
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: #9fe3d0;
    box-shadow: 0 0 14px rgba(159, 227, 208, 0.8);
  }
  @media (min-width: 900px) {
    .chaine {
      grid-template-columns: repeat(3, 1fr);
      gap: 1.75rem;
    }
  }
  .maillon h3 {
    font-family: var(--font-serif);
    font-size: 1.18rem;
    font-weight: 500;
    line-height: 1.35;
    color: rgba(255, 255, 255, 0.94);
    margin-bottom: 0.55rem;
    text-wrap: balance;
  }
  .maillon p {
    color: rgba(226, 232, 240, 0.72);
    line-height: 1.68;
    font-size: 0.92rem;
  }
  .ia-limite {
    margin: 2.75rem auto 0;
    text-align: center;
    font-size: 0.88rem;
    color: rgba(203, 213, 225, 0.6);
    max-width: 34rem;
    line-height: 1.6;
  }

  .publics {
    background: rgb(var(--bg-secondary));
    padding: 5.5rem 0;
  }
  .publics-grid {
    display: grid;
    gap: 1rem;
    margin-top: 3rem;
  }
  @media (min-width: 640px) {
    .publics-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }
  @media (min-width: 1024px) {
    .publics-grid {
      grid-template-columns: repeat(4, 1fr);
    }
  }
  .public-card {
    border: 1px solid rgb(var(--border));
    border-radius: 14px;
    padding: 1.35rem;
    background: rgb(var(--bg-primary));
    transition:
      transform 200ms cubic-bezier(0.2, 0.7, 0.3, 1),
      border-color 200ms ease,
      box-shadow 200ms ease;
  }
  .public-card:hover {
    transform: translateY(-4px);
    border-color: rgb(var(--border-strong));
    box-shadow: 0 14px 32px rgba(15, 23, 42, 0.08);
  }
  .public-card h3 {
    font-size: 0.98rem;
    font-weight: 600;
    color: rgb(var(--text-primary));
    margin-bottom: 0.45rem;
  }
  .public-card p {
    font-size: 0.86rem;
    line-height: 1.6;
    color: rgb(var(--text-secondary));
  }

  /* La page se referme sur le noir du hero plutôt que sur un bleu à elle : ce
     bleu ardoise ne se raccordait ni à la scène, ni aux sections claires. */
  .final {
    position: relative;
    background: var(--hero-void);
    color: white;
    padding: 5.5rem 0;
    overflow: hidden;
  }
  .final::before {
    content: '';
    position: absolute;
    inset: -40% 0 auto;
    height: 200%;
    background: radial-gradient(
      ellipse 60% 50% at 50% 0%,
      rgba(82, 143, 255, 0.16),
      transparent 70%
    );
    pointer-events: none;
  }
  .final .wrap {
    position: relative;
  }
  .final h2 {
    font-family: var(--font-serif);
    font-size: clamp(1.8rem, 3.4vw, 2.6rem);
    font-weight: 500;
    margin-bottom: 0.75rem;
  }
  .final p {
    color: rgba(226, 232, 240, 0.78);
    margin-bottom: 1.75rem;
  }
  .cta-light {
    background: white;
    color: #14161f;
  }
  .cta-light:hover {
    transform: translateY(-2px);
  }

  /* ===================== ÉTROIT ===================== */
  /* Deux défauts corrigés ici, tous deux visibles seulement au téléphone :
     la page débordait de 60 px sur la droite (une valeur de champ en
     `nowrap` élargissait sa colonne de grille, qui ne peut pas se réduire
     sans `min-width: 0`), et la scène du hero réservait un carré plein
     écran suivi d'un emplacement de panneau vide. */
  .geste-copy,
  .demo,
  .field-val,
  .v-text {
    min-width: 0;
  }
  @media (max-width: 639px) {
    .field {
      flex-wrap: wrap;
      gap: 0.15rem 0.75rem;
    }
    .field-key {
      width: auto;
      font-size: 0.74rem;
    }
    .field-val,
    .v-text {
      white-space: normal;
      overflow: visible;
      text-overflow: clip;
    }
    .verdict {
      align-items: flex-start;
      flex-wrap: wrap;
    }
    .v-state {
      margin-left: 1.8rem;
    }
  }
  @media (max-width: 1023px) {
    .hero {
      padding-bottom: 1.5rem;
    }
    .hero-inner {
      padding-top: 2.5rem;
    }
    /* La scène est rognée haut et bas : le carré du canvas contient beaucoup
       de vide autour du pulsar, et ce vide poussait les repères hors de vue. */
    .stage-canvas {
      margin: -5rem -1.5rem -7rem;
      width: calc(100% + 3rem);
    }
    .panel-slot {
      min-height: 0;
    }
    .panel {
      margin-top: 1rem;
    }
    .fil,
    .usages,
    .gestes,
    .ia,
    .publics,
    .final {
      padding-top: 3.75rem;
      padding-bottom: 3.75rem;
    }
    .section-lede {
      margin-bottom: 2.5rem;
    }
    .geste {
      padding: 1.5rem 0;
    }
  }
  /* Au doigt, la cible d'un repère doit tenir les 44 px recommandés, et un
     glissement vertical doit toujours faire défiler la page plutôt que
     traîner une planète. */
  @media (pointer: coarse) {
    .stage-canvas {
      touch-action: pan-y;
    }
    .marker {
      padding: 0.55rem 0.85rem;
      font-size: 0.8rem;
    }
    .hint-plus,
    .hint-clic {
      display: none;
    }
    .hint-touche {
      display: inline;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .hero-aurora,
    .veil,
    .hint-dot,
    .ring.on {
      animation: none;
    }
    .fil-item:global([data-reveal])::before {
      transition: none;
    }
    :global([data-reveal].is-revealed) .field,
    :global([data-reveal].is-revealed) .verdict {
      animation: none;
      opacity: 1;
    }
  }
</style>
