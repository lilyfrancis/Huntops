import { useEffect, useRef } from "react";

/** Move an element against the scroll, gently.
 *
 * Driven from rAF rather than from the scroll event directly: a scroll
 * handler that writes to style on every event forces layout on a thread
 * that is already busy, and the result judders on exactly the cheap
 * hardware this has to feel smooth on.
 *
 * Respects prefers-reduced-motion by doing nothing at all.
 */
export function useParallax<T extends HTMLElement>(rate = -0.08) {
  const ref = useRef<T | null>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;

    let frame = 0;
    const update = () => {
      frame = 0;
      const { top, height } = node.getBoundingClientRect();
      // Only while it is anywhere near the viewport; off-screen work is
      // work nobody sees.
      if (top > window.innerHeight || top + height < 0) return;
      node.style.transform = `translate3d(0, ${(top * rate).toFixed(2)}px, 0)`;
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };

    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    return () => {
      if (frame) cancelAnimationFrame(frame);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [rate]);

  return ref;
}
