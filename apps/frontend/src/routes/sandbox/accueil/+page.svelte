<script lang="ts">
  /**
   * Atelier : page d'accueil v2.
   *
   * Le pari de cette version : le hero ne décore plus, il explique. Les sept
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

  type PulsarNodeFrame = {
    colorIdx: number;
    x: number;
    y: number;
    r: number;
    depth: number;
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
      title: 'Vous collez une URL, la source se remplit',
      body: "Titre, auteur·ices, date, DOI, revue : Philum va les chercher chez l'éditeur. Vous relisez au lieu de recopier.",
      color: '#528FFF',
    },
    {
      idx: 1,
      label: 'Citations vérifiées',
      title: 'Le passage exact, retrouvé dans la page',
      body: "Vous citez un passage, Philum le cherche mot pour mot dans la source telle qu'elle est aujourd'hui, et vous dit lequel a bougé.",
      color: '#73DB8C',
    },
    {
      idx: 2,
      label: 'Archivage',
      title: 'Une capture datée, pour le jour où la page bougera',
      body: "Chaque source part à l'archive avec son horodatage. Quand l'article disparaît, votre citation tient encore.",
      color: '#4DD1FF',
    },
    {
      idx: 3,
      label: 'Positions',
      title: 'Dites ce que la source fait à votre propos',
      body: 'Appuie, nuance, contredit. Une bibliographie qui déclare ses désaccords vaut mieux qu’une liste plate.',
      color: '#FA7380',
    },
    {
      idx: 4,
      label: 'Découpage',
      title: 'Un texte long devient des passages citables',
      body: 'Collez plusieurs pages : Philum propose un découpage, vous gardez les passages qui comptent.',
      color: '#FFB85C',
    },
    {
      idx: 5,
      label: 'Sources liées',
      title: 'Une source qui en cite une autre lui reste rattachée',
      body: 'Le satellite tourne autour de la source qui le cite. On suit le fil de la référence sans quitter la fiche.',
      color: '#C780FF',
    },
    {
      idx: 6,
      label: 'Export',
      title: 'Repartez avec, dans le format de votre outil',
      body: 'CSL-JSON, RIS, BibTeX, PDF, Word, et une page publique que votre audience peut ouvrir.',
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
  const timeScale = $derived(survole || selected !== null ? 0.08 : 1);

  // Hauteur d'un repère : sert d'unité pour les écarter quand deux planètes
  // se croisent. En dessous, deux étiquettes se recouvrent et aucune ne se lit.
  const MARKER_H = 26;
  // Position affichée de chaque repère, distincte de sa cible. Écrire la cible
  // directement faisait sauter les étiquettes d'un rang à l'autre d'une image
  // sur l'autre, et la scène entière paraissait désordonnée. Elles glissent.
  const posesLissees: { x: number; y: number; o: number }[] = [];
  const LISSAGE = 0.14;

  function handleFrame(nodes: PulsarNodeFrame[]) {
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

    // L'ordre de résolution des chevauchements est figé sur l'identité du
    // nœud, jamais sur sa profondeur : deux planètes qui se croisent
    // échangeraient leur rang, et le repère qui perd sa place descendrait
    // d'un cran d'un seul coup. C'est ce qui rendait la scène brouillonne.
    const ordre = [...nodes].sort((a, b) => a.colorIdx - b.colorIdx);
    const poses: { x: number; y: number; w: number }[] = [];

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

      const cibleX = Math.max(half + 4, Math.min(stageW - half - 4, cx));
      let cibleY = cy + n.r + 10;

      // Le test de chevauchement porte sur les positions affichées, pas sur
      // les cibles : sinon un repère s'écarterait d'un voisin qui n'est pas
      // encore arrivé là.
      for (let essai = 0; essai < 6; essai++) {
        const heurte = poses.some(
          (p) => Math.abs(p.y - cibleY) < MARKER_H && Math.abs(p.x - cibleX) < (p.w + w) / 2 + 8
        );
        if (!heurte) break;
        cibleY += MARKER_H + 2;
      }

      // Un repère porté par un nœud passé derrière le pulsar doit reculer
      // avec lui, sinon l'étiquette flotte devant ce qu'elle désigne.
      const cibleO = 0.4 + 0.6 * n.depth;
      const p = (posesLissees[n.colorIdx] ??= { x: cibleX, y: cibleY, o: cibleO });
      p.x += (cibleX - p.x) * LISSAGE;
      p.y += (cibleY - p.y) * LISSAGE;
      p.o += (cibleO - p.o) * LISSAGE;
      poses.push({ x: p.x, y: p.y, w });

      el.style.transform = `translate3d(${p.x.toFixed(1)}px, ${p.y.toFixed(1)}px, 0) translateX(-50%)`;
      el.style.opacity = p.o.toFixed(3);
      el.style.zIndex = String(10 + Math.round(n.depth * 10));

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
    { texte: '« Le sommeil accroît l’espace interstitiel de 60 %. »', etat: 'retrouvée' },
    { texte: '« La clairance du β-amyloïde double pendant le sommeil. »', etat: 'deplacee' },
    { texte: '« Les canaux gliaux se dilatent à l’endormissement. »', etat: 'illisible' },
  ];

  const PUBLICS = [
    {
      titre: 'Vulgarisateur·ices',
      texte: 'Votre audience peut ouvrir ce que vous avez lu, pas seulement vous croire.',
    },
    {
      titre: 'Journalistes',
      texte:
        'Une capture horodatée par source : votre méthode reste opposable quand la page change.',
    },
    {
      titre: 'Chercheur·ses',
      texte: 'Une bibliographie navigable, exportable dans le format de votre gestionnaire.',
    },
    {
      titre: 'Enseignant·es',
      texte: 'Montrez le chemin d’une affirmation à sa source, passage par passage.',
    },
  ];
</script>

<svelte:head>
  <title>Atelier : accueil v2 | Philum</title>
</svelte:head>

<svelte:window onkeydown={onWindowKeydown} />

<div class="page">
  <!-- ===================== HERO ===================== -->
  <section class="hero">
    <div class="hero-stars" aria-hidden="true"></div>
    <div class="hero-aurora" aria-hidden="true"></div>

    <div class="hero-inner">
      <div class="hero-copy">
        <p class="eyebrow">Bibliographies vérifiables</p>
        <h1>
          Vous allez adorer<br />
          <span class="accent">partager vos références</span>
        </h1>
        <p class="lede">
          Philum prend l’URL de votre contenu, en extrait les références, retrouve les passages que
          vous citez dans les pages d’origine, et publie tout ça en une fiche que votre audience
          peut parcourir.
        </p>
        <div class="ctas">
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
          <a class="cta-ghost" href="/@example/memoire-et-cerveau">Voir une fiche →</a>
        </div>
        <p class="hint">
          <span class="hint-dot" aria-hidden="true"></span>
          Cliquez une planète : elle dit ce que Philum sait faire.
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

  <!-- ===================== TROIS GESTES ===================== -->
  <section class="gestes">
    <div class="wrap">
      <h2 class="section-title" use:reveal>Trois gestes, et la fiche existe</h2>
      <p class="section-lede" use:reveal>
        Rien à saisir deux fois. Ce que la page d’origine contient déjà, Philum le lit.
      </p>

      <div class="geste" use:reveal>
        <div class="geste-copy">
          <span class="geste-n">01</span>
          <h3>Coller une URL</h3>
          <p>
            La page de votre vidéo, de votre article ou de votre étude. Philum en sort les
            références citées, puis remplit chaque source à la ligne : titre, auteur·ices, date,
            identifiant, archive.
          </p>
        </div>
        <div class="demo demo-fields" aria-hidden="true">
          <div class="demo-bar"><span></span><span></span><span></span></div>
          <div class="demo-url">https://youtu.be/…</div>
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
          <h3>Citer un passage</h3>
          <p>
            Le passage reste mot pour mot celui de la source. Vous lui ajoutez un intitulé et une
            phrase qui le situe, écrits à côté du verbatim, jamais dedans.
          </p>
        </div>
        <div class="demo demo-quote" aria-hidden="true">
          <p class="q-title">Coût énergétique</p>
          <p class="q-text">«&nbsp;Le cerveau consomme 20 % de l’oxygène au repos.&nbsp;»</p>
          <p class="q-ctx">Ordre de grandeur posé en introduction.</p>
        </div>
      </div>

      <div class="geste" use:reveal>
        <div class="geste-copy">
          <span class="geste-n">03</span>
          <h3>Relire la source</h3>
          <p>
            Un an plus tard, la page a bougé. Philum relit et rend un verdict par citation. Une page
            illisible se dit illisible : elle n’accuse pas la citation d’être fausse.
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
      <h2>Vos sources méritent d’être ouvertes.</h2>
      <p>Créez votre première fiche en quelques minutes. C’est gratuit.</p>
      <a class="cta-light" href={googleLoginUrl}>Commencer</a>
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
  .hero {
    position: relative;
    overflow: hidden;
    color: white;
    background:
      radial-gradient(ellipse at 50% 45%, rgba(70, 90, 180, 0.1) 0%, transparent 60%),
      linear-gradient(165deg, #02020a 0%, #07091a 52%, #03030d 100%);
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
  .hint-dot {
    width: 7px;
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

  /* ===================== SECTIONS CLAIRES ===================== */
  .section-title {
    font-family: var(--font-serif);
    font-size: clamp(1.8rem, 3.4vw, 2.6rem);
    font-weight: 500;
    color: rgb(var(--text-primary));
    letter-spacing: -0.015em;
    text-align: center;
  }
  .section-lede {
    text-align: center;
    color: rgb(var(--text-secondary));
    margin: 0.75rem auto 3.5rem;
    max-width: 34rem;
    line-height: 1.6;
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

  .publics {
    background: rgb(var(--bg-primary));
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

  .final {
    background: #101a30;
    color: white;
    padding: 5.5rem 0;
  }
  :global(.dark) .final {
    background: #0b1220;
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

  @media (prefers-reduced-motion: reduce) {
    .hero-aurora,
    .hint-dot,
    .ring.on {
      animation: none;
    }
    :global([data-reveal].is-revealed) .field,
    :global([data-reveal].is-revealed) .verdict {
      animation: none;
      opacity: 1;
    }
  }
</style>
