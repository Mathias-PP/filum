<script lang="ts">
  import { onMount } from 'svelte';
  import { Renderer, Program, Mesh, Triangle, Vec2, Vec3 } from 'ogl';

  let canvasEl: HTMLCanvasElement;
  let wrapEl: HTMLDivElement;

  // Tunables
  let bloomStrength = $state(0.30);
  let pulseSpeed = $state(0.25);
  let orbitSpeed = $state(0.12);
  let nodeCount = $state(6);
  let orbitMix = $state(0.55);
  let coreHue = $state(0.58);
  let nodeSpread = $state(1.0);

  const NODE_COLORS: [number, number, number][] = [
    [0.75, 0.87, 0.59],
    [0.71, 0.83, 0.96],
    [0.98, 0.78, 0.46],
    [0.65, 0.91, 0.85],
    [0.81, 0.80, 0.96],
    [0.99, 0.90, 0.54],
    [0.95, 0.65, 0.75],
    [0.60, 0.95, 0.78],
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

    // A glowing exoplanet-like orb lit by the pulsar.
    // 'lightFrom2D' is the direction in screen-space TOWARD the pulsar (XY).
    // 'biome' (0..3) picks a surface pattern style; 'seed' offsets the noise.
    vec4 nodeSphere(vec2 uv, vec2 c, float r, vec3 baseCol, vec2 lightFrom2D, float biome, float seed) {
      vec2 d = uv - c;
      float r2 = r * r;
      float d2 = dot(d, d);
      float dist = sqrt(d2);
      float aa = uAaPixel.x * 1.4;
      float alpha = 1.0 - smoothstep(r - aa, r + aa, dist);
      if (alpha <= 0.0) return vec4(0.0);
      float zSq = max(r2 - d2, 0.0);
      float zLocal = sqrt(zSq) / r;
      vec3 n = vec3(d.x / r, d.y / r, zLocal);
      // Spherical surface coords (rough, view-aligned — fine for small orbs)
      vec2 sp = n.xy + vec2(seed, seed * 0.7);
      // Almost imperceptibly slow rotation
      float rot = uTime * 0.0006 * (0.7 + 0.6 * fract(seed * 7.31));
      vec2 rsp = vec2(sp.x * cos(rot) - sp.y * sin(rot), sp.x * sin(rot) + sp.y * cos(rot));

      // Per-biome surface pattern — sharper feature definition, gentle color shift
      float pattern = 0.5;
      if (biome < 0.5) {
        // 0 — gas giant: well-defined bands with subtle turbulence between them
        float warp = fbm(rsp * 3.0) - 0.5;
        float bands = sin((rsp.y + warp * 0.55) * 6.5);
        // Sharpen the bands a bit
        bands = sign(bands) * pow(abs(bands), 0.7);
        pattern = bands * 0.5 + 0.5;
      } else if (biome < 1.5) {
        // 1 — rocky / continents with crisp coastlines
        float h = fbm(rsp * 4.0);
        pattern = smoothstep(0.44, 0.52, h);
      } else if (biome < 2.5) {
        // 2 — strongly marbled / swirly: domain warping for distinguished features
        float warp = fbm(rsp * 2.0);
        vec2 q = rsp * 3.5 + vec2(warp * 2.2, fbm(rsp * 2.3) * 2.0);
        float v = fbm(q);
        // Sharpen the contrast of the pattern (but apply gently to color)
        pattern = smoothstep(0.35, 0.65, v);
      } else {
        // 3 — icy / fine network of cracks
        float v = fbm(rsp * 6.0);
        pattern = 1.0 - smoothstep(0.42, 0.48, abs(v - 0.5));
      }
      // Very subtle tone variation — features are PRESENT but barely shift the color
      vec3 darkCol  = baseCol * 0.94;
      vec3 lightCol = mix(baseCol, vec3(1.0), 0.025);
      vec3 surfaceCol = mix(darkCol, lightCol, pattern);
      // Soft hue variation across the surface (very gentle, breaks uniformity)
      vec3 tintA = mix(baseCol, vec3(baseCol.g, baseCol.b, baseCol.r), 0.18);
      vec3 tintB = mix(baseCol, vec3(baseCol.b, baseCol.r, baseCol.g), 0.18);
      float tintMix = fbm(rsp * 1.8) * 0.5 + 0.5;
      vec3 sideTint = mix(tintA, tintB, tintMix);
      surfaceCol = mix(surfaceCol, sideTint, (1.0 - pattern) * 0.20);

      // Lighting from pulsar direction
      vec3 L = normalize(vec3(lightFrom2D.x, lightFrom2D.y, 0.35));
      float lam = max(dot(n, L), 0.0);
      // Soft terminator — lifted floor so the dark side still shows the pattern
      // (no more "features disappearing as the planet orbits")
      float diffuseAmt = mix(0.45, 1.10, smoothstep(0.0, 0.70, lam));
      // Tight specular (oceans/icy reflective)
      vec3 viewDir = vec3(0.0, 0.0, 1.0);
      vec3 h = normalize(L + viewDir);
      float specPow = mix(28.0, 70.0, pattern);
      float spec = pow(max(dot(n, h), 0.0), specPow) * mix(0.18, 0.45, pattern);
      vec3 specCol = mix(baseCol, vec3(1.0), 0.7) * spec;
      // Atmospheric rim (Fresnel) in the node's own hue — visible halo of air
      float fres = pow(1.0 - zLocal, 2.5);
      vec3 atmoRim = mix(baseCol, vec3(1.0), 0.15) * fres * 1.0;
      // Night-side glow includes the surface pattern (not just flat color) so
      // features remain consistently visible as the planet orbits the pulsar.
      vec3 nightSide = surfaceCol * 0.22 * (1.0 - lam);

      vec3 col = surfaceCol * diffuseAmt + specCol + atmoRim + nightSide;
      return vec4(col, alpha);
    }

    void main() {
      vec2 uv = (vUv - 0.5) * 2.0;
      uv.x *= uResolution.x / uResolution.y;

      vec3 col = vec3(0.0);

      // --- Background nebula (very faint) ---
      float neb = fbm(uv * 0.6 + vec2(uTime * 0.01, 0.0));
      col += mix(vec3(0.010, 0.012, 0.025), vec3(0.04, 0.025, 0.07), neb) * 0.12;

      // --- Procedural starfield (sparse) ---
      vec2 starGrid = uv * 40.0;
      vec2 starId = floor(starGrid);
      vec2 starF = fract(starGrid) - 0.5;
      float starRand = hash(starId);
      if (starRand > 0.985) {
        float twinkle = 0.7 + 0.3 * sin(uTime * 0.8 + starRand * 100.0);
        float starDist = length(starF);
        col += vec3(smoothstep(0.04, 0.0, starDist) * twinkle * 0.7);
      } else if (starRand > 0.965) {
        col += vec3(smoothstep(0.025, 0.0, length(starF)) * 0.3);
      }

      // --- Pulsar (3D sphere at origin) ---
      vec2 coreC = uMouse * 0.025;
      float coreR = 0.085;
      float pulse = 0.5 + 0.5 * sin(uTime * uPulseSpeed * 2.0);
      float coreRPulsed = coreR * (0.985 + 0.030 * pulse);
      vec3 coreColor = hueShift(uCoreHue);
      // --- Stellar corona: multi-layered halo + diffraction spikes ---
      vec2 sd = uv - coreC;
      float dCore = length(sd);
      float ang = atan(sd.y, sd.x);
      float haloOut = max(dCore - coreRPulsed * 0.96, 0.0);

      // 1. Tight bright chromosphere (just outside the limb)
      float chrom = exp(-haloOut * 30.0) * 0.95;
      // 2. Mid-range corona (medium spread)
      float corona = exp(-haloOut * 8.0) * 0.45;
      // 3. Wide diffuse outer halo (extends far)
      float farHalo = exp(-dCore * 2.5) * 0.35;
      vec3 haloColor = mix(coreColor, vec3(1.0), 0.30);
      col += haloColor * (chrom + corona) * (0.95 + 0.10 * pulse);
      col += coreColor * farHalo * (0.85 + 0.15 * pulse);

      // 4. Diffraction spikes — short, gentle stellar shimmer
      float spikeH = exp(-pow(abs(sd.y) * 160.0, 1.4)) * exp(-abs(sd.x) * 9.0);
      float spikeV = exp(-pow(abs(sd.x) * 160.0, 1.4)) * exp(-abs(sd.y) * 9.0);
      float spike = (spikeH + spikeV) * (0.90 + 0.15 * pulse);
      col += mix(coreColor, vec3(1.0), 0.45) * spike * 0.20;

      // 6. Asymmetric limb flares / prominences — animated plasma jets
      float flAng = ang + uTime * 0.08;
      float flPattern = fbm(vec2(flAng * 1.4, dCore * 14.0) + uTime * 0.05);
      float flFalloff = exp(-haloOut * 10.0) * step(coreRPulsed * 0.97, dCore);
      float flare = pow(flPattern, 5.0) * flFalloff * 1.6;
      col += coreColor * flare;

      // Connection lines node→core (always visible — no popping based on z)
      for (int i = 0; i < 8; i++) {
        float active = step(float(i) + 0.5, float(uNodeCount));
        vec4 n = uNodes[i];
        vec2 a = n.xy;
        vec2 d = coreC - a;
        float lineLen = max(length(d), 0.001);
        vec2 dir = d / lineLen;
        vec2 rel = uv - a;
        float along = dot(rel, dir);
        float across = length(rel - dir * along);
        float onSeg = step(n.w * 1.05, along) * step(along, lineLen - coreRPulsed * 1.02);
        float aa = uAaPixel.x * 1.2;
        float lineMask = (1.0 - smoothstep(0.0015 - aa, 0.0015 + aa, across)) * onSeg;
        // Subtle depth modulation (lines further back are slightly dimmer, but
        // never disappear).
        float depthFade = 0.55 + 0.45 * clamp(n.z / 0.35 + 0.5, 0.0, 1.0);
        col += uNodeColors[i] * lineMask * 0.32 * depthFade * active;
      }

      // Pulsar sphere — hot blue main-sequence star (Rigel/Spica style)
      {
        vec2 d = uv - coreC;
        float r2 = coreRPulsed * coreRPulsed;
        float d2 = dot(d, d);
        float dist = sqrt(d2);
        float aa = uAaPixel.x * 1.4;
        float alpha = 1.0 - smoothstep(coreRPulsed - aa, coreRPulsed + aa, dist);
        if (alpha > 0.0) {
          float zSq = max(r2 - d2, 0.0);
          float zN = sqrt(zSq) / coreRPulsed;
          vec2 sp = d / coreRPulsed;

          // Balanced 3-stop palette — pre-compensated for Reinhard tonemap.
          // Goal: smooth gradient from blue rim → blue body → blue-cyan center,
          // never grey/white in the middle, never too dark at the edge.
          vec3 photoRim    = vec3(0.30, 0.75, 1.50);                 // bright blue (less extreme rim)
          vec3 photoMid    = vec3(0.70, 1.30, 2.20);                 // electric cyan-blue
          vec3 photoCenter = vec3(1.20, 1.85, 2.60);                 // bright cyan-blue (still BLUE-dominant)
          // Re-tint stops by the user-chosen hue (preserve slider effect)
          photoRim    = mix(photoRim,    coreColor * 1.6, 0.25);
          photoMid    = mix(photoMid,    mix(coreColor, vec3(1.0), 0.30) * 2.2, 0.30);
          photoCenter = mix(photoCenter, mix(coreColor, vec3(1.0), 0.45) * 2.5, 0.28);

          vec3 starSurface = mix(photoRim, photoMid, smoothstep(0.0, 0.55, zN));
          starSurface     = mix(starSurface, photoCenter, smoothstep(0.55, 0.95, zN));

          // Limb darkening
          float limb = 0.70 + 0.30 * pow(zN, 0.42);

          // Granulation: very fine, very subtle
          float granul = fbm(sp * 24.0 + uTime * 0.02);
          starSurface *= 0.97 + 0.06 * (granul - 0.5);

          // Hotspot — tight, but ALSO blue-tinted so it doesn't desaturate the center
          float hotspot = pow(zN, 8.0) * 0.45;
          starSurface += mix(coreColor, vec3(0.85, 0.95, 1.0), 0.35) * hotspot;

          // Star scintillation (very subtle global brightness flicker)
          float scint = 0.97 + 0.06 * sin(uTime * 3.1 + fbm(sp * 6.0) * 8.0);
          starSurface *= scint;

          // Pulse breathing
          starSurface *= 0.94 + 0.08 * pulse;

          col = mix(col, starSurface * limb, alpha);
        }
      }

      // --- Nodes (already depth-sorted back-to-front in JS) ---
      for (int i = 0; i < 8; i++) {
        float active = step(float(i) + 0.5, float(uNodeCount));
        vec4 n = uNodes[i];
        vec3 nodeColor = uNodeColors[i];
        float depthBright = 0.75 + 0.25 * clamp(n.z / 0.35 + 0.5, 0.0, 1.0);

        // Occlusion mask: 0 if hidden behind pulsar, 1 otherwise
        float distToCore = length(n.xy - coreC);
        float occBehind = step(n.z, -coreRPulsed * 0.2);
        float occInside = step(distToCore, coreRPulsed - n.w * 0.5);
        float visible = 1.0 - occBehind * occInside;
        float mask = active * visible;

        // Light comes FROM the pulsar TOWARD the node — so the node's "lit
        // side" faces the pulsar.
        vec2 toCore = coreC - n.xy;
        vec2 lightDir2D = normalize(toCore + vec2(0.0001));
        // Biome and seed derived from index — deterministic per node.
        float biome = mod(float(i), 4.0);
        float seed = float(i) * 13.37;
        vec4 sh = nodeSphere(uv, n.xy, n.w, nodeColor, lightDir2D, biome, seed);
        vec3 lit = sh.rgb * depthBright;

        // Soft outer glow (additive, exp falloff — clean)
        float dN = length(uv - n.xy);
        float glowOut = max(dN - n.w * 0.95, 0.0);
        float glowRim  = exp(-glowOut * 28.0) * 0.45;
        float glowWide = exp(-glowOut * 9.0)  * 0.20;
        col += nodeColor * (glowRim + glowWide) * depthBright * mask;

        col = mix(col, lit, sh.a * mask);
      }

      // --- Light bloom on bright pixels ---
      vec3 bloomBoost = pow(max(col - 0.78, 0.0), vec3(1.7)) * uBloom * 0.30;
      col += bloomBoost;

      // Tonemap (Reinhard) + slight gamma
      col = col / (1.0 + col);
      col = pow(col, vec3(0.88));

      // Vignette
      float vig = smoothstep(1.7, 0.5, length(uv));
      col *= 0.6 + 0.4 * vig;

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
    gl.clearColor(0.02, 0.02, 0.04, 1);

    const geometry = new Triangle(gl);

    const colorUniform: Vec3[] = [];
    for (let i = 0; i < 8; i++) {
      const c = NODE_COLORS[i % NODE_COLORS.length];
      colorUniform.push(new Vec3(c[0], c[1], c[2]));
    }
    // OGL detects array uniforms via Array.isArray() — must be plain Array,
    // not Float32Array. Each element is itself a plain Array (vec4 or vec3).
    const nodesArr: number[][] = Array.from({ length: 8 }, () => [0, 0, 0, 0.04]);
    const colorsArr: number[][] = Array.from({ length: 8 }, (_, i) => {
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
    function onMove(e: PointerEvent) {
      const rect = wrapEl.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
      const aspect = rect.width / rect.height;
      targetMouse.set(x * aspect, y);
    }
    function onLeave() {
      targetMouse.set(0, 0);
    }
    wrapEl.addEventListener('pointermove', onMove);
    wrapEl.addEventListener('pointerleave', onLeave);

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
    type NodeParam = {
      baseAngle: number;
      orbitRx: number;
      orbitRy: number;
      orbitRz: number;
      tilt: number;
      speed: number;
      radius: number;
      colorIdx: number;
    };
    const NODES: NodeParam[] = Array.from({ length: 8 }, (_, i) => {
      const t = i / 6;
      return {
        baseAngle: (i / 6) * Math.PI * 2,
        orbitRx: 0.48 + 0.10 * Math.sin(i * 2.3),
        orbitRy: 0.36 + 0.08 * Math.cos(i * 1.7),
        orbitRz: 0.28 + 0.08 * Math.sin(i * 1.1 + 1.0),
        tilt: i * 0.45,
        speed: 0.85 + 0.30 * Math.sin(i * 1.9), // multiplied by orbitSpeed
        radius: 0.038 + 0.012 * Math.sin(i * 1.3),
        colorIdx: i,
      };
    });

    type Computed = { x: number; y: number; z: number; r: number; colorIdx: number };
    const computed: Computed[] = Array.from({ length: 8 }, () => ({
      x: 0, y: 0, z: 0, r: 0.04, colorIdx: 0,
    }));

    const start = performance.now();
    function loop(t: number) {
      rafId = 0;
      if (!visible) return;
      currentMouse.x += (targetMouse.x - currentMouse.x) * 0.06;
      currentMouse.y += (targetMouse.y - currentMouse.y) * 0.06;
      const time = (t - start) / 1000;

      // Compute node 3D positions
      const n = nodeCount;
      const spread = nodeSpread;
      const mix01 = orbitMix; // for ellipticity blend
      const mouseAttract = 0.04; // small
      for (let i = 0; i < n; i++) {
        const p = NODES[i];
        const a = p.baseAngle + time * orbitSpeed * p.speed;
        // 3D ellipse in orbit-local space, then rotate around X by tilt for inclination
        const lx = Math.cos(a) * p.orbitRx * spread;
        const ly0 = Math.sin(a) * (p.orbitRy * (1 - 0.4 * mix01) + p.orbitRx * 0.4 * mix01) * spread;
        const lz0 = Math.sin(a + p.tilt * 0.7) * p.orbitRz * spread;
        // Rotate around X by tilt to incline the orbit plane
        const cs = Math.cos(p.tilt);
        const sn = Math.sin(p.tilt);
        const ly = ly0 * cs - lz0 * sn;
        const lz = ly0 * sn + lz0 * cs;
        // Mouse pulls slightly
        const cx = lx + (currentMouse.x - lx) * mouseAttract;
        const cy = ly + (currentMouse.y - ly) * mouseAttract;
        // Depth → size and (later) brightness
        const depthScale = 0.85 + 0.30 * (lz / 0.35);
        computed[i].x = cx;
        computed[i].y = cy;
        computed[i].z = lz;
        computed[i].r = p.radius * depthScale;
        computed[i].colorIdx = p.colorIdx;
      }
      // Sort back-to-front
      const slice = computed.slice(0, n).sort((a, b) => a.z - b.z);
      // Write into flat uniform arrays (reorder colors to match sorted nodes).
      const arr = program.uniforms.uNodes.value as number[][];
      const colArr = program.uniforms.uNodeColors.value as number[][];
      for (let i = 0; i < n; i++) {
        arr[i][0] = slice[i].x;
        arr[i][1] = slice[i].y;
        arr[i][2] = slice[i].z;
        arr[i][3] = slice[i].r;
        const c = NODE_COLORS[slice[i].colorIdx];
        colArr[i][0] = c[0];
        colArr[i][1] = c[1];
        colArr[i][2] = c[2];
      }

      program.uniforms.uMouse.value.copy(currentMouse);
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
    background: #02020a;
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
