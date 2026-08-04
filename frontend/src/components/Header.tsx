import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useTheme, THEME_DOTS, THEME_LABELS, type TerminalTheme } from "../lib/ThemeContext";

function useLiveClock() {
  const [time, setTime] = useState(() => new Date());
  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);
  return time;
}

/**
 * Approximate NYSE session check — Mon-Fri, 9:30-16:00 America/New_York.
 * Doesn't account for market holidays; this is a display indicator, not
 * a trading-hours source of truth.
 */
function useMarketsOpen(): boolean {
  const time = useLiveClock();
  const nyParts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    hour: "numeric",
    minute: "numeric",
    hour12: false,
    weekday: "short",
  }).formatToParts(time);

  const weekday = nyParts.find((p) => p.type === "weekday")?.value ?? "";
  const hour = parseInt(nyParts.find((p) => p.type === "hour")?.value ?? "0", 10);
  const minute = parseInt(nyParts.find((p) => p.type === "minute")?.value ?? "0", 10);

  const isWeekday = !["Sat", "Sun"].includes(weekday);
  const minutesSinceMidnight = hour * 60 + minute;
  const marketOpen = 9 * 60 + 30;   // 9:30 AM ET
  const marketClose = 16 * 60;      // 4:00 PM ET

  return isWeekday && minutesSinceMidnight >= marketOpen && minutesSinceMidnight < marketClose;
}

function formatClock(time: Date): string {
  const nyTime = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(time);
  return nyTime;
}

const THEMES: TerminalTheme[] = ["amber", "cyan", "green"];

/**
 * Measures the header's own rendered height and publishes it as a CSS
 * custom property on <html>, so any other sticky element on the page
 * (e.g. the ticker page's nav row) can position itself with
 * `top: var(--cardinal-header-height)` instead of a hardcoded guess.
 * Re-measures on resize so it stays correct across breakpoints.
 */
function usePublishHeaderHeight(ref: React.RefObject<HTMLElement | null>) {
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;

    function publish() {
      const height = el?.getBoundingClientRect().height ?? 0;
      document.documentElement.style.setProperty("--cardinal-header-height", `${height}px`);
    }

    publish();
    const observer = new ResizeObserver(publish);
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
}

export default function Header() {
  const { theme, setTheme } = useTheme();
  const clockTime = useLiveClock();
  const marketsOpen = useMarketsOpen();
  const headerRef = useRef<HTMLElement>(null);
  usePublishHeaderHeight(headerRef);

  return (
    <header ref={headerRef} className="sticky top-0 z-40 bg-term-bg border-b border-term-border">
      <div className="mx-auto max-w-7xl px-6 py-3 flex items-center justify-between">
        <Link to="/" className="flex items-baseline gap-2.5">
          <span className="font-display text-xl font-bold text-term-text tracking-tight">
            CARDINAL
          </span>
          <span className="hidden sm:inline text-[11px] font-mono text-term-accent tracking-wider uppercase">
            equity terminal
          </span>
        </Link>

        <div className="flex items-center gap-5">
          {/* Markets open indicator */}
          <div className="hidden md:flex items-center gap-1.5 font-mono text-[11px] text-term-text-dim">
            <span
              className={`w-1.5 h-1.5 rounded-full ${marketsOpen ? "bg-term-accent-2" : "bg-term-danger"}`}
            />
            <span className="uppercase tracking-wider">
              {marketsOpen ? "Markets Open" : "Markets Closed"}
            </span>
          </div>

          {/* Live clock */}
          <span className="hidden sm:inline font-mono text-[11px] text-term-text-dim tabular-nums">
            {formatClock(clockTime)}
          </span>

          {/* Theme switcher */}
          <div className="flex items-center gap-1 border border-term-border rounded-lg p-0.5">
            {THEMES.map((t) => (
              <button
                key={t}
                onClick={() => setTheme(t)}
                title={THEME_LABELS[t]}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-mono uppercase tracking-wider transition-colors ${
                  theme === t
                    ? "bg-term-panel-alt text-term-text"
                    : "text-term-text-faint hover:text-term-text-dim"
                }`}
              >
                <span
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ backgroundColor: THEME_DOTS[t] }}
                />
                {THEME_LABELS[t]}
              </button>
            ))}
          </div>
        </div>
      </div>
    </header>
  );
}