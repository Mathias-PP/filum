<script lang="ts">
  // Hero pulsar — WebGL render (OGL) with SVG fallback for LCP and a11y.
  //
  // Design contract:
  // - The SVG fallback renders synchronously on first paint so LCP is preserved.
  // - The WebGL module is lazy-loaded (dynamic import) on mount.
  // - IntersectionObserver pauses the RAF loop when the canvas is off-screen.
  // - prefers-reduced-motion → never load WebGL; stay on the SVG fallback.
  // - DPR is capped at 2 to keep mobile GPU usage bounded.
  // - Canvas itself is fully transparent at edges (premultiplied alpha) so the
  //   host hero section background bleeds through; no visible rectangle.
  //
  // All constants below were tuned in the sandbox at `/sandbox/hero`. No live
  // tuning in prod. See ADR-024.

  import { onMount } from 'svelte';

  let canvasEl: HTMLCanvasElement | undefined = $state();
  let wrapEl: HTMLDivElement | undefined = $state();
  let webglReady = $state(false);

  // Tuned defaults — validated in the sandbox.
  const BLOOM_STRENGTH = 0.3;
  const PULSE_SPEED = 0.25;
  const ORBIT_SPEED = 0.12;
  const NODE_COUNT = 7;
  const ORBIT_MIX = 0.55;
  const CORE_HUE = 0.58;
  const NODE_SPREAD = 1.0;
  // Pulsar disk radius in NDC. Doit rester aligné avec la constante `coreR`
  // hardcodée dans le fragment shader.
  const CORE_R = 0.143;
  // Scale ×1.3 du graphe (orbites + rayons nœuds).
  const G_SCALE = 1.3;

  // Trail ring buffer
  const TRAIL_HISTORY = 6;
  const TRAIL_DT = 0.08;

  // Identité des deux twins du Y-fork (par colorIdx).
  const FORK_TWIN_A_COLOR_IDX = 3;
  const FORK_TWIN_B_COLOR_IDX = 4;

  // Palette tunée — chroma poussée, jamais fluo. Inspiration data-viz 2026
  // (Linear / Vercel / OpenAI) : couleurs matérielles, contours nets.
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

  const LIGHT_DIR = (() => {
    const v = [-0.55, 0.6, 0.58];
    const m = Math.hypot(v[0], v[1], v[2]);
    return [v[0] / m, v[1] / m, v[2] / m];
  })();

  // VIRTUAL FORK BASE — point M qui orbite le pulsar mais n'est jamais rendu
  // comme nœud. L'axe pulsar↔M sert d'axe de rotation pour les deux twins.
  const VIRTUAL_FORK = {
    baseAngle: 1.3,
    orbitRx: 0.46 * G_SCALE,
    orbitRy: 0.34 * G_SCALE,
    orbitRz: 0.24 * G_SCALE,
    tilt: 0.7,
    speed: 0.95,
    // Distance M ↔ twin
    branchLen: 0.2,
    // Demi-angle d'ouverture du Y : 35° → angle TOTAL = 70°, jamais droit.
    branchAngleRad: (35 * Math.PI) / 180,
    // Vitesse de rotation du plan des branches autour de l'axe pulsar↔M
    twinSpinSpeed: 2.2,
  };

  const vert = /* glsl */ `
    attribute vec2 position;
    varying vec2 vUv;
    void main() {
      vUv = position * 0.5 + 0.5;
      gl_Position = vec4(position, 0.0, 1.0);
    }
  `;

  const frag = /* glsl */ `
    precision highp float;
    varying vec2 vUv;
    uniform vec2 uAaPixel;
    uniform vec2 uResolution;
    uniform float uTime;
    uniform vec2 uMouse;
    uniform float uBloom;
    uniform float uPulseSpeed;
    uniform float uCoreHue;
    uniform int uNodeCount;
    uniform vec4 uNodes[8];        // (x, y, z, radius)
    uniform vec3 uNodeColors[8];
    uniform vec3 uLightDir;
    uniform float uHoverNode[8];
    uniform float uHoverCore;
    // Trails orbitaux : 8 nœuds × 6 history points = 48 entries (ordre natif).
    uniform vec4 uTrails[48];
    uniform vec3 uTrailColors[8];
    // Identité (colorIdx) du nœud occupant chaque slot trié — sert à dériver
    // biome et seed de manière STABLE indépendamment du tri back-to-front.
    uniform float uNodeIdx[8];
    // Ancre par slot trié : (x, y, z, r). Z permet le test d'occlusion 3D
    // ligne ↔ pulsar.
    uniform vec4 uAnchors[8];
    // Y-fork trunk : (Mx, My, Mz, active). active=0 → désactivé.
    uniform vec4 uForkTrunk;
    uniform vec3 uForkTrunkColor;

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

    // Sphère matérielle : biome procédural discret (gas-giant / rocky / marbré
    // / icy), terminator courbe, rim atmo fin, rotation propre Earth-like
    // très lente.
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

      vec2 sp = n.xy + vec2(seed, seed * 0.7);
      float spinSpeed = 0.03 * (0.7 + 0.6 * fract(seed * 7.31));
      vec2 rsp = sp + vec2(uTime * spinSpeed, 0.0);

      float pattern = 0.5;
      if (biome < 0.5) {
        float warp = fbm(rsp * 3.2) - 0.5;
        float bands = sin((rsp.y + warp * 0.55) * 6.0);
        bands = sign(bands) * pow(abs(bands), 0.85);
        pattern = bands * 0.5 + 0.5;
      } else if (biome < 1.5) {
        float h = fbm(rsp * 4.0);
        pattern = smoothstep(0.40, 0.56, h);
      } else if (biome < 2.5) {
        float warp = fbm(rsp * 2.0);
        vec2 q = rsp * 3.5 + vec2(warp * 2.2, fbm(rsp * 2.3) * 2.0);
        float v = fbm(q);
        pattern = smoothstep(0.28, 0.72, v);
      } else {
        float v = fbm(rsp * 6.5);
        pattern = 1.0 - smoothstep(0.40, 0.50, abs(v - 0.5));
      }

      vec3 darkCol  = baseCol * 0.92;
      vec3 lightCol = mix(baseCol, vec3(1.0), 0.05);
      vec3 surfaceCol = mix(darkCol, lightCol, pattern);

      vec3 L = normalize(vec3(lightFrom2D.x, lightFrom2D.y, 0.35));
      float lam = max(dot(n, L), 0.0);
      float diffuseAmt = mix(0.18, 1.15, smoothstep(0.0, 0.65, lam));

      vec3 viewDir = vec3(0.0, 0.0, 1.0);
      vec3 hVec = normalize(L + viewDir);
      float specPow = mix(32.0, 70.0, pattern);
      float spec = pow(max(dot(n, hVec), 0.0), specPow) * mix(0.25, 0.55, pattern);
      vec3 specCol = mix(baseCol, vec3(1.0), 0.80) * spec;

      float fres = pow(1.0 - zLocal, 3.0);
      vec3 atmoRim = mix(baseCol, vec3(1.0), 0.20) * fres * 1.25;

      vec3 nightSide = surfaceCol * 0.18 * (1.0 - lam);

      vec3 col = surfaceCol * diffuseAmt + specCol + atmoRim + nightSide;
      return vec4(col, alpha);
    }

    void main() {
      vec2 uv = (vUv - 0.5) * 2.0;
      uv.x *= uResolution.x / uResolution.y;

      vec3 col = vec3(0.0);

      // -- BACKGROUND : cosmic web filaments + dust lanes --------------------
      vec2 driftA = vec2(uTime * 0.0025, uTime * 0.0009);
      vec2 driftB = vec2(uTime * -0.0018, uTime * 0.0013);

      col = vec3(0.004, 0.005, 0.010);

      vec2 matUv = uv * 1.2 + driftA;
      float m1 = fbm(matUv);
      float m2 = fbm(matUv * 2.3 + vec2(5.0));
      float ridge1 = 1.0 - abs(m1 - 0.5) * 2.0;
      float ridge2 = 1.0 - abs(m2 - 0.5) * 2.0;
      float webBase = pow(ridge1, 2.5) * 0.4 + pow(ridge2, 3.0) * 0.2;
      float density = fbm(uv * 0.5 + driftB);

      vec3 cool = vec3(0.006, 0.009, 0.022);
      vec3 lit  = vec3(0.014, 0.022, 0.052);
      vec3 matrix = mix(cool, lit, smoothstep(0.35, 0.85, webBase));
      matrix *= 0.50 + 0.50 * density;
      col += matrix;

      vec2 dustUv = uv * vec2(1.4, 0.9) + vec2(2.0, -1.5) + driftB;
      float dustField = fbm(dustUv);
      float dustField2 = fbm(dustUv * 2.5 + vec2(7.0));
      float dustRidge = 1.0 - abs(dustField - 0.5) * 2.0;
      dustRidge *= 0.6 + 0.4 * dustField2;
      float dustMask = smoothstep(0.72, 0.95, dustRidge);
      col *= 1.0 - dustMask * 0.20;

      // -- STARFIELD : 3 layers -----------------------------------------------
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
      {
        vec2 g = uv * 35.0;
        vec2 id = floor(g);
        vec2 fp = fract(g) - 0.5;
        float h = hash(id);
        if (h > 0.978) {
          float d = length(fp);
          float size = mix(0.025, 0.06, hash(id + 0.5));
          float twinkle = 0.65 + 0.35 * sin(uTime * 0.7 + h * 100.0);
          float ct = hash(id + 1.7);
          vec3 starCol = mix(vec3(0.7, 0.8, 1.0), vec3(1.0, 0.85, 0.65), ct);
          col += starCol * smoothstep(size, 0.0, d) * twinkle * 0.65;
        }
      }
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
          float core = smoothstep(0.05, 0.0, d);
          float sx = exp(-abs(fp.x) * 50.0) * exp(-abs(fp.y) * 250.0);
          float sy = exp(-abs(fp.y) * 50.0) * exp(-abs(fp.x) * 250.0);
          float spikes = (sx + sy) * 0.45;
          col += starCol * (core + spikes) * twinkle * 0.9;
        }
      }

      // -- TRAILS ORBITAUX : sillage de chaque nœud --------------------------
      for (int i = 0; i < 8; i++) {
        float active = step(float(i) + 0.5, float(uNodeCount));
        if (active < 0.5) continue;
        vec3 trailCol = uTrailColors[i];
        for (int j = 0; j < 6; j++) {
          vec4 t = uTrails[i * 6 + j];
          float age = float(j) / 5.0;
          float ageFade = exp(-age * 2.4);
          float depthDim = 0.55 + 0.45 * clamp(t.w / 0.35 + 0.5, 0.0, 1.0);
          vec2 dT = uv - t.xy;
          float dT2 = dot(dT, dT);
          float sigma = mix(0.012, 0.020, age);
          float intensity = exp(-dT2 / (sigma * sigma)) * 0.18 * ageFade * depthDim;
          col += trailCol * intensity;
        }
      }

      // -- PULSAR : halo + corona + chromosphère ------------------------------
      vec2 coreC = uMouse; // uMouse = position pulsar (set by JS)
      float coreR = 0.143;
      float pulse = 0.5 + 0.5 * sin(uTime * uPulseSpeed * 2.0);
      float coreRPulsed = coreR;
      vec3 coreColor = hueShift(uCoreHue);
      vec2 sd = uv - coreC;
      float dCore = length(sd);
      float ang = atan(sd.y, sd.x);
      float haloOut = max(dCore - coreRPulsed * 0.96, 0.0);

      float chrom = exp(-haloOut * 30.0) * 0.95;
      float corona = exp(-haloOut * 8.0) * 0.45;
      float farHalo = exp(-dCore * 2.5) * 0.35;
      vec3 haloColor = mix(coreColor, vec3(1.0), 0.30);
      col += haloColor * (chrom + corona) * (0.95 + 0.10 * pulse);
      col += coreColor * farHalo * (0.85 + 0.15 * pulse);

      float spikeH = exp(-pow(abs(sd.y) * 160.0, 1.4)) * exp(-abs(sd.x) * 9.0);
      float spikeV = exp(-pow(abs(sd.x) * 160.0, 1.4)) * exp(-abs(sd.y) * 9.0);
      float spike = (spikeH + spikeV) * (0.90 + 0.15 * pulse);
      col += mix(coreColor, vec3(1.0), 0.45) * spike * 0.20;

      // Anneau chromosphérique fin (toujours centré, pas de noise)
      float chromoBreath = 1.0 + 0.04 * sin(uTime * 0.6);
      float chromoFalloff = exp(-haloOut * 65.0 * chromoBreath);
      float chromoMask = chromoFalloff * step(coreRPulsed * 0.985, dCore);
      vec3 chromoCol = vec3(1.00, 0.55, 0.50);
      col += chromoCol * chromoMask * 0.55;

      // -- CONNEXIONS PASSE 1 : nœud↔ancre (dessinées AVANT le pulsar) -------
      for (int i = 0; i < 8; i++) {
        float active = step(float(i) + 0.5, float(uNodeCount));
        vec4 n = uNodes[i];
        vec2 a = n.xy;
        vec3 anc3 = uAnchors[i].xyz;
        vec2 anc = anc3.xy;
        float ancZ = anc3.z;
        float ancR = uAnchors[i].w;
        vec2 d = anc - a;
        float lineLen = max(length(d), 0.001);
        vec2 dir = d / lineLen;
        vec2 rel = uv - a;
        float along = dot(rel, dir);
        float across = length(rel - dir * along);
        float onSeg = step(n.w * 1.02, along) * step(along, lineLen - ancR * 1.00);
        float aa = uAaPixel.x * 1.1;
        float lineMask = (1.0 - smoothstep(0.0022 - aa, 0.0022 + aa, across)) * onSeg;
        float tNorm = along / lineLen;
        // Endpoint taper → joint Y-fork invisible (3 hazes additives ne forment
        // pas de halo).
        float endTaper = smoothstep(0.0, 0.08, tNorm) * (1.0 - smoothstep(0.85, 1.0, tNorm));
        float lineHaze = exp(-across * 220.0) * onSeg * 0.35 * endTaper;
        float depthFade = 0.55 + 0.45 * clamp(n.z / 0.35 + 0.5, 0.0, 1.0);
        // Y-fork twin : gradient de couleur node→trunk → joint invisible.
        bool isYforkTwin = uAnchors[i].w < 0.001 && uForkTrunk.w > 0.5;
        vec3 nodeBaseCol = mix(uNodeColors[i], vec3(1.0), 0.15);
        vec3 trunkBaseCol = mix(uForkTrunkColor, vec3(1.0), 0.20);
        vec3 lineColor = isYforkTwin
          ? mix(nodeBaseCol, trunkBaseCol, smoothstep(0.15, 1.0, tNorm))
          : nodeBaseCol;
        col += lineColor * (lineMask * 0.45 + lineHaze * 0.7) * depthFade * active;

        // Data pulse : comète qui glisse du nœud vers son ancre.
        float lt = fract(uTime * 0.25 + float(i) * 0.137);
        float env = smoothstep(0.0, 0.15, lt) * (1.0 - smoothstep(0.85, 1.0, lt));
        float pulsePos = lt * (lineLen - n.w - ancR) + n.w;
        float pulseDist = along - pulsePos;
        float head = exp(-pulseDist * pulseDist * 6000.0);
        float tail = exp(pulseDist * 40.0) * step(pulseDist, 0.0) * 0.45;
        float lateral = exp(-across * across * 80000.0);
        float dataPulse = (head + tail) * lateral * onSeg * env;
        col += mix(uNodeColors[i], vec3(1.0), 0.50) * dataPulse * 1.3 * depthFade * active;
      }

      // -- Y-FORK TRUNK : tige du Y reliant M au pulsar ----------------------
      if (uForkTrunk.w > 0.5) {
        vec2 mPoint = uForkTrunk.xy;
        float mZ = uForkTrunk.z;
        float pR = coreR;
        vec2 d = coreC - mPoint;
        float lineLen = max(length(d), 0.001);
        vec2 dir = d / lineLen;
        vec2 rel = uv - mPoint;
        float along = dot(rel, dir);
        float across = length(rel - dir * along);
        float onSeg = step(0.0, along) * step(along, lineLen - pR * 1.00);
        float aa = uAaPixel.x * 1.1;
        float lineMask = (1.0 - smoothstep(0.0024 - aa, 0.0024 + aa, across)) * onSeg;
        float tNorm = along / lineLen;
        float endTaper = smoothstep(0.0, 0.08, tNorm) * (1.0 - smoothstep(0.95, 1.0, tNorm));
        float lineHaze = exp(-across * 200.0) * onSeg * 0.30 * endTaper;
        vec3 trunkColor = mix(uForkTrunkColor, vec3(1.0), 0.20);
        col += trunkColor * (lineMask * 0.50 + lineHaze * 0.7);

        float lt = fract(uTime * 0.25 + 0.5);
        float env = smoothstep(0.0, 0.15, lt) * (1.0 - smoothstep(0.85, 1.0, lt));
        float pulsePos = lt * (lineLen - pR);
        float pulseDist = along - pulsePos;
        float head = exp(-pulseDist * pulseDist * 6000.0);
        float tail = exp(pulseDist * 40.0) * step(pulseDist, 0.0) * 0.45;
        float lateral = exp(-across * across * 80000.0);
        float dataPulse = (head + tail) * lateral * onSeg * env;
        col += mix(uForkTrunkColor, vec3(1.0), 0.50) * dataPulse * 1.2;
      }

      // -- PULSAR SPHERE : naine bleue-blanche --------------------------------
      {
        vec2 d = uv - coreC;
        float r2 = coreRPulsed * coreRPulsed;
        float d2 = dot(d, d);
        float dist = sqrt(d2);
        float aa = uAaPixel.x * 0.9;
        float alpha = 1.0 - smoothstep(coreRPulsed - aa, coreRPulsed + aa, dist);
        if (alpha > 0.0) {
          float zSq = max(r2 - d2, 0.0);
          float zN = sqrt(zSq) / coreRPulsed;
          vec2 sp = d / coreRPulsed;

          vec3 photoRim    = vec3(0.50, 0.85, 1.50);
          vec3 photoMid    = vec3(1.05, 1.45, 2.05);
          vec3 photoCenter = vec3(1.90, 2.10, 2.50);
          photoRim    = mix(photoRim,    coreColor * 1.5, 0.18);
          photoMid    = mix(photoMid,    coreColor * 1.7, 0.15);
          photoCenter = mix(photoCenter, coreColor * 2.0, 0.10);

          vec3 starSurface = mix(photoRim, photoMid, smoothstep(0.0, 0.55, zN));
          starSurface     = mix(starSurface, photoCenter, smoothstep(0.55, 0.95, zN));

          float limb = 0.70 + 0.30 * pow(zN, 0.42);

          float granul = fbm(sp * 24.0 + uTime * 0.02);
          starSurface *= 0.97 + 0.06 * (granul - 0.5);

          float hotspot = pow(zN, 8.0) * 0.45;
          starSurface += mix(coreColor, vec3(0.95, 0.97, 1.0), 0.40) * hotspot;

          float scint = 0.97 + 0.06 * sin(uTime * 3.1 + fbm(sp * 6.0) * 8.0);
          starSurface *= scint;

          starSurface *= 0.97 + 0.04 * pulse;

          col = mix(col, starSurface * limb, alpha);
        }
      }

      // -- CONNEXIONS PASSE 2 : portions de lignes DEVANT le pulsar ----------
      // Pour chaque pixel à l'intérieur du disque pulsar, on calcule la z 3D
      // de la ligne en ce point (interp node.z → anchor.z) et on la compare à
      // la z frontale du pulsar. Si la ligne est devant → redessinée par-dessus.
      {
        vec2 dCoreL = uv - coreC;
        float dCore2L = dot(dCoreL, dCoreL);
        float coreR2 = coreRPulsed * coreRPulsed;
        if (dCore2L < coreR2) {
          float pulsarFrontZ = sqrt(coreR2 - dCore2L);
          for (int i = 0; i < 8; i++) {
            float active = step(float(i) + 0.5, float(uNodeCount));
            if (active < 0.5) continue;
            vec4 n = uNodes[i];
            vec3 anc3 = uAnchors[i].xyz;
            vec2 anc = anc3.xy;
            float ancZ = anc3.z;
            float ancR = uAnchors[i].w;
            vec2 d = anc - n.xy;
            float lineLen = max(length(d), 0.001);
            vec2 dir = d / lineLen;
            vec2 rel = uv - n.xy;
            float along = dot(rel, dir);
            float across = length(rel - dir * along);
            float onSeg = step(n.w * 1.02, along) * step(along, lineLen - ancR * 1.00);
            if (onSeg < 0.5) continue;
            float tParam = clamp(along / lineLen, 0.0, 1.0);
            float lineZ = mix(n.z, ancZ, tParam);
            if (lineZ <= pulsarFrontZ) continue;
            float aaL = uAaPixel.x * 1.1;
            float lineMaskL = (1.0 - smoothstep(0.0022 - aaL, 0.0022 + aaL, across)) * onSeg;
            float tNormL = along / lineLen;
            float endTaperL = smoothstep(0.0, 0.08, tNormL) * (1.0 - smoothstep(0.85, 1.0, tNormL));
            float lineHazeL = exp(-across * 220.0) * onSeg * 0.35 * endTaperL;
            float depthFadeL = 0.55 + 0.45 * clamp(n.z / 0.35 + 0.5, 0.0, 1.0);
            bool isYforkTwinL = uAnchors[i].w < 0.001 && uForkTrunk.w > 0.5;
            vec3 nodeBaseColL = mix(uNodeColors[i], vec3(1.0), 0.15);
            vec3 trunkBaseColL = mix(uForkTrunkColor, vec3(1.0), 0.20);
            vec3 lineColorL = isYforkTwinL
              ? mix(nodeBaseColL, trunkBaseColL, smoothstep(0.15, 1.0, tNormL))
              : nodeBaseColL;
            col += lineColorL * (lineMaskL * 0.45 + lineHazeL * 0.7) * depthFadeL;
          }
          if (uForkTrunk.w > 0.5) {
            vec2 mPt = uForkTrunk.xy;
            float mZT = uForkTrunk.z;
            vec2 dT = coreC - mPt;
            float lineLenT = max(length(dT), 0.001);
            vec2 dirT = dT / lineLenT;
            vec2 relT = uv - mPt;
            float alongT = dot(relT, dirT);
            float acrossT = length(relT - dirT * alongT);
            float onSegT = step(0.0, alongT) * step(alongT, lineLenT - coreR * 1.00);
            if (onSegT >= 0.5) {
              float tT = clamp(alongT / lineLenT, 0.0, 1.0);
              float trunkZ = mix(mZT, 0.0, tT);
              if (trunkZ > pulsarFrontZ) {
                float aaT = uAaPixel.x * 1.1;
                float lineMaskT = (1.0 - smoothstep(0.0024 - aaT, 0.0024 + aaT, acrossT)) * onSegT;
                float tNormT = alongT / lineLenT;
                float endTaperT = smoothstep(0.0, 0.08, tNormT) * (1.0 - smoothstep(0.95, 1.0, tNormT));
                float lineHazeT = exp(-acrossT * 200.0) * onSegT * 0.30 * endTaperT;
                vec3 trunkColorT = mix(uForkTrunkColor, vec3(1.0), 0.20);
                col += trunkColorT * (lineMaskT * 0.50 + lineHazeT * 0.7);
              }
            }
          }
        }
      }

      // -- NODES (already depth-sorted back-to-front in JS) ------------------
      for (int i = 0; i < 8; i++) {
        float active = step(float(i) + 0.5, float(uNodeCount));
        vec4 n = uNodes[i];
        vec3 nodeColor = uNodeColors[i];
        float depthBright = 0.75 + 0.25 * clamp(n.z / 0.35 + 0.5, 0.0, 1.0);

        float hover = uHoverNode[i];
        float nodeR = n.w;

        float dPixelToCore = length(uv - coreC);
        float aaCore = uAaPixel.x * 1.4;
        float pulsarCoverage = 1.0 - smoothstep(coreRPulsed - aaCore, coreRPulsed + aaCore, dPixelToCore);
        float behindMix = smoothstep(coreRPulsed * 0.05, -coreRPulsed * 0.05, n.z);
        float occlude = pulsarCoverage * behindMix;
        float mask = active;

        vec2 toCore = coreC - n.xy;
        vec2 lightDir2D = normalize(toCore + vec2(0.0001));
        float biome = mod(uNodeIdx[i], 4.0);
        float seed = uNodeIdx[i] * 13.37;
        vec4 sh = nodeSphere(uv, n.xy, nodeR, nodeColor, lightDir2D, biome, seed);
        vec3 lit = sh.rgb * (depthBright + 0.40 * hover);

        float dN = length(uv - n.xy);
        float glowOut = max(dN - nodeR * 0.95, 0.0);
        float glowBoost = 1.0 + 1.30 * hover;
        float glowRim  = exp(-glowOut * 32.0) * 0.62 * glowBoost;
        float glowWide = exp(-glowOut * 10.0) * 0.28 * glowBoost;
        col += nodeColor * (glowRim + glowWide) * depthBright * mask * (1.0 - occlude);

        col = mix(col, lit, sh.a * mask * (1.0 - occlude));
      }

      // -- Bloom + tonemap + edge alpha (transparent at the edges) -----------
      vec3 bloomBoost = pow(max(col - 0.78, 0.0), vec3(1.7)) * uBloom * 0.30;
      col += bloomBoost;

      col = col / (1.0 + col);
      col = pow(col, vec3(0.88));

      float radialVig = smoothstep(1.7, 0.6, length(uv));
      col *= 0.55 + 0.45 * radialVig;
      vec2 edge = abs(vUv - 0.5) * 2.0;
      float edgeDist = max(edge.x, edge.y);
      // Wide dissolve : inner ~45 % fully opaque, alpha decays continuously
      // across the outer 55 %. Premultiplied alpha to avoid fringing.
      float alpha = 1.0 - smoothstep(0.45, 1.05, edgeDist);
      gl_FragColor = vec4(col * alpha, alpha);
    }
  `;

  onMount(() => {
    if (!canvasEl || !wrapEl) return;

    // Respect reduced-motion: never load WebGL, stay on the SVG fallback.
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      return;
    }

    let cancelled = false;
    let dispose: (() => void) | undefined;

    // Lazy import OGL — keeps the chunk off the initial bundle of every other route.
    import('ogl')
      .then(({ Renderer, Program, Mesh, Triangle, Vec2, Vec3 }) => {
        if (cancelled || !canvasEl || !wrapEl) return;

        const renderer = new Renderer({
          canvas: canvasEl,
          dpr: Math.min(window.devicePixelRatio, 2),
          alpha: true,
          premultipliedAlpha: true,
          antialias: true,
        });
        const gl = renderer.gl;
        gl.clearColor(0, 0, 0, 0);

        const geometry = new Triangle(gl);

        // OGL detects array uniforms via Array.isArray() — plain Array required.
        const nodesArr: number[][] = Array.from({ length: 8 }, () => [0, 0, 0, 0.05]);
        const colorsArr: number[][] = Array.from({ length: 8 }, (_, i) => {
          const c = NODE_COLORS[i % NODE_COLORS.length];
          return [c[0], c[1], c[2]];
        });
        const trailsArr: number[][] = Array.from({ length: 8 * TRAIL_HISTORY }, () => [0, 0, 0, 0]);
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
            uBloom: { value: BLOOM_STRENGTH },
            uPulseSpeed: { value: PULSE_SPEED },
            uCoreHue: { value: CORE_HUE },
            uNodeCount: { value: NODE_COUNT },
            uNodes: { value: nodesArr },
            uNodeColors: { value: colorsArr },
            uLightDir: { value: new Vec3(LIGHT_DIR[0], LIGHT_DIR[1], LIGHT_DIR[2]) },
            uHoverNode: { value: Array.from({ length: 8 }, () => 0) },
            uHoverCore: { value: 0 },
            uTrails: { value: trailsArr },
            uTrailColors: { value: trailColorsArr },
            uNodeIdx: { value: Array.from({ length: 8 }, () => 0) },
            uAnchors: {
              value: Array.from({ length: 8 }, () => [0, 0, 0, CORE_R] as number[]),
            },
            uForkTrunk: { value: [0, 0, 0, 0] as number[] },
            uForkTrunkColor: {
              value: new Vec3(
                (NODE_COLORS[FORK_TWIN_A_COLOR_IDX][0] + NODE_COLORS[FORK_TWIN_B_COLOR_IDX][0]) *
                  0.5,
                (NODE_COLORS[FORK_TWIN_A_COLOR_IDX][1] + NODE_COLORS[FORK_TWIN_B_COLOR_IDX][1]) *
                  0.5,
                (NODE_COLORS[FORK_TWIN_A_COLOR_IDX][2] + NODE_COLORS[FORK_TWIN_B_COLOR_IDX][2]) *
                  0.5
              ),
            },
          },
        });

        const mesh = new Mesh(gl, { geometry, program });

        function resize() {
          if (!wrapEl) return;
          const rect = wrapEl.getBoundingClientRect();
          renderer.setSize(rect.width, rect.height);
          program.uniforms.uResolution.value.set(rect.width, rect.height);
          const aa = 2 / Math.max(rect.height, 1);
          program.uniforms.uAaPixel.value.set(aa, aa);
        }
        resize();
        const ro = new ResizeObserver(resize);
        ro.observe(wrapEl);

        const targetMouse = new Vec2(0, 0);
        const currentMouse = new Vec2(0, 0);
        let draggingNodeKey = -1;
        let draggingCore = false;
        const coreDisp = { x: 0, y: 0 };

        function onMove(e: PointerEvent) {
          if (!wrapEl) return;
          const rect = wrapEl.getBoundingClientRect();
          const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
          const y = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
          const aspect = rect.width / rect.height;
          targetMouse.set(x * aspect, y);
        }
        function onLeave() {
          targetMouse.set(0, 0);
          draggingNodeKey = -1;
          draggingCore = false;
        }
        function onDown(e: PointerEvent) {
          let pickKey = -1;
          let bestD = Infinity;
          for (let i = 0; i < NODE_COUNT; i++) {
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
            wrapEl?.setPointerCapture?.(e.pointerId);
            return;
          }
          const dx = currentMouse.x - coreDisp.x;
          const dy = currentMouse.y - coreDisp.y;
          const coreHitR = CORE_R * 1.2;
          if (dx * dx + dy * dy < coreHitR * coreHitR) {
            draggingCore = true;
            wrapEl?.setPointerCapture?.(e.pointerId);
          }
        }
        function onUp(e: PointerEvent) {
          draggingNodeKey = -1;
          draggingCore = false;
          wrapEl?.releasePointerCapture?.(e.pointerId);
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

        // -- NODES config : régulier / parent / moon / forkTwin ---------------
        type NodeRole = 'regular' | 'parent' | 'moon' | 'forkTwin';
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
          parentColorIdx: number;
          localOrbitR: number;
          localSpeed: number;
          localPhase: number;
          twinSide: number;
        };

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
              return { ...orbital, role: 'forkTwin', twinSide: 1 };
            case 4:
              return { ...orbital, role: 'forkTwin', twinSide: -1 };
            case 5:
              return {
                ...orbital,
                role: 'moon',
                parentColorIdx: 1,
                radius: baseRadius * 0.55,
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
          anchorX: number;
          anchorY: number;
          anchorZ: number;
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
          anchorZ: 0,
          anchorR: CORE_R,
        }));
        const displacement = Array.from({ length: 8 }, () => ({ x: 0, y: 0 }));
        const hoverTarget = new Array(8).fill(0) as number[];
        const hoverCurrent = program.uniforms.uHoverNode.value as number[];
        let hoverCoreTarget = 0;

        const start = performance.now();
        let lastTrailSample = -Infinity;

        function loop(t: number) {
          rafId = 0;
          if (!visible) return;
          currentMouse.x += (targetMouse.x - currentMouse.x) * 0.1;
          currentMouse.y += (targetMouse.y - currentMouse.y) * 0.1;
          const time = (t - start) / 1000;

          // PASSE A : orbites simples autour du pulsar
          for (let i = 0; i < NODE_COUNT; i++) {
            const p = NODES[i];
            const a = p.baseAngle + time * ORBIT_SPEED * p.speed;
            const lx = Math.cos(a) * p.orbitRx * NODE_SPREAD;
            const ly0 =
              Math.sin(a) *
              (p.orbitRy * (1 - 0.4 * ORBIT_MIX) + p.orbitRx * 0.4 * ORBIT_MIX) *
              NODE_SPREAD;
            const lz0 = Math.sin(a + p.tilt * 0.7) * p.orbitRz * NODE_SPREAD;
            const cs = Math.cos(p.tilt);
            const sn = Math.sin(p.tilt);
            const ly = ly0 * cs - lz0 * sn;
            const lz = ly0 * sn + lz0 * cs;
            const isDragging =
              p.colorIdx === draggingNodeKey && p.role !== 'moon' && p.role !== 'forkTwin';
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
            computed[i].anchorX = coreDisp.x;
            computed[i].anchorY = coreDisp.y;
            computed[i].anchorZ = 0;
            computed[i].anchorR = CORE_R;
          }

          // PASSE B : override moon (orbite locale) + Y-fork (axe pulsar↔M)
          const findByColorIdx = (cidx: number): number => {
            for (let k = 0; k < NODE_COUNT; k++) if (NODES[k].colorIdx === cidx) return k;
            return -1;
          };
          for (let i = 0; i < NODE_COUNT; i++) {
            const p = NODES[i];
            if (p.role !== 'moon') continue;
            const pIdx = findByColorIdx(p.parentColorIdx);
            if (pIdx === -1) continue;
            const pNode = computed[pIdx];
            const la = p.localPhase + time * ORBIT_SPEED * p.localSpeed;
            const mx = Math.cos(la) * p.localOrbitR;
            const my = Math.sin(la) * p.localOrbitR * 0.6;
            const mz = Math.sin(la + 0.6) * p.localOrbitR * 0.35;
            computed[i].x = pNode.x + mx;
            computed[i].y = pNode.y + my;
            computed[i].z = pNode.z + mz;
            computed[i].anchorX = pNode.x;
            computed[i].anchorY = pNode.y;
            computed[i].anchorZ = pNode.z;
            computed[i].anchorR = pNode.r;
          }

          const twinAidx = findByColorIdx(FORK_TWIN_A_COLOR_IDX);
          const twinBidx = findByColorIdx(FORK_TWIN_B_COLOR_IDX);
          let forkActive = 0;
          let forkMx = 0;
          let forkMy = 0;
          let forkMz = 0;
          if (
            twinAidx !== -1 &&
            twinBidx !== -1 &&
            twinAidx < NODE_COUNT &&
            twinBidx < NODE_COUNT
          ) {
            const aP = VIRTUAL_FORK.baseAngle + time * ORBIT_SPEED * VIRTUAL_FORK.speed;
            const lxP = Math.cos(aP) * VIRTUAL_FORK.orbitRx * NODE_SPREAD;
            const lyP0 =
              Math.sin(aP) *
              (VIRTUAL_FORK.orbitRy * (1 - 0.4 * ORBIT_MIX) +
                VIRTUAL_FORK.orbitRx * 0.4 * ORBIT_MIX) *
              NODE_SPREAD;
            const lzP0 =
              Math.sin(aP + VIRTUAL_FORK.tilt * 0.7) * VIRTUAL_FORK.orbitRz * NODE_SPREAD;
            const csP = Math.cos(VIRTUAL_FORK.tilt);
            const snP = Math.sin(VIRTUAL_FORK.tilt);
            const Mx = lxP;
            const My = lyP0 * csP - lzP0 * snP;
            const Mz = lyP0 * snP + lzP0 * csP;
            forkMx = Mx;
            forkMy = My;
            forkMz = Mz;
            forkActive = 1;

            const axDx = Mx - coreDisp.x;
            const axDy = My - coreDisp.y;
            const axDz = Mz;
            const axLen = Math.hypot(axDx, axDy, axDz) || 1;
            const axNx = axDx / axLen;
            const axNy = axDy / axLen;
            const axNz = axDz / axLen;

            const tx = Math.abs(axNy) < 0.9 ? 0 : 1;
            const ty = Math.abs(axNy) < 0.9 ? 1 : 0;
            const tz = 0;
            let p1x = axNy * tz - axNz * ty;
            let p1y = axNz * tx - axNx * tz;
            let p1z = axNx * ty - axNy * tx;
            const p1len = Math.hypot(p1x, p1y, p1z) || 1;
            p1x /= p1len;
            p1y /= p1len;
            p1z /= p1len;
            const p2x = axNy * p1z - axNz * p1y;
            const p2y = axNz * p1x - axNx * p1z;
            const p2z = axNx * p1y - axNy * p1x;

            const spin = time * ORBIT_SPEED * VIRTUAL_FORK.twinSpinSpeed;
            const cS = Math.cos(spin);
            const sS = Math.sin(spin);
            const L = VIRTUAL_FORK.branchLen;
            const distAlong = L * Math.cos(VIRTUAL_FORK.branchAngleRad);
            const distPerp = L * Math.sin(VIRTUAL_FORK.branchAngleRad);
            const perpRotX = cS * p1x + sS * p2x;
            const perpRotY = cS * p1y + sS * p2y;
            const perpRotZ = cS * p1z + sS * p2z;
            const aloX = distAlong * axNx;
            const aloY = distAlong * axNy;
            const aloZ = distAlong * axNz;
            const perX = distPerp * perpRotX;
            const perY = distPerp * perpRotY;
            const perZ = distPerp * perpRotZ;

            computed[twinAidx].x = Mx + aloX + perX;
            computed[twinAidx].y = My + aloY + perY;
            computed[twinAidx].z = Mz + aloZ + perZ;
            computed[twinAidx].anchorX = Mx;
            computed[twinAidx].anchorY = My;
            computed[twinAidx].anchorZ = Mz;
            computed[twinAidx].anchorR = 0.0;

            computed[twinBidx].x = Mx + aloX - perX;
            computed[twinBidx].y = My + aloY - perY;
            computed[twinBidx].z = Mz + aloZ - perZ;
            computed[twinBidx].anchorX = Mx;
            computed[twinBidx].anchorY = My;
            computed[twinBidx].anchorZ = Mz;
            computed[twinBidx].anchorR = 0.0;
          }
          const trunkU = program.uniforms.uForkTrunk.value as number[];
          trunkU[0] = forkMx;
          trunkU[1] = forkMy;
          trunkU[2] = forkMz;
          trunkU[3] = forkActive;

          // Trail sampling : shift le ring buffer toutes les TRAIL_DT secondes.
          if (time - lastTrailSample >= TRAIL_DT) {
            lastTrailSample = time;
            const trails = program.uniforms.uTrails.value as number[][];
            for (let i = 0; i < 8; i++) {
              for (let k = TRAIL_HISTORY - 1; k > 0; k--) {
                const dst = trails[i * TRAIL_HISTORY + k];
                const src = trails[i * TRAIL_HISTORY + k - 1];
                dst[0] = src[0];
                dst[1] = src[1];
                dst[2] = src[2];
                dst[3] = src[3];
              }
              const live = computed[i];
              const head = trails[i * TRAIL_HISTORY + 0];
              head[0] = live.x;
              head[1] = live.y;
              head[2] = live.z;
              head[3] = 0;
            }
          }

          // Sort back-to-front + write uniforms
          const slice = computed.slice(0, NODE_COUNT).sort((a, b) => a.z - b.z);
          const arr = program.uniforms.uNodes.value as number[][];
          const colArr = program.uniforms.uNodeColors.value as number[][];
          const idxArr = program.uniforms.uNodeIdx.value as number[];
          const anchArr = program.uniforms.uAnchors.value as number[][];
          for (let i = 0; i < NODE_COUNT; i++) {
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
            anchArr[i][2] = slice[i].anchorZ;
            anchArr[i][3] = slice[i].anchorR;
          }

          // Hover : pick the front-most node under the cursor.
          let pickIdx = -1;
          for (let i = 0; i < NODE_COUNT; i++) {
            const sNode = slice[i];
            const dx = currentMouse.x - sNode.x;
            const dy = currentMouse.y - sNode.y;
            const r = sNode.r * 1.25;
            if (dx * dx + dy * dy < r * r) pickIdx = i;
          }
          const coreDx = currentMouse.x - coreDisp.x;
          const coreDy = currentMouse.y - coreDisp.y;
          const coreHit =
            pickIdx === -1 && coreDx * coreDx + coreDy * coreDy < CORE_R * CORE_R * 1.5;
          hoverCoreTarget = coreHit ? 1 : 0;
          for (let i = 0; i < 8; i++) hoverTarget[i] = i === pickIdx ? 1 : 0;
          for (let i = 0; i < 8; i++) {
            hoverCurrent[i] += (hoverTarget[i] - hoverCurrent[i]) * 0.18;
          }
          program.uniforms.uHoverCore.value +=
            (hoverCoreTarget - program.uniforms.uHoverCore.value) * 0.18;
          if (wrapEl) {
            const wantPointer = pickIdx !== -1 || coreHit;
            if (wantPointer && wrapEl.style.cursor !== 'pointer') wrapEl.style.cursor = 'pointer';
            else if (!wantPointer && wrapEl.style.cursor !== '') wrapEl.style.cursor = '';
          }

          {
            const tx = draggingCore ? currentMouse.x : 0;
            const ty = draggingCore ? currentMouse.y : 0;
            const ease = draggingCore ? 0.28 : 0.08;
            coreDisp.x += (tx - coreDisp.x) * ease;
            coreDisp.y += (ty - coreDisp.y) * ease;
          }
          program.uniforms.uMouse.value.set(coreDisp.x, coreDisp.y);
          program.uniforms.uTime.value = time;

          renderer.render({ scene: mesh });
          rafId = requestAnimationFrame(loop);
        }

        // First frame — set webglReady so the fallback SVG fades out.
        loop(performance.now());
        webglReady = true;

        dispose = () => {
          cancelAnimationFrame(rafId);
          ro.disconnect();
          io.disconnect();
          wrapEl?.removeEventListener('pointermove', onMove);
          wrapEl?.removeEventListener('pointerleave', onLeave);
          wrapEl?.removeEventListener('pointerdown', onDown);
          wrapEl?.removeEventListener('pointerup', onUp);
          wrapEl?.removeEventListener('pointercancel', onUp);
        };
      })
      .catch(() => {
        // Module failed to load — stay on the SVG fallback silently.
      });

    return () => {
      cancelled = true;
      dispose?.();
    };
  });
