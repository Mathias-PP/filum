<script lang="ts">
  import { onMount } from 'svelte';
  import { Renderer, Program, Mesh, Triangle, Vec2, Vec3 } from 'ogl';

  let canvasEl: HTMLCanvasElement;
  let wrapEl: HTMLDivElement;

  // Tunables
  let bloomStrength = $state(0.3);
  let pulseSpeed = $state(0.25);
  let orbitSpeed = $state(0.12);
  let nodeCount = $state(7);
  let orbitMix = $state(0.55);
  let coreHue = $state(0.58);
  let nodeSpread = $state(1.0);

  // Identité des deux twins du Y-fork (par colorIdx). Définis ici pour
  // pouvoir nourrir la couleur du trunk dès la création du program GL.
  const FORK_TWIN_A_COLOR_IDX = 3;
  const FORK_TWIN_B_COLOR_IDX = 4;

  // Palette tunée 2026 : chroma poussée + bornes blanc/noir évitées pour
  // garder la cohérence avec le reste de l'UI (jamais de pur RGB primaire).
  // Inspiration : Linear/Vercel/OpenAI — couleurs nettes mais matérielles,
  // jamais fluo.
  const NODE_COLORS: [number, number, number][] = [
    [0.32, 0.56, 1.0], // electric cobalt
    [0.45, 0.86, 0.55], // emerald
    [0.3, 0.82, 1.0], // cyan azure
    [0.98, 0.45, 0.5], // coral red
    [1.0, 0.72, 0.36], // sunlit amber
    [0.78, 0.5, 1.0], // violet
    [1.0, 0.86, 0.42], // gold
    [0.45, 0.92, 0.75], // jade
  ];

  // Fixed virtual light direction (normalized): upper-left, slightly toward viewer
  const LIGHT_DIR = (() => {
    const v = [-0.55, 0.6, 0.58];
    const m = Math.hypot(v[0], v[1], v[2]);
    return [v[0] / m, v[1] / m, v[2] / m];
  })();

  const vert = /* glsl */ `
    attribute vec2 position;
    varying vec2 vUv;
    void main() {
      vUv = position * 0.5 + 0.5;
      gl_Position = vec4(position, 0.0, 1.0);
    }
  `;

  // Each node uniform: vec4(x, y, z, radius)
  // We pass colors and node count separately.
  const frag = /* glsl */ `
    precision highp float;
    varying vec2 vUv;
    uniform vec2 uAaPixel;        // 2.0 / resolution.y (NDC pixel size on Y)
    uniform vec2 uResolution;
    uniform float uTime;
    uniform vec2 uMouse;
    uniform float uBloom;
    uniform float uPulseSpeed;
    uniform float uCoreHue;
    uniform int uNodeCount;
    uniform vec4 uNodes[8];       // xyz position (z: depth), w: radius
    uniform vec3 uNodeColors[8];
    uniform vec3 uLightDir;
    uniform float uHoverNode[8];  // 0..1 per node — 1 = fully hovered
    uniform float uHoverCore;     // 0..1 — pulsar hover state
    // Trails orbitaux : 8 nodes × 6 history points = 48 entries, ordre natif
    // (jamais réordonné par le tri back-to-front). Chaque entrée vec4 :
    // (x, y, z, unused). Les couleurs viennent de uTrailColors (identité
    // stable, indépendante du tri rendering).
    uniform vec4 uTrails[48];
    uniform vec3 uTrailColors[8];
    // Identité du nœud par slot de rendering (= colorIdx du nœud occupant
    // ce slot après tri back-to-front). Utilisé pour dériver biome et seed
    // de manière STABLE : si deux nœuds échangent leur z et donc leur slot,
    // leur biome ne change PAS car il est attaché à leur identité.
    uniform float uNodeIdx[8];
    // Ancre par slot trié : (x, y, anchorR). Pour la plupart des nœuds c'est
    // le pulsar ; pour les lunes c'est leur parent ; pour les twins Y-fork
    // c'est le point M (midpoint partagé). Sert à dessiner ligne + data-pulse
    // de la node vers son vrai point d'attache.
    uniform vec3 uAnchors[8];
    // Y-fork trunk : (Mx, My, active, pulsarR). La "tige" du Y qui relie
    // le midpoint au pulsar. active=0 : pas de Y-fork à dessiner.
    uniform vec4 uForkTrunk;
    uniform vec3 uForkTrunkColor;

    // Hash + value noise
    float hash(vec2 p) {
      p = fract(p * vec2(123.34, 456.21));
      p += dot(p, p + 45.32);
      return fract(p.x * p.y);
    }
    float noise(vec2 p) {
      vec2 i = floor(p);
      vec2 f = fract(p);
      vec2 u = f * f * (3.0 - 2.0 * f);
      return mix(
        mix(hash(i + vec2(0.0, 0.0)), hash(i + vec2(1.0, 0.0)), u.x),
        mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x),
        u.y
      );
    }
    float fbm(vec2 p) {
      float v = 0.0;
      float a = 0.5;
      for (int i = 0; i < 4; i++) {
        v += a * noise(p);
        p *= 2.0;
        a *= 0.5;
      }
      return v;
    }

    vec3 hueShift(float h) {
      vec3 k = vec3(1.0, 2.0 / 3.0, 1.0 / 3.0);
      vec3 p = abs(fract(vec3(h) + k) * 6.0 - 3.0);
      return clamp(p - 1.0, 0.0, 1.0);
    }

    // Sphère matérielle avec biome procédural (gas-giant / rocky / marbré /
    // icy). Différence vs. pass 1 originale :
    //   • Edge AA 0.8× → limbe net
    //   • Pattern features durcies via smoothstep tight (contraste +)
    //   • Color delta dark/light élargi (pattern ressort)
    //   • Rim atmo 1.25 (1.35 trop ; 1.30 ok ; on garde 1.25 pour du nerf
    //     sans saturer la silhouette)
    //   • Terminator courbe naturelle
    vec4 nodeSphere(vec2 uv, vec2 c, float r, vec3 baseCol, vec2 lightFrom2D, float biome, float seed) {
      vec2 d = uv - c;
      float r2 = r * r;
      float d2 = dot(d, d);
      float dist = sqrt(d2);
      float aa = uAaPixel.x * 0.8;
      float alpha = 1.0 - smoothstep(r - aa, r + aa, dist);
      if (alpha <= 0.0) return vec4(0.0);
      float zSq = max(r2 - d2, 0.0);
      float zLocal = sqrt(zSq) / r;
      vec3 n = vec3(d.x / r, d.y / r, zLocal);

      // Rotation propre très lente (Earth-like discret). 0.03 rad/s ≈ 200s
      // par rev — perceptible si on regarde fixe, jamais distrayant ni
      // "brusque".
      vec2 sp = n.xy + vec2(seed, seed * 0.7);
      float spinSpeed = 0.03 * (0.7 + 0.6 * fract(seed * 7.31));
      vec2 rsp = sp + vec2(uTime * spinSpeed, 0.0);

      // Patterns par biome — features adoucies (smoothstep élargi, bandes
      // moins puissantes). Combinées au color delta serré (0.05), elles
      // donnent une texture organique sans dominer la couleur du nœud.
      float pattern = 0.5;
      if (biome < 0.5) {
        // 0 — gas giant : bandes douces
        float warp = fbm(rsp * 3.2) - 0.5;
        float bands = sin((rsp.y + warp * 0.55) * 6.0);
        bands = sign(bands) * pow(abs(bands), 0.85); // bordures plus douces
        pattern = bands * 0.5 + 0.5;
      } else if (biome < 1.5) {
        // 1 — rocky / continents — côtes graduelles (élargi 0.46-0.50 → 0.40-0.56)
        float h = fbm(rsp * 4.0);
        pattern = smoothstep(0.40, 0.56, h);
      } else if (biome < 2.5) {
        // 2 — marbré — gradient large (0.32-0.68 → 0.28-0.72)
        float warp = fbm(rsp * 2.0);
        vec2 q = rsp * 3.5 + vec2(warp * 2.2, fbm(rsp * 2.3) * 2.0);
        float v = fbm(q);
        pattern = smoothstep(0.28, 0.72, v);
      } else {
        // 3 — icy / craquelures — élargi (0.43-0.47 → 0.40-0.50)
        float v = fbm(rsp * 6.5);
        pattern = 1.0 - smoothstep(0.40, 0.50, abs(v - 0.5));
      }

      // Color delta resserré (delta 0.14 → 0.05) — les marbrures restent
      // visibles mais bien plus discrètes, surtout sur les nœuds saturés
      // (violet, emerald) où le contraste précédent dominait la couleur.
      vec3 darkCol  = baseCol * 0.92;
      vec3 lightCol = mix(baseCol, vec3(1.0), 0.05);
      vec3 surfaceCol = mix(darkCol, lightCol, pattern);

      // Lighting from pulsar
      vec3 L = normalize(vec3(lightFrom2D.x, lightFrom2D.y, 0.35));
      float lam = max(dot(n, L), 0.0);
      // Terminator courbe naturelle (pas de plancher relevé qui aplatit)
      float diffuseAmt = mix(0.18, 1.15, smoothstep(0.0, 0.65, lam));

      // Specular variable par pattern (pôles brillants sur ice / rocky)
      vec3 viewDir = vec3(0.0, 0.0, 1.0);
      vec3 hVec = normalize(L + viewDir);
      float specPow = mix(32.0, 70.0, pattern);
      float spec = pow(max(dot(n, hVec), 0.0), specPow) * mix(0.25, 0.55, pattern);
      vec3 specCol = mix(baseCol, vec3(1.0), 0.80) * spec;

      // Rim atmo Fresnel (1.25 — assez net sans étouffer)
      float fres = pow(1.0 - zLocal, 3.0);
      vec3 atmoRim = mix(baseCol, vec3(1.0), 0.20) * fres * 1.25;

      // Night side : surface pattern visible côté nuit (jamais noir total)
      vec3 nightSide = surfaceCol * 0.18 * (1.0 - lam);

      vec3 col = surfaceCol * diffuseAmt + specCol + atmoRim + nightSide;
      return vec4(col, alpha);
    }

    void main() {
      vec2 uv = (vUv - 0.5) * 2.0;
      uv.x *= uResolution.x / uResolution.y;

      vec3 col = vec3(0.0);

      // ====================================================================
      // BACKGROUND — Continuous cosmic web / nebula matrix.
      // ====================================================================
      // The goal: a coherent textured field that reads as deep-space structure
      // (cosmic web of gas and dust), not isolated bright color blobs.
      // Strategy: build a SHARED structural field once, then apply it as both
      // a brightness pattern AND a color modulation. Colors are very desaturated
      // so the texture dominates the eye, not the hue.

      vec2 driftA = vec2(uTime * 0.0025, uTime * 0.0009);
      vec2 driftB = vec2(uTime * -0.0018, uTime * 0.0013);

      // 1) Deep void base — darker than before
      col = vec3(0.004, 0.005, 0.010);

      // 2) MATRIX — fond très atténué : on garde l'effet "structure cosmique"
      //    mais à intensité ~40 % de la précédente, et avec un blend doux
      //    (lit / cool plus proches) → plus de "courbes quart-de-cercle"
      //    visibles qui faisaient de la concurrence au pulsar.
      vec2 matUv = uv * 1.2 + driftA;
      float m1 = fbm(matUv);
      float m2 = fbm(matUv * 2.3 + vec2(5.0));
      float ridge1 = 1.0 - abs(m1 - 0.5) * 2.0;
      float ridge2 = 1.0 - abs(m2 - 0.5) * 2.0;
      // Exposants plus élevés → filaments plus rares et plus discrets
      float webBase = pow(ridge1, 2.5) * 0.4 + pow(ridge2, 3.0) * 0.2;
      float density = fbm(uv * 0.5 + driftB);

      // 3) Matrix brightness — gradient plus serré, base plus sombre.
      vec3 cool = vec3(0.006, 0.009, 0.022);
      vec3 lit  = vec3(0.014, 0.022, 0.052);   // ~ moitié de la précédente
      vec3 matrix = mix(cool, lit, smoothstep(0.35, 0.85, webBase));
      matrix *= 0.50 + 0.50 * density;
      col += matrix;

      // 4) Dust lanes : intensité 0.50 → 0.20 (à peine perceptibles, jamais
      //    en concurrence avec le pulsar).
      vec2 dustUv = uv * vec2(1.4, 0.9) + vec2(2.0, -1.5) + driftB;
      float dustField = fbm(dustUv);
      float dustField2 = fbm(dustUv * 2.5 + vec2(7.0));
      float dustRidge = 1.0 - abs(dustField - 0.5) * 2.0;
      dustRidge *= 0.6 + 0.4 * dustField2;
      float dustMask = smoothstep(0.72, 0.95, dustRidge);
      col *= 1.0 - dustMask * 0.20;

      // NOTE: colored emission regions and distant galaxy disks were removed —
      // they read as luminous patches rather than as cosmic structure.

      // ====================================================================
      // STARFIELD — three layers at different scales for depth
      // ====================================================================

      // Layer 1: distant tiny stars (very dense, low brightness)
      {
        vec2 g = uv * 80.0;
        vec2 id = floor(g);
        vec2 fp = fract(g) - 0.5;
        float h = hash(id);
        if (h > 0.985) {
          float d = length(fp);
          col += vec3(0.6, 0.65, 0.75) * smoothstep(0.025, 0.0, d) * 0.4;
        }
      }

      // Layer 2: mid stars (medium density, varied size)
      {
        vec2 g = uv * 35.0;
        vec2 id = floor(g);
        vec2 fp = fract(g) - 0.5;
        float h = hash(id);
        if (h > 0.978) {
          float d = length(fp);
          float size = mix(0.025, 0.06, hash(id + 0.5));
          float twinkle = 0.65 + 0.35 * sin(uTime * 0.7 + h * 100.0);
          // Color temp: subtly cooler or warmer per star
          float ct = hash(id + 1.7);
          vec3 starCol = mix(vec3(0.7, 0.8, 1.0), vec3(1.0, 0.85, 0.65), ct);
          col += starCol * smoothstep(size, 0.0, d) * twinkle * 0.65;
        }
      }

      // Layer 3: bright foreground stars (rare, bigger, with diffraction spikes)
      {
        vec2 g = uv * 14.0;
        vec2 id = floor(g);
        vec2 fp = fract(g) - 0.5;
        float h = hash(id);
        if (h > 0.992) {
          float d = length(fp);
          float twinkle = 0.7 + 0.3 * sin(uTime * 1.1 + h * 200.0);
          float ct = hash(id + 3.3);
          vec3 starCol = mix(vec3(0.65, 0.80, 1.0), vec3(1.0, 0.90, 0.75), ct);
          // Bright core
          float core = smoothstep(0.05, 0.0, d);
          // Tiny diffraction cross (only on the brightest)
          float sx = exp(-abs(fp.x) * 50.0) * exp(-abs(fp.y) * 250.0);
          float sy = exp(-abs(fp.y) * 50.0) * exp(-abs(fp.x) * 250.0);
          float spikes = (sx + sy) * 0.45;
          col += starCol * (core + spikes) * twinkle * 0.9;
        }
      }

      // ====================================================================
      // TRAILS ORBITAUX — sillage de chaque nœud sur son orbite récente
      // ====================================================================
      // Chaque nœud laisse 6 "fantômes" gaussiens fade. On les dessine AVANT
      // le pulsar et les nœuds — ils passent dessous, c'est ce qui donne la
      // sensation de "passé". L'intensité décroît exponentiellement avec
      // l'âge ; la couleur est celle du nœud, dimmed par sa profondeur.
      for (int i = 0; i < 8; i++) {
        float active = step(float(i) + 0.5, float(uNodeCount));
        if (active < 0.5) continue;
        vec3 trailCol = uTrailColors[i];
        for (int j = 0; j < 6; j++) {
          vec4 t = uTrails[i * 6 + j];
          // age 0 = most recent ghost, age 1 = oldest. Falloff exponentiel.
          float age = float(j) / 5.0;
          float ageFade = exp(-age * 2.4);
          float depthDim = 0.55 + 0.45 * clamp(t.w / 0.35 + 0.5, 0.0, 1.0);
          vec2 dT = uv - t.xy;
          float dT2 = dot(dT, dT);
          // Gaussian dot. Plus le segment est ancien, plus il est diffus.
          float sigma = mix(0.012, 0.020, age);
          float intensity = exp(-dT2 / (sigma * sigma)) * 0.18 * ageFade * depthDim;
          col += trailCol * intensity;
        }
      }

      // --- Pulsar (3D sphere — position controlled by JS for click-drag) ---
      vec2 coreC = uMouse;  // uMouse repurposed as "pulsar position" (set by JS)
      // Pulsar scale FIXE — l'effet hover passe par la luminosité (halo),
      // jamais par la taille. Sinon visuellement on perçoit un "gonflement"
      // quand un nœud passe sous le curseur et frôle le pulsar.
      float coreR = 0.143;
      float pulse = 0.5 + 0.5 * sin(uTime * uPulseSpeed * 2.0);
      // Taille constante : pas de breathing pour éviter l'illusion que le
      // pulsar "change de taille" quand un nœud passe devant.
      float coreRPulsed = coreR;
      vec3 coreColor = hueShift(uCoreHue);
      // --- Stellar corona: multi-layered halo + diffraction spikes ---
      vec2 sd = uv - coreC;
      float dCore = length(sd);
      float ang = atan(sd.y, sd.x);
      float haloOut = max(dCore - coreRPulsed * 0.96, 0.0);

      // 1. Chromosphère brillante (just outside limb) — niveau pass 3
      float chrom = exp(-haloOut * 30.0) * 0.95;
      // 2. Corona mid-range — niveau pass 3
      float corona = exp(-haloOut * 8.0) * 0.45;
      // 3. Halo diffus large — niveau pass 3
      float farHalo = exp(-dCore * 2.5) * 0.35;
      vec3 haloColor = mix(coreColor, vec3(1.0), 0.30);
      col += haloColor * (chrom + corona) * (0.95 + 0.10 * pulse);
      col += coreColor * farHalo * (0.85 + 0.15 * pulse);

      // 4. Diffraction spikes — pass 3 (discrets)
      float spikeH = exp(-pow(abs(sd.y) * 160.0, 1.4)) * exp(-abs(sd.x) * 9.0);
      float spikeV = exp(-pow(abs(sd.x) * 160.0, 1.4)) * exp(-abs(sd.y) * 9.0);
      float spike = (spikeH + spikeV) * (0.90 + 0.15 * pulse);
      col += mix(coreColor, vec3(1.0), 0.45) * spike * 0.20;

      // 5. Anneau chromosphérique fin — remplace les flares multi-couches.
      //    Toujours CENTRÉ (pas de noise → pas de "halos désaxés derrière le
      //    pulsar"). Couleur pinkish-warm comme la vraie chromosphère d'une
      //    étoile bleue type O/B. Très fin, juste à l'extérieur du limbe.
      //    Modulation très subtile et lente du rayon (battement chromosphère).
      float chromoBreath = 1.0 + 0.04 * sin(uTime * 0.6);
      float chromoFalloff = exp(-haloOut * 65.0 * chromoBreath);
      float chromoMask = chromoFalloff * step(coreRPulsed * 0.985, dCore);
      vec3 chromoCol = vec3(1.00, 0.55, 0.50);  // rose-saumon, classique
      col += chromoCol * chromoMask * 0.55;

      // ====================================================================
      // CONNEXIONS nœud↔ancre — chaque nœud se relie à SON ancre (pulsar
      // pour la majorité, parent pour les lunes, forkBase pour les twins).
      // ====================================================================
      for (int i = 0; i < 8; i++) {
        float active = step(float(i) + 0.5, float(uNodeCount));
        vec4 n = uNodes[i];
        vec2 a = n.xy;
        vec2 anc = uAnchors[i].xy;
        float ancR = uAnchors[i].z;
        vec2 d = anc - a;
        float lineLen = max(length(d), 0.001);
        vec2 dir = d / lineLen;
        vec2 rel = uv - a;
        float along = dot(rel, dir);
        float across = length(rel - dir * along);
        float onSeg = step(n.w * 1.02, along) * step(along, lineLen - ancR * 1.00);
        float aa = uAaPixel.x * 1.1;
        float lineMask = (1.0 - smoothstep(0.0022 - aa, 0.0022 + aa, across)) * onSeg;
        float lineHaze = exp(-across * 220.0) * onSeg * 0.35;
        float depthFade = 0.55 + 0.45 * clamp(n.z / 0.35 + 0.5, 0.0, 1.0);
        vec3 lineColor = mix(uNodeColors[i], vec3(1.0), 0.15);
        col += lineColor * (lineMask * 0.45 + lineHaze * 0.7) * depthFade * active;

        // Data pulse : "comète" qui glisse du nœud vers le pulsar.
        // Phase indépendante par nœud → flux asynchrone.
        // Fluidité : (1) envelope smoothstep aux deux extrémités pour éviter
        // le wrap brutal de fract() qui faisait apparaître/disparaître le
        // pulse d'un coup. (2) trail comète additionnelle plus large derrière
        // la tête → le mouvement reste lisible même à framerate variable.
        float lt = fract(uTime * 0.42 + float(i) * 0.137);
        // Envelope : 0→1 sur les premiers 8 %, 1→0 sur les derniers 8 %.
        // → fade in / fade out doux, jamais de "pop".
        float env = smoothstep(0.0, 0.08, lt) * (1.0 - smoothstep(0.92, 1.0, lt));
        float pulsePos = lt * (lineLen - n.w - ancR) + n.w;
        float pulseDist = along - pulsePos;
        // Tête : gaussien serré.
        float head = exp(-pulseDist * pulseDist * 2400.0);
        // Comète : queue exp asymétrique qui s'étire derrière (vers le nœud).
        // pulseDist > 0 = derrière la tête (vers le pulsar) → pas de queue
        // pulseDist < 0 = devant (vers le nœud) → queue
        float tail = exp(pulseDist * 26.0) * step(pulseDist, 0.0) * 0.55;
        float lateral = exp(-across * across * 50000.0);
        float dataPulse = (head + tail) * lateral * onSeg * env;
        col += mix(uNodeColors[i], vec3(1.0), 0.50) * dataPulse * 1.6 * depthFade * active;
      }

      // ====================================================================
      // Y-FORK TRUNK — tige du Y reliant le midpoint M au pulsar.
      // ====================================================================
      // Active seulement si uForkTrunk.z > 0.5 (passé par le JS). Même
      // mécanique que les lignes de connexion mais entre M et le pulsar.
      if (uForkTrunk.z > 0.5) {
        vec2 mPoint = uForkTrunk.xy;
        float pR = uForkTrunk.w;
        vec2 d = coreC - mPoint;
        float lineLen = max(length(d), 0.001);
        vec2 dir = d / lineLen;
        vec2 rel = uv - mPoint;
        float along = dot(rel, dir);
        float across = length(rel - dir * along);
        // Start tout près de M (petit buffer pour fusion visuelle avec les
        // deux branches), fin avant le pulsar.
        float onSeg = step(0.005, along) * step(along, lineLen - pR * 1.00);
        float aa = uAaPixel.x * 1.1;
        float lineMask = (1.0 - smoothstep(0.0024 - aa, 0.0024 + aa, across)) * onSeg;
        float lineHaze = exp(-across * 200.0) * onSeg * 0.30;
        vec3 trunkColor = mix(uForkTrunkColor, vec3(1.0), 0.20);
        col += trunkColor * (lineMask * 0.50 + lineHaze * 0.7);

        // Data pulse sur le trunk — M → pulsar (continuité du flux d'in-
        // formation depuis les twins).
        float lt = fract(uTime * 0.42 + 0.5);
        float env = smoothstep(0.0, 0.08, lt) * (1.0 - smoothstep(0.92, 1.0, lt));
        float pulsePos = lt * (lineLen - 0.005 - pR) + 0.005;
        float pulseDist = along - pulsePos;
        float head = exp(-pulseDist * pulseDist * 2400.0);
        float tail = exp(pulseDist * 26.0) * step(pulseDist, 0.0) * 0.55;
        float lateral = exp(-across * across * 50000.0);
        float dataPulse = (head + tail) * lateral * onSeg * env;
        col += mix(uForkTrunkColor, vec3(1.0), 0.50) * dataPulse * 1.4;
      }

      // Pulsar sphere — hot blue main-sequence star (Rigel/Spica style)
      {
        vec2 d = uv - coreC;
        float r2 = coreRPulsed * coreRPulsed;
        float d2 = dot(d, d);
        float dist = sqrt(d2);
        // AA pulsar réduit (1.4 → 0.9) pour un limbe net comme les nœuds.
        float aa = uAaPixel.x * 0.9;
        float alpha = 1.0 - smoothstep(coreRPulsed - aa, coreRPulsed + aa, dist);
        if (alpha > 0.0) {
          float zSq = max(r2 - d2, 0.0);
          float zN = sqrt(zSq) / coreRPulsed;
          vec2 sp = d / coreRPulsed;

          // Palette naine bleue-blanche (~25 000 K, type Sirius B). Le
          // RIM lit bleu intense, le CENTRE blanc-chaud avec un voile cyan,
          // jamais électrique. Reinhard tonemap mange ~30 % → on prépousse
          // les stops au-dessus de 1.0 en valeur linéaire.
          vec3 photoRim    = vec3(0.50, 0.85, 1.50);  // rim bleu net
          vec3 photoMid    = vec3(1.05, 1.45, 2.05);  // transition cyan-blanc
          vec3 photoCenter = vec3(1.90, 2.10, 2.50);  // cœur blanc-chaud légèrement bleuté
          // Re-tint par slider — atténué (0.18 / 0.15 / 0.10) pour ne pas
          // re-saturer en bleu quand on bouge la teinte.
          photoRim    = mix(photoRim,    coreColor * 1.5, 0.18);
          photoMid    = mix(photoMid,    coreColor * 1.7, 0.15);
          photoCenter = mix(photoCenter, coreColor * 2.0, 0.10);

          vec3 starSurface = mix(photoRim, photoMid, smoothstep(0.0, 0.55, zN));
          starSurface     = mix(starSurface, photoCenter, smoothstep(0.55, 0.95, zN));

          // Limb darkening
          float limb = 0.70 + 0.30 * pow(zN, 0.42);

          // Granulation: very fine, very subtle
          float granul = fbm(sp * 24.0 + uTime * 0.02);
          starSurface *= 0.97 + 0.06 * (granul - 0.5);

          // Hotspot — tight, but ALSO blue-tinted so it doesn't desaturate the center
          // Hotspot blanc-chaud légèrement bleuté (naine blanche/bleue).
          float hotspot = pow(zN, 8.0) * 0.45;
          starSurface += mix(coreColor, vec3(0.95, 0.97, 1.0), 0.40) * hotspot;

          // Star scintillation (very subtle global brightness flicker)
          float scint = 0.97 + 0.06 * sin(uTime * 3.1 + fbm(sp * 6.0) * 8.0);
          starSurface *= scint;

          // Pulse breathing
          // Subtle brightness pulse only (no size change). Garde l'étoile
          // "vivante" sans gonfler ni rétrécir.
          starSurface *= 0.97 + 0.04 * pulse;

          col = mix(col, starSurface * limb, alpha);
        }
      }

      // --- Nodes (already depth-sorted back-to-front in JS) ---
      for (int i = 0; i < 8; i++) {
        float active = step(float(i) + 0.5, float(uNodeCount));
        vec4 n = uNodes[i];
        vec3 nodeColor = uNodeColors[i];
        float depthBright = 0.75 + 0.25 * clamp(n.z / 0.35 + 0.5, 0.0, 1.0);

        // Hover: enlarge the radius and brighten the orb
        float hover = uHoverNode[i];
        // Taille fixe — l'effet hover passe uniquement par le glow (gérée
        // plus bas via glowBoost), jamais par la taille du nœud.
        float nodeR = n.w;

        // Per-pixel occlusion by the pulsar (smooth, depth-aware).
        // pulsarCoverage: 1 inside pulsar disk, 0 outside, AA at edge.
        // behindMix: 1 if node is behind, 0 if in front, smooth around z=0.
        float dPixelToCore = length(uv - coreC);
        float aaCore = uAaPixel.x * 1.4;
        float pulsarCoverage = 1.0 - smoothstep(coreRPulsed - aaCore, coreRPulsed + aaCore, dPixelToCore);
        float behindMix = smoothstep(coreRPulsed * 0.05, -coreRPulsed * 0.05, n.z);
        float occlude = pulsarCoverage * behindMix;
        float mask = active;

        // Light comes FROM the pulsar TOWARD the node — so the node's "lit
        // side" faces the pulsar.
        vec2 toCore = coreC - n.xy;
        vec2 lightDir2D = normalize(toCore + vec2(0.0001));
        // biome & seed dérivés de l'IDENTITÉ du nœud (uNodeIdx[i] = colorIdx),
        // pas du slot trié. Sinon, à chaque croisement en z, deux nœuds
        // échangent leurs slots et donc leurs biomes → "netteté qui change".
        float biome = mod(uNodeIdx[i], 4.0);
        float seed = uNodeIdx[i] * 13.37;
        vec4 sh = nodeSphere(uv, n.xy, nodeR, nodeColor, lightDir2D, biome, seed);
        vec3 lit = sh.rgb * (depthBright + 0.40 * hover);

        // Glow extérieur additif — rim tight + wide. Renforcé pour pop la
        // couleur autour de chaque nœud sans saturer le centre.
        float dN = length(uv - n.xy);
        float glowOut = max(dN - nodeR * 0.95, 0.0);
        float glowBoost = 1.0 + 1.30 * hover;
        float glowRim  = exp(-glowOut * 32.0) * 0.62 * glowBoost;
        float glowWide = exp(-glowOut * 10.0) * 0.28 * glowBoost;
        col += nodeColor * (glowRim + glowWide) * depthBright * mask * (1.0 - occlude);

        col = mix(col, lit, sh.a * mask * (1.0 - occlude));
      }

      // --- Light bloom on bright pixels ---
      vec3 bloomBoost = pow(max(col - 0.78, 0.0), vec3(1.7)) * uBloom * 0.30;
      col += bloomBoost;

      // Tonemap (Reinhard) + slight gamma
      col = col / (1.0 + col);
      col = pow(col, vec3(0.88));

      // Edge fade — blends the canvas with the surrounding page bg so there's
      // no visible rectangle boundary. Two fades: a soft radial darkening
      // (cosmic vignette) and a per-axis fade that LERPs to the page bg color
      // matching the CSS .stage background.
      vec3 pageBg = vec3(0.011, 0.011, 0.025);
      // Radial vignette (subtle, cosmic feel)
      float radialVig = smoothstep(1.7, 0.6, length(uv));
      col *= 0.55 + 0.45 * radialVig;
      // Per-axis edge fade — fades sharply only in the last 15% of each axis
      vec2 edge = abs(vUv - 0.5) * 2.0;
      float edgeDist = max(edge.x, edge.y);
      float blend = 1.0 - smoothstep(0.70, 1.0, edgeDist);
      col = mix(pageBg, col, blend);

      gl_FragColor = vec4(col, 1.0);
    }
  `;

  onMount(() => {
    const renderer = new Renderer({
      canvas: canvasEl,
      dpr: Math.min(window.devicePixelRatio, 2),
      alpha: false,
      antialias: true,
    });
    const gl = renderer.gl;
    gl.clearColor(0.011, 0.011, 0.025, 1);

    const geometry = new Triangle(gl);

    const colorUniform: Vec3[] = [];
    for (let i = 0; i < 8; i++) {
      const c = NODE_COLORS[i % NODE_COLORS.length];
      colorUniform.push(new Vec3(c[0], c[1], c[2]));
    }
    // OGL detects array uniforms via Array.isArray() — must be plain Array,
    // not Float32Array. Each element is itself a plain Array (vec4 or vec3).
    const nodesArr: number[][] = Array.from({ length: 8 }, () => [0, 0, 0, 0.05]);
    const colorsArr: number[][] = Array.from({ length: 8 }, (_, i) => {
      const c = NODE_COLORS[i % NODE_COLORS.length];
      return [c[0], c[1], c[2]];
    });
    // 8 nodes × 6 history points. Layout: [n0_t-1, n0_t-2, ..., n0_t-6, n1_t-1, ...].
    // vec4 = (x, y, z, 0). z dim les segments back-orbit comme leur nœud vivant.
    // Ordre natif (jamais réordonné par le tri back-to-front).
    const TRAIL_HISTORY = 6;
    const trailsArr: number[][] = Array.from({ length: 8 * TRAIL_HISTORY }, () => [0, 0, 0, 0]);
    // Couleurs trails dans l'ordre natif (identité de nœud, jamais réordonnée).
    const trailColorsArr: number[][] = Array.from({ length: 8 }, (_, i) => {
      const c = NODE_COLORS[i % NODE_COLORS.length];
      return [c[0], c[1], c[2]];
    });

    const program = new Program(gl, {
      vertex: vert,
      fragment: frag,
      uniforms: {
        uResolution: { value: new Vec2(1, 1) },
        uAaPixel: { value: new Vec2(0.002, 0.002) },
        uTime: { value: 0 },
        uMouse: { value: new Vec2(0, 0) },
        uBloom: { value: bloomStrength },
        uPulseSpeed: { value: pulseSpeed },
        uCoreHue: { value: coreHue },
        uNodeCount: { value: nodeCount },
        uNodes: { value: nodesArr },
        uNodeColors: { value: colorsArr },
        uLightDir: { value: new Vec3(LIGHT_DIR[0], LIGHT_DIR[1], LIGHT_DIR[2]) },
        uHoverNode: { value: Array.from({ length: 8 }, () => 0) },
        uHoverCore: { value: 0 },
        uTrails: { value: trailsArr },
        uTrailColors: { value: trailColorsArr },
        // colorIdx du nœud occupant chaque slot trié (réécrit chaque frame
        // par la même boucle qui réordonne uNodes / uNodeColors).
        uNodeIdx: { value: Array.from({ length: 8 }, () => 0) },
        // Ancre par slot trié (x, y, anchorR) — pulsar pour la majorité,
        // parent pour les lunes, point M pour les twins Y-fork.
        uAnchors: {
          value: Array.from({ length: 8 }, () => [0, 0, 0.143] as number[]),
        },
        // Y-fork trunk : (Mx, My, active, pulsarR). Décrit la "tige" du Y
        // qui prolonge le point M jusqu'au pulsar.
        uForkTrunk: { value: [0, 0, 0, 0.143] as number[] },
        // Couleur du trunk : mix des deux twins (calculée statiquement).
        uForkTrunkColor: {
          value: new Vec3(
            (NODE_COLORS[FORK_TWIN_A_COLOR_IDX][0] + NODE_COLORS[FORK_TWIN_B_COLOR_IDX][0]) * 0.5,
            (NODE_COLORS[FORK_TWIN_A_COLOR_IDX][1] + NODE_COLORS[FORK_TWIN_B_COLOR_IDX][1]) * 0.5,
            (NODE_COLORS[FORK_TWIN_A_COLOR_IDX][2] + NODE_COLORS[FORK_TWIN_B_COLOR_IDX][2]) * 0.5,
          ),
        },
      },
    });

    const mesh = new Mesh(gl, { geometry, program });

    function resize() {
      const rect = wrapEl.getBoundingClientRect();
      renderer.setSize(rect.width, rect.height);
      program.uniforms.uResolution.value.set(rect.width, rect.height);
      // AA pixel size in NDC units (y-axis), used for sub-pixel anti-aliasing.
      const aa = 2 / Math.max(rect.height, 1);
      program.uniforms.uAaPixel.value.set(aa, aa);
    }
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(wrapEl);

    const targetMouse = new Vec2(0, 0);
    const currentMouse = new Vec2(0, 0);
    let draggingIdx = -1; // index into the sorted slice (matches current frame)
    let draggingNodeKey = -1; // stable node identity (NODES index)
    let draggingCore = false;
    // Pulsar displacement from its anchor (0,0), eased toward cursor on drag,
    // toward 0 on release.
    const coreDisp = { x: 0, y: 0 };

    function onMove(e: PointerEvent) {
      const rect = wrapEl.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
      const aspect = rect.width / rect.height;
      targetMouse.set(x * aspect, y);
    }
    function onLeave() {
      targetMouse.set(0, 0);
      draggingIdx = -1;
      draggingNodeKey = -1;
      draggingCore = false;
    }
    function onDown(e: PointerEvent) {
      // Front-most pick wins: iterate all nodes, keep the closest hit.
      const n = nodeCount;
      let pickKey = -1;
      let bestD = Infinity;
      for (let i = 0; i < n; i++) {
        const c = computed[i];
        const dx = currentMouse.x - c.x;
        const dy = currentMouse.y - c.y;
        const r = c.r * 1.25;
        const d2 = dx * dx + dy * dy;
        if (d2 < r * r && d2 < bestD) {
          bestD = d2;
          pickKey = c.colorIdx;
        }
      }
      if (pickKey !== -1) {
        draggingNodeKey = pickKey;
        wrapEl.setPointerCapture?.(e.pointerId);
        return;
      }
      // No node hit — check the pulsar.
      const cx = coreDisp.x;
      const cy = coreDisp.y;
      const dx = currentMouse.x - cx;
      const dy = currentMouse.y - cy;
      const coreHitR = 0.143 * 1.2;
      if (dx * dx + dy * dy < coreHitR * coreHitR) {
        draggingCore = true;
        wrapEl.setPointerCapture?.(e.pointerId);
      }
    }
    function onUp(e: PointerEvent) {
      draggingNodeKey = -1;
      draggingCore = false;
      wrapEl.releasePointerCapture?.(e.pointerId);
    }
    wrapEl.addEventListener('pointermove', onMove);
    wrapEl.addEventListener('pointerleave', onLeave);
    wrapEl.addEventListener('pointerdown', onDown);
    wrapEl.addEventListener('pointerup', onUp);
    wrapEl.addEventListener('pointercancel', onUp);

    let rafId = 0;
    let visible = true;
    const io = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting;
        if (visible && !rafId) loop(performance.now());
      },
      { threshold: 0.01 }
    );
    io.observe(wrapEl);

    // Per-node static parameters (deterministic from index)
    // - role 'regular' : orbite simplement le pulsar
    // - role 'parent'  : idem, mais a une lune attachée
    // - role 'moon'    : orbite son parent (parentColorIdx) au lieu du pulsar
    // - role 'forkBase': idem regular, mais ancre les deux twins
    // - role 'forkTwin': orbite un base avec rotation axiale autour de l'axe
    //                    base↔pulsar (les 2 twins sont diamétralement opposés)
    type NodeRole = 'regular' | 'parent' | 'moon' | 'forkBase' | 'forkTwin';
    type NodeParam = {
      baseAngle: number;
      orbitRx: number;
      orbitRy: number;
      orbitRz: number;
      tilt: number;
      speed: number;
      radius: number;
      colorIdx: number;
      role: NodeRole;
      // pour moon et forkTwin : identité du parent (colorIdx)
      parentColorIdx: number;
      // rayon de l'orbite locale autour du parent
      localOrbitR: number;
      // vitesse de spin (multipliée par orbitSpeed pour suivre le slider)
      localSpeed: number;
      localPhase: number;
      // pour forkTwin : +1 ou -1 (les deux twins sont opposés sur l'axe)
      twinSide: number;
    };
    // Scale graphe ×1.3 demandé : orbites et rayons nœuds multipliés par 1.3.
    const G_SCALE = 1.3;
    // Rôles configurés explicitement pour 7 nœuds :
    //   0 régulier (cobalt)
    //   1 PARENT (emerald, +20% taille) — ancre la MOON 5
    //   2 régulier (cyan azure)
    //   3 FORK TWIN (coral) — partage un trunk Y-fork avec node 4
    //   4 FORK TWIN (amber) — partage le trunk avec node 3
    //   5 MOON (violet, -45%) du parent 1
    //   6 régulier (gold)
    // Twins 3 et 4 : orbites normales autour du pulsar, MAIS leur ligne de
    // connexion se rejoint sur un point M (midpoint dynamique) et un trunk
    // M→pulsar prolonge l'ensemble. Aucune mécanique orbitale partagée.
    // Les colorIdx des twins sont déclarés au niveau module (cf. en haut du
    // <script>) car utilisés dès la création du program GL.
    function makeNode(i: number): NodeParam {
      const baseRadius = (0.038 + 0.012 * Math.sin(i * 1.3)) * 1.5;
      const orbital = {
        baseAngle: (i / 6) * Math.PI * 2,
        orbitRx: (0.48 + 0.1 * Math.sin(i * 2.3)) * G_SCALE,
        orbitRy: (0.36 + 0.08 * Math.cos(i * 1.7)) * G_SCALE,
        orbitRz: (0.28 + 0.08 * Math.sin(i * 1.1 + 1.0)) * G_SCALE,
        tilt: i * 0.45,
        speed: 0.85 + 0.3 * Math.sin(i * 1.9),
        radius: baseRadius,
        colorIdx: i,
        role: 'regular' as NodeRole,
        parentColorIdx: -1,
        localOrbitR: 0,
        localSpeed: 0,
        localPhase: 0,
        twinSide: 0,
      };
      switch (i) {
        case 1:
          return { ...orbital, role: 'parent', radius: baseRadius * 1.2 };
        case 3:
          // Twin "A" du Y-fork : orbite NORMALE, marquage role pour
          // déclencher le routage de connexion vers M.
          return { ...orbital, role: 'forkTwin', twinSide: 1 };
        case 4:
          // Twin "B" du Y-fork : orbite NORMALE, marquage role.
          return { ...orbital, role: 'forkTwin', twinSide: -1 };
        case 5:
          return {
            ...orbital,
            role: 'moon',
            parentColorIdx: 1,
            radius: baseRadius * 0.55,
            // Distance lune-parent bien lisible (0.13 → 0.28).
            localOrbitR: 0.28,
            localSpeed: 4.5,
            localPhase: 1.2,
          };
        default:
          return orbital;
      }
    }
    const NODES: NodeParam[] = Array.from({ length: 8 }, (_, i) => makeNode(i));

    type Computed = {
      x: number;
      y: number;
      z: number;
      r: number;
      colorIdx: number;
      role: NodeRole;
      // Ancre = point auquel la ligne de connexion de ce nœud aboutit.
      // Pour régulier/parent/forkBase : c'est le pulsar. Pour moon : son
      // parent. Pour forkTwin : sa forkBase.
      anchorX: number;
      anchorY: number;
      anchorR: number;
    };
    const computed: Computed[] = Array.from({ length: 8 }, () => ({
      x: 0,
      y: 0,
      z: 0,
      r: 0.05,
      colorIdx: 0,
      role: 'regular' as NodeRole,
      anchorX: 0,
      anchorY: 0,
      anchorR: 0.143,
    }));
    // Per-node displacement from its orbital position (for click-and-drag).
    // Decays back to (0, 0) when the node is released — re-joins the orbit.
    const displacement = Array.from({ length: 8 }, () => ({ x: 0, y: 0 }));

    // Hover state — smoothed values, target values computed by mouse picking.
    const hoverTarget = new Array(8).fill(0) as number[];
    const hoverCurrent = program.uniforms.uHoverNode.value as number[];
    let hoverCoreTarget = 0;

    const start = performance.now();
    // Trail sampling : on enregistre une position toutes les TRAIL_DT secondes
    // par nœud, pas à chaque frame — sinon la trace devient une bande épaisse
    // peu lisible. ~80ms entre deux échantillons donne 6 points sur ~500ms,
    // soit ~quart d'orbite à vitesse par défaut.
    const TRAIL_DT = 0.08;
    let lastTrailSample = -Infinity;
    function loop(t: number) {
      rafId = 0;
      if (!visible) return;
      currentMouse.x += (targetMouse.x - currentMouse.x) * 0.1;
      currentMouse.y += (targetMouse.y - currentMouse.y) * 0.1;
      const time = (t - start) / 1000;

      // Compute node 3D positions (no cursor pull on the cosmos — orbits are sacred).
      // Click-drag adds a transient displacement to a single node, which decays
      // back to zero when released so the node rejoins its orbit smoothly.
      const n = nodeCount;
      const spread = nodeSpread;
      const mix01 = orbitMix;
      const PULSAR_R = 0.143;
      // PASSE A : orbite simple autour du pulsar pour tous les nœuds
      // (régulier / parent / forkBase). Les moon et forkTwin auront leur
      // position OVERWRITE dans la passe B après que parent/base sont
      // résolus, sinon ils traînent d'une frame.
      for (let i = 0; i < n; i++) {
        const p = NODES[i];
        const a = p.baseAngle + time * orbitSpeed * p.speed;
        const lx = Math.cos(a) * p.orbitRx * spread;
        const ly0 =
          Math.sin(a) * (p.orbitRy * (1 - 0.4 * mix01) + p.orbitRx * 0.4 * mix01) * spread;
        const lz0 = Math.sin(a + p.tilt * 0.7) * p.orbitRz * spread;
        const cs = Math.cos(p.tilt);
        const sn = Math.sin(p.tilt);
        const ly = ly0 * cs - lz0 * sn;
        const lz = ly0 * sn + lz0 * cs;
        // Drag handling : seul un nœud directement ancré au pulsar accepte
        // un drag pour simplicité (les moons/twins suivent leur ancre).
        const isDragging = p.colorIdx === draggingNodeKey && p.role !== 'moon' && p.role !== 'forkTwin';
        const dispTargetX = isDragging ? currentMouse.x - lx : 0;
        const dispTargetY = isDragging ? currentMouse.y - ly : 0;
        const ease = isDragging ? 0.28 : 0.08;
        displacement[i].x += (dispTargetX - displacement[i].x) * ease;
        displacement[i].y += (dispTargetY - displacement[i].y) * ease;
        computed[i].x = lx + displacement[i].x;
        computed[i].y = ly + displacement[i].y;
        computed[i].z = lz;
        computed[i].r = p.radius;
        computed[i].colorIdx = p.colorIdx;
        computed[i].role = p.role;
        // Ancre par défaut = pulsar (régulier / parent / forkBase)
        computed[i].anchorX = coreDisp.x;
        computed[i].anchorY = coreDisp.y;
        computed[i].anchorR = PULSAR_R;
      }
      // PASSE B : override position pour moon (orbite locale autour du
      // parent), et override ANCRE pour les twins Y-fork (point M partagé).
      const findByColorIdx = (cidx: number): number => {
        for (let k = 0; k < n; k++) if (NODES[k].colorIdx === cidx) return k;
        return -1;
      };
      // 1) Moons : position locale autour du parent
      for (let i = 0; i < n; i++) {
        const p = NODES[i];
        if (p.role !== 'moon') continue;
        const pIdx = findByColorIdx(p.parentColorIdx);
        if (pIdx === -1) continue;
        const pNode = computed[pIdx];
        const la = p.localPhase + time * orbitSpeed * p.localSpeed;
        const mx = Math.cos(la) * p.localOrbitR;
        const my = Math.sin(la) * p.localOrbitR * 0.6;
        const mz = Math.sin(la + 0.6) * p.localOrbitR * 0.35;
        computed[i].x = pNode.x + mx;
        computed[i].y = pNode.y + my;
        computed[i].z = pNode.z + mz;
        computed[i].anchorX = pNode.x;
        computed[i].anchorY = pNode.y;
        computed[i].anchorR = pNode.r;
      }
      // 2) Y-fork : routage de connexion via un midpoint M dynamique.
      // Les twins gardent leur orbite normale (calculée passe A) ; on leur
      // assigne juste une ancre = M (à mi-chemin entre pulsar et centroïde
      // des deux twins). Plus le trunk M→pulsar sera dessiné séparément.
      const twinAidx = findByColorIdx(FORK_TWIN_A_COLOR_IDX);
      const twinBidx = findByColorIdx(FORK_TWIN_B_COLOR_IDX);
      let forkActive = 0;
      let forkMx = 0;
      let forkMy = 0;
      if (twinAidx !== -1 && twinBidx !== -1 && twinAidx < n && twinBidx < n) {
        const ta = computed[twinAidx];
        const tb = computed[twinBidx];
        // Centroïde des deux twins
        const cx = (ta.x + tb.x) * 0.5;
        const cy = (ta.y + tb.y) * 0.5;
        // M = 55 % du chemin entre pulsar et centroïde → trunk court, branches
        // longues. Résulte en un Y bien identifiable.
        forkMx = coreDisp.x + 0.55 * (cx - coreDisp.x);
        forkMy = coreDisp.y + 0.55 * (cy - coreDisp.y);
        forkActive = 1;
        // Petit rayon "tampon" autour de M : la ligne du twin s'arrête
        // juste avant M (sinon les lignes se chevauchent en désordre).
        const M_BUFFER_R = 0.018;
        computed[twinAidx].anchorX = forkMx;
        computed[twinAidx].anchorY = forkMy;
        computed[twinAidx].anchorR = M_BUFFER_R;
        computed[twinBidx].anchorX = forkMx;
        computed[twinBidx].anchorY = forkMy;
        computed[twinBidx].anchorR = M_BUFFER_R;
      }
      // Trunk uniform — utilisé par le shader pour dessiner la ligne
      // M ↔ pulsar (la "tige" du Y). Mutation in-place : OGL upload le
      // tableau à chaque draw.
      const trunkU = program.uniforms.uForkTrunk.value as number[];
      trunkU[0] = forkMx;
      trunkU[1] = forkMy;
      trunkU[2] = forkActive;
      trunkU[3] = PULSAR_R;
      // Échantillonnage des trails (ordre natif). Quand l'intervalle TRAIL_DT
      // est écoulé, on shift le ring buffer : t-1 ← t (live), t-2 ← t-1, ...
      if (time - lastTrailSample >= TRAIL_DT) {
        lastTrailSample = time;
        const trails = program.uniforms.uTrails.value as number[][];
        for (let i = 0; i < 8; i++) {
          // Shift from oldest to newest : slot k ← slot k-1.
          for (let k = TRAIL_HISTORY - 1; k > 0; k--) {
            const dst = trails[i * TRAIL_HISTORY + k];
            const src = trails[i * TRAIL_HISTORY + k - 1];
            dst[0] = src[0];
            dst[1] = src[1];
            dst[2] = src[2];
            dst[3] = src[3];
          }
          // Slot 0 ← position vivante actuelle de ce nœud (identité, pas tri).
          const live = computed[i];
          const head = trails[i * TRAIL_HISTORY + 0];
          head[0] = live.x;
          head[1] = live.y;
          head[2] = live.z;
          head[3] = 0;
        }
      }

      // Sort back-to-front
      const slice = computed.slice(0, n).sort((a, b) => a.z - b.z);
      // Write into flat uniform arrays (reorder colors to match sorted nodes).
      // On écrit aussi uNodeIdx[i] = colorIdx — sert au shader pour dériver
      // biome/seed depuis l'identité du nœud (stable au tri).
      // Et uAnchors[i] = (anchorX, anchorY, anchorR) pour redessiner les
      // lignes vers le vrai point d'attache (pulsar / parent / forkBase).
      const arr = program.uniforms.uNodes.value as number[][];
      const colArr = program.uniforms.uNodeColors.value as number[][];
      const idxArr = program.uniforms.uNodeIdx.value as number[];
      const anchArr = program.uniforms.uAnchors.value as number[][];
      for (let i = 0; i < n; i++) {
        arr[i][0] = slice[i].x;
        arr[i][1] = slice[i].y;
        arr[i][2] = slice[i].z;
        arr[i][3] = slice[i].r;
        const c = NODE_COLORS[slice[i].colorIdx];
        colArr[i][0] = c[0];
        colArr[i][1] = c[1];
        colArr[i][2] = c[2];
        idxArr[i] = slice[i].colorIdx;
        anchArr[i][0] = slice[i].anchorX;
        anchArr[i][1] = slice[i].anchorY;
        anchArr[i][2] = slice[i].anchorR;
      }

      // --- Mouse picking: find the node under the cursor (front-most only).
      // Iterate sorted list back-to-front; the LAST matching wins (= front).
      let pickIdx = -1;
      for (let i = 0; i < n; i++) {
        const sNode = slice[i];
        const dx = currentMouse.x - sNode.x;
        const dy = currentMouse.y - sNode.y;
        const r = sNode.r * 1.25; // generous hit area
        if (dx * dx + dy * dy < r * r) pickIdx = i;
      }
      // Hovering the pulsar (only if no node is picked). Use the pulsar's
      // CURRENT position (it may have been dragged) for the hit test.
      const coreDx = currentMouse.x - coreDisp.x;
      const coreDy = currentMouse.y - coreDisp.y;
      const coreHit = pickIdx === -1 && coreDx * coreDx + coreDy * coreDy < 0.085 * 0.085 * 1.5;
      hoverCoreTarget = coreHit ? 1 : 0;
      for (let i = 0; i < 8; i++) hoverTarget[i] = i === pickIdx ? 1 : 0;
      // Smooth toward target
      for (let i = 0; i < 8; i++) {
        hoverCurrent[i] += (hoverTarget[i] - hoverCurrent[i]) * 0.18;
      }
      program.uniforms.uHoverCore.value +=
        (hoverCoreTarget - program.uniforms.uHoverCore.value) * 0.18;
      // Update CSS cursor for affordance
      const wantPointer = pickIdx !== -1 || coreHit;
      if (wantPointer && wrapEl.style.cursor !== 'pointer') wrapEl.style.cursor = 'pointer';
      else if (!wantPointer && wrapEl.style.cursor !== 'crosshair')
        wrapEl.style.cursor = 'crosshair';

      // Pulsar drag/release easing — anchored at (0,0), decays back when released.
      {
        const tx = draggingCore ? currentMouse.x : 0;
        const ty = draggingCore ? currentMouse.y : 0;
        const ease = draggingCore ? 0.28 : 0.08;
        coreDisp.x += (tx - coreDisp.x) * ease;
        coreDisp.y += (ty - coreDisp.y) * ease;
      }
      // uMouse uniform is repurposed: it now carries the pulsar's current
      // 2D position (the shader reads it as `coreC`).
      program.uniforms.uMouse.value.set(coreDisp.x, coreDisp.y);
      program.uniforms.uTime.value = time;
      program.uniforms.uBloom.value = bloomStrength;
      program.uniforms.uPulseSpeed.value = pulseSpeed;
      program.uniforms.uCoreHue.value = coreHue;
      program.uniforms.uNodeCount.value = nodeCount;

      renderer.render({ scene: mesh });
      rafId = requestAnimationFrame(loop);
    }
    loop(performance.now());

    return () => {
      cancelAnimationFrame(rafId);
      ro.disconnect();
      io.disconnect();
      wrapEl.removeEventListener('pointermove', onMove);
      wrapEl.removeEventListener('pointerleave', onLeave);
      wrapEl.removeEventListener('pointerdown', onDown);
      wrapEl.removeEventListener('pointerup', onUp);
      wrapEl.removeEventListener('pointercancel', onUp);
    };
  });
