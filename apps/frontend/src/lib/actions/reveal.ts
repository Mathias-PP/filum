/**
 * Svelte action: reveal element on viewport intersection.
 * Adds `is-revealed` class once when the element enters the viewport.
 * No-op if `prefers-reduced-motion` is set.
 */
export function reveal(
  node: HTMLElement,
  options: { threshold?: number; rootMargin?: string } = {}
) {
  const reduced =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

  node.setAttribute('data-reveal', '');

  if (reduced || typeof IntersectionObserver === 'undefined') {
    node.classList.add('is-revealed');
    return {};
  }

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          node.classList.add('is-revealed');
          observer.disconnect();
        }
      }
    },
    { threshold: options.threshold ?? 0.15, rootMargin: options.rootMargin ?? '0px' }
  );

  observer.observe(node);

  return {
    destroy() {
      observer.disconnect();
    },
  };
}

/**
 * Svelte action: 3D parallax via mouse tracking.
 * Sets CSS custom properties `--mx` and `--my` (range -1..1) on the node
 * based on mouse position relative to the element.
 * No-op when `prefers-reduced-motion` is set.
 */
export function mouseParallax(node: HTMLElement, options: { strength?: number } = {}) {
  const strength = options.strength ?? 1;
  const reduced =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

  if (reduced) {
    node.style.setProperty('--mx', '0');
    node.style.setProperty('--my', '0');
    return {};
  }

  let frame = 0;

  function onMove(e: MouseEvent) {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      const rect = node.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const mx = ((e.clientX - cx) / (rect.width / 2)) * strength;
      const my = ((e.clientY - cy) / (rect.height / 2)) * strength;
      node.style.setProperty('--mx', String(Math.max(-1, Math.min(1, mx))));
      node.style.setProperty('--my', String(Math.max(-1, Math.min(1, my))));
    });
  }

  function onLeave() {
    cancelAnimationFrame(frame);
    node.style.setProperty('--mx', '0');
    node.style.setProperty('--my', '0');
  }

  window.addEventListener('mousemove', onMove, { passive: true });
  window.addEventListener('mouseleave', onLeave, { passive: true });
  node.style.setProperty('--mx', '0');
  node.style.setProperty('--my', '0');

  return {
    destroy() {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseleave', onLeave);
      cancelAnimationFrame(frame);
    },
  };
}
