import { useEffect } from 'react';

/** Tables that scroll sideways (phones, P12.1) must be reachable with the keyboard so their
 * hidden columns can be scrolled into view (WCAG 2.1.1; axe "scrollable-region-focusable"). */
export function useFocusableScrollRegions(root: () => HTMLElement | null) {
  useEffect(() => {
    const el = root();
    if (!el) return;
    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        el.querySelectorAll<HTMLElement>('table.table, .table-scroll').forEach((t) => {
          const scrolls = t.scrollWidth > t.clientWidth + 1;
          if (scrolls && !t.hasAttribute('tabindex')) {
            t.setAttribute('tabindex', '0');
            t.dataset.scrollFocus = '1';
          } else if (!scrolls && t.dataset.scrollFocus) {
            t.removeAttribute('tabindex');
            delete t.dataset.scrollFocus;
          }
        });
      });
    };
    update();
    const observer = new MutationObserver(update);
    observer.observe(el, { childList: true, subtree: true });
    window.addEventListener('resize', update);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener('resize', update);
    };
  }, [root]);
}