</script>

<svelte:head>
  <title>Sandbox · Hero pulsar</title>
  <meta name="robots" content="noindex, nofollow" />
</svelte:head>

<div class="page">
  <header class="bar">
    <h1>Sandbox · Hero pulsar</h1>
    <p>Prototype WebGL (OGL). Pas indexé. Modifiez les curseurs pour explorer le rendu.</p>
  </header>

  <div class="layout">
    <div class="stage" bind:this={wrapEl}>
      <canvas bind:this={canvasEl}></canvas>
    </div>

    <aside class="panel">
      <label>
        <span>Bloom <em>{bloomStrength.toFixed(2)}</em></span>
        <input type="range" min="0" max="2" step="0.02" bind:value={bloomStrength} />
      </label>
      <label>
        <span>Vitesse pulsation <em>{pulseSpeed.toFixed(2)}</em></span>
        <input type="range" min="0" max="1.5" step="0.02" bind:value={pulseSpeed} />
      </label>
      <label>
        <span>Vitesse orbite <em>{orbitSpeed.toFixed(2)}</em></span>
        <input type="range" min="0" max="0.6" step="0.01" bind:value={orbitSpeed} />
      </label>
      <label>
        <span>Nombre de nœuds <em>{nodeCount}</em></span>
        <input type="range" min="3" max="8" step="1" bind:value={nodeCount} />
      </label>
      <label>
        <span>Ellipticité <em>{orbitMix.toFixed(2)}</em></span>
        <input type="range" min="0" max="1" step="0.02" bind:value={orbitMix} />
      </label>
      <label>
        <span>Teinte cœur <em>{coreHue.toFixed(2)}</em></span>
        <input type="range" min="0" max="1" step="0.01" bind:value={coreHue} />
      </label>
      <label>
        <span>Étendue nœuds <em>{nodeSpread.toFixed(2)}</em></span>
        <input type="range" min="0.5" max="1.5" step="0.02" bind:value={nodeSpread} />
      </label>
      <p class="hint">
        Bougez la souris sur le canvas pour interagir.<br />
        Une fois la version validée, on l'extrait en composant et on remplace le hero.
      </p>
    </aside>
  </div>
