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
