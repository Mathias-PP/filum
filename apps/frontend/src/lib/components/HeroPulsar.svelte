<script lang="ts">
  // Hero pulsar — WebGL render (OGL) with SVG fallback for LCP and a11y.
  //
  // Design contract:
  // - The SVG fallback renders synchronously on first paint so LCP is preserved.
  // - The WebGL module is lazy-loaded (dynamic import) on mount.
  // - IntersectionObserver pauses the RAF loop when the canvas is off-screen.
  // - prefers-reduced-motion → never load WebGL; stay on the SVG fallback.
  // - DPR is capped at 2 to keep mobile GPU usage bounded.
  //
  // Shader and rendering logic are kept inline for visibility — the sandbox at
  // `/sandbox/hero` was used to tune every constant. See ADR-024.

  import { onMount } from 'svelte';

  let canvasEl: HTMLCanvasElement | undefined = $state();
  let wrapEl: HTMLDivElement | undefined = $state();
  let webglReady = $state(false);

  // Tuned defaults — validated in the sandbox. No live tuning in prod.
  const BLOOM_STRENGTH = 0.3;
  const PULSE_SPEED = 0.25;
  const ORBIT_SPEED = 0.12;
  const NODE_COUNT = 6;
  const ORBIT_MIX = 0.55;
  const CORE_HUE = 0.58;
  const NODE_SPREAD = 1.0;

  const NODE_COLORS: [number, number, number][] = [
    [0.35, 0.55, 0.95],
    [0.55, 0.8, 0.55],
    [0.4, 0.78, 0.92],
    [0.85, 0.55, 0.55],
    [0.85, 0.72, 0.48],
    [0.72, 0.55, 0.85],
    [0.85, 0.8, 0.55],
    [0.55, 0.82, 0.65],
  ];

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
    uniform vec4 uNodes[8];
    uniform vec3 uNodeColors[8];
    uniform vec3 uLightDir;
    uniform float uHoverNode[8];
    uniform float uHoverCore;

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
      vec2 sp = n.xy + vec2(seed, seed * 0.7);
      float rot = uTime * 0.0006 * (0.7 + 0.6 * fract(seed * 7.31));
      vec2 rsp = vec2(sp.x * cos(rot) - sp.y * sin(rot), sp.x * sin(rot) + sp.y * cos(rot));

      float pattern = 0.5;
      if (biome < 0.5) {
        float warp = fbm(rsp * 3.0) - 0.5;
        float bands = sin((rsp.y + warp * 0.55) * 6.5);
        bands = sign(bands) * pow(abs(bands), 0.7);
        pattern = bands * 0.5 + 0.5;
      } else if (biome < 1.5) {
        float h = fbm(rsp * 4.0);
        pattern = smoothstep(0.44, 0.52, h);
      } else if (biome < 2.5) {
        float warp = fbm(rsp * 2.0);
        vec2 q = rsp * 3.5 + vec2(warp * 2.2, fbm(rsp * 2.3) * 2.0);
        float v = fbm(q);
        pattern = smoothstep(0.35, 0.65, v);
      } else {
        float v = fbm(rsp * 6.0);
        pattern = 1.0 - smoothstep(0.42, 0.48, abs(v - 0.5));
      }
      vec3 darkCol  = baseCol * 0.94;
      vec3 lightCol = mix(baseCol, vec3(1.0), 0.025);
      vec3 surfaceCol = mix(darkCol, lightCol, pattern);
      vec3 tintA = mix(baseCol, vec3(baseCol.g, baseCol.b, baseCol.r), 0.18);
      vec3 tintB = mix(baseCol, vec3(baseCol.b, baseCol.r, baseCol.g), 0.18);
      float tintMix = fbm(rsp * 1.8) * 0.5 + 0.5;
      vec3 sideTint = mix(tintA, tintB, tintMix);
      surfaceCol = mix(surfaceCol, sideTint, (1.0 - pattern) * 0.20);

      vec3 L = normalize(vec3(lightFrom2D.x, lightFrom2D.y, 0.35));
      float lam = max(dot(n, L), 0.0);
      float diffuseAmt = mix(0.45, 1.10, smoothstep(0.0, 0.70, lam));
      vec3 viewDir = vec3(0.0, 0.0, 1.0);
      vec3 h = normalize(L + viewDir);
      float specPow = mix(28.0, 70.0, pattern);
      float spec = pow(max(dot(n, h), 0.0), specPow) * mix(0.18, 0.45, pattern);
      vec3 specCol = mix(baseCol, vec3(1.0), 0.7) * spec;
      float fres = pow(1.0 - zLocal, 2.5);
      vec3 atmoRim = mix(baseCol, vec3(1.0), 0.15) * fres * 1.0;
      vec3 nightSide = surfaceCol * 0.22 * (1.0 - lam);

      vec3 col = surfaceCol * diffuseAmt + specCol + atmoRim + nightSide;
      return vec4(col, alpha);
    }

    void main() {
      vec2 uv = (vUv - 0.5) * 2.0;
      uv.x *= uResolution.x / uResolution.y;

      vec3 col = vec3(0.0);

      vec2 driftA = vec2(uTime * 0.0025, uTime * 0.0009);
      vec2 driftB = vec2(uTime * -0.0018, uTime * 0.0013);

      col = vec3(0.004, 0.005, 0.010);

      vec2 matUv = uv * 1.2 + driftA;
      float m1 = fbm(matUv);
      float m2 = fbm(matUv * 2.3 + vec2(5.0));
      float ridge1 = 1.0 - abs(m1 - 0.5) * 2.0;
      float ridge2 = 1.0 - abs(m2 - 0.5) * 2.0;
      float webBase = pow(ridge1, 1.4) * 0.6 + pow(ridge2, 2.0) * 0.4;
      float density = fbm(uv * 0.5 + driftB);

      vec3 cool = vec3(0.008, 0.012, 0.028);
      vec3 lit  = vec3(0.028, 0.040, 0.095);
      vec3 matrix = mix(cool, lit, smoothstep(0.25, 0.90, webBase));
      matrix *= 0.50 + 0.70 * density;
      col += matrix;

      float warmKnot = smoothstep(0.70, 0.95, webBase) * density;
      col += vec3(0.045, 0.025, 0.015) * warmKnot;

      vec2 dustUv = uv * vec2(1.4, 0.9) + vec2(2.0, -1.5) + driftB;
      float dustField = fbm(dustUv);
      float dustField2 = fbm(dustUv * 2.5 + vec2(7.0));
      float dustRidge = 1.0 - abs(dustField - 0.5) * 2.0;
      dustRidge *= 0.6 + 0.4 * dustField2;
      float dustMask = smoothstep(0.62, 0.95, dustRidge);
      col *= 1.0 - dustMask * 0.50;

      // Starfield (3 depth layers)
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

      // Pulsar core position (uMouse holds the dragged offset; defaults to 0)
      vec2 coreC = uMouse;
      float coreR = 0.085 * (1.0 + 0.10 * uHoverCore);
      float pulse = 0.5 + 0.5 * sin(uTime * uPulseSpeed * 2.0);
      float coreRPulsed = coreR * (0.985 + 0.030 * pulse);
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

      float flAng = ang + uTime * 0.08;
      float flPattern = fbm(vec2(flAng * 1.4, dCore * 14.0) + uTime * 0.05);
      float flFalloff = exp(-haloOut * 10.0) * step(coreRPulsed * 0.97, dCore);
      float flare = pow(flPattern, 5.0) * flFalloff * 1.6;
      col += coreColor * flare;

      // Connection lines node→pulsar
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
        float depthFade = 0.55 + 0.45 * clamp(n.z / 0.35 + 0.5, 0.0, 1.0);
        col += uNodeColors[i] * lineMask * 0.32 * depthFade * active;
      }

      // Pulsar sphere (emissive blue star)
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

          vec3 photoRim    = vec3(0.30, 0.75, 1.50);
          vec3 photoMid    = vec3(0.70, 1.30, 2.20);
          vec3 photoCenter = vec3(1.20, 1.85, 2.60);
          photoRim    = mix(photoRim,    coreColor * 1.6, 0.25);
          photoMid    = mix(photoMid,    mix(coreColor, vec3(1.0), 0.30) * 2.2, 0.30);
          photoCenter = mix(photoCenter, mix(coreColor, vec3(1.0), 0.45) * 2.5, 0.28);

          vec3 starSurface = mix(photoRim, photoMid, smoothstep(0.0, 0.55, zN));
          starSurface     = mix(starSurface, photoCenter, smoothstep(0.55, 0.95, zN));

          float limb = 0.70 + 0.30 * pow(zN, 0.42);
          float granul = fbm(sp * 24.0 + uTime * 0.02);
          starSurface *= 0.97 + 0.06 * (granul - 0.5);
          float hotspot = pow(zN, 8.0) * 0.45;
          starSurface += mix(coreColor, vec3(0.85, 0.95, 1.0), 0.35) * hotspot;
          float scint = 0.97 + 0.06 * sin(uTime * 3.1 + fbm(sp * 6.0) * 8.0);
          starSurface *= scint;
          starSurface *= 0.94 + 0.08 * pulse;

          col = mix(col, starSurface * limb, alpha);
        }
      }

      // Nodes (depth-sorted back-to-front in JS)
      for (int i = 0; i < 8; i++) {
        float active = step(float(i) + 0.5, float(uNodeCount));
        vec4 n = uNodes[i];
        vec3 nodeColor = uNodeColors[i];
        float depthBright = 0.75 + 0.25 * clamp(n.z / 0.35 + 0.5, 0.0, 1.0);

        float hover = uHoverNode[i];
        float nodeR = n.w * (1.0 + 0.35 * hover);

        float dPixelToCore = length(uv - coreC);
        float aaCore = uAaPixel.x * 1.4;
        float pulsarCoverage = 1.0 - smoothstep(coreRPulsed - aaCore, coreRPulsed + aaCore, dPixelToCore);
        float behindMix = smoothstep(coreRPulsed * 0.05, -coreRPulsed * 0.05, n.z);
        float occlude = pulsarCoverage * behindMix;
        float mask = active;

        vec2 toCore = coreC - n.xy;
        vec2 lightDir2D = normalize(toCore + vec2(0.0001));
        float biome = mod(float(i), 4.0);
        float seed = float(i) * 13.37;
        vec4 sh = nodeSphere(uv, n.xy, nodeR, nodeColor, lightDir2D, biome, seed);
        vec3 lit = sh.rgb * (depthBright + 0.40 * hover);

        float dN = length(uv - n.xy);
        float glowOut = max(dN - nodeR * 0.95, 0.0);
        float glowBoost = 1.0 + 1.30 * hover;
        float glowRim  = exp(-glowOut * 28.0) * 0.45 * glowBoost;
        float glowWide = exp(-glowOut * 9.0)  * 0.20 * glowBoost;
        col += nodeColor * (glowRim + glowWide) * depthBright * mask * (1.0 - occlude);

        col = mix(col, lit, sh.a * mask * (1.0 - occlude));
      }

      // Bloom on bright pixels
      vec3 bloomBoost = pow(max(col - 0.78, 0.0), vec3(1.7)) * uBloom * 0.30;
      col += bloomBoost;

      // Tonemap + gamma
      col = col / (1.0 + col);
      col = pow(col, vec3(0.88));

      // Edge fade — true alpha transparency so whatever is behind the canvas
      // (the host hero section background) shows through unchanged. No solid
      // rectangle, no visible boundary.
      float radialVig = smoothstep(1.7, 0.6, length(uv));
      col *= 0.55 + 0.45 * radialVig;
      vec2 edge = abs(vUv - 0.5) * 2.0;
      float edgeDist = max(edge.x, edge.y);
      // Fade per axis: starts at 65% so the inner ~65% of the canvas remains
      // fully opaque (the graph reads big and bright), then dissolves
      // continuously to fully transparent at the edges.
      float alpha = 1.0 - smoothstep(0.65, 1.0, edgeDist);
      // Premultiplied alpha avoids fringing when the canvas composites over
      // a textured background.
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
          alpha: true, // canvas itself is transparent at edges (see frag shader)
          premultipliedAlpha: true,
          antialias: true,
        });
        const gl = renderer.gl;
        // Fully transparent clear — canvas does not paint a background rect.
        gl.clearColor(0, 0, 0, 0);

        const geometry = new Triangle(gl);

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
            uBloom: { value: BLOOM_STRENGTH },
            uPulseSpeed: { value: PULSE_SPEED },
            uCoreHue: { value: CORE_HUE },
            uNodeCount: { value: NODE_COUNT },
            uNodes: { value: nodesArr },
            uNodeColors: { value: colorsArr },
            uLightDir: { value: new Vec3(LIGHT_DIR[0], LIGHT_DIR[1], LIGHT_DIR[2]) },
            uHoverNode: { value: Array.from({ length: 8 }, () => 0) },
            uHoverCore: { value: 0 },
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
          const coreHitR = 0.085 * 1.2;
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
        const NODES: NodeParam[] = Array.from({ length: 8 }, (_, i) => ({
          baseAngle: (i / 6) * Math.PI * 2,
          orbitRx: 0.48 + 0.1 * Math.sin(i * 2.3),
          orbitRy: 0.36 + 0.08 * Math.cos(i * 1.7),
          orbitRz: 0.28 + 0.08 * Math.sin(i * 1.1 + 1.0),
          tilt: i * 0.45,
          speed: 0.85 + 0.3 * Math.sin(i * 1.9),
          radius: 0.038 + 0.012 * Math.sin(i * 1.3),
          colorIdx: i,
        }));

        type Computed = { x: number; y: number; z: number; r: number; colorIdx: number };
        const computed: Computed[] = Array.from({ length: 8 }, () => ({
          x: 0,
          y: 0,
          z: 0,
          r: 0.04,
          colorIdx: 0,
        }));
        const displacement = Array.from({ length: 8 }, () => ({ x: 0, y: 0 }));
        const hoverTarget = new Array(8).fill(0) as number[];
        const hoverCurrent = program.uniforms.uHoverNode.value as number[];
        let hoverCoreTarget = 0;

        const start = performance.now();

        function loop(t: number) {
          rafId = 0;
          if (!visible) return;
          currentMouse.x += (targetMouse.x - currentMouse.x) * 0.1;
          currentMouse.y += (targetMouse.y - currentMouse.y) * 0.1;
          const time = (t - start) / 1000;

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
            const depthScale = 0.85 + 0.3 * (lz / 0.35);
            const isDragging = p.colorIdx === draggingNodeKey;
            const dispTargetX = isDragging ? currentMouse.x - lx : 0;
            const dispTargetY = isDragging ? currentMouse.y - ly : 0;
            const ease = isDragging ? 0.28 : 0.08;
            displacement[i].x += (dispTargetX - displacement[i].x) * ease;
            displacement[i].y += (dispTargetY - displacement[i].y) * ease;
            computed[i].x = lx + displacement[i].x;
            computed[i].y = ly + displacement[i].y;
            computed[i].z = lz;
            computed[i].r = p.radius * depthScale;
            computed[i].colorIdx = p.colorIdx;
          }
          const slice = computed.slice(0, NODE_COUNT).sort((a, b) => a.z - b.z);
          const arr = program.uniforms.uNodes.value as number[][];
          const colArr = program.uniforms.uNodeColors.value as number[][];
          for (let i = 0; i < NODE_COUNT; i++) {
            arr[i][0] = slice[i].x;
            arr[i][1] = slice[i].y;
            arr[i][2] = slice[i].z;
            arr[i][3] = slice[i].r;
            const c = NODE_COLORS[slice[i].colorIdx];
            colArr[i][0] = c[0];
            colArr[i][1] = c[1];
            colArr[i][2] = c[2];
          }

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
          const coreHit = pickIdx === -1 && coreDx * coreDx + coreDy * coreDy < 0.085 * 0.085 * 1.5;
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
    aria-label="Illustration : pulsar bleu entouré de planètes en orbite, représentant les sources reliées au nœud central Filum"
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
    <!-- Subtle scattered stars -->
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
    <!-- Central halo + core -->
    <circle cx="240" cy="210" r="180" fill="url(#hp-halo)" />
    <circle cx="240" cy="210" r="60" fill="url(#hp-core)" />
    <circle cx="240" cy="210" r="32" fill="#4A6CF7" />
    <!-- Connecting lines to nodes -->
    <g stroke="#ffffff" stroke-opacity="0.18" stroke-width="1.2" stroke-linecap="round">
      <line x1="240" y1="210" x2="100" y2="110" />
      <line x1="240" y1="210" x2="380" y2="110" />
      <line x1="240" y1="210" x2="110" y2="320" />
      <line x1="240" y1="210" x2="380" y2="320" />
      <line x1="240" y1="210" x2="230" y2="60" />
      <line x1="240" y1="210" x2="260" y2="370" />
    </g>
    <!-- Six planets in the brand palette (no warm orange) -->
    <circle cx="100" cy="110" r="14" fill="#5985F1" />
    <circle cx="380" cy="110" r="14" fill="#8DC78D" />
    <circle cx="110" cy="320" r="14" fill="#66C4EB" />
    <circle cx="380" cy="320" r="14" fill="#D88D8D" />
    <circle cx="230" cy="60" r="12" fill="#D9B97A" />
    <circle cx="260" cy="370" r="12" fill="#B88DD8" />
  </svg>

  <canvas bind:this={canvasEl} class="canvas" aria-hidden="true"></canvas>
</div>

<style>
  /* Wrapper is fully transparent — width/height/aspect controlled by parent.
     No background, no border, no border-radius: the WebGL canvas fades to
     transparent at the edges (alpha output) and the host's section background
     bleeds through, so the visual integrates seamlessly with the page. */
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