</div>

<style>
  .page {
    min-height: 100vh;
    background: #050508;
    color: #e5e7eb;
    padding: 1.5rem;
    font-family: 'Inter', system-ui, sans-serif;
  }
  .bar h1 {
    font-size: 1.25rem;
    font-weight: 500;
    margin: 0 0 0.25rem;
  }
  .bar p {
    font-size: 0.85rem;
    color: #94a3b8;
    margin: 0 0 1.25rem;
  }
  .layout {
    display: grid;
    grid-template-columns: 1fr 280px;
    gap: 1rem;
    max-width: 1400px;
    margin: 0 auto;
  }
  .stage {
    aspect-ratio: 4 / 3;
    width: 100%;
    border-radius: 14px;
    overflow: hidden;
    background: #030307;
    position: relative;
    cursor: crosshair;
  }
  .stage canvas {
    display: block;
    width: 100%;
    height: 100%;
  }
  .panel {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.85rem;
  }
  .panel label {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    font-size: 0.8rem;
    color: #cbd5e1;
  }
  .panel label span {
    display: flex;
    justify-content: space-between;
  }
  .panel label em {
    font-style: normal;
    color: #94a3b8;
    font-variant-numeric: tabular-nums;
  }
  .panel input[type='range'] {
    width: 100%;
    accent-color: #6b8aff;
  }
  .hint {
    font-size: 0.75rem;
    color: #64748b;
    line-height: 1.5;
    margin-top: 0.5rem;
  }
  @media (max-width: 800px) {
    .layout {
      grid-template-columns: 1fr;
    }
  }
</style>
