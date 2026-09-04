import { useCallback, useEffect, useRef, useState } from "react";
import { loadBootstrap, loadStats } from "./lib/api";
import type { Bootstrap, StatsPayload } from "./lib/types";

/** Fetches every payload the dashboard needs once, in parallel. */
export function useBootstrap() {
  const [data, setData] = useState<Bootstrap | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    loadBootstrap()
      .then((d) => {
        if (alive) setData(d);
      })
      .catch((e: unknown) => {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      alive = false;
    };
  }, []);

  return { data, error, loading: data === null && error === null };
}

export type Theme = "dark" | "light";
const THEME_KEY = "optiroute-theme";

/** Dark-first theme with localStorage persistence. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      const saved = localStorage.getItem(THEME_KEY);
      if (saved === "light" || saved === "dark") return saved;
    } catch {
      /* storage unavailable (private mode) — fall through to default */
    }
    return "dark";
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* ignore */
    }
  }, [theme]);

  const toggle = useCallback(
    () => setTheme((t) => (t === "dark" ? "light" : "dark")),
    []
  );
  return { theme, toggle };
}

/** Distance below the fold at which a section starts its reveal animation. */
const PRELOAD_PX = 320;

/**
 * Progressive reveal: adds .is-visible the first time the node approaches view.
 *
 * Sections here are far taller than the viewport (the arena alone is ~2400px),
 * so the observer uses threshold 0 — a leading-edge trigger — rather than an
 * area ratio, which would need a large fraction of a huge section on screen
 * before firing and left most of the page at opacity 0 while scrolling.
 */
export function useReveal<T extends HTMLElement = HTMLDivElement>() {
  const ref = useRef<T | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const show = () => el.classList.add("is-visible");
    /** True once any part of the node is on screen or just below the fold. */
    const nearViewport = () => {
      const r = el.getBoundingClientRect();
      return r.top < window.innerHeight + PRELOAD_PX && r.bottom > 0;
    };

    // No IntersectionObserver (old browser): reveal immediately.
    if (typeof IntersectionObserver === "undefined") {
      show();
      return;
    }
    // Already on screen at mount — never wait for a scroll that may not come.
    if (nearViewport()) {
      show();
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            show();
            io.unobserve(el);
          }
        }
      },
      // Positive bottom margin starts the animation before the section arrives,
      // so the user never scrolls into an empty band.
      { threshold: 0, rootMargin: `0px 0px ${PRELOAD_PX}px 0px` }
    );
    io.observe(el);

    // Safety net: geometry is checked directly, so content can never stay
    // invisible if the observer stalls (background tab, resize, layout shift).
    const failsafe = window.setInterval(() => {
      if (nearViewport()) {
        show();
        window.clearInterval(failsafe);
        io.disconnect();
      }
    }, 400);

    return () => {
      io.disconnect();
      window.clearInterval(failsafe);
    };
  }, []);

  return ref;
}

/**
 * Demo-session telemetry. Polls on an interval and exposes refresh() so the
 * arena can update the counters immediately after a routing decision.
 */
export function useSessionStats(intervalMs = 4000) {
  const [stats, setStats] = useState<StatsPayload | null>(null);

  const refresh = useCallback(() => {
    loadStats()
      .then(setStats)
      .catch(() => {
        /* telemetry is decorative — never break routing on it */
      });
  }, []);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, intervalMs);
    return () => window.clearInterval(id);
  }, [refresh, intervalMs]);

  return { stats, refresh };
}

/** Highlights the nav link for whichever section is currently in view. */
export function useActiveSection(ids: string[]) {
  const [active, setActive] = useState<string>(ids[0] ?? "");

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const nodes = ids
      .map((id) => document.getElementById(id))
      .filter((n): n is HTMLElement => n !== null);
    if (!nodes.length) return;

    const io = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible) setActive(visible.target.id);
      },
      { rootMargin: "-45% 0px -50% 0px", threshold: [0, 0.2, 0.6] }
    );
    nodes.forEach((n) => io.observe(n));
    return () => io.disconnect();
  }, [ids]);

  return active;
}
