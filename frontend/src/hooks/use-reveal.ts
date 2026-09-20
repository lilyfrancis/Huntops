import { useEffect, useRef, useState } from "react";

/**
 * Reveals an element the first time it reaches the viewport.
 *
 * The element starts hidden, so anything that stops the reveal from firing
 * leaves a blank section on the page. A fast scroll can carry an element
 * through the viewport between two of the browser's intersection
 * computations, and a restored scroll position or an anchor jump can put an
 * element above the fold before the observer is even attached. Both are
 * covered here: the position is checked when the effect runs and again on
 * scroll, so the observer is a fast path rather than the only path.
 */
export function useReveal<T extends HTMLElement>(threshold = 0) {
  const ref = useRef<T | null>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    let done = false;
    const show = () => {
      done = true;
      setIsVisible(true);
    };

    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reducedMotion || typeof IntersectionObserver === "undefined") {
      show();
      return;
    }

    // Reached, or already scrolled past.
    const reached = () => node.getBoundingClientRect().top < window.innerHeight * 0.9;
    if (reached()) {
      show();
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting || entry.boundingClientRect.top < 0) {
          show();
          observer.disconnect();
        }
      },
      { threshold, rootMargin: "0px 0px -10% 0px" },
    );
    observer.observe(node);

    let queued = false;
    const onScroll = () => {
      if (done || queued) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false;
        if (done) return;
        if (reached()) {
          show();
          stop();
        }
      });
    };
    const stop = () => {
      observer.disconnect();
      window.removeEventListener("scroll", onScroll);
    };
    window.addEventListener("scroll", onScroll, { passive: true });

    return stop;
  }, [threshold]);

  return { ref, isVisible };
}