</script>

<div class="hero-pulsar" bind:this={wrapEl}>
  <!-- SVG fallback: renders on first paint so LCP isn't blocked by the WebGL
       module download. Fades out once the canvas has its first frame.
       Transparent background — relies on the host's bg to show through. -->
  <svg
    viewBox="0 0 480 420"
    preserveAspectRatio="xMidYMid slice"
    class="fallback"
    class:hidden={webglReady}
    role="img"
    aria-label="Illustration : étoile bleue centrale entourée de planètes en orbite, représentant les sources reliées au nœud central Filum"
  >
    <defs>
      <radialGradient id="hp-halo" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="#6B8AFF" stop-opacity="0.55" />
        <stop offset="55%" stop-color="#4A6CF7" stop-opacity="0.18" />
        <stop offset="100%" stop-color="#4A6CF7" stop-opacity="0" />
      </radialGradient>
      <radialGradient id="hp-core" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="#ffffff" stop-opacity="0.5" />
        <stop offset="60%" stop-color="#B5D4F4" stop-opacity="0.25" />
        <stop offset="100%" stop-color="#4A6CF7" stop-opacity="0" />
      </radialGradient>
    </defs>
    <g fill="#ffffff" opacity="0.6">
      <circle cx="60" cy="50" r="0.8" />
      <circle cx="420" cy="80" r="1" />
      <circle cx="160" cy="120" r="0.6" />
      <circle cx="380" cy="290" r="0.9" />
      <circle cx="80" cy="320" r="0.7" />
      <circle cx="220" cy="380" r="0.8" />
      <circle cx="450" cy="200" r="0.6" />
      <circle cx="40" cy="220" r="0.7" />
      <circle cx="320" cy="40" r="0.8" />
      <circle cx="130" cy="250" r="0.6" />
    </g>
    <circle cx="240" cy="210" r="180" fill="url(#hp-halo)" />
    <circle cx="240" cy="210" r="70" fill="url(#hp-core)" />
    <circle cx="240" cy="210" r="36" fill="#4A6CF7" />
    <g stroke="#ffffff" stroke-opacity="0.18" stroke-width="1.2" stroke-linecap="round">
      <line x1="240" y1="210" x2="100" y2="110" />
      <line x1="240" y1="210" x2="380" y2="110" />
      <line x1="240" y1="210" x2="110" y2="320" />
      <line x1="240" y1="210" x2="230" y2="60" />
      <line x1="240" y1="210" x2="260" y2="370" />
      <line x1="380" y1="110" x2="350" y2="160" />
    </g>
    <circle cx="100" cy="110" r="14" fill="#5985F1" />
    <circle cx="380" cy="110" r="18" fill="#8DC78D" />
    <circle cx="110" cy="320" r="14" fill="#66C4EB" />
    <circle cx="380" cy="320" r="11" fill="#D88D8D" />
    <circle cx="230" cy="60" r="11" fill="#D9B97A" />
    <circle cx="350" cy="160" r="9" fill="#B88DD8" />
    <circle cx="260" cy="370" r="12" fill="#D9B97A" />
  </svg>

  <canvas bind:this={canvasEl} class="canvas" aria-hidden="true"></canvas>
</div>

<style>
  /* Wrapper is fully transparent — width/height/aspect controlled by parent.
     No background, no border: the WebGL canvas fades to transparent at the
     edges (premultiplied alpha) and the host's section background shows
     through, so the visual integrates seamlessly with the page. */
  .hero-pulsar {
    position: relative;
    width: 100%;
    height: 100%;
  }
  .fallback,
  .canvas {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    display: block;
  }
  .fallback {
    transition: opacity 400ms ease;
    opacity: 1;
  }
  .fallback.hidden {
    opacity: 0;
    pointer-events: none;
  }
  /* .canvas cursor is set imperatively in JS ('' or 'pointer') based on hit-test. */
</style>
